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
    assert list(df.id) == ["F-2026-11-19-06", "F-2026-11-19-07", "F-2026-11-19-10"]
    assert (df.source_url.str.startswith("https://www.nfl.com/")).all()


def test_render_site_has_no_shadowed_2026_11_19_section_functions():
    """Two sections named _flagged_2026_11_19_section silently shadowed each other on main (PR #108 + this branch).
    Every module-level function name in render_site.py must be unique."""
    import ast
    tree = ast.parse((ROOT / "pipeline" / "render_site.py").read_text(encoding="utf-8"))
    names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert dupes == [], dupes


def test_built_flagged_page_renders_both_2026_11_19_sections():
    html = (ROOT / "flagged.html").read_text(encoding="utf-8")
    assert "Findings from the 2026-11-19 re-read" in html
    assert "Findings from the 2026-11-19 session" in html


def test_executive_summary_carries_the_2026_11_19_update_with_unique_ids():
    text = (ROOT / "EXECUTIVE_SUMMARY.md").read_text(encoding="utf-8")
    assert "## Update — 2026-11-19" in text
    assert "F-2026-11-19-06" in text and "F-2026-11-19-07" in text
