"""Fail-closed tests for the R7-01 price-snapshot store."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import price_snapshots as ps  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "data" / "prices" / "price_snapshots.csv"


@pytest.fixture(scope="module")
def snap():
    return pd.read_csv(SNAP, low_memory=False)


def test_snapshot_kind_vocabulary_is_closed(snap):
    """A kind that is not in the fixed vocabulary must never reach the store."""
    assert set(snap.snapshot_kind.unique()) <= set(ps.KINDS)


def test_no_row_claims_a_capture_time(snap):
    """No source in the pin carries a timestamp, so no row may claim one."""
    assert not snap.capture_time_known.any()
    assert snap.captured_utc.isna().all()


def test_undated_is_never_described_as_open_or_close(snap):
    """The games.csv instrument must stay UNDATED whatever the column means."""
    und = snap[snap.source_key == "games_csv"]
    assert len(und) > 0
    assert set(und.snapshot_kind.unique()) == {ps.UNDATED}


def test_initial_only_covers_the_season_the_file_states(snap):
    ini = snap[snap.snapshot_kind == ps.INITIAL]
    assert set(ini.season.unique()) == {2021}
    assert set(ini.book.unique()) == {"WSGT"}


def test_closing_covers_only_the_seasons_the_file_covers(snap):
    clo = snap[snap.snapshot_kind == ps.CLOSING]
    assert clo.season.min() == 2006 and clo.season.max() == 2018


def test_no_game_carries_two_named_kinds(snap):
    """If an opener and a closer ever overlap, the movement column becomes live
    and this test must be updated deliberately rather than silently passing."""
    g = snap[snap.snapshot_kind.isin([ps.INITIAL, ps.CLOSING])]
    both = (g.groupby("game_id").snapshot_kind.nunique() > 1).sum()
    assert both == 0, ("a game now carries both an INITIAL and a CLOSING print; "
                       "the movement restriction in price_snapshots.coverage() must be revisited")


def test_every_row_names_a_source_url(snap):
    assert snap.source_url.notna().all()
    assert snap.source_url.str.startswith("https://").all()


def test_provenance_flags_undocumented_columns():
    import json
    prov = json.loads((ROOT / "data" / "prices" / "price_provenance.json").read_text())
    games = prov["sources"]["games_csv"]
    assert games["claims_kind"] == ps.UNDATED
    assert games["timestamp_field"] is None
    assert games["documented_columns"] == []


def test_side_sign_convention_is_the_home_handicap(snap):
    """spread_line is positive when HOME is favoured (DATASETS.md); the stored
    HOME line must therefore be its negation."""
    g = pd.read_csv(ROOT / "data" / "raw" / "games.csv", low_memory=False)
    g = g[g.spread_line.notna()].head(50)
    home = snap[(snap.market == "SPREAD") & (snap.side == "HOME") & (snap.snapshot_kind == ps.UNDATED)]
    m = g[["game_id", "spread_line"]].merge(home[["game_id", "line"]], on="game_id")
    assert len(m) > 0
    assert ((m.line + m.spread_line).abs() < 1e-9).all()
