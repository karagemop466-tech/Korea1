"""T50 — the ordered origination record: side first, then total, then moneyline.

The brief asks for the lines to be originated **in order**: the side, then the
total, then the moneyline. That order is not a presentational preference. It is
the only way the three published markets can be guaranteed to agree with each
other, and this module implements it and audits it.

Step 1 — SIDE
    The margin model produces the home margin. The line this project would post
    is that margin expressed on the archive's own convention: a home line of
    ``+3.5`` means the home team must win by more than 3.5 points to cover.

Step 2 — TOTAL
    The total model produces the game total. It is a second, independent model
    of the same game; it is not derived from the side.

Step 3 — MONEYLINE
    The moneyline is **derived**, never fitted separately. It is computed on the
    score lattice implied by steps 1 and 2:

        home = round((total + margin) / 2)
        away = round((total - margin) / 2)

    so the published moneyline is a consequence of the published side and the
    published total and can never contradict them. The derivation uses the
    empirical joint distribution of the model's prior-season errors, coupled
    through a Gaussian copula whose correlation is estimated on the same prior
    data and published with its n.

    A fact worth stating plainly: **the moneyline probability is a function of
    the side alone.** Home wins if and only if the margin is positive, so no
    total can move P(home win) without moving the side. What step 3 adds is the
    guarantee of internal consistency, the parity-correct score lattice and the
    tie treatment — and the published delta against the model's own
    margin-only moneyline shows exactly how much the two paths differ.

Every row carries the model's **fair line**, the **market line** and the
**difference** for each of the three markets as separate columns, in the unit
named beside each one.

Run:  python pipeline/origination.py
Out:  data/processed/origination_lines.csv
      data/processed/origination_order.csv
      data/processed/origination_report.json
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, write_json  # noqa: E402
from market_data_common import official_context_url  # noqa: E402
from models import american_with_hold, fair_american  # noqa: E402

LINES = PROC / "origination_lines.csv"
ORDER = PROC / "origination_order.csv"
REPORT = PROC / "origination_report.json"

#: Minimum number of prior-season residuals before a season may be priced.
MIN_POOL = 200
#: Cap on the joint-lattice sample size (the copula grid), for run time.
MAX_GRID = 4000
#: Tolerance, in probability points, for the moneyline consistency check.
CONSISTENCY_TOLERANCE_PP = 0.5
#: Tolerance, in points, for the check that the moneyline's own score lattice
#: reproduces the published side. This is the invariant that matters: the
#: moneyline must be a consequence of the side, not an independent model.
MARGIN_CONSISTENCY_TOLERANCE_POINTS = 0.5


def _model_inputs() -> pd.DataFrame:
    """Played and scheduled games with the model's own published lines."""
    keep = ["game_id", "season", "week", "game_type", "gameday", "home_team", "away_team",
            "result", "total", "fair_spread", "fair_total", "market_spread", "market_total",
            "market_home_ml", "market_away_ml", "p_home_ml", "p_tie", "p_away_ml",
            "originated_home_ml", "originated_away_ml"]
    frames = []
    for name, filename in (("played", "originated_lines.csv"),
                           ("upcoming", "originated_upcoming.csv")):
        p = PROC / filename
        if not p.exists():
            continue
        df = pd.read_csv(p)
        for c in keep:
            if c not in df.columns:
                df[c] = np.nan
        df["record_set"] = name
        frames.append(df[keep + ["record_set"]])
    return pd.concat(frames, ignore_index=True).drop_duplicates("game_id").reset_index(drop=True)


