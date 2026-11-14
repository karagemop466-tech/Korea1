"""Fail-closed tests for R7-07 (official-source correlations)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import official_correlations as oc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"


@pytest.fixture(scope="module")
def table():
    return pd.read_csv(PROC / "official_correlations.csv")


def test_no_value_is_published_without_an_n(table):
    computed = table[table.status.str.startswith("COMPUTED")]
    assert len(computed) > 0
    assert (computed.n >= oc.MIN_N).all()


def test_no_value_is_published_without_an_interval(table):
    computed = table[table.status.str.startswith("COMPUTED")]
    assert computed.ci_lo.notna().all() and computed.ci_hi.notna().all()
    assert (computed.ci_lo <= computed.pearson_r).all()
    assert (computed.pearson_r <= computed.ci_hi).all()


def test_a_blank_row_carries_no_number(table):
    blank = table[table.status.str.startswith("BLANK")]
    assert len(blank) > 0
    assert blank.pearson_r.isna().all()
    assert blank.n.eq(0).all()


def test_every_row_states_why_it_is_blank_or_computed(table):
    assert table.note.notna().all()
    assert (table.note.str.len() > 20).all()


def test_inputs_are_official_scores_only():
    inp = pd.read_csv(PROC / "official_corr_inputs.csv")
    feed = pd.read_csv(ROOT / "data" / "results" / "results_feed.csv")
    ok = feed[feed.settleable == "YES"]
    assert len(inp) == len(ok)
    assert set(inp.game_id) == set(ok.game_id)
    assert inp.page_url.str.contains("nfl.com").all()


def test_margin_and_total_are_arithmetic_on_the_two_scores():
    inp = pd.read_csv(PROC / "official_corr_inputs.csv")
    assert ((inp.official_margin - (inp.home_score - inp.away_score)).abs() < 1e-9).all()
    assert ((inp.official_total - (inp.home_score + inp.away_score)).abs() < 1e-9).all()


def test_a_prop_or_parlay_pair_is_refused_not_approximated(table):
    for pair in table.pair:
        if "parlay" in pair.lower() or "receiver" in pair.lower() or "QB" in pair:
            row = table[table.pair == pair].iloc[0]
            assert row.pearson_r != row.pearson_r  # NaN
            assert row.status.startswith("BLANK")


def test_fisher_interval_is_monotone_in_n():
    lo1, hi1 = oc._fisher_ci(0.3, 20)
    lo2, hi2 = oc._fisher_ci(0.3, 200)
    assert (hi2 - lo2) < (hi1 - lo1)
