"""T54 — the leaderboard with **signal** and **staking** separated.

The problem this solves
-----------------------
A leaderboard that ranks on money alone cannot tell a good signal from a good
week. A strategy that fires a few times and gets lucky can sit at the top of a
return table while its predictive content is nil, and a strategy with a real
edge can sit at the bottom while the variance works against it. Ranking on the
return therefore ranks luck.

So the two are measured separately and published separately:

**Signal** — is the prediction good? Measured **without reference to the price
that was paid**:

  * `signal_hit_rate`       how often the signal's direction was right
  * `signal_edge`           hit rate minus the break-even rate implied by the
                            average price actually paid — the expected profit
                            per bet expressed in probability, not in money
  * `signal_edge_at_even`   the same edge recomputed at even money, so the
                            price's own contribution is removed entirely
  * `signal_edge_lo/hi`     a Wilson interval on the hit rate, compared with
                            the break-even rate

**Staking** — did the money work? Measured at the price actually paid:

  * `staking_roi`, `staking_profit`, `staking_hit_rate`, `staking_avg_price`
  * `staking_weekly_vol`, `staking_max_drawdown`
  * `staking_verdict`       **SKILL** only when the power gate is met and the
                            bootstrap lower bound on the return is positive

The rule that makes the separation bite: **a staking result may never promote
a strategy whose signal is not positive.** A positive return with a
non-positive signal is labelled `LUCKY_STAKE_BAD_SIGNAL` and is capped at
paper, whatever its rank on the money table. The leaderboard is ranked on the
signal; the money columns are shown beside it and never used to order it.

Outputs
-------
  data/processed/leaderboard_signal_staking.csv   the two scorecards
  assets/data/leaderboard_signal_staking.csv       the same, for the site

Run:  python pipeline/leaderboard_split.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from common import PROC  # noqa: E402

SITE_DATA = ROOT / "assets" / "data"

COLUMNS = [
    "strategy", "name", "family", "market", "division",
    # ---- signal scorecard ------------------------------------------------
    "signal_bets", "signal_decided_bets", "signal_wins", "signal_losses",
    "signal_pushes", "signal_hit_rate", "signal_hit_rate_lo", "signal_hit_rate_hi",
    "signal_break_even_rate", "signal_edge", "signal_edge_lo", "signal_edge_hi",
    "signal_edge_at_even", "signal_verdict",
    # ---- staking scorecard ----------------------------------------------
    "staking_units", "staking_roi", "staking_profit", "staking_hit_rate",
    "staking_avg_price", "staking_weekly_vol", "staking_max_drawdown",
    "staking_bootstrap_roi_lo", "staking_p_holm", "staking_n_weeks",
    "staking_n_weeks_required", "staking_verdict",
    # ---- combined --------------------------------------------------------
    "combined_verdict", "signal_rank", "staking_rank", "tier_cap",
    "gates_passed", "gates_failed", "reward", "note",
]


def _num(x) -> float:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return f if np.isfinite(f) else float("nan")


def _wilson(wins: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (no continuity term)."""
    if n <= 0:
        return float("nan"), float("nan")
    p = wins / n
    d = 1.0 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - half) / d, (centre + half) / d


def _max_drawdown(series: list[float]) -> float:
    """Peak-to-trough drawdown of a cumulative weekly return series."""
    peak, worst, cum = 0.0, 0.0, 0.0
    for x in series:
        cum += x
        peak = max(peak, cum)
        worst = min(worst, cum - peak)
    return worst


def _decimal_price(price, units: str) -> float:
    """The decimal payout multiple a bet was priced at.

    Single bets carry American odds; parlay tickets carry the decimal price of
    the whole ticket. Nothing is assumed about the units: the file states them.
    """
    p = _num(price)
    if not np.isfinite(p) or p <= 0:
        return float("nan")
    if str(units).strip().lower() == "decimal":
        return p
    if p > 0:
        return 1.0 + p / 100.0
    if p > -100:
        return 1.0 + 100.0 / abs(p)
    return float("nan")


