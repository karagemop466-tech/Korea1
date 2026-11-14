"""Fail-closed tests for R7-08 (demotion gate)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import demotion_gate as dg  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"


@pytest.fixture(scope="module")
def gate():
    return pd.read_csv(PROC / "demotion_gate.csv")


def test_rules_are_pre_registered_with_a_date():
    assert dg.REGISTERED_UTC.endswith("Z")
    assert dg.REGISTERED_UTC.startswith("2026-11-14")


def test_no_strategy_is_live_while_no_authenticated_price_exists(gate):
    """P4 needs a bootstrap bound over authenticated prices. There are none."""
    assert gate.state.ne("LIVE").all()


def test_every_strategy_has_a_recorded_state_and_reason(gate):
    assert gate.state.notna().all()
    assert gate.promotion_failures.notna().all()
    assert gate.triggers.notna().all()
    dem = gate[gate.state.str.startswith("DEMOTED")]
    assert len(dem) == len(gate)
    assert (dem.triggers != "none").all()


def test_demotion_beats_promotion():
    """A row that would promote but breaches a trigger must be demoted."""
    gate = pd.read_csv(PROC / "demotion_gate.csv")
    for r in gate.itertuples():
        fired = r.triggers != "none"
        if fired:
            assert r.state != "LIVE", f"{r.strategy} promoted while a trigger fired"


def test_the_staking_trigger_matches_the_signal_module():
    gate = pd.read_csv(PROC / "demotion_gate.csv")
    debt = pd.read_csv(PROC / "signal_staking.csv")
    m = gate.merge(debt[["strategy", "sign_flips_with_staking"]], on="strategy")
    assert len(m) == len(gate)
    flips = m[m.sign_flips_with_staking_y.fillna(False)]
    assert flips.triggers.str.contains("D6").all()
    noflip = m[~m.sign_flips_with_staking_y.fillna(False)]
    assert not noflip.triggers.str.contains("D6").any()


def test_signal_trigger_fires_only_below_the_floor():
    gate = pd.read_csv(PROC / "demotion_gate.csv")
    fired = gate[gate.triggers.str.contains("D5")]
    for r in fired.itertuples():
        assert r.signal_z < dg.TH["DEMOTE_SIGNAL_Z_FLOOR"]
    notfired = gate[~gate.triggers.str.contains("D5") & gate.signal_z.notna()]
    assert (notfired.signal_z >= dg.TH["DEMOTE_SIGNAL_Z_FLOOR"]).all()


def test_thresholds_are_not_mutable_at_runtime():
    """The gate reads module constants; a caller cannot pass a softer threshold."""
    import inspect
    sig = inspect.signature(dg.evaluate)
    assert len(sig.parameters) == 0
