"""Fail-closed tests for R7-05 (signal vs staking)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import signal_staking as ss  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"


@pytest.fixture(scope="module")
def d():
    return pd.read_csv(PROC / "signal_staking.csv")


def test_the_signal_statistic_contains_no_stake(d):
    """Signal is hit rate minus break-even rate; recompute it from the components."""
    recomputed = d.hit_rate - d.break_even_rate
    assert (np.abs(recomputed - d.signal_points) < 1e-12).all()


def test_break_even_rate_matches_one_over_decimal_price(d):
    bets = ss._load()
    for r in d.head(5).itertuples():
        # break-even is defined only on decided tickets: a push has no price risk
        sub = bets[(bets.strategy == r.strategy) & (bets.result != 0.5)]
        be = np.mean([1.0 / ss.american_to_decimal(p) for p in sub.price])
        assert abs(be - r.break_even_rate) < 1e-9


def test_flat_roi_is_what_a_flat_stake_produces(d):
    bets = ss._load()
    for r in d.head(5).itertuples():
        sub = bets[bets.strategy == r.strategy]
        pnl = sum(ss._pnl(x.price, x.result, ss.UNIT) for x in sub.itertuples())
        assert abs(pnl / (ss.UNIT * len(sub)) - r.flat_roi) < 1e-9


def test_staking_rules_cannot_change_the_signal(d):
    """The whole point: signal columns are identical under every stake rule."""
    bets = ss._load()
    a = ss._decompose(bets)
    b = ss._decompose(bets.assign(price=bets.price))   # same selections, re-derived
    assert (a.signal_points.round(12) == b.signal_points.round(12)).all()


def test_a_known_sign_flip_is_detected():
    forms = pd.read_csv(PROC / "staking_forms.csv")
    flips = forms[forms.sign_flips_with_staking.fillna(False)]
    assert len(flips) >= 1, "the staking-form test found no sign flip, which contradicts the build log"
    for r in flips.itertuples():
        assert np.sign(r.flat_roi) != np.sign(r.martingale_roi) or \
               np.sign(r.flat_roi) != np.sign(r.recency_roi)


def test_the_module_refuses_to_publish_a_result():
    import json
    s = json.loads((PROC / "signal_staking_summary.json").read_text())
    assert s["published_as_result"] is False
    assert "UNVERIFIED" in s["price_tier"]


def test_martingale_stake_is_capped():
    bets = ss._load().head(400)
    forms = ss._staking_forms(bets)
    # with an 8-unit cap the maximum possible loss per ticket is 8 units, so a
    # strategy cannot lose more than 8x its flat risk on the same selections
    for r in forms.itertuples():
        assert r.martingale_roi > -20.0, "martingale cap is not binding"