def build() -> pd.DataFrame:
    gates = pd.read_csv(PROC / "strategy_gates.csv")
    summary = pd.read_csv(PROC / "strategy_summary.csv")
    bets = pd.read_csv(PROC / "strategy_bets.csv", dtype=str).fillna("")
    weekly = pd.read_csv(PROC / "strategy_weekly_matrix.csv")
    try:
        stats_ = pd.read_csv(PROC / "strategy_stats.csv")
    except FileNotFoundError:
        stats_ = pd.DataFrame(columns=["strategy"])

    meta = summary.set_index("strategy")[["name", "family", "market"]].to_dict("index")
    st = stats_.set_index("strategy").to_dict("index") if len(stats_) else {}

    # Per-bet decimal price, so the break-even rate is the one each bet
    # actually carried and not the break-even of the average price.
    bets = bets.copy()
    bets["_dec"] = [_decimal_price(p, u) for p, u in
                    zip(bets.price, bets.get("price_units", pd.Series([""] * len(bets))))]

    rows = []
    for _, g in gates.sort_values("strategy").iterrows():
        sid = str(g["strategy"])
        m = meta.get(sid, {})
        b = bets[bets.strategy == sid]

        # ---- signal scorecard ---------------------------------------------
        # The signal is the directional quality of the rule, compared with the
        # rate it had to reach to pay for itself at the price each bet carried.
        wins = int(g["wins"])
        losses = int(g["losses"])
        pushes = int(g["pushes"])
        decided = wins + losses
        hit = wins / decided if decided else float("nan")
        dec = b["_dec"].dropna()
        breakeven = float((1.0 / dec).mean()) if len(dec) else float("nan")
        avg_dec = float(dec.mean()) if len(dec) else float("nan")
        lo, hi = _wilson(wins, decided)
        edge = hit - breakeven if np.isfinite(hit) and np.isfinite(breakeven) else float("nan")
        edge_lo = lo - breakeven if np.isfinite(lo) and np.isfinite(breakeven) else float("nan")
        edge_hi = hi - breakeven if np.isfinite(hi) and np.isfinite(breakeven) else float("nan")
        edge_even = (2 * hit - 1) if np.isfinite(hit) else float("nan")

        if not np.isfinite(edge):
            sig_verdict = "NO DATA"
        elif edge_lo > 0:
            sig_verdict = "SKILL"
        elif edge_hi < 0:
            sig_verdict = "NO EDGE"
        else:
            sig_verdict = "UNRESOLVED"

        # ---- staking scorecard (everything here uses the price paid) -------
        units = int(g["n"])
        roi = _num(g["roi"])
        profit = _num(g["profit"])
        w = weekly[["week_key", sid]] if sid in weekly.columns else pd.DataFrame()
        series = [float(x) for x in w[sid].tolist()] if len(w) else []
        vol = float(np.std(series, ddof=1)) if len(series) > 1 else float("nan")
        dd = _max_drawdown(series) if series else float("nan")
        boot_lo = _num(g.get("G5_boot_roi_lo"))
        p_holm = _num(g.get("G4_p_adj"))
        n_weeks = int(g["n_weeks"])
        n_weeks_req = int(round(float(g["required_n_weeks"])))

        if units <= 0:
            stk_verdict = "NO DATA"
        elif n_weeks < n_weeks_req:
            stk_verdict = "INSUFFICIENT SAMPLE — consistent with luck"
        elif np.isfinite(boot_lo) and boot_lo > 0 and bool(g.get("G4_significance")):
            stk_verdict = "SKILL"
        elif roi > 0:
            stk_verdict = "POSITIVE BUT NOT DISTINGUISHABLE FROM LUCK"
        else:
            stk_verdict = "NEGATIVE"

        # ---- combined -------------------------------------------------------
        if sig_verdict == "SKILL" and stk_verdict == "SKILL":
            combined = "SKILL CONFIRMED — signal and staking agree"
        elif sig_verdict == "SKILL":
            combined = "GOOD SIGNAL, STAKING NOT YET DISTINGUISHABLE FROM LUCK"
        elif roi > 0:
            combined = ("LUCKY STAKING RUN — the signal is not positive; this "
                        "result must not be read as skill")
        elif sig_verdict == "NO EDGE":
            combined = "NO EDGE"
        else:
            combined = "NO EDGE OR UNRESOLVED"

        tier_cap = ("PAPER — a positive return with a non-positive signal cannot "
                    "be promoted" if combined.startswith("LUCKY STAKING")
                    else "no cap beyond the eight gates")

        gate_names = ["G1_data", "G2_leakage", "G3_power", "G4_significance",
                      "G5_luck", "G6_economic", "G7_stability", "G8_redundancy"]
        passed = [x for x in gate_names if bool(g.get(x))]
        failed = [x.split("_")[0] for x in gate_names if not bool(g.get(x))]

        rows.append({
            "strategy": sid, "name": m.get("name", ""), "family": m.get("family", ""),
            "market": m.get("market", ""),
            "division": {"parlay": "P · Parlays"}.get(m.get("family", ""),
                                                     "S · Single bets"),
            "signal_bets": units, "signal_decided_bets": decided,
            "signal_wins": wins, "signal_losses": losses, "signal_pushes": pushes,
            "signal_hit_rate": _r(hit), "signal_hit_rate_lo": _r(lo),
            "signal_hit_rate_hi": _r(hi),
            "signal_break_even_rate": _r(breakeven),
            "signal_edge": _r(edge), "signal_edge_lo": _r(edge_lo),
            "signal_edge_hi": _r(edge_hi),
            "signal_edge_at_even": _r(edge_even),
            "signal_verdict": sig_verdict,
            "staking_units": units, "staking_roi": _r(roi),
            "staking_profit": _r(profit),
            "staking_hit_rate": _r(_num(g["win_rate"])),
            "staking_avg_price": _r(avg_dec),
            "staking_weekly_vol": _r(vol), "staking_max_drawdown": _r(dd),
            "staking_bootstrap_roi_lo": _r(boot_lo), "staking_p_holm": _r(p_holm),
            "staking_n_weeks": n_weeks,
            "staking_n_weeks_required": n_weeks_req,
            "staking_verdict": stk_verdict,
            "combined_verdict": combined,
            "signal_rank": 0, "staking_rank": 0,
            "tier_cap": tier_cap,
            "gates_passed": len(passed),
            "gates_failed": "; ".join(failed) or "none",
            "reward": str(g["reward"]),
            "note": ("The signal scorecard uses no price. The staking scorecard "
                     "uses only the price actually paid."),
        })

    df = pd.DataFrame(rows, columns=COLUMNS)

    # The leaderboard is ranked on the signal. The staking rank is published
    # beside it and never used to order the leaderboard.
    df["_sig_key"] = df.signal_edge.fillna(-9)
    df = df.sort_values(["_sig_key", "signal_decided_bets"], ascending=[False, False])
    df["signal_rank"] = range(1, len(df) + 1)
    df["_stk_key"] = df.staking_roi.fillna(-9)
    df = df.sort_values(["_stk_key", "staking_units"], ascending=[False, False])
    df["staking_rank"] = range(1, len(df) + 1)
    df = df.sort_values("signal_rank").drop(columns=["_sig_key", "_stk_key"])
    return df.reset_index(drop=True)


def _r(x, nd: int = 6) -> str:
    """A number for the CSV, or an empty cell when it is not defined."""
    f = _num(x)
    if not np.isfinite(f):
        return ""
    return f"{round(f, nd):g}"


def main() -> None:
    df = build()
    df.to_csv(PROC / "leaderboard_signal_staking.csv", index=False)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    df.to_csv(SITE_DATA / "leaderboard_signal_staking.csv", index=False)
    print(f"leaderboard_signal_staking: {len(df)} strategies")
    if len(df):
        print(f"  signal verdicts: {df.signal_verdict.value_counts().to_dict()}")
        print(f"  staking verdicts: {df.staking_verdict.value_counts().to_dict()}")
        print(f"  combined: {df.combined_verdict.str.slice(0, 40).value_counts().to_dict()}")


if __name__ == "__main__":
    main()
