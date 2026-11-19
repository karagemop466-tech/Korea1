"""DT3 (arena/a0e376ae-korea1) — dual-estimator game totals with a walk-forward comparison.

Brief item REQ-62 / RR-62: "Publish every model total twice until one wins. Keep both estimators
visible with the gap column, and only collapse to one after a walk-forward comparison."

What this module does
---------------------
1. Computes a **second, independent** total estimate (estimator B) for every game: the mean of
   each team's up-to-five most recent regular-season combined scores strictly before the game
   (the pre-registered form model; zero fitted parameters).
2. Joins it to the published ensemble total (estimator A, `pred_total_ensemble`) and writes the
   per-game gap.
3. Runs the **pre-registered walk-forward comparison** over seasons 2004-2026, regular season
   only: per-season and pooled MAE/RMSE/bias for both estimators, the paired mean absolute-error
   difference with a 95% t-interval, and the pre-registered verdict.
4. Tiers every evaluated row by outcome evidence: OFFICIAL_READ (the final is on a committed
   official read) or PINNED_COMMUNITY (pinned community archive final, settlement unverified).

The rule text was committed before this file existed — `research/dual-totals-prereg.md`,
registration commit `b364c23706a46f7b04173370f88b2f4a22a44aac` (v2). Nothing here re-fits,
reweights or reselects estimator A, and nothing here is a strategy, a leaderboard row or a
validation-gate change.

Inputs (all committed; no network, no clock)
  data/processed/originated_lines.csv      estimator A + outcome per played game
  data/processed/originated_upcoming.csv   the published upcoming board (gap columns)
  data/processed/games_model.csv           team histories for the form model
  data/results/verified_results.csv        officially read finals (tier OFFICIAL_READ)
  data/audit/nfl_com_score_audit.csv       official score audit rows (tier OFFICIAL_READ)
  research/dual-totals-prereg.md           the registered rule text

Outputs
  data/processed/dual_totals.csv              one row per evaluated game
  data/processed/dual_totals_walkforward.csv  one row per season + the pooled row
  data/processed/dual_totals_upcoming.csv     one row per upcoming board game
  data/processed/dual_totals_summary.json     headline verdict for the page

Run:  python pipeline/dual_totals.py
"""
from __future__ import annotations

import bisect
import hashlib
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, write_json  # noqa: E402

PREREG = ROOT / "research" / "dual-totals-prereg.md"
# The commit whose text this module honours (pre-registration v2, made before this file existed).
REGISTRATION_COMMIT = "b364c23706a46f7b04173370f88b2f4a22a44aac"

OUT_GAMES = PROC / "dual_totals.csv"
OUT_WF = PROC / "dual_totals_walkforward.csv"
OUT_UP = PROC / "dual_totals_upcoming.csv"
OUT_JSON = PROC / "dual_totals_summary.json"

ORIGINATED = PROC / "originated_lines.csv"
UPCOMING = PROC / "originated_upcoming.csv"
GAMES = PROC / "games_model.csv"
VERIFIED = ROOT / "data" / "results" / "verified_results.csv"
AUDIT = ROOT / "data" / "audit" / "nfl_com_score_audit.csv"

# Official, season-scoped source printed on every walk-forward row (both URLs re-read live
# on 2026-11-19 with the page tool: titles "2026 NFL League Standings" / "2004 NFL League
# Standings"; the scores root is the settlement source the registers cite).
STANDINGS_URL = "https://www.nfl.com/standings/league/{season}/REG"
SCORES_URL = "https://www.nfl.com/scores/"

WINDOW = 5          # pre-registered form window, in games
EVAL_START = 2004   # first season with a published estimator A
ALPHA = 0.05        # two-sided paired interval


# --------------------------------------------------------------------------- helpers
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(name, dtype=str, keep_default_na=False)


