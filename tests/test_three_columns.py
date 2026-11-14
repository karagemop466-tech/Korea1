"""Fail-closed tests for R7-03 (origination order) and R7-04 (three columns)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import origination_order as oo  # noqa: E402
import three_columns as tc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"


@pytest.fixture(scope="module")
def cols():
    return pd.read_csv(PROC / "three_columns.csv")


def test_side_total_moneyline_is_the_published_order():
    assert tc.MARKET_ORDER == ["SIDE", "TOTAL", "MONEYLINE"]
    assert [r["market"] for r in oo.FIT_ORDER] == ["SIDE (spread)", "TOTAL", "MONEYLINE"]


def test_moneyline_is_derived_not_fitted():
    ml = [r for r in oo.FIT_ORDER if r["market"] == "MONEYLINE"][0]
    assert ml["role"].startswith("DERIVED")
    assert ml["fitted"].startswith("no")


def test_difference_is_exactly_fair_minus_market(cols):
    d = (cols.fair_line - cols.market_line - cols.difference).abs()
    d = d[np.isfinite(d)]
    assert d.max() < 1e-12


def test_a_row_without_a_market_line_has_no_difference(cols):
    no = cols[~cols.market_line_present]
    assert no.difference.isna().all()


def test_the_moneyline_market_column_is_a_probability_not_a_price(cols):
    ml = cols[cols.market == "MONEYLINE"].dropna(subset=["market_line"])
    assert ml.market_line.between(0, 1).all()
    assert ml.fair_line.between(0, 1).all()


def test_the_side_market_column_is_a_handicap_not_a_probability(cols):
    side = cols[cols.market == "SIDE"].dropna(subset=["market_line"])
    assert side.market_line.abs().max() > 1.5


def test_all_three_markets_come_from_one_distribution():
    order, cons, summary = oo.build()
    assert summary["verdict"].startswith("PASS")
    assert summary["max_side_partition_violation"] <= 1e-9
    assert summary["max_ml_partition_violation"] <= 1e-9


def test_consistency_test_would_catch_a_broken_distribution():
    """Mutate an input so the partition cannot sum to one, and assert it is caught."""
    pred = pd.read_csv(PROC / "originated_lines.csv").head(50).copy()
    pred.loc[pred.index[0], "p_home_ml"] = 0.9
    cons = oo._consistency(pred)
    assert cons.worst_violation.max() > 1e-6


def test_every_published_column_has_a_definition():
    market_columns = {(d["column"], d["market"]) for d in tc.DEFINITIONS}
    for market in tc.MARKET_ORDER:
        for col in ("fair_line", "market_line", "difference"):
            assert (col, market) in market_columns
