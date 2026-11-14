"""U2 (arena/fcba7eb5-korea1): the demotion gate sends a LIVE strategy back to PAPER.

No strategy is LIVE today, so the real register cannot show a demotion. These tests build
synthetic candidates and check that each trigger, on its own, demotes a LIVE strategy, that
an unevaluable trigger is a failure (fail-closed), and that a PAPER strategy is never demoted.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import demotion_register as dg  # noqa: E402

GATES = ["G1_data", "G2_leakage", "G3_power", "G4_significance", "G5_luck",
         "G6_economic", "G7_stability", "G8_redundancy"]


def gates_row(name: str, fail: str | None = None) -> dict:
    row = {"strategy": name}
    for g in GATES:
        row[g] = g != fail
    return row


def scoreboard_row(name: str, horizon: bool = True, f4: str = "PASS", f5: str = "PASS") -> dict:
    return dict(strategy=name, horizon_reached=str(horizon), F4_skill=f4, F5_economics=f5)


def registry_row(name: str, sha: str | None) -> dict:
    d = dict(strategy=name, first_freeze_seq=1, registered_utc="2026-11-12T13:26:48Z")
    if sha is not None:
        d["rule_sha256"] = sha
    return d


def one(gates_list, sb=None, reg=None, hashes=None, state=None) -> pd.Series:
    out = dg.evaluate(pd.DataFrame(gates_list),
                      pd.DataFrame(sb) if sb is not None else None,
                      pd.DataFrame(reg) if reg is not None else None,
                      live_hashes=hashes, live_state=state)
    return out.set_index("strategy").loc[gates_list[0]["strategy"]]


def healthy_live(name="LIVE_A", **kw):
    base = dict(
        gates_list=[gates_row(name)],
        sb=[scoreboard_row(name)],
        reg=[registry_row(name, "abc")],
        hashes={name: "abc"},
        state={name: dg.LIVE},
    )
    base.update(kw)
    return base


def test_real_register_has_no_live_strategy_and_no_demotion():
    gates = pd.read_csv(ROOT / "data" / "processed" / "strategy_gates.csv")
    sb = pd.read_csv(ROOT / "data" / "forward" / "scoreboard.csv")
    reg = pd.read_csv(ROOT / "data" / "forward" / "trial_registry.csv")
    out = dg.evaluate(gates, sb, reg, live_state=dg.read_live_state())
    assert len(out) == len(gates) == 18
    assert (out.current_status == dg.PAPER).all()
    assert not out.action.str.startswith("DEMOTE").any()
    assert dg.summary(out)["live_now"] == 0


def test_live_strategy_that_keeps_every_trigger_passing_stays_live():
    r = one(**healthy_live())
    assert r.next_status == dg.LIVE
    assert r.failing_triggers == "none"


def test_paper_strategy_is_never_demoted_even_when_gates_fail():
    r = one([gates_row("P", fail="G5_luck")], state={})
    assert r.current_status == dg.PAPER
    assert r.next_status == dg.PAPER
    assert not r.action.startswith("DEMOTE")


def test_D1_signal_gate_lost_demotes_a_live_strategy():
    kw = healthy_live("LIVE_A")
    kw["gates_list"] = [gates_row("LIVE_A", fail="G4_significance")]
    r = one(**kw)
    assert r.next_status == dg.PAPER
    assert "D1" in r.failing_triggers
    assert r.action.startswith("DEMOTE TO PAPER")


def test_D2_execution_gate_lost_demotes_a_live_strategy():
    kw = healthy_live("LIVE_A")
    kw["gates_list"] = [gates_row("LIVE_A", fail="G6_economic")]
    r = one(**kw)
    assert r.next_status == dg.PAPER
    assert "D2" in r.failing_triggers


def test_D3_forward_failure_at_horizon_demotes_a_live_strategy():
    kw = healthy_live("LIVE_A")
    kw["sb"] = [scoreboard_row("LIVE_A", horizon=True, f4="FAIL")]
    r = one(**kw)
    assert r.next_status == dg.PAPER
    assert "D3" in r.failing_triggers


def test_D3_before_horizon_is_not_due_and_does_not_demote():
    kw = healthy_live("LIVE_A")
    kw["sb"] = [scoreboard_row("LIVE_A", horizon=False, f4="NOT EVALUATED", f5="NOT EVALUATED")]
    r = one(**kw)
    assert r.D3_forward_record == dg.NOT_DUE
    assert r.next_status == dg.LIVE


def test_D3_horizon_reached_but_forward_not_evaluated_is_a_failure():
    kw = healthy_live("LIVE_A")
    kw["sb"] = [scoreboard_row("LIVE_A", horizon=True, f4="NOT EVALUATED", f5="NOT EVALUATED")]
    r = one(**kw)
    assert r.next_status == dg.PAPER


def test_D4_breach_demotes_a_live_strategy():
    kw = healthy_live("LIVE_A")
    kw["hashes"] = {"LIVE_A": "different"}
    r = one(**kw)
    assert r.D4_preregistration == dg.FAIL
    assert r.next_status == dg.PAPER


def test_D4_unevaluable_is_a_failure_for_a_live_strategy_fail_closed():
    kw = healthy_live("LIVE_A")
    kw["reg"] = [registry_row("LIVE_A", None)]          # no rule hash at freeze
    kw["hashes"] = {}
    r = one(**kw)
    assert r.D4_preregistration == dg.NOT_EVAL
    assert r.next_status == dg.PAPER


def test_nothing_is_eligible_while_D4_cannot_be_evaluated():
    r = one([gates_row("CAND")], sb=[scoreboard_row("CAND", horizon=False, f4="NOT EVALUATED")],
            reg=[registry_row("CAND", None)], state={})
    assert not r.action.startswith("ELIGIBLE")


def test_candidate_with_all_gates_and_clean_triggers_is_listed_for_review_not_promoted():
    r = one([gates_row("CAND")], sb=[scoreboard_row("CAND", horizon=False, f4="NOT EVALUATED")],
            reg=[registry_row("CAND", "h")], hashes={"CAND": "h"}, state={})
    assert r.action.startswith("ELIGIBLE")
    assert r.next_status == dg.PAPER                    # promotion is an owner decision
