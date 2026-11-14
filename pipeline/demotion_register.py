"""U2 (session arena/fcba7eb5-korea1) — the demotion gate.

The brief asks for a rule that sends a *live* strategy back to paper. This module
defines that rule, evaluates it on every run, and writes the result as a register.
It is deliberately a pure function of its inputs so the rule can be tested with
synthetic live strategies (see tests/test_demotion_register.py) even though, today,
no strategy is live.

Definitions
-----------
PAPER  the default state. Every candidate starts here. Paper results are published,
       including failures, but earn no tier and carry no live status.
LIVE   a recorded state in data/governance/live_status.csv. A candidate reaches LIVE
       only by an explicit, recorded promotion, and only when all eight fail-closed
       gates in data/processed/strategy_gates.csv pass and no trigger is failing (the
       gate set of reward tier T4 in pipeline/session_competition.py). LIVE is a state
       that persists between runs; re-evaluation can take it away. It is not recomputed
       from today's gates, because that would make the demotion triggers unreachable.
ELIGIBLE  a PAPER candidate whose gates and triggers would allow promotion. It is listed,
       never promoted automatically: promotion needs an owner decision.

Demotion triggers (any one sends a LIVE strategy to PAPER)
----------------------------------------------------------
D1  Signal gate lost   Any of G2, G3, G4, G5, G7, G8 fails on re-evaluation.
D2  Execution gate lost  G1 (authenticated, timestamped quote) or G6 (ROI at or above
                       the configured floor and positive adverse-price stress) fails.
D3  Forward record     Once the F3 horizon is reached (150 counted single picks or 60
                       parlay tickets, over 30 weeks), F4 skill or F5 economics must
                       PASS. Before the horizon the trigger is NOT DUE: no interim
                       verdict is ever issued (ledger gate F3).
D4  Pre-registration   The strategy's frozen rule hash must match the hash recorded at
                       first freeze (rules R1 and R3). A missing hash is NOT EVALUATED.

Fail-closed rule: for a LIVE strategy, a trigger that is NOT EVALUATED counts as a
failure. A live status that cannot be re-checked is not kept. For promotion, a trigger
that is NOT EVALUATED also blocks eligibility.

Outputs
-------
  data/governance/demotion_register.csv   one row per strategy, every trigger shown
  competition.html                    section "Demotion gate", rendered by session_competition.py

Run:  python pipeline/demotion_register.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parent
PROC = ROOT / "data" / "processed"
FWD = ROOT / "data" / "forward"
GOV = ROOT / "data" / "governance"

SIGNAL_GATES = ["G2_leakage", "G3_power", "G4_significance", "G5_luck", "G7_stability", "G8_redundancy"]
EXEC_GATES = ["G1_data", "G6_economic"]
ALL_GATES = SIGNAL_GATES + EXEC_GATES

PAPER = "PAPER"
LIVE = "LIVE"

PASS, FAIL, NOT_DUE, NOT_EVAL = "PASS", "FAIL", "NOT DUE", "NOT EVALUATED"

TRIGGERS = [
    ("D1", "Signal gate lost",
     "Any of G2 leakage, G3 power, G4 significance, G5 luck, G7 stability or G8 redundancy fails on re-evaluation."),
    ("D2", "Execution gate lost",
     "G1 authenticated quote provenance or G6 economic reality (ROI floor and positive adverse-price stress) fails."),
    ("D3", "Forward record failed at horizon",
     "After the F3 horizon (150 single picks or 60 parlay tickets, over 30 weeks), F4 skill and F5 economics must both PASS. "
     "Before the horizon the trigger is NOT DUE and no interim verdict is issued."),
    ("D4", "Pre-registration breach",
     "The rule hash recorded at first freeze must still match the rule being run (rules R1, R3). Without a recorded hash the trigger is NOT EVALUATED."),
]


def forward_trigger(row: pd.Series | None) -> str:
    """D3 from one row of the forward scoreboard (or None when the strategy has no record)."""
    if row is None:
        return NOT_EVAL
    if str(row.get("horizon_reached", "")).strip().lower() not in ("true", "1", "yes"):
        return NOT_DUE
    f4, f5 = str(row.get("F4_skill", "")).strip(), str(row.get("F5_economics", "")).strip()
    return PASS if (f4 == PASS and f5 == PASS) else FAIL


def preregistration_trigger(row: pd.Series | None, live_hash: str | None) -> str:
    """D4. The trial registry must hold `rule_sha256` at first freeze; none does today."""
    if row is None or "rule_sha256" not in row.index or not str(row.get("rule_sha256", "")).strip():
        return NOT_EVAL
    if live_hash is None:
        return NOT_EVAL
    return PASS if str(row["rule_sha256"]).strip() == live_hash else FAIL


def all_gates_pass(gate_row: pd.Series) -> bool:
    return all(bool(gate_row[g]) for g in ALL_GATES)


def evaluate(gates: pd.DataFrame, scoreboard: pd.DataFrame | None = None,
             registry: pd.DataFrame | None = None, live_hashes: dict | None = None,
             live_state: dict | None = None) -> pd.DataFrame:
    """Pure evaluation. Frames are keyed by `strategy`; `live_state` maps strategy -> LIVE/PAPER
    as recorded in live_status.csv (absent = PAPER). No file I/O."""
    sb = {} if scoreboard is None or scoreboard.empty else \
        {r["strategy"]: r for r in scoreboard.to_dict("records")}
    rg = {} if registry is None or registry.empty else \
        {r["strategy"]: pd.Series(r) for r in registry.to_dict("records")}
    live_hashes = live_hashes or {}
    live_state = live_state or {}
    rows = []
    for _, g in gates.sort_values("strategy").iterrows():
        s = g["strategy"]
        recorded = live_state.get(s, PAPER)
        d1 = PASS if all(bool(g[x]) for x in SIGNAL_GATES) else FAIL
        d2 = PASS if all(bool(g[x]) for x in EXEC_GATES) else FAIL
        d3 = forward_trigger(pd.Series(sb[s]) if s in sb else None)
        d4 = preregistration_trigger(rg.get(s), live_hashes.get(s))
        results = {"D1": d1, "D2": d2, "D3": d3, "D4": d4}
        failing = [k for k, v in results.items() if v in (FAIL, NOT_EVAL)]
        if recorded == LIVE:
            if failing:
                nxt, action = PAPER, "DEMOTE TO PAPER: " + ", ".join(failing)
            else:
                nxt, action = LIVE, "Stays live: every trigger passes"
        else:
            ok_to_promote = all_gates_pass(g) and not failing
            if ok_to_promote:
                nxt, action = PAPER, "ELIGIBLE for promotion review (owner decision required)"
            else:
                nxt, action = PAPER, "Stays on paper: not live, nothing to demote"
        rows.append(dict(
            strategy=s, current_status=recorded,
            gates_passed_of_8=int(sum(bool(g[x]) for x in ALL_GATES)),
            D1_signal_gates=d1, D2_execution_gates=d2, D3_forward_record=d3, D4_preregistration=d4,
            failing_triggers="; ".join(failing) if failing else "none",
            next_status=nxt, action=action,
        ))
    return pd.DataFrame(rows)


def summary(reg: pd.DataFrame) -> dict:
    return dict(
        strategies=int(len(reg)),
        live_now=int((reg.current_status == LIVE).sum()),
        demoted=int(reg.action.str.startswith("DEMOTE").sum()),
        eligible=int(reg.action.str.startswith("ELIGIBLE").sum()),
    )


def read_live_state() -> dict:
    p = GOV / "live_status.csv"
    if not p.exists():
        return {}
    t = pd.read_csv(p, dtype=str, keep_default_na=False)
    return {r["strategy"]: r["status"] for r in t.to_dict("records") if r["status"]}


def main() -> None:
    gates = pd.read_csv(PROC / "strategy_gates.csv")
    sb = pd.read_csv(FWD / "scoreboard.csv") if (FWD / "scoreboard.csv").exists() else None
    reg = pd.read_csv(FWD / "trial_registry.csv") if (FWD / "trial_registry.csv").exists() else None
    out = evaluate(gates, sb, reg, live_state=read_live_state())
    GOV.mkdir(parents=True, exist_ok=True)
    out.to_csv(GOV / "demotion_register.csv", index=False)
    s = summary(out)
    print(f"  demotion_register.csv {s['strategies']} strategies · live {s['live_now']} · "
          f"demoted this run {s['demoted']} · eligible for review {s['eligible']}")


if __name__ == "__main__":
    main()
