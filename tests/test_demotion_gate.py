"""Tests for pipeline/demotion_gate.py (added 2026-11-14, arena/b400d3ae-korea1)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import demotion_gate as dg  # noqa: E402


def _ledger(n=120, seasons=3, pnl_mean=0.0, stress_shift=-0.05, seed=7, clv=None):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        pnl = float(rng.choice([0.909, -1.0], p=[0.5, 0.5])) + pnl_mean
        rows.append(dict(status="OFFICIAL", outcome=1.0 if pnl > 0 else 0.0, pnl=pnl,
                         pnl_stress=pnl + stress_shift, season=2023 + (i % seasons),
                         week=1 + (i // seasons) % 18, freeze_before_kickoff=True,
                         **({"clv": clv} if clv is not None else {})))
    return pd.DataFrame(rows)


def test_requires_columns():
    try:
        dg.evaluate(pd.DataFrame({"status": []}))
    except ValueError as e:
        assert "missing required columns" in str(e)
    else:
        raise AssertionError("missing columns must raise, not be imputed")


def test_small_sample_is_insufficient_not_pass():
    r = dg.evaluate(_ledger(n=40, seasons=3))
    assert r["verdict"] == dg.INSUFFICIENT
    assert r["state_recommendation"] == "NO CHANGE"


def test_look_ahead_demotes_immediately_even_on_small_sample():
    led = _ledger(n=10)
    led.loc[3, "freeze_before_kickoff"] = False
    r = dg.evaluate(led)
    assert r["verdict"] == dg.DEMOTE
    assert r["triggers"][0]["rule"] == "DG1"


def test_settled_row_without_outcome_demotes_and_is_not_filled():
    led = _ledger(n=10)
    led.loc[2, "outcome"] = np.nan
    r = dg.evaluate(led)
    assert r["verdict"] == dg.DEMOTE
    assert any(t["rule"] == "DG2" for t in r["triggers"])


def test_losing_strategy_with_enough_sample_is_demoted_to_paper():
    r = dg.evaluate(_ledger(n=150, seasons=3, pnl_mean=-0.30))
    assert r["verdict"] == dg.DEMOTE
    assert r["state_recommendation"] == "PAPER"
    assert {t["rule"] for t in r["triggers"]} & {"DG4", "DG5"}


def test_clear_winner_passes_and_is_not_demoted():
    r = dg.evaluate(_ledger(n=300, seasons=3, pnl_mean=0.25, stress_shift=0.0), n_boot=2000)
    assert r["verdict"] == dg.PASS
    assert r["state_recommendation"] == "LIVE"


def test_negative_clv_demotes_when_fully_covered():
    r = dg.evaluate(_ledger(n=150, seasons=3, pnl_mean=0.25, stress_shift=0.0, clv=-0.5),
                    n_boot=2000)
    assert r["verdict"] == dg.DEMOTE
    assert any(t["rule"] == "DG6" for t in r["triggers"])


def test_partial_clv_coverage_does_not_trigger_dg6():
    led = _ledger(n=150, seasons=3, pnl_mean=0.25, stress_shift=0.0, clv=-0.5)
    led["clv"] = led["clv"].astype(object)
    led.loc[0, "clv"] = np.nan
    r = dg.evaluate(led, n_boot=2000)
    assert not any(t["rule"] == "DG6" for t in r["triggers"])


def test_drawdown_only_applies_when_owner_sets_a_limit():
    led = _ledger(n=150, seasons=3, pnl_mean=0.25, stress_shift=0.0)
    assert not any(t["rule"] == "DRAWDOWN" for t in dg.evaluate(led, n_boot=2000)["triggers"])
    r = dg.evaluate(led, max_drawdown_units=0.5, n_boot=2000)
    assert any(t["rule"] == "DRAWDOWN" for t in r["triggers"])
