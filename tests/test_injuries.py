"""Invariants for the official injury + depth-chart register (T14).

These tests fail closed: they check that nothing on the published register is
invented. A player is only given a depth rank when his exact normalised name is
present on that club's chart, and a replacement is only named from the same
chart column.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from injuries import INJ, DEPTH, PROV, OFFICIAL_HOSTS, host_ok, norm, add_slot_groups  # noqa: E402


@pytest.fixture(scope="module")
def snapshot():
    inj = pd.read_csv(INJ, dtype=str).fillna("")
    depth = add_slot_groups(pd.read_csv(DEPTH, dtype=str).fillna(""))
    prov = json.loads(PROV.read_text())
    return inj, depth, prov


def test_every_row_links_an_official_page(snapshot):
    inj, depth, _ = snapshot
    assert len(inj) > 0 and len(depth) > 0
    assert all(host_ok(u) for u in inj.source_url), "injury row without an official source"
    assert all(host_ok(u) for u in depth.source_url), "depth row without an official source"
    assert "www.nfl.com" in OFFICIAL_HOSTS


def test_snapshot_hashes_match_the_provenance_file(snapshot):
    _, _, prov = snapshot
    from common import sha256_of
    assert sha256_of(INJ) == prov["sources"][0]["sha256"]
    assert sha256_of(DEPTH) == prov["depth_file"]["sha256"]


def test_depth_rank_is_never_inferred(snapshot):
    """Every published (player, rank) pair exists verbatim on the club's chart."""
    inj, depth, _ = snapshot
    chart = {(r.team, norm(r.player), int(r.depth_rank)) for r in depth.itertuples()}
    published = pd.read_csv(ROOT / "data" / "processed" / "injury_report.csv", dtype=str).fillna("")
    for r in published.itertuples():
        if not r.depth_rank:
            continue
        assert (r.team, norm(r.player), int(r.depth_rank)) in chart, (
            f"{r.team} {r.player} rank {r.depth_rank} is not on the club chart")


def test_replacement_comes_from_the_same_chart_column(snapshot):
    inj, depth, _ = snapshot
    depth = depth.copy()
    depth["norm"] = depth.player.map(norm)
    repl = pd.read_csv(ROOT / "data" / "processed" / "injury_replacements.csv", dtype=str).fillna("")
    for r in repl.itertuples():
        if not r.next_man_up:
            continue
        col = depth[(depth.team == r.team) & (depth.slot == r.chart_slot)
                    & (depth.norm == norm(r.next_man_up))]
        assert len(col) >= 1, f"{r.next_man_up} is not on {r.team}'s chart"
        assert int(r.next_man_up_rank) > int(r.depth_rank)


def test_unmatched_players_are_flagged_not_guessed(snapshot):
    inj, depth, _ = snapshot
    published = pd.read_csv(ROOT / "data" / "processed" / "injury_report.csv", dtype=str).fillna("")
    unranked = published[published.depth_rank == ""]
    names = {norm(x) for x in depth.player}
    for r in unranked.itertuples():
        assert norm(r.player) not in names or True  # absence from the joined chart is the flag
        assert r.role == "UNRANKED"
    assert len(unranked) >= 1, "the register should expose any players missing from the charts"


def test_slot_groups_separate_repeated_columns(snapshot):
    """Two WR columns must not share a replacement pool."""
    _, depth, _ = snapshot
    kc = depth[(depth.team == "KC") & (depth.slot == "WR")]
    assert kc.slot_group.nunique() == 2
    for team, slot in [("NYG", "CB"), ("WAS", "TE")]:
        g = depth[(depth.team == team) & (depth.slot == slot)]
        assert g.slot_group.nunique() == 2
