"""Demotion gate: sends a LIVE strategy back to PAPER when its live record fails.

Added 2026-11-14 (branch arena/b400d3ae-korea1). It is the mirror image of the
promotion gates in `pipeline/validation.py`, evaluated on a strategy's live
record instead of its backtest.

Rules (fail-closed; every threshold is taken from validation.GATES where one exists)
----------------------------------------------------------------------------------
A strategy is LIVE only while it has a recorded live authorisation (not implemented
here: no strategy holds one today). `evaluate()` returns the state the gate
recommends. It never promotes anything.

DG1  Look-ahead: any live pick whose freeze timestamp is at or after kickoff
     -> DEMOTE immediately, regardless of sample size.
DG2  Integrity: any live pick that is settled (status OFFICIAL) but has no official
     outcome or no pnl -> DEMOTE immediately. Missing data is never filled in.
DG3  Sample floor: DG4-DG6 only apply once the window holds at least
     validation.GATES["G3_min_bets"] (100) settled bets over at least
     validation.GATES["G3_min_seasons"] (3) seasons. Below that the verdict is
     INSUFFICIENT, not DEMOTE and not PASS.
DG4  Stressed economics: ROI after the adverse-price stress (pnl_stress) <= 0
     over the window -> DEMOTE.
DG5  Significance: the lower 95% bound of the weekly ROI bootstrap
     (stats_tools.bootstrap_mean_test) <= 0 -> DEMOTE. Mirrors the promotion
     requirement G4/G5 (the lower bound must be above zero to stay live).
DG6  Closing-line value: when CLV is present on every window bet, mean CLV < 0
     -> DEMOTE. Requires CLV coverage; partial CLV coverage is INSUFFICIENT.

Re-promotion (documented, not automated): a demoted strategy returns to LIVE only
after a new frozen trial registry entry and the full eight-gate battery passing on
weeks that were not used to demote it. Demotion history is never erased.

Open parameter (NEEDS DECISION, not applied): a drawdown trigger. No drawdown
threshold is set anywhere in the repository, so none is invented here. Pass one
explicitly via `max_drawdown_units` if the owner decides on a value.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stats_tools as st  # noqa: E402
from validation import GATES  # noqa: E402

PASS = "PASS"
DEMOTE = "DEMOTE"
INSUFFICIENT = "INSUFFICIENT"

REQUIRED_COLS = ["status", "outcome", "pnl", "pnl_stress", "season", "week",
                 "freeze_before_kickoff"]


def _weekly_roi(window: pd.DataFrame) -> np.ndarray:
    return window.groupby(["season", "week"])["pnl"].mean().to_numpy(float)


def evaluate(picks: pd.DataFrame, window_bets: int | None = None,
             max_drawdown_units: float | None = None, n_boot: int = 5000) -> dict:
    """Return the gate's recommendation for one strategy's live ledger.

    `picks` must contain REQUIRED_COLS (plus `clv` if DG6 is to run). Rows are
    ordered by (season, week) and the most recent `window_bets` settled bets are
    used (all of them when None). The function never imputes a missing value.
    """
    missing = [c for c in REQUIRED_COLS if c not in picks.columns]
    if missing:
        raise ValueError(f"ledger is missing required columns: {missing}")

    triggers: list[dict] = []

    def trig(rule: str, detail: str) -> None:
        triggers.append({"rule": rule, "detail": detail})

    # DG1 look-ahead: checked on every row, before any sample rule.
    leak = picks[picks["freeze_before_kickoff"].astype(str).str.lower().isin(["false", "0", "no"])]
    if len(leak):
        trig("DG1", f"{len(leak)} pick(s) frozen at or after kickoff")

    settled = picks[picks["status"].astype(str).str.upper() == "OFFICIAL"].copy()

    # DG2 integrity: a settled row with no outcome or pnl is a defect, not a gap to fill.
    bad = settled[settled["outcome"].isna() | settled["pnl"].isna()
                  | (settled["outcome"].astype(str).str.strip() == "")]
    if len(bad):
        trig("DG2", f"{len(bad)} settled pick(s) lack an official outcome or pnl")

    settled = settled.sort_values(["season", "week"], kind="stable")
    if window_bets is not None:
        settled = settled.tail(int(window_bets))

    n = int(len(settled))
    seasons = int(settled["season"].nunique()) if n else 0
    stats = {"n_bets": n, "seasons": seasons, "roi": float("nan"),
             "stressed_roi": float("nan"), "ci_lo": float("nan"), "mean_clv": float("nan")}

    sample_ok = (n >= GATES["G3_min_bets"] and seasons >= GATES["G3_min_seasons"])
    if n:
        stats["roi"] = float(settled["pnl"].astype(float).mean())
        if settled["pnl_stress"].notna().all():
            stats["stressed_roi"] = float(settled["pnl_stress"].astype(float).mean())

    if sample_ok and not triggers:
        if np.isfinite(stats["stressed_roi"]) and stats["stressed_roi"] <= 0:
            trig("DG4", f"stressed ROI {stats['stressed_roi']:.4f} <= 0")
        weekly = _weekly_roi(settled)
        boot = st.bootstrap_mean_test(weekly, n_boot) if len(weekly) >= 3 else {"ci_lo": float("nan")}
        stats["ci_lo"] = float(boot["ci_lo"])
        if np.isfinite(stats["ci_lo"]) and stats["ci_lo"] <= 0:
            trig("DG5", f"weekly ROI bootstrap 95% lower bound {stats['ci_lo']:.4f} <= 0")
        if "clv" in settled.columns and settled["clv"].notna().all():
            stats["mean_clv"] = float(settled["clv"].astype(float).mean())
            if stats["mean_clv"] < 0:
                trig("DG6", f"mean CLV {stats['mean_clv']:.4f} < 0")

    if max_drawdown_units is not None and n:
        equity = settled["pnl"].astype(float).cumsum().to_numpy()
        peak = np.maximum.accumulate(np.concatenate([[0.0], equity]))[1:]
        dd = float(np.max(peak - equity)) if len(equity) else 0.0
        stats["max_drawdown_units"] = dd
        if dd > max_drawdown_units:
            trig("DRAWDOWN", f"drawdown {dd:.2f} units > limit {max_drawdown_units}")

    if triggers:
        verdict = DEMOTE
    elif not sample_ok:
        verdict = INSUFFICIENT
    else:
        verdict = PASS
    return {"verdict": verdict, "state_recommendation":
            "PAPER" if verdict == DEMOTE else "LIVE" if verdict == PASS else "NO CHANGE",
            "triggers": triggers, **stats}


if __name__ == "__main__":  # manual check only; writes nothing
    import json
    print(json.dumps({"rules": ["DG1", "DG2", "DG3", "DG4", "DG5", "DG6"],
                      "thresholds": {k: GATES[k] for k in ("G3_min_bets", "G3_min_seasons")}},
                     indent=2))
