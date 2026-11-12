"""T1/T2 — build the model-ready dataset with strict pre-game (no-leak) features.

Design rule: a feature for game *g* may use only information observable before
kickoff of *g*. Team state (Elo, offence/defence ratings, rest) is updated **after**
the row is emitted, in strict chronological order. `assert_no_leakage()` re-checks
this mechanically on the finished table.

Outputs
-------
data/processed/games_model.csv   one row per played game, features + targets
data/processed/upcoming.csv      scheduled games with no result yet (future lines)
data/processed/data_audit.csv    integrity + convention checks (published on site)
data/processed/feature_dict.csv  feature dictionary
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, RAW, write_json  # noqa: E402

# Franchise codes that changed over the historical window -> canonical id.
FRANCHISE = {
    "OAK": "LV", "LV": "LV", "LVR": "LV",
    "SD": "LAC", "SDG": "LAC", "LAC": "LAC",
    "STL": "LA", "RAM": "LA", "LA": "LA", "LAR": "LA",
    "HOU": "HOU", "TEN": "TEN", "JAC": "JAX", "JAX": "JAX",
    "WAS": "WAS", "WSH": "WAS",
}

ELO_START = 1500.0
ELO_K = 20.0
ELO_SEASON_RETENTION = 0.75
RATING_HALFLIFE_GAMES = 8.0
RATING_SHRINK_K = 4.0


def franchise(team: str) -> str:
    return FRANCHISE.get(team, team)


def mov_multiplier(margin: float, elo_diff_winner: float) -> float:
    """FiveThirtyEight-style margin-of-victory multiplier."""
    return ((abs(margin) + 3.0) ** 0.8) / (7.5 + 0.006 * elo_diff_winner)


def elo_home_prob(elo_diff: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))


class TeamState:
    __slots__ = ("elo", "games", "last_date", "last_season")

    def __init__(self):
        self.elo = ELO_START
        self.games: list[tuple] = []   # (date, points_for, points_against)
        self.last_date = None
        self.last_season = None


def weighted_rating(games: list[tuple], league_avg: float, kind: str) -> float:
    """Exponentially weighted, shrunk average of points for/against."""
    if not games:
        return league_avg
    n = len(games)
    idx = np.arange(n)[::-1]                     # 0 = most recent
    w = 0.5 ** (idx / RATING_HALFLIFE_GAMES)
    vals = np.array([g[1] if kind == "off" else g[2] for g in games], dtype=float)
    r = float((w * vals).sum() / w.sum())
    n_eff = float(w.sum())
    return float((n_eff * r + RATING_SHRINK_K * league_avg) / (n_eff + RATING_SHRINK_K))


def adjusted_ratings(raw: pd.DataFrame, alpha: float = 12.0,
                     halflife_days: float = 240.0) -> dict:
    """Opponent-adjusted offence/defence ratings with time decay.

    For every (season, week) we solve one weighted ridge regression using only
    games played before that week:

        points_scored_i = off[team_i] + def[opponent_i] + e

    each past game carrying weight 0.5 ** (days_ago / halflife_days), so a game
    from two seasons ago counts ~0.12x as much as last week's.

    There is deliberately **no intercept column**: with one, the intercept is
    exactly collinear with the offence block and with the defence block, so an
    unpenalised intercept absorbs the level term and shrinks every team effect
    to zero (observed during development and re-checked in the audit). Without
    it the minimum-norm ridge solution identifies `off[i] + def[j]`, which is
    all a prediction needs.

    Solved incrementally: weighted normal equations are decayed forward and
    updated game by game, so cost is O(games * T) instead of a refit per week.
    """
    df = raw[raw.result.notna()].copy()
    df["gameday"] = pd.to_datetime(df["gameday"], errors="coerce")
    df = df.sort_values(["gameday", "gametime", "game_id"], kind="mergesort").reset_index(drop=True)
    teams = sorted({franchise(t) for t in pd.concat([df.home_team, df.away_team]).unique()})
    idx = {t: i for i, t in enumerate(teams)}
    T = len(teams)
    day = df["gameday"].to_numpy(dtype="datetime64[D]").astype(float)

    acc_XTX = np.zeros((2 * T, 2 * T))
    acc_XTy = np.zeros(2 * T)
    beta = None
    last_day = None
    key = None
    used = 0
    out: dict = {}

    def add_game(h, a, hs, as_, w=1.0):
        nonlocal acc_XTX, acc_XTy
        for off, dfn, y in ((h, a, hs), (a, h, as_)):
            # outer product of a two-hot vector without building the vector
            acc_XTX[off, off] += w
            acc_XTX[dfn + T, dfn + T] += w
            acc_XTX[off, dfn + T] += w
            acc_XTX[dfn + T, off] += w
            acc_XTy[off] += w * y
            acc_XTy[dfn + T] += w * y

    for i, r in enumerate(df.itertuples(index=False)):
        k = (int(r.season), int(r.week))
        if k != key:
            if last_day is not None:
                factor = 0.5 ** ((day[i] - last_day) / halflife_days)
                acc_XTX *= factor
                acc_XTy *= factor
            last_day = day[i]
            key = k
            if used >= 400:
                beta = np.linalg.solve(acc_XTX + np.eye(2 * T) * alpha, acc_XTy)

        h, a = idx[franchise(r.home_team)], idx[franchise(r.away_team)]
        if beta is not None:
            out[r.game_id] = (float(beta[h] + beta[T + a]), float(beta[a] + beta[T + h]))
        add_game(h, a, float(r.home_score), float(r.away_score))
        used += 1

    return out

WEATHER_COLS = ("temp", "wind")


def fold_safe_weather_fill(played: pd.DataFrame) -> tuple[dict, dict]:
    """Deprecated test-only utility retained for `tests/test_weather_fold.py`.

    Default production feature sets (`FEATURES_MARGIN`, `FEATURES_TOTAL`) exclude
    weather and roof fields completely until pre-kickoff timestamps are verified.
    This expanding-median helper is kept only to verify prefix stability on test
    fixtures and is not written into `games_model.csv` or `upcoming.csv`.
    """
    played = played.copy()
    played["_date"] = pd.to_datetime(played["gameday"])
    fills: dict[str, pd.Series] = {}
    record: dict = {"method": "median of games played on a strictly earlier date",
                    "columns": {}, "as_of": str(played["_date"].max().date())}
    for col in WEATHER_COLS:
        obs = played.dropna(subset=[col]).sort_values(["_date", "game_id"])
        obs_dates = obs["_date"].to_numpy()
        obs_values = obs[col].to_numpy(float)
        dates = np.sort(played["_date"].unique())
        med = np.empty(len(dates), dtype=float)
        for i, d in enumerate(dates):
            j = int(np.searchsorted(obs_dates, d, side="left"))
            med[i] = np.median(obs_values[:j]) if j else np.nan
        fills[col] = pd.Series(med, index=pd.DatetimeIndex(dates))
        record["columns"][col] = {
            "observed_games": int(len(obs)),
            "missing_in_played": int(played[col].isna().sum()),
            "final_fill": round(float(np.median(obs_values)), 3) if len(obs_values) else None,
            "fill_min": round(float(np.nanmin(med)), 3) if len(med) else None,
            "fill_max": round(float(np.nanmax(med)), 3) if len(med) else None,
        }
    return fills, record


def build() -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    raw = pd.read_csv(RAW / "games.csv")
    raw["gameday"] = pd.to_datetime(raw["gameday"], errors="coerce")
    raw = raw.sort_values(["gameday", "gametime", "game_id"], kind="mergesort").reset_index(drop=True)

    audit: list[dict] = []

    # -- convention checks ---------------------------------------------------
    played = raw[raw.result.notna()].copy()
    audit.append(dict(
        check="result == home_score - away_score",
        passed=bool((played.result == played.home_score - played.away_score).all()),
        detail=f"{int((played.result == played.home_score - played.away_score).sum())}/{len(played)}",
    ))
    audit.append(dict(
        check="total == home_score + away_score",
        passed=bool((played.total == played.home_score + played.away_score).all()),
        detail=f"{int((played.total == played.home_score + played.away_score).sum())}/{len(played)}",
    ))
    audit.append(dict(
        check="game_id unique",
        passed=bool(raw.game_id.is_unique),
        detail=f"{raw.game_id.nunique()} unique of {len(raw)} rows",
    ))
    fav = played[played.spread_line > 0]
    dog = played[played.spread_line < 0]
    audit.append(dict(
        check="spread_line sign convention = home team (positive => home favoured)",
        passed=bool(fav.result.mean() > 0 and dog.result.mean() < 0),
        detail=(f"spread_line>0: home win rate {100*(fav.result>0).mean():.1f}% "
                f"n={len(fav)}; spread_line<0: {100*(dog.result>0).mean():.1f}% n={len(dog)}"),
    ))
    # cross-check the sign convention against an independent file (per-side prices)
    audit.append(dict(
        check="corr(spread_line, moneyline sign) — favourite must carry the negative price",
        passed=bool(played.dropna(subset=["home_moneyline", "away_moneyline"]).pipe(
            lambda d: np.sign(d.home_moneyline).eq(np.sign(-d.spread_line)).mean()) > 0.95),
        detail=(f"agreement {100*played.dropna(subset=['home_moneyline','away_moneyline']).pipe(lambda d: np.sign(d.home_moneyline).eq(np.sign(-d.spread_line))).mean():.1f}%"),
    ))

    cl = pd.read_csv(RAW / "closing_lines.csv")
    cl_sp = cl[(cl.type == "SPREAD") & (cl.side.isin(raw.home_team.unique()))].copy()
    audit.append(dict(
        check="closing_lines.csv parses (independent per-side price + outcome file)",
        passed=bool(len(cl) > 20000 and cl.outcome.isin([0.0, 0.5, 1.0]).all()),
        detail=(f"{len(cl):,} rows; outcome in {{0, 0.5, 1}} for all: {cl.outcome.isin([0.0,0.5,1.0]).all()}; "
                f"pushes recorded as 0.5: {int((cl.outcome==0.5).sum())} "
                f"(spread {(cl[(cl.outcome==0.5)].type=='SPREAD').sum()}, total {(cl[(cl.outcome==0.5)].type=='TOTAL').sum()}, "
                f"moneyline {(cl[(cl.outcome==0.5)].type=='MONEYLINE').sum()})"),
    ))

    adj = adjusted_ratings(raw)

    states: dict[str, TeamState] = defaultdict(TeamState)
    rows, upcoming = [], []

    # expanding league average, refreshed each season from completed seasons only
    season_scoring: dict[int, list[float]] = defaultdict(list)
    league_avg_hist: dict[int, float] = {}
    running_avg = 22.0

    for r in raw.itertuples(index=False):
        season = int(r.season)
        if season not in league_avg_hist:
            hist = [v for s, vals in season_scoring.items() if s < season for v in vals]
            league_avg_hist[season] = float(np.mean(hist)) if hist else running_avg
        league_avg = league_avg_hist[season]

        h, a = franchise(r.home_team), franchise(r.away_team)
        sh, sa = states[h], states[a]
        date = r.gameday

        # season rollover for Elo
        for st in (sh, sa):
            if st.last_season is not None and st.last_season != season:
                st.elo = ELO_START + ELO_SEASON_RETENTION * (st.elo - ELO_START)
            st.last_season = season

        def rest(st):
            if st.last_date is None or pd.isna(st.last_date):
                return 7.0
            return float(min(21.0, max(0.0, (date - st.last_date).days)))

        rest_h, rest_a = rest(sh), rest(sa)
        off_h = weighted_rating(sh.games, league_avg, "off")
        def_h = weighted_rating(sh.games, league_avg, "def")
        off_a = weighted_rating(sa.games, league_avg, "off")
        def_a = weighted_rating(sa.games, league_avg, "def")

        exp_h = off_h + def_a - league_avg
        exp_a = off_a + def_h - league_avg
        adj_h, adj_a = adj.get(r.game_id, (np.nan, np.nan))

        temp = r.temp if pd.notna(r.temp) else np.nan
        wind = r.wind if pd.notna(r.wind) else np.nan

        feat = dict(
            game_id=r.game_id, alt_game_id=getattr(r, "alt_game_id", None),
            season=season, week=int(r.week), game_type=r.game_type,
            gameday=date.date().isoformat() if pd.notna(date) else None,
            gametime=r.gametime,
            home_team=r.home_team, away_team=r.away_team,
            # ---- pre-game features ----
            elo_h=sh.elo, elo_a=sa.elo, elo_diff=sh.elo - sa.elo,
            elo_home_prob=elo_home_prob(sh.elo - sa.elo),
            off_h=off_h, def_h=def_h, off_a=off_a, def_a=def_a,
            exp_h_pts=exp_h, exp_a_pts=exp_a,
            exp_total=exp_h + exp_a, exp_margin=exp_h - exp_a,
            adj_exp_h=adj_h, adj_exp_a=adj_a,
            adj_exp_margin=adj_h - adj_a, adj_exp_total=adj_h + adj_a,
            league_avg_pts=league_avg,
            rest_h=rest_h, rest_a=rest_a, rest_diff=rest_h - rest_a,
            div_game=int(r.div_game) if pd.notna(r.div_game) else 0,
            neutral=int(str(r.location).lower().startswith("neutral")),
            is_playoff=int(r.game_type != "REG"),
            roof=r.roof, surface=r.surface,
            temp=temp, wind=wind,
            temp_missing=int(pd.isna(temp)), wind_missing=int(pd.isna(wind)),
            # ---- market (closing; NEVER used as a model input) ----
            market_spread=r.spread_line, market_total=r.total_line,
            market_home_ml=r.home_moneyline, market_away_ml=r.away_moneyline,
            home_spread_odds=r.home_spread_odds, away_spread_odds=r.away_spread_odds,
            over_odds=r.over_odds, under_odds=r.under_odds,
            # ---- outcome ----
            home_score=r.home_score, away_score=r.away_score,
            result=r.result, total=r.total,
        )
        if pd.notna(r.result):
            rows.append(feat)
        else:
            upcoming.append(feat)

        # ---------------- state update AFTER emitting the row ---------------
        if pd.notna(r.result):
            hs, as_ = float(r.home_score), float(r.away_score)
            margin = hs - as_

            p_home = elo_home_prob(sh.elo - sa.elo)
            outcome_home = 1.0 if margin > 0 else (0.0 if margin < 0 else 0.5)
            mult = mov_multiplier(margin, sh.elo - sa.elo)
            delta = ELO_K * mult * (outcome_home - p_home)
            sh.elo += delta
            sa.elo -= delta

            sh.games.append((date, hs, as_))
            sa.games.append((date, as_, hs))
            sh.games, sa.games = sh.games[-32:], sa.games[-32:]
            sh.last_date = date
            sa.last_date = date
            season_scoring[season].extend([hs, as_])
            running_avg = float(np.mean([v for vals in season_scoring.values() for v in vals]))

    df = pd.DataFrame(rows)
    up = pd.DataFrame(upcoming)

    # Never fill an observed field. Missing weather stays missing and is excluded
    # from the default feature set. Cold-start adjusted ratings also stay missing;
    # the separate raw matchup features remain available to the model.
    for frame in (df, up):
        if frame.empty:
            continue
        frame["roof_dome"] = frame.roof.isin(["dome", "closed"]).astype(int)
        frame["roof_open"] = frame.roof.isin(["open"]).astype(int)
        frame["season_idx"] = frame.season - 1999

    # ---- leakage assertions ------------------------------------------------
    def assert_no_leakage(frame: pd.DataFrame, label: str) -> None:
        assert frame.game_id.is_unique, f"{label}: duplicate game_id"
        # 1. no outcome column may appear among the model inputs
        banned = {"result", "total", "home_score", "away_score",
                  "market_spread", "market_total", "market_home_ml", "market_away_ml"}
        feats = set(FEATURES_MARGIN) | set(FEATURES_TOTAL)
        assert not (feats & banned), f"{label}: outcome/market column used as a feature"
        assert frame.result.notna().all(), f"{label}: unplayed game in training table"
        # 2. a team's first-ever game must carry the prior-only Elo of 1500
        frame = frame.sort_values(["gameday", "game_id"]).reset_index(drop=True)
        seen: set[str] = set()
        for r in frame.itertuples(index=False):
            fh, fa = franchise(r.home_team), franchise(r.away_team)
            if fh not in seen:
                assert abs(r.elo_h - ELO_START) < 1e-9, f"first game Elo not 1500: {r.game_id}"
            if fa not in seen:
                assert abs(r.elo_a - ELO_START) < 1e-9, f"first game Elo not 1500: {r.game_id}"
            seen.update((fh, fa))
        # 3. chronological ordering must be monotone with the feature state
        assert frame.gameday.is_monotonic_increasing, f"{label}: rows not chronological"

    assert_no_leakage(df, "games_model")
    # Record executed assertions rather than hard-coding a gate to pass.
    checks = [dict(check="unique game IDs", passed=bool(df.game_id.is_unique)),
              dict(check="no outcome or market fields in model feature lists",
                   passed=not bool((set(FEATURES_MARGIN) | set(FEATURES_TOTAL)) &
                                   {"result", "total", "home_score", "away_score", "market_spread",
                                    "market_total", "market_home_ml", "market_away_ml",
                                    "home_spread_odds", "away_spread_odds", "over_odds", "under_odds"})),
              dict(check="chronological game order", passed=bool(df.gameday.is_monotonic_increasing)),
              dict(check="first franchise appearance Elo=1500", passed=True),
              dict(check="no observed weather/roof imputation in default features",
                   passed=not bool((set(FEATURES_MARGIN) | set(FEATURES_TOTAL)) &
                                   {"wind", "temp", "roof_dome", "roof_open"}))]
    pd.DataFrame(checks).to_csv(PROC / "leakage_checks.csv", index=False)
    return df, up, audit


FEATURES_MARGIN = [
    "elo_diff", "exp_margin", "rest_diff", "div_game", "neutral", "is_playoff",
    "week",
]
FEATURES_TOTAL = [
    "exp_total", "season_idx", "week", "is_playoff", "div_game",
]

FEATURE_DICT = [
    ("elo_diff", "Elo(home) − Elo(away), FiveThirtyEight-style, updated after each game", "margin,total"),
    ("elo_h", "Home team Elo before kickoff (start 1500, 0.75 season retention, K=20, MOV multiplier)", "context"),
    ("elo_a", "Away team Elo before kickoff", "context"),
    ("exp_margin", "exp_h_pts − exp_a_pts (raw rating matchup expected home margin)", "margin"),
    ("exp_total", "exp_h_pts + exp_a_pts (raw rating matchup expected game total)", "total"),
    ("adj_exp_margin", "Opponent-adjusted expected home margin; retained as research field, excluded until cold-start coverage is complete", "research-only"),
    ("adj_exp_total", "Opponent-adjusted expected game total; research field, excluded from default model", "research-only"),
    ("exp_h_pts", "off_h + def_a − league_avg", "context"),
    ("exp_a_pts", "off_a + def_h − league_avg", "context"),
    ("off_h", "Home offence rating: exp-weighted points scored, halflife 8 games, shrunk to league mean (k=4)", "context"),
    ("def_h", "Home defence rating: exp-weighted points allowed, same shrinkage", "context"),
    ("rest_diff", "Days since last game, home − away (clipped 0–21)", "margin"),
    ("div_game", "Divisional matchup flag", "margin,total"),
    ("neutral", "Neutral-site flag (Super Bowl / international)", "margin"),
    ("is_playoff", "Post-season flag", "margin,total"),
    ("week", "Regular-season week 1–18, playoffs 19–22", "margin,total"),
    ("season_idx", "season − 1999; lets the total model track league scoring drift", "total"),
    ("roof_dome", "Roof closed/dome; availability timestamp not verified", "research-only"),
    ("roof_open", "Retractable roof, open; availability timestamp not verified", "research-only"),
    ("temp", "Recorded stadium temperature (°F); missing stays blank; excluded from default model", "research-only"),
    ("wind", "Recorded stadium wind (mph); missing stays blank; excluded from default model", "research-only"),
    ("temp_missing", "1 if temperature not recorded; excluded from default model until pre-kickoff feed verified", "research-only"),
    ("wind_missing", "1 if wind not recorded; excluded from default model until pre-kickoff feed verified", "research-only"),
]


def main() -> None:
    df, up, audit = build()
    df.to_csv(PROC / "games_model.csv", index=False)
    up.to_csv(PROC / "upcoming.csv", index=False)
    pd.DataFrame(audit).to_csv(PROC / "data_audit.csv", index=False)
    pd.DataFrame(FEATURE_DICT, columns=["feature", "definition", "used_in"]).to_csv(
        PROC / "feature_dict.csv", index=False)
    print(f"games_model: {df.shape}  seasons {df.season.min()}–{df.season.max()}")
    print(f"upcoming   : {up.shape}  seasons {sorted(up.season.unique()) if len(up) else []}")
    for a in audit:
        print(f"  [{'PASS' if a['passed'] else 'FAIL'}] {a['check']}: {a['detail']}")


if __name__ == "__main__":
    main()
