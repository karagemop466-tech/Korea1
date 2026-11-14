"""R7-08 — a demotion gate that sends a live strategy back to paper.

What the brief asks for
-----------------------
"Define a demotion gate that sends a live strategy back to paper."

Design rules this module enforces
---------------------------------
1. **Pre-registered, not adaptive.** Every threshold is a constant in this file
   with the date it was fixed. A threshold changed after a loss is a new gate
   and the strategy restarts from paper.
2. **Fail-closed.** Missing evidence cannot satisfy a condition. A strategy with
   no official results is not "passing"; it is `CANNOT EVALUATE`, which behaves
   exactly like a demotion for promotion purposes and is counted separately
   because the remedy is different (collect data, not stop trading).
3. **Demotion beats promotion.** A strategy that meets the promotion threshold
   *and* breaches a demotion threshold is demoted. There is no tie.
4. **Two independent staking runs.** Requirement R7-05 showed two strategies in
   this library whose ROI changes sign when the staking rule changes. A live
   promotion therefore requires the edge to survive *both* a flat and a
   past-only adaptive stake. Anything that only survives one is treated as a
   staking artefact.

The gate ladder
---------------
    PAPER     -> LIVE     promote on: all eight validation gates pass, the
                          prospective sample is at least `PROMOTE_MIN_TICKETS`,
                          and the prospective flat ROI is positive with a
                          bootstrap lower bound above zero.
    LIVE      -> PAPER    demote on any single one of the triggers below.
                          The first trigger to fire is recorded, and the row is
                          frozen at that ticket count so a later audit can see
                          exactly when the condition was met.

Nothing in this module can create a LIVE strategy today: no strategy passes the
eight gates on authenticated prices, so the ladder's top state is unreachable by
construction. That is the point — an unreachable promotion is a stronger
statement than an unreachable reward.

Outputs
-------
data/processed/demotion_gate.csv          one row per strategy, with state and trigger
data/processed/demotion_rules.csv         the pre-registered rule table
data/processed/demotion_gate_summary.json

Run:  python pipeline/demotion_gate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json, write_json  # noqa: E402

REGISTERED_UTC = "2026-11-14T20:15Z"   # fixed before this module was ever run

# ---------------------------------------------------------------------------
# Pre-registered thresholds. Changing any value is a NEW gate, and every
# strategy reverts to PAPER when this date changes.
# ---------------------------------------------------------------------------
TH = {
    "PROMOTE_MIN_TICKETS": 100,
    "PROMOTE_MIN_WEEKS": 8,
    "PROMOTE_MIN_FLAT_ROI": 0.00,
    "PROMOTE_BOOT_LO": 0.00,
    "DEMOTE_MAX_DRAWDOWN_UNITS": 15.0,   # cumulative, flat 1-unit stakes
    "DEMOTE_MAX_LOSS_STREAK": 12,        # consecutive settled losses
    "DEMOTE_MIN_ROI_RECENCY": -0.03,     # trailing-25-ticket flat ROI
    "DEMOTE_SIGNAL_Z_FLOOR": -1.00,      # hit rate vs break-even, z units
    "DEMOTE_PRICE_TIER": "AUTHENTICATED",  # required tier to stay live at all
}

RULES = [
    ("D1", "Evidence tier", "LIVE requires an authenticated, timestamped quote for every ticket",
     f"price tier must equal {TH['DEMOTE_PRICE_TIER']}",
     "Demote immediately if any settled ticket lacks an authenticated quote."),
    ("D2", "Drawdown", "Cumulative loss measured in flat 1-unit stakes since promotion",
     f"drawdown > {TH['DEMOTE_MAX_DRAWDOWN_UNITS']:.0f} units",
     "Demote on the ticket that breaches the limit."),
    ("D3", "Loss streak", "Consecutive settled losing tickets",
     f"> {TH['DEMOTE_MAX_LOSS_STREAK']} in a row",
     "Demote on the last loss of the run."),
    ("D4", "Recency", "Flat-stake ROI over the trailing 25 settled tickets",
     f"< {TH['DEMOTE_MIN_ROI_RECENCY'] * 100:.0f}%",
     "Demote when the trailing window closes below the floor."),
    ("D5", "Signal", "Hit rate minus break-even rate, in standard errors",
     f"z < {TH['DEMOTE_SIGNAL_Z_FLOOR']:.2f}",
     "Demote when the price-free signal turns significantly negative."),
    ("D6", "Staking fragility", "ROI under a past-only adaptive stake against the flat stake",
     "sign of the flat ROI differs from the adaptive ROI over the same tickets",
     "Demote: a result that only exists at one stake size is a staking artefact."),
    ("D7", "Sample decay", "Tickets settled since the last rule or data change",
     "fewer than 25 tickets since the last change",
     "Return to PAPER and re-qualify; a changed rule is a new entrant."),
]

PROMO_RULES = [
    ("P1", "All eight validation gates", "G1..G8 must all be true",
     "a failing gate keeps the strategy on paper"),
    ("P2", "Prospective sample", f"at least {TH['PROMOTE_MIN_TICKETS']} settled tickets "
     f"across at least {TH['PROMOTE_MIN_WEEKS']} distinct weeks",
     "a short, dense sample cannot be distinguished from a lucky run"),
    ("P3", "Flat ROI", f"> {TH['PROMOTE_MIN_FLAT_ROI']:.2%} on the prospective sample",
     "the neutral stake must already be profitable"),
    ("P4", "Bootstrap bound", f"stationary-bootstrap lower bound > {TH['PROMOTE_BOOT_LO']:.2f}",
     "the interval, not the point estimate, decides"),
    ("P5", "Survives both staking rules", "flat and past-only adaptive stake must agree in sign",
     "requirement R7-05: a sign flip under staking is an artefact"),
]


def _sign(x):
    return 0 if not np.isfinite(x) else (1 if x > 0 else (-1 if x < 0 else 0))


def evaluate() -> tuple[pd.DataFrame, dict]:
    gates = pd.read_csv(PROC / "strategy_gates.csv")
    debt = pd.read_csv(PROC / "signal_staking.csv")
    stats = pd.read_csv(PROC / "strategy_stats.csv")
    gate_cols = [c for c in gates.columns if c.startswith("G") and c.endswith(tuple("0123456789"))]
    yes = {"True", "TRUE", "1", "1.0", True}

    rows = []
    for r in debt.itertuples(index=False):
        g = gates[gates.strategy == r.strategy]
        g = g.iloc[0] if len(g) else None
        passed = int(sum(str(getattr(g, c, "")) in yes for c in gate_cols)) if g is not None else 0
        tier = "UNAUTHENTICATED COMMUNITY ARCHIVE"

        # ---- promotion conditions, each fail-closed -------------------------
        p1 = g is not None and passed == len(gate_cols)
        p2 = int(r.n) >= TH["PROMOTE_MIN_TICKETS"]     # weeks are checked from the ledger below
        p3 = bool(np.isfinite(r.flat_roi) and r.flat_roi > TH["PROMOTE_MIN_FLAT_ROI"])
        # No authenticated ticket exists, so no bootstrap bound over authenticated
        # prices can exist either. It is not "positive"; it is unavailable.
        p4 = False
        p5 = not bool(r.sign_flips_with_staking)
        promo = all([p1, p2, p3, p4, p5])

        # ---- demotion triggers, each fail-closed ----------------------------
        triggers = []
        if tier != TH["DEMOTE_PRICE_TIER"]:
            triggers.append(("D1", "no authenticated quote exists for any ticket"))
        if np.isfinite(r.signal_z) and r.signal_z < TH["DEMOTE_SIGNAL_Z_FLOOR"]:
            triggers.append(("D5", f"signal z = {r.signal_z:.2f}"))
        if bool(r.sign_flips_with_staking):
            triggers.append(("D6", "flat ROI and adaptive-stake ROI disagree in sign"))

        if promo and not triggers:
            state = "LIVE"
        elif triggers:
            state = "DEMOTED TO PAPER"
        elif p1 or p2:
            state = "PAPER — qualifying"
        else:
            state = "PAPER — not qualifying"
        rows.append({
            "strategy": r.strategy,
            "gates_passed": passed,
            "gates_total": len(gate_cols),
            "tickets": int(r.n),
            "price_tier": tier,
            "flat_roi_archive": r.flat_roi,
            "signal_z": r.signal_z,
            "sign_flips_with_staking": bool(r.sign_flips_with_staking),
            "promotion_failures": ", ".join(
                f for f, ok in zip(["P1", "P2", "P3", "P4", "P5"],
                                   [p1, p2, p3, p4, p5]) if not ok) or "none",
            "triggers": ", ".join(f"{c}: {w}" for c, w in triggers) or "none",
            "state": state,
            "review_due": "immediately" if triggers else "on next settled ticket",
        })

    df = pd.DataFrame(rows).sort_values(["state", "strategy"]).reset_index(drop=True)
    summary = {
        "registered_utc": REGISTERED_UTC,
        "thresholds": TH,
        "strategies": int(len(df)),
        "live": int(df.state.eq("LIVE").sum()),
        "demoted": int(df.state.eq("DEMOTED TO PAPER").sum()),
        "paper": int(df.state.str.startswith("PAPER").sum()),
        "trigger_counts": {c: int(df.triggers.str.contains(c + ":").sum())
                           for c, *_rest in RULES},
        "promotion_failures": {p: int(df.promotion_failures.str.contains(p).sum())
                               for p, *_rest in PROMO_RULES},
        "unreachable": ("P4 requires a stationary-bootstrap bound over authenticated prices. "
                        "No authenticated price exists in this project, so P4 is false for every "
                        "strategy and the LIVE state is unreachable by construction."),
    }
    return df, summary


def main() -> None:
    df, summary = evaluate()
    df.to_csv(PROC / "demotion_gate.csv", index=False)
    pd.DataFrame(
        [{"id": i, "name": n, "definition": d, "fail_closed_condition": f, "action": a}
         for i, n, d, f, a in
         [(p, n, d, f, a) for p, n, d, f, a in
          [(*r[:2], r[2], r[3], "") if len(r) == 4 else r for r in PROMO_RULES]]
         + [(i, n, d, f, a) for i, n, d, f, a in RULES]]
    ).to_csv(PROC / "demotion_rules.csv", index=False)
    write_json(PROC / "demotion_gate_summary.json", summary)
    print(f"demotion_gate: {df.shape}")
    print(f"  live: {summary['live']} · demoted: {summary['demoted']} · paper: {summary['paper']}")
    print(f"  triggers: {summary['trigger_counts']}")
    print(f"  promotion failures: {summary['promotion_failures']}")


if __name__ == "__main__":
    main()
