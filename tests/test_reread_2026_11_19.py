"""Regression tests for the 2026-11-19 official re-read (arena/fea5cdab-korea1)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))


def test_reread_matches_every_transcribed_row():
    import reread_2026_11_19 as rr

    df, stats = rr.compare()
    assert stats["injury_live"] == 44
    assert stats["injury_match"] == 44
    assert stats["reserve_live"] == 17
    assert stats["reserve_match"] == 17
    assert stats["field_mismatch"] == 0
    assert set(stats["clubs"]) == {"WAS", "NYG", "NE", "DET"}
    assert (df.verdict == "MATCH").all()


def test_lions_trio_is_out_on_the_official_page_and_in_the_capture():
    df = pd.read_csv(ROOT / "data/live/reread_2026_11_19/official_rows_read.csv", dtype=str, keep_default_na=False)
    lions = df[(df.club == "DET") & df.player.isin(["Kerby Joseph", "Cade Mays", "D.J. Reed"])]
    assert len(lions) == 3 and (lions.game_status == "Out").all()


def test_findings_have_official_links_and_unique_ids():
    f = pd.read_csv(ROOT / "data/integration/findings_2026_11_19.csv", dtype=str, keep_default_na=False)
    assert f.id.is_unique and len(f) == 5
    assert f.url.str.startswith("https://www.nfl.com/").all()


def test_rolling_reserve_file_is_not_used_as_a_dated_reference():
    src = (ROOT / "pipeline/session_20261118.py").read_text()
    assert "reserve\" / \"latest.csv\"" not in src.split("def compare_reserve")[1].split("def ")[0]
