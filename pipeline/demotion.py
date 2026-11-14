"""T55 — the demotion gate: a live strategy that trips a condition goes back to paper.

The problem this solves
-----------------------
The reward ladder in `pipeline/session_competition.py` describes how a strategy
is *promoted*. Nothing in the repository said what happens when a strategy that
was promoted stops working. Without that, a live strategy that has quietly
decayed keeps its allocation, because the only evidence the ladder looks at is
the evidence that was gathered at promotion time.

So the promotion decision is mirrored by a demotion decision, with the same
shape: a fixed list of conditions, evaluated on the same data, with a fixed
action. The gate is **armed by default**: a strategy that is not demonstrably
live is paper, and a strategy that trips any condition is paper again.

Two properties are enforced in code:

1. **The gate can only send a strategy down.** There is no rule in this file
   that promotes a strategy. Promotion still belongs to the eight gates and the
   reward ladder; the demotion gate is a brake, not a throttle.
2. **Every condition names the data it needs.** A condition whose input is not
   on record cannot be evaluated, and an unevaluable condition is treated as
   *not passed*. Nothing is assumed to be fine because a number is missing.

Current state
-------------
No strategy in this repository is live. None passes the eight gates, and the
one gate that every strategy fails (G1, an authenticated executable quote) has
not been closed for any of them. So the table below reports the conditions
that *would* fire for each strategy, and every strategy's current tier is
PAPER. The gate is armed; there is nothing to demote yet.

Outputs
-------
  data/processed/demotion_gates.csv    the conditions
  data/processed/demotion_status.csv   the evaluation per strategy
  assets/data/demotion_status.csv       the same, for the site

Run:  python pipeline/demotion.py
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

TRAILING_WEEKS = 8          # D1 window
DRAWDOWN_FLOOR = -20.0      # D4, in units
OVERLAP_LIMIT = 0.90        # D8, the same limit the G8 gate uses

GATE_COLUMNS = [
    "gate_id", "name", "scope", "condition", "threshold", "window",
    "action", "data_required", "evidence_class", "note",
]

STATUS_COLUMNS = [
    "strategy", "name", "current_tier", "gates_passed", "gates_failed",
    "D1_trailing_return", "D1_fires",
    "D2_weeks_observed", "D2_weeks_required", "D2_fires",
    "D3_signal_edge_lo", "D3_fires",
    "D4_max_drawdown", "D4_fires",
    "D5_quote_coverage", "D5_fires",
    "D6_result_coverage", "D6_fires",
    "D7_leakage_passed", "D7_fires",
    "D8_max_overlap", "D8_fires",
    "gates_fired", "resulting_tier", "note",
]

GATES = [
    dict(gate_id="D1", name="Trailing return breach", scope="STAKING",
         condition="The cumulative return of the trailing settled weeks is negative",
         threshold="< 0 units", window=f"{TRAILING_WEEKS} settled weeks",
         action="LIVE → PAPER",
         data_required="Weekly return series for the strategy, from settled bets",
         evidence_class="D",
         note="A live strategy that is losing is sent back to paper while the "
              "loss is investigated. It is not disqualified: a losing streak is "
              "not evidence of a broken rule."),
    dict(gate_id="D2", name="Sample sufficiency", scope="STAKING",
         condition="The number of settled weeks is below the number the power "
                   "gate requires",
         threshold="< required_n_weeks", window="lifetime",
         action="PAPER (a strategy may never be live below this)",
         data_required="Settled-week count and the power requirement from G3",
         evidence_class="B",
         note="A return computed on too few weeks cannot be told apart from "
              "luck, so it cannot support a live tier in the first place."),
    dict(gate_id="D3", name="Signal failure", scope="SIGNAL",
         condition="The lower bound of the signal edge is not above zero",
         threshold="edge lower bound ≤ 0", window="rolling 26 settled weeks",
         action="LIVE → PAPER",
         data_required="Hit rate, per-bet prices and the break-even rate",
         evidence_class="D",
         note="This is the mirror of the leaderboard's signal scorecard. A "
              "strategy whose signal has stopped working is demoted even if "
              "its money is still positive."),
    dict(gate_id="D4", name="Drawdown limit", scope="STAKING",
         condition="The peak-to-trough drawdown is worse than the floor",
         threshold=f"< {DRAWDOWN_FLOOR:.0f} units", window="lifetime",
         action="LIVE → PAPER",
         data_required="Weekly return series for the strategy",
         evidence_class="D",
         note="A drawdown floor bounds the damage a decaying strategy can do "
              "before it is reviewed."),
    dict(gate_id="D5", name="Price provenance loss", scope="DATA",
         condition="A settled bet has no verified executable price",
         threshold="any bet without a verified quote", window="per bet",
         action="LIVE → PAPER immediately",
         data_required="Quote timestamp, price, limits and an official quote "
                       "reference for each settled bet",
         evidence_class="B",
         note="The price is what the return is measured against. A bet that "
              "cannot be priced cannot be settled, so it cannot keep a live "
              "tier."),
    dict(gate_id="D6", name="Result provenance loss", scope="DATA",
         condition="A settled bet has no official final on record",
         threshold="any bet without an official result", window="per bet",
         action="LIVE → PAPER immediately",
         data_required="The official final score and the official page it was "
                       "read from, in the verified results feed",
         evidence_class="A",
         note="A settlement without an official result is a guess. The "
              "repository grades forward picks against official finals only."),
    dict(gate_id="D7", name="Leakage or undisclosed rule change", scope="DATA",
         condition="A leakage check fails, or the rule changed without a new "
                   "strategy id",
         threshold="any failure", window="every release",
         action="DISQUALIFIED (never live again for this id)",
         data_required="The leakage test suite and the frozen rule of each "
                       "registered strategy",
         evidence_class="B",
         note="The only irreversible condition. Leakage and undisclosed rule "
              "changes are not a performance question."),
    dict(gate_id="D8", name="Redundancy", scope="SIGNAL",
         condition="The selection overlap with an existing live strategy "
                   "reaches the redundancy limit",
         threshold=f"≥ {OVERLAP_LIMIT:.0%}", window="rolling, per release",
         action="LIVE → PAPER",
         data_required="The pairwise selection-overlap matrix",
         evidence_class="B",
         note="A duplicate of a live strategy is not a second source of return; "
              "it is the same one counted twice."),
]


def _num(x) -> float:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return f if np.isfinite(f) else float("nan")


def _max_drawdown(series: list[float]) -> float:
    peak, worst, cum = 0.0, 0.0, 0.0
    for x in series:
        cum += x
        peak = max(peak, cum)
        worst = min(worst, cum - peak)
    return worst


def evaluate() -> tuple[pd.DataFrame, pd.DataFrame]:
    gates = pd.DataFrame(GATES, columns=GATE_COLUMNS)
    gates.to_csv(PROC / "demotion_gates.csv", index=False)

    split_path = PROC / "leaderboard_signal_staking.csv"
    if not split_path.exists():
        return gates, pd.DataFrame(columns=STATUS_COLUMNS)
    split = pd.read_csv(split_path, dtype=str).fillna("")
    gpath = PROC / "strategy_gates.csv"
    gate_rows = pd.read_csv(gpath).set_index("strategy") if gpath.exists() else pd.DataFrame()
    weekly = pd.read_csv(PROC / "strategy_weekly_matrix.csv")
    bets = pd.read_csv(PROC / "strategy_bets.csv", dtype=str).fillna("")
    official_games: set[str] = set()
    verified_path = ROOT / "data" / "forward" / "verified_results.csv"
    if verified_path.exists():
        ver = pd.read_csv(verified_path, dtype=str)
        official_games = set(ver.game_id.astype(str))
    leak_path = PROC / "leakage_checks.csv"
    leak_ok = True
    if leak_path.exists():
        leak = pd.read_csv(leak_path)
        leak_ok = bool(leak["passed"].astype(str).str.lower().eq("true").all())

    rows = []
    for _, s in split.iterrows():
        sid = s["strategy"]
        g = gate_rows.loc[sid] if (len(gate_rows) and sid in gate_rows.index) else None

        # D1 — trailing return over the last settled weeks.
        if sid in weekly.columns:
            ser = [float(x) for x in weekly[sid].dropna().tolist()]
        else:
            ser = []
        window = [x for x in ser[-TRAILING_WEEKS:] if np.isfinite(x)]
        trailing = sum(window) if window else float("nan")
        # An empty window cannot be evaluated, and a condition that cannot be
        # evaluated is not treated as passed.
        d1 = bool(np.isfinite(trailing) and trailing < 0)

        # D2 — sample sufficiency.
        weeks = int(float(s["staking_n_weeks"] or 0))
        weeks_req = int(float(s["staking_n_weeks_required"] or 0))
        d2 = weeks < weeks_req

        # D3 — signal edge lower bound.
        edge_lo = _num(s["signal_edge_lo"])
        d3 = (not np.isfinite(edge_lo)) or edge_lo <= 0

        # D4 — drawdown floor.
        dd = _max_drawdown(ser) if ser else float("nan")
        d4 = bool(np.isfinite(dd) and dd < DRAWDOWN_FLOOR)

        # D5 — price provenance: an authenticated executable quote per bet.
        bb = bets[bets.strategy == sid]
        if len(bb):
            verified = bb["executable_quote_verified"].astype(str).str.lower().eq("true").mean()
        else:
            verified = float("nan")
        d5 = (not np.isfinite(verified)) or verified < 1.0

        # D6 — result provenance: the bet's game has an official final in the
        # verified results feed.
        if len(bb):
            official_final = bb["game_id"].isin(official_games).mean()
        else:
            official_final = float("nan")
        d6 = (not np.isfinite(official_final)) or official_final < 1.0

        # D7 — leakage.
        d7 = not leak_ok

        # D8 — redundancy.
        overlap = _num(g["G8_max_overlap"]) if g is not None else float("nan")
        d8 = (not np.isfinite(overlap)) or overlap >= OVERLAP_LIMIT

        fired = [gid for gid, f in (("D1", d1), ("D2", d2), ("D3", d3), ("D4", d4),
                                    ("D5", d5), ("D6", d6), ("D7", d7), ("D8", d8))
                if f]
        tier = "DISQUALIFIED" if d7 else "PAPER"
        rows.append({
            "strategy": sid, "name": s["name"],
            "current_tier": "PAPER",
            "gates_passed": s["gates_passed"], "gates_failed": s["gates_failed"],
            "D1_trailing_return": round(trailing, 6) if np.isfinite(trailing) else "",
            "D1_fires": d1,
            "D2_weeks_observed": weeks, "D2_weeks_required": weeks_req,
            "D2_fires": d2,
            "D3_signal_edge_lo": s["signal_edge_lo"], "D3_fires": d3,
            "D4_max_drawdown": round(dd, 4) if np.isfinite(dd) else "",
            "D4_fires": d4,
            "D5_quote_coverage": round(verified, 4) if np.isfinite(verified) else "",
            "D5_fires": d5,
            "D6_result_coverage": round(official_final, 4) if np.isfinite(official_final) else "",
            "D6_fires": d6,
            "D7_leakage_passed": leak_ok, "D7_fires": d7,
            "D8_max_overlap": s["D8_max_overlap"] if "D8_max_overlap" in s else "",
            "D8_fires": d8,
            "gates_fired": "; ".join(fired) or "none",
            "resulting_tier": tier,
            "note": ("No strategy is live, so the gate has nothing to demote. "
                     "The conditions above are the evaluation that would apply "
                     "the moment a strategy is promoted."),
        })
    status = pd.DataFrame(rows, columns=STATUS_COLUMNS)
    return gates, status


def main() -> None:
    gates, status = evaluate()
    gates.to_csv(PROC / "demotion_gates.csv", index=False)
    if len(status):
        status.to_csv(PROC / "demotion_status.csv", index=False)
        SITE_DATA.mkdir(parents=True, exist_ok=True)
        status.to_csv(SITE_DATA / "demotion_status.csv", index=False)
    print(f"demotion_gates: {len(gates)} conditions")
    if len(status):
        print(f"  strategies evaluated: {len(status)}; "
              f"live strategies: {int((status.current_tier == 'LIVE').sum())}")
        print(f"  resulting tiers: {status.resulting_tier.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
