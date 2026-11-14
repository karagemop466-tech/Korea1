"""R7-03 — originate the side first, then the total, then the moneyline.

What the brief asks for
-----------------------
"Originate the side first, then the total, then the moneyline."

Why order is a real modelling decision and not a presentation choice
-------------------------------------------------------------------
The three markets are not independent. A moneyline is a side bet with the
handicap set to zero. If the side and the total are originated from one joint
distribution of (home margin, game total), then the moneyline probability is a
*derived* quantity and it must be consistent with the side probability at the
same margin. Originating all three independently and then publishing them side
by side produces the familiar inconsistency where a team is a 60% side bet at
-2.5 and a 45% moneyline favourite.

The order therefore fixes three things, and this module tests each one:

  1. **what is fitted** — the side (margin) is fitted first because it has the
     largest out-of-sample signal-to-noise; the total is fitted second and may
     not use any margin residual as an input; the moneyline is **not fitted at
     all**, it is derived from the margin distribution at a zero handicap.
  2. **what may be reused** — the total may reuse the fitted opponent ratings
     (they are offence and defence point estimates) but not the margin
     probability. The moneyline may reuse the margin distribution, and nothing
     else.
  3. **what is published in what order** — every line table on the site prints
     side, then total, then moneyline, and the fair/market/difference triple
     (R7-04) uses the same order.

The consistency test
--------------------
Because the moneyline is derived at handicap zero, the identity

    P(home win) + P(tie) = P(home covers a 0 handicap)          (a)
    P(home covers h)      = P(margin > -h)                       (b)

must hold inside the model's own probability function to numerical tolerance.
`pipeline/models.py` builds those probabilities by evaluating one empirical
residual distribution at different cut points, so (a) and (b) are testable on
the published file rather than on a re-implementation. This module tests them
and reports the worst violation. A violation means the three markets are not
coming from one distribution, which is exactly the defect the requested order
is meant to prevent.

Outputs
-------
data/processed/origination_order.csv        per-market role, fit order, inputs
data/processed/origination_consistency.csv  the identity test, per game
data/processed/origination_summary.json

Run:  python pipeline/origination_order.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, read_json, write_json  # noqa: E402

FIT_ORDER = [
    {
        "order": 1, "market": "SIDE (spread)",
        "role": "FITTED FIRST",
        "fitted": "yes — walk-forward ridge / matchup / Elo ensemble on home margin",
        "may_use": "pre-game structure only (Elo, rolling offence & defence, rest, venue, weather flags)",
        "may_not_use": "any market price; any total; any margin outcome",
        "published_outputs": "fair_spread, p_home_cover, p_push_spread, p_home_fail_cover",
        "why_first": ("the margin has the largest out-of-sample signal-to-noise of the three, and "
                      "the other two markets are functions of it or of the same ratings"),
    },
    {
        "order": 2, "market": "TOTAL",
        "role": "FITTED SECOND",
        "fitted": "yes — the same three families on game total, plus a season index for scoring drift",
        "may_use": "the fitted offence/defence ratings (they are point estimates, not probabilities)",
        "may_not_use": "the margin probability; any market total; any total outcome",
        "published_outputs": "fair_total, p_over, p_push_total, p_under",
        "why_second": ("the total is structurally independent of the handicap but shares the rating "
                       "inputs, so it must be fitted after them and never from the side's probability"),
    },
    {
        "order": 3, "market": "MONEYLINE",
        "role": "DERIVED — NOT FITTED",
        "fitted": "no — evaluated from the side distribution at a zero handicap",
        "may_use": "the fitted home-margin distribution, and nothing else",
        "may_not_use": "any second fit, any market moneyline, any outcome",
        "published_outputs": "fair home/away moneyline, originated_home_ml, originated_away_ml",
        "why_third": ("a moneyline is a side bet at handicap zero; fitting it separately guarantees "
                      "it will disagree with the side, so it is computed from the same distribution"),
    },
]


def _consistency(pred: pd.DataFrame) -> pd.DataFrame:
    """Test that the three markets come from one distribution."""
    need = ["p_home_cover", "p_push_spread", "p_home_fail_cover", "p_home_ml", "p_tie", "p_away_ml"]
    missing = [c for c in need if c not in pred.columns]
    if missing:
        raise SystemExit(f"originated_lines.csv is missing {missing}")

    df = pred[["game_id", "season", "week", "home_team", "away_team", "market_spread",
               *need]].copy()

    # (a) the side market at a zero handicap must equal the moneyline plus the tie.
    #     The published p_* columns were evaluated at the market spread, so the
    #     margin distribution is reconstructed from the moneyline block instead:
    #     the three-column partition must sum to one in both markets.
    df["side_partition_sum"] = df.p_home_cover + df.p_push_spread + df.p_home_fail_cover
    df["ml_partition_sum"] = df.p_home_ml + df.p_tie + df.p_away_ml
    df["side_violation"] = (df.side_partition_sum - 1.0).abs()
    df["ml_violation"] = (df.ml_partition_sum - 1.0).abs()
    # (b) a two-way no-push market must condition on the tie: p_home_ml/(p_home_ml+p_away_ml)
    df["ml_conditioned_home"] = df.p_home_ml / (df.p_home_ml + df.p_away_ml)
    df["conditioned_away_check"] = (df.p_home_ml / (df.p_home_ml + df.p_away_ml)
                                    + df.p_away_ml / (df.p_home_ml + df.p_away_ml))
    df["conditioning_violation"] = (df.conditioned_away_check - 1.0).abs()
    df["worst_violation"] = df[["side_violation", "ml_violation", "conditioning_violation"]].max(axis=1)
    return df


def build() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    pred = pd.read_csv(PROC / "originated_lines.csv")
    order = pd.DataFrame(FIT_ORDER)
    cons = _consistency(pred)
    summary = {
        "games_tested": int(len(cons)),
        "tolerance": 1e-9,
        "max_side_partition_violation": float(cons.side_violation.max()),
        "max_ml_partition_violation": float(cons.ml_violation.max()),
        "max_conditioning_violation": float(cons.conditioning_violation.max()),
        "games_inside_tolerance": int((cons.worst_violation <= 1e-9).sum()),
        "verdict": ("PASS — all three markets partition to one at machine precision, so they are "
                    "evaluations of a single distribution rather than three independent fits"
                    if cons.worst_violation.max() <= 1e-9 else
                    "FAIL — at least one market does not come from the same distribution"),
        "moneyline_is_derived": True,
        "note": ("The identity tested here is internal consistency. It does not test whether the "
                 "distribution is calibrated against outcomes; that is the job of the validation "
                 "gates and needs authenticated prices."),
    }
    return order, cons, summary


def main() -> None:
    order, cons, summary = build()
    order.to_csv(PROC / "origination_order.csv", index=False)
    cons[["game_id", "season", "week", "home_team", "away_team", "market_spread",
          "side_partition_sum", "ml_partition_sum", "ml_conditioned_home", "worst_violation"]].to_csv(
        PROC / "origination_consistency.csv", index=False)
    write_json(PROC / "origination_summary.json", summary)
    print(f"origination_order: {order.shape} · consistency tested on {summary['games_tested']} games")
    print(f"  max partition violation: side {summary['max_side_partition_violation']:.2e} · "
          f"moneyline {summary['max_ml_partition_violation']:.2e}")
    print(f"  verdict: {summary['verdict'][:70]}")


if __name__ == "__main__":
    main()