# --------------------------------------------------------------------------- estimator B
class FormPriors:
    """Last-N regular-season form, strictly before a game (pre-registered v2).

    For a query (team, season, week) only games whose (season, week) key sorts before the
    query are read, so a game can never see itself, its own week or any later game. The
    league fallback is the mean combined score of the most recent earlier regular season
    present in the corpus.
    """

    def __init__(self, games: pd.DataFrame):
        reg = games[(games.game_type == "REG") & (games.total != "")].copy()
        reg["total_f"] = reg.total.astype(float)
        reg["season_i"] = reg.season.astype(int)
        reg["week_i"] = reg.week.astype(int)

        self._hist: dict[str, list[tuple[int, int, float]]] = {}
        for r in reg.itertuples():
            row = (r.season_i, r.week_i, r.total_f)
            self._hist.setdefault(r.home_team, []).append(row)
            self._hist.setdefault(r.away_team, []).append(row)
        for team in self._hist:
            self._hist[team].sort(key=lambda t: (t[0], t[1]))
        self._keys: dict[str, list[tuple[int, int]]] = {
            t: [(s, w) for s, w, _ in rows] for t, rows in self._hist.items()}

        self._league: dict[int, float] = {}
        for season, grp in reg.groupby("season_i"):
            self._league[int(season)] = float(grp.total_f.mean())

    def prior(self, team: str, season: int, week: int) -> tuple[float | None, str]:
        keys = self._keys.get(team)
        if keys:
            cut = bisect.bisect_left(keys, (season, week))          # entries strictly before
            window = self._hist[team][max(0, cut - WINDOW):cut]
            if window:
                return float(np.mean([t for _, _, t in window])), f"last{len(window)}"
        earlier = [s for s in self._league if s < season]
        if earlier:
            s = max(earlier)
            return self._league[s], f"league_mean_{s}"
        return None, "unavailable"

    def estimate(self, home: str, away: str, season: int, week: int) -> tuple[float | None, str]:
        ph, sh = self.prior(home, season, week)
        pa, sa = self.prior(away, season, week)
        if ph is None or pa is None:
            return None, "unavailable"
        return (ph + pa) / 2.0, f"{sh}+{sa}"


# --------------------------------------------------------------------------- statistics
def _paired_ci(d: np.ndarray) -> tuple[float, float]:
    """Two-sided 95% t-interval for the mean of the paired differences."""
    n = len(d)
    if n < 2:
        return (math.nan, math.nan)
    se = float(np.std(d, ddof=1)) / math.sqrt(n)
    tcrit = float(stats.t.ppf(1 - ALPHA / 2, n - 1))
    m = float(np.mean(d))
    return m - tcrit * se, m + tcrit * se


def _season_stats(frame: pd.DataFrame, label: str) -> dict:
    ea = frame.err_a.to_numpy(dtype=float)
    eb = frame.err_b.to_numpy(dtype=float)
    d = np.abs(eb) - np.abs(ea)          # >0 means B was worse on that game
    lo, hi = _paired_ci(d)
    delta = float(np.mean(d))
    if not np.isfinite(lo):
        verdict = "no separation"
    elif hi < 0:
        verdict = "B wins"
    elif lo > 0:
        verdict = "A wins"
    else:
        verdict = "no separation"
    return dict(
        season=label,
        n=int(len(frame)),
        mae_a=float(np.mean(np.abs(ea))),
        mae_b=float(np.mean(np.abs(eb))),
        rmse_a=float(np.sqrt(np.mean(ea ** 2))),
        rmse_b=float(np.sqrt(np.mean(eb ** 2))),
        bias_a=float(np.mean(ea)),
        bias_b=float(np.mean(eb)),
        delta_mae=delta,
        ci_low=lo,
        ci_high=hi,
        verdict=verdict,
        n_official_read=int((frame.outcome_tier == "OFFICIAL_READ").sum()),
        n_pinned_community=int((frame.outcome_tier == "PINNED_COMMUNITY").sum()),
    )


def _verdict_pooled(lo: float, hi: float) -> str:
    if np.isfinite(lo) and lo > 0:
        return "A wins"
    if np.isfinite(hi) and hi < 0:
        return "B wins"
    return "inconclusive - both estimators remain published"


