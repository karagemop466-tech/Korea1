"""Independent tests for the T24 dated official-availability snapshot audit."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import current_snapshot_audit as audit  # noqa: E402


@pytest.fixture(scope="module")
def result() -> dict:
    return audit.audit_snapshot()


def test_manifest_has_nfl_report_and_all_club_sources(result: dict) -> None:
    assert len(result["sources"]) == 33
    assert sum(source["kind"] == "injury_report" for source in result["sources"]) == 1
    assert sum(source["kind"] == "depth_chart" for source in result["sources"]) == 32
    assert result["successful_depth_captures"] + len(result["failed_depth_captures"]) == 32


def test_published_availability_outputs_are_reproducible(result: dict) -> None:
    assert result["derived_tables_rebuilt"] == 3
    assert result["history_files_checked"] == 3
    assert result["injury_rows"] > 0
    assert result["depth_rows"] > 0
    assert result["slots"] > 0


def test_capture_failures_are_explicit_not_promoted_as_current_rows(result: dict) -> None:
    for source in result["failed_depth_captures"]:
        assert source["error"]
        assert source["rows"] == 0
        if not source["previous_snapshot_kept"]:
            assert source["team"] in result["depth_teams_missing"]
        else:
            assert source["team"] not in result["depth_teams_missing"]


def test_report_source_ledger_links_each_official_page(result: dict) -> None:
    report = audit.render_report(result)
    for source in result["sources"]:
        assert source["url"] in report
    ledger = report.split("## Reconciled findings", 1)[0]
    source_rows = [line for line in ledger.splitlines() if line.startswith("| ") and "official source" in line]
    assert len(source_rows) == 33
    assert all(re.search(r"\]\(https://www\.[^ )]+\)", line) for line in source_rows)
    assert "## Flagged for review and evidence boundaries" in report


def test_report_flags_post_snapshot_official_discrepancy_without_rewriting_history(result: dict) -> None:
    report = audit.render_report(result)
    assert "DET Kerby Joseph" in report
    assert "Full Participation in Practice" in report
    assert "Did Not Participate In Practice" in report
    assert "IR-2026-11-13-03" in report
    assert "https://www.nfl.com/injuries/league/2026/reg10" in report
    assert "No historical value was overwritten" in report
