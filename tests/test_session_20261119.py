"""db0e98e2 (2026-11-19): the live reserve-page read must equal the 2026-11-19 capture, and the
new flag rows must cite an official NFL.com page."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import session_20261119 as s  # noqa: E402


def test_live_read_matches_2026_11_19_capture_row_for_row():
    stats = s.build()
    assert stats["live_rows"] == 25
    live = pd.read_csv(ROOT / "data/live/spotcheck_2026_11_19/reserve_list_2026_11_live_read.csv", dtype=str)
    assert len(live) == 25
    assert (live.on_2026_11_19_capture == "yes").all()
    assert len(stats["dropped"]) == 4 and len(stats["added"]) == 4


def test_dropped_rows_include_malik_willis_and_are_on_the_retained_2026_11_18_capture():
    stats = s.build()
    names = {p for _, _, p in stats["dropped"]}
    assert "Malik Willis" in names
    cap = pd.read_csv(ROOT / "data/availability/reserve/history/2026-11-18T044201Z/reserve_list.csv", dtype=str)
    assert "Malik Willis" in set(cap.player)


def test_flag_rows_have_official_source_and_ids():
    df = pd.read_csv(ROOT / "data/integration/flagged_2026_11_19.csv", dtype=str, keep_default_na=False)
    assert list(df.id) == ["F-52", "F-53"]
    assert (df.source_url.str.startswith("https://www.nfl.com/")).all()
