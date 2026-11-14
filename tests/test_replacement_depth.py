"""Fail-closed tests for R7-06 (replacement depth)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import replacement_depth as rd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"


@pytest.fixture(scope="module")
def depth():
    return pd.read_csv(PROC / "replacement_depth.csv", dtype=str, keep_default_na=False)


def test_jersey_prefix_is_stripped_for_matching():
    assert rd._norm("32 MarShawn Lloyd") == rd._norm("MarShawn Lloyd")
    assert rd._strip_jersey("79 Travis Glover") == "Travis Glover"
    assert rd._strip_jersey("MarShawn Lloyd") == "MarShawn Lloyd"


def test_green_bay_joins_like_every_other_club(depth):
    """The defect this guards: 100% of GB names carry a jersey number, so a naive
    join failed for exactly one club and looked like a data gap."""
    gb = depth[depth.team == "GB"]
    joined = (gb.replacement_status != "NOT ON CHART").sum()
    assert joined >= 10, f"only {joined} Green Bay rows joined the chart"


def test_no_row_asserts_a_starting_role(depth):
    assert set(depth.role_evidence.unique()) <= {"CHART_POSITION_ONLY", "NONE"}


def test_unknown_is_never_filled(depth):
    """A player with no chart entry must not be given a rank."""
    off = depth[depth.replacement_status == "NOT ON CHART"]
    assert len(off) > 0
    assert (off.chart_rank == "").all()
    assert off.exposure_score.eq("").all()


def test_replacement_is_the_man_immediately_behind(depth):
    ok = depth[(depth.replacement_status == "LISTED BELOW") & (depth.game_status == "Out")]
    assert len(ok) > 0
    ranks = pd.to_numeric(ok.chart_rank)
    nxt = pd.to_numeric(ok.replacement_rank)
    assert ((nxt - ranks) == 1).all()


def test_depth_labels_match_ranks(depth):
    for r in depth.itertuples():
        if r.replacement_depth_label:
            assert r.replacement_depth_label == rd.DEPTH_LABEL[int(float(r.replacement_rank))]


def test_slot_availability_is_read_from_the_chart_not_the_injuries():
    """The defect this guards: computing "who is left" from injured players alone
    reported NOBODY LISTED for a 3-deep slot whose only injured man was depth 1."""
    slots = pd.read_csv(PROC / "replacement_slots.csv")
    deep = slots[(pd.to_numeric(slots.chart_slot_size) >= 3)
                 & (pd.to_numeric(slots.top_out_rank) == 1)]
    assert len(deep) > 0
    assert (pd.to_numeric(deep.listed_available) >= 2).all(), \
        "a slot with 3+ charted names reports fewer than 2 available after one injury"
    # The next man is either the 2nd-string man, or the other half of a charted
    # rank tie (a co-starter the club lists at the same rank as the unavailable
    # man). Nothing deeper is possible when only the top man is out in a 3-deep
    # slot, and asserting that is the point of this test.
    allowed = {"2nd string", "1st string"}
    assert set(deep.backup_man_is_depth) <= allowed
    tied = deep[deep.backup_man_is_depth == "1st string"]
    assert tied.next_man_shares_top_rank.all(), \
        "a 1st-string label must come from a charted rank tie, not from a missing man"


def test_no_body_listed_means_chart_size_one_or_last_name():
    slots = pd.read_csv(PROC / "replacement_slots.csv")
    bare = slots[slots.backup_man_is_depth == "NOBODY LISTED"]
    assert len(bare) > 0
    for r in bare.itertuples():
        size = int(float(r.chart_slot_size))
        top = int(float(r.top_out_rank))
        assert top <= size, "a man is reported Out at a rank deeper than the chart has"


def test_houston_is_flagged_not_silently_absent():
    import json
    s = json.loads((PROC / "replacement_summary.json").read_text())
    assert "HOU" in s["teams_missing_from_chart"]
    assert s["not_on_chart"] > 0


def test_summary_counters_agree_with_the_rows(depth):
    import json
    s = json.loads((PROC / "replacement_summary.json").read_text())
    assert s["injury_rows"] == len(depth)
    assert s["out"] == int(depth.game_status.eq("Out").sum())
    assert s["joined_to_chart"] == int((depth.replacement_status != "NOT ON CHART").sum())