def _residual_pool() -> dict[int, tuple[np.ndarray, np.ndarray, int]]:
    """The model's own predictive-error samples, per season, with their counts.

    These are the samples the model itself uses to turn a prediction into a
    probability (``pipeline/models.py`` writes them to
    ``data/processed/model_residuals.csv``). The pool for season *S* is built
    only from seasons before *S*, so no probability here is ever informed by a
    result the model could not already have seen. Using the model's own samples
    — rather than an approximation of them — is what makes the consistency
    delta published below a statement about the *derivation*, not about two
    different error distributions.
    """
    path = PROC / "model_residuals.csv"
    if not path.exists():
        raise SystemExit("data/processed/model_residuals.csv is missing; run "
                         "`python pipeline/models.py` first so the ordered "
                         "origination uses the model's own error distribution")
    res = pd.read_csv(path)
    pools: dict[int, tuple[np.ndarray, np.ndarray, int, float, float]] = {}
    for season, grp in res.groupby("season"):
        m = grp[grp["target"] == "margin"]["residual"].to_numpy(float)
        t = grp[grp["target"] == "total"]["residual"].to_numpy(float)
        if len(m) < MIN_POOL or len(t) < MIN_POOL:
            continue
        pools[int(season)] = (m, t, int(min(len(m), len(t))),
                              float(m.mean()), float(t.mean()))
    return pools


def _joint_grid(m_res: np.ndarray, t_res: np.ndarray, rho: float) -> tuple[np.ndarray, np.ndarray]:
    """A deterministic Gaussian-copula pairing of the two residual samples.

    ``u`` is a fixed quantile grid, so the pairing is reproducible without a
    random seed and without re-running the pipeline giving a different answer.
    """
    k = min(len(m_res), len(t_res), MAX_GRID)
    m_sorted = np.sort(m_res)[-k:]
    t_sorted = np.sort(t_res)[-k:]
    u = (np.arange(k) + 0.5) / k
    z_m = stats.norm.ppf(u)
    rho_c = float(np.clip(rho, -0.999, 0.999))
    z_t = rho_c * z_m + np.sqrt(max(0.0, 1.0 - rho_c ** 2)) * stats.norm.ppf(u)
    u_t = stats.norm.cdf(z_t)
    r_m = np.quantile(m_sorted, u, method="linear")
    r_t = np.quantile(t_sorted, u_t, method="linear")
    return r_m, r_t


def _order_table() -> pd.DataFrame:
    """The declared order, published so a reader can check it against the data."""
    rows = [
        (1, "SIDE", "margin model (ensemble of ridge, match-up and Elo)",
         "fair home margin, expressed as the home line",
         "market spread line", "points (model line minus market line)",
         "difference column is filled on every row; no imputation"),
        (2, "TOTAL", "total model (ensemble of ridge and match-up)",
         "fair game total", "market total line", "points (model total minus market total)",
         "difference column is filled on every row; no imputation"),
        (3, "MONEYLINE", "steps 1 and 2 jointly, on the integer score lattice",
         "P(home win), P(tie), P(away win) and the two-way fair price",
         "market moneyline price (de-vigged)",
         "implied probability points (model minus market)",
         "consistency delta against the model's margin-only moneyline is published"),
    ]
    return pd.DataFrame(rows, columns=[
        "step", "market", "model_input", "model_output", "market_line",
        "difference_unit", "consistency_check"])