# --------------------------------------------------------------------------- main
def build() -> dict:
    if not PREREG.exists():
        raise SystemExit(f"missing pre-registration text: {PREREG}")
    prereg_text = PREREG.read_text(encoding="utf-8")
    if "registration" not in prereg_text.lower():
        raise SystemExit("pre-registration text does not look like the registered rule")

    games = _read(GAMES)
    originated = _read(ORIGINATED)
    upcoming = _read(UPCOMING)

    # ---- estimator B over the whole corpus (chronology-safe by construction) ------------
    priors = FormPriors(games)

    # ---- official-read tier ------------------------------------------------------------
    official_url: dict[str, str] = {}
    if VERIFIED.exists():
        vr = _read(VERIFIED)
        for r in vr[vr.verified == "FINAL"].itertuples():
            if r.official_url:
                official_url.setdefault(r.game_id, r.official_url)
    if AUDIT.exists():
        au = _read(AUDIT)
        for r in au[au.status == "MATCH"].itertuples():
            if r.nfl_com_url:
                official_url[r.game_id] = r.nfl_com_url
    official_ids = set(official_url)

    # ---- evaluation rows: regular season, estimator A published, outcome on record ------
    ev = originated[originated.game_type == "REG"].copy()
    if ev.empty:
        raise SystemExit("originated_lines.csv holds no regular-season rows")
    if (ev.total == "").any():
        raise SystemExit("an evaluated row has no outcome total; refusing to fill it")
    if (ev.pred_total_ensemble == "").any():
        raise SystemExit("an evaluated row has no estimator A; refusing to fill it")

    rows = []
    for r in ev.itertuples():
        season, week = int(r.season), int(r.week)
        b, b_src = priors.estimate(r.home_team, r.away_team, season, week)
        tier = "OFFICIAL_READ" if r.game_id in official_ids else "PINNED_COMMUNITY"
        url = official_url.get(r.game_id, "")
        if b is None:
            rows.append(dict(
                game_id=r.game_id, season=season, week=week, gameday=r.gameday,
                home_team=r.home_team, away_team=r.away_team,
                total_a=float(r.pred_total_ensemble), total_b="",
                gap_a_minus_b="", outcome_total=float(r.total),
                abs_err_a="", abs_err_b="", b_source=b_src, b_available=False,
                outcome_tier=tier, official_url=url))
            continue
        a = float(r.pred_total_ensemble)
        y = float(r.total)
        rows.append(dict(
            game_id=r.game_id, season=season, week=week, gameday=r.gameday,
            home_team=r.home_team, away_team=r.away_team,
            total_a=a, total_b=b, gap_a_minus_b=a - b, outcome_total=y,
            abs_err_a=abs(a - y), abs_err_b=abs(b - y), b_source=b_src, b_available=True,
            outcome_tier=tier, official_url=url))
    games_out = pd.DataFrame(rows)

    usable = games_out[games_out.b_available].copy()
    if usable.empty:
        raise SystemExit("estimator B produced no computable row")
    usable["err_a"] = usable.total_a.astype(float) - usable.outcome_total.astype(float)
    usable["err_b"] = usable.total_b.astype(float) - usable.outcome_total.astype(float)

    # ---- walk-forward table: one row per season + pooled -------------------------------
    wf_rows = []
    for season, grp in usable.groupby("season"):
        wf_rows.append(_season_stats(grp, str(int(season))))
    pooled = _season_stats(usable, "ALL")
    pooled["verdict"] = _verdict_pooled(pooled["ci_low"], pooled["ci_high"])
    wf_rows.append(pooled)
    wf = pd.DataFrame(wf_rows)

    # pre-registered collapse gate (reported, never executed by this module)
    season_rows = wf[wf.season != "ALL"]
    a_wins = int((season_rows.verdict == "A wins").sum())
    b_wins = int((season_rows.verdict == "B wins").sum())
    n_seasons = int(len(season_rows))
    overall = pooled["verdict"]
    if overall == "A wins":
        collapse_candidate = a_wins >= math.ceil(2 * n_seasons / 3)
        collapse_reason = "A wins pooled gate" + (" + season supermajority" if collapse_candidate else " but no season supermajority")
    elif overall == "B wins":
        collapse_candidate = b_wins >= math.ceil(2 * n_seasons / 3)
        collapse_reason = "B wins pooled gate" + (" + season supermajority" if collapse_candidate else " but no season supermajority")
    else:
        collapse_candidate = False
        collapse_reason = "pooled gate inconclusive"

    # ---- upcoming board: both estimates and the gap ------------------------------------
    up_rows = []
    for r in upcoming.itertuples():
        b, b_src = priors.estimate(r.home_team, r.away_team, int(r.season), int(r.week))
        a = float(r.fair_total) if str(r.fair_total).strip() else math.nan
        ok = b is not None and np.isfinite(a)
        up_rows.append(dict(
            game_id=r.game_id, season=int(r.season), week=int(r.week), gameday=r.gameday,
            home_team=r.home_team, away_team=r.away_team,
            total_a=a, total_b=b if b is not None else "",
            gap_a_minus_b=(a - b) if ok else "",
            b_source=b_src, b_available=bool(ok)))
    upcoming_out = pd.DataFrame(up_rows)

    # ---- write (deterministic; no clock) ------------------------------------------------
    games_out.to_csv(OUT_GAMES, index=False)
    wf.to_csv(OUT_WF, index=False)
    upcoming_out.to_csv(OUT_UP, index=False)

    n_off = int((usable.outcome_tier == "OFFICIAL_READ").sum())
    n_pin = int((usable.outcome_tier == "PINNED_COMMUNITY").sum())
    summary = dict(
        registration_commit=REGISTRATION_COMMIT,
        prereg_sha256=_sha256(PREREG),
        window="2004-2026 regular season; both estimators on the same games",
        n_evaluated=int(len(usable)),
        n_b_unavailable=int(len(games_out) - len(usable)),
        seasons_evaluated=n_seasons,
        seasons_a_won=a_wins,
        seasons_b_won=b_wins,
        seasons_no_separation=n_seasons - a_wins - b_wins,
        pooled=dict(
            mae_a=pooled["mae_a"], mae_b=pooled["mae_b"],
            rmse_a=pooled["rmse_a"], rmse_b=pooled["rmse_b"],
            delta_mae=pooled["delta_mae"],
            ci_low=pooled["ci_low"], ci_high=pooled["ci_high"],
            verdict=overall),
        outcome_tiers=dict(official_read=n_off, pinned_community=n_pin),
        verdict_status="PROVISIONAL" if n_pin else "OFFICIAL-COVERED",
        collapse=dict(candidate=bool(collapse_candidate), reason=collapse_reason,
                      executed=False,
                      rule="pooled CI names a winner and that winner takes >= 2/3 of seasons; "
                           "the collapse itself is an owner decision (DECISIONS.md)"),
        upcoming_rows=int(len(upcoming_out)),
        upcoming_b_available=int(upcoming_out.b_available.sum()) if len(upcoming_out) else 0,
        estimators=dict(
            A="pred_total_ensemble as published on lines.html (not retrained here)",
            B="mean of each team's up-to-5 most recent regular-season totals strictly "
              "before the game; league-mean fallback; zero fitted parameters"),
        inputs=dict(originated_lines="data/processed/originated_lines.csv",
                    games_model="data/processed/games_model.csv",
                    verified_results="data/results/verified_results.csv",
                    score_audit="data/audit/nfl_com_score_audit.csv"),
    )
    write_json(OUT_JSON, summary)

    print(f"dual_totals: {len(usable)} evaluated rows "
          f"({n_off} OFFICIAL_READ / {n_pin} PINNED_COMMUNITY), "
          f"{n_seasons} seasons, pooled verdict '{overall}', "
          f"MAE A={pooled['mae_a']:.3f} B={pooled['mae_b']:.3f}, "
          f"delta={pooled['delta_mae']:+.3f} "
          f"[{pooled['ci_low']:+.3f}, {pooled['ci_high']:+.3f}]")
    print(f"dual_totals: upcoming {len(upcoming_out)} rows, "
          f"{summary['upcoming_b_available']} with a B estimate")
    return summary


if __name__ == "__main__":
    build()