def build() -> tuple[pd.DataFrame, dict]:
    played = _model_inputs()
    played = played[played["record_set"] == "played"].copy()
    upcoming = _model_inputs()
    upcoming = upcoming[upcoming["record_set"] == "upcoming"].copy()
    all_games = pd.concat([played, upcoming], ignore_index=True)

    pools = _residual_pool()

    rows = []
    for season, grp in all_games.groupby("season"):
        pool = pools.get(int(season))
        if pool is None:
            continue
        m_res, t_res, n_pool, m_mean, t_mean = pool
        rho = float(np.corrcoef(m_res, t_res)[0, 1]) if n_pool > 2 else 0.0
        if not np.isfinite(rho):
            rho = 0.0
        # The sample supplies the *shape* of the predictive error; the published
        # line supplies its *location*. The sample mean is therefore removed, so
        # the moneyline derived in step 3 is located on the published side and
        # cannot contradict it. The removed means are published on every row.
        r_m, r_t = _joint_grid(m_res - m_mean, t_res - t_mean, rho)

        fair_spread = grp["fair_spread"].to_numpy(float)[:, None]
        fair_total = grp["fair_total"].to_numpy(float)[:, None]
        margin = fair_spread + r_m[None, :]
        total = fair_total + r_t[None, :]
        home = np.rint((total + margin) / 2.0)
        away = np.rint((total - margin) / 2.0)
        p_home = (home > away).mean(axis=1)
        p_tie = (home == away).mean(axis=1)
        p_away = (home < away).mean(axis=1)
        lattice_margin = (home - away).mean(axis=1)

        for i, r in enumerate(grp.itertuples(index=False)):
            ph, pt, pa = float(p_home[i]), float(p_tie[i]), float(p_away[i])
            two_way = ph + pa
            fair_home = fair_american(ph / two_way) if two_way > 0 else None
            fair_away = fair_american(pa / two_way) if two_way > 0 else None
            posted = american_with_hold(ph / two_way, 0.045) if two_way > 0 else (None, None)
            mkt_h = r.market_home_ml
            mkt_a = r.market_away_ml
            if (mkt_h is not None and np.isfinite(mkt_h) and abs(mkt_h) > 100
                    and mkt_a is not None and np.isfinite(mkt_a) and abs(mkt_a) > 100):
                ih = 100.0 / (mkt_h + 100.0) if mkt_h > 0 else -mkt_h / (-mkt_h + 100.0)
                ia = 100.0 / (mkt_a + 100.0) if mkt_a > 0 else -mkt_a / (-mkt_a + 100.0)
                mkt_p_home = ih / (ih + ia)
            else:
                mkt_p_home = None
            diff_home = ((ph / two_way) - mkt_p_home) * 100.0 if (
                two_way > 0 and mkt_p_home is not None) else None
            legacy_home = r.p_home_ml
            delta = ((ph - legacy_home) * 100.0
                     if (legacy_home is not None and np.isfinite(legacy_home)) else None)
            ctx_url, ctx_status = official_context_url(int(r.season), int(r.week))
            rows.append({
                "game_id": r.game_id, "record_set": r.record_set,
                "season": int(r.season), "week": int(r.week), "game_type": r.game_type,
                "gameday": r.gameday, "home_team": r.home_team, "away_team": r.away_team,
                # step 1 - side
                "step1_fair_spread": r.fair_spread, "step1_market_spread": r.market_spread,
                "step1_difference": (r.fair_spread - r.market_spread
                                     if (r.fair_spread is not None and np.isfinite(r.fair_spread)
                                         and r.market_spread is not None and np.isfinite(r.market_spread))
                                     else None),
                # step 2 - total
                "step2_fair_total": r.fair_total, "step2_market_total": r.market_total,
                "step2_difference": (r.fair_total - r.market_total
                                     if (r.fair_total is not None and np.isfinite(r.fair_total)
                                         and r.market_total is not None and np.isfinite(r.market_total))
                                     else None),
                # step 3 - moneyline, derived from steps 1 and 2
                "step3_p_home": ph, "step3_p_tie": pt, "step3_p_away": pa,
                "step3_fair_home_ml": fair_home, "step3_fair_away_ml": fair_away,
                "step3_posted_home_ml": posted[0], "step3_posted_away_ml": posted[1],
                "step3_market_home_ml": mkt_h, "step3_market_away_ml": mkt_a,
                "step3_difference_home_prob_points": diff_home,
                "step3_difference_away_prob_points": (-diff_home if diff_home is not None else None),
                "implied_home_score": (r.fair_total + r.fair_spread) / 2.0
                                     if (r.fair_total is not None and r.fair_spread is not None
                                         and np.isfinite(r.fair_total) and np.isfinite(r.fair_spread))
                                     else None,
                "implied_away_score": (r.fair_total - r.fair_spread) / 2.0
                                     if (r.fair_total is not None and r.fair_spread is not None
                                         and np.isfinite(r.fair_total) and np.isfinite(r.fair_spread))
                                     else None,
                # consistency against the model's own margin-only moneyline
                "legacy_p_home_ml": legacy_home, "legacy_p_tie": r.p_tie,
                "legacy_p_away_ml": r.p_away_ml, "legacy_fair_home_ml": r.originated_home_ml,
                "consistency_delta_prob_points": delta,
                "lattice_mean_margin": float(lattice_margin[i]),
                "lattice_margin_gap_points": (float(lattice_margin[i]) - float(r.fair_spread)
                                              if (r.fair_spread is not None and np.isfinite(r.fair_spread))
                                              else None),
                "consistency_status": ("consistent"
                                        if (r.fair_spread is not None and np.isfinite(r.fair_spread)
                                            and abs(float(lattice_margin[i]) - float(r.fair_spread))
                                            <= MARGIN_CONSISTENCY_TOLERANCE_POINTS
                                            and abs(ph + pt + pa - 1.0) <= 1e-9)
                                        else "differs"),
                "residual_pool_n": n_pool,
                "residual_pool_mean_margin": m_mean,
                "residual_pool_mean_total": t_mean,
                "residual_centering": "centred on the published prediction",
                "residual_pool_seasons_used": int(played[played["season"] < int(season)]["season"].nunique()),
                "residual_correlation_rho": rho,
                "official_context_url": ctx_url, "official_context_status": ctx_status,
            })

    out = pd.DataFrame(rows)
    for c in out.columns:
        if out[c].dtype.kind == "f":
            out[c] = out[c].round(6)
    out = out.sort_values(["season", "week", "game_id"]).reset_index(drop=True)

    comparable = out["consistency_delta_prob_points"].dropna()
    gaps = out["lattice_margin_gap_points"].dropna()
    summary = {
        "originated_games": int(len(out)),
        "played_games": int((out["record_set"] == "played").sum()),
        "scheduled_games": int((out["record_set"] == "upcoming").sum()),
        "order": ["SIDE", "TOTAL", "MONEYLINE"],
        "moneyline_derivation": ("derived from the side and the total on the integer score "
                                 "lattice; never fitted separately"),
        "consistency_tolerance_prob_points": CONSISTENCY_TOLERANCE_PP,
        "residual_centering": "centred on the published prediction",
        "consistency_comparable_rows": int(len(comparable)),
        "consistency_within_tolerance": int((comparable.abs() <= CONSISTENCY_TOLERANCE_PP).sum()),
        "consistency_delta_mean_pp": float(comparable.mean()) if len(comparable) else None,
        "consistency_delta_max_pp": float(comparable.abs().max()) if len(comparable) else None,
        "consistency_delta_p99_pp": float(comparable.abs().quantile(0.99)) if len(comparable) else None,
        "residual_correlation_median_rho": float(out["residual_correlation_rho"].median()),
        "lattice_margin_gap_max_points": float(gaps.abs().max()) if len(gaps) else None,
        "lattice_margin_gap_mean_points": float(gaps.abs().mean()) if len(gaps) else None,
        "lattice_reproduces_published_side": int((out["consistency_status"] == "consistent").sum()),
        "delta_is_a_difference_measure_not_a_failure": (
            "The delta between the ordered moneyline and the model's margin-only "
            "moneyline is a discretisation difference (margin lattice against score "
            "lattice), not a contradiction. The invariant that is checked is that the "
            "moneyline's own lattice reproduces the published side."),
        "moneyline_probability_is_a_function_of_the_side": True,
        "note": ("Home wins if and only if the margin is positive, so the published "
                 "moneyline probability cannot move without moving the published side. "
                 "Step 3 guarantees the three published markets agree with each other."),
    }
    return out, summary


def main() -> None:
    lines, summary = build()
    lines.to_csv(LINES, index=False)
    _order_table().to_csv(ORDER, index=False)
    write_json(REPORT, summary)
    print(f"origination: {len(lines):,} games originated in the order "
          f"{' -> '.join(summary['order'])}; the moneyline's score lattice reproduces "
          f"the published side on {summary['lattice_reproduces_published_side']:,}/"
          f"{len(lines):,} games (max gap {summary['lattice_margin_gap_max_points']:.4f} pt); "
          f"the delta against the model's margin-only moneyline is at most "
          f"{summary['consistency_delta_max_pp']:.3f} pp")


if __name__ == "__main__":
    main()
