from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reconcile_depth_charts.py"
PROTECTED = [
    ROOT / "data" / "availability" / "depth_charts.csv",
    ROOT / "data" / "availability" / "history" / "2026-11-13" / "depth_charts.csv",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reconciliation_utility_is_read_only_and_checks_same_date_capture():
    before = {path: _sha256(path) for path in PROTECTED}

    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "read-only comparison" in result.stdout
    assert "No capture was written or modified." in result.stdout
    assert before == {path: _sha256(path) for path in PROTECTED}


def test_reserve_spotcheck_separates_the_cited_historical_capture_from_latest():
    sys.path.insert(0, str(ROOT / "pipeline"))
    import session_20261118 as session

    rows, stats = session.compare_reserve()
    assert stats["historical"]["label"] == "2026-11-17T19:59:57Z capture"
    assert stats["historical"]["both"] == 17
    assert stats["historical"]["live_only"] == 8
    assert stats["historical"]["capture_only"] == 8
    assert stats["latest"]["label"] == "2026-11-18T04:42:01Z capture"
    assert stats["latest"]["both"] == 25
    assert stats["latest"]["live_only"] == 0
    assert stats["latest"]["capture_only"] == 0
    # The rolling latest.csv now holds the 2026-11-19 capture: it is reported under its own
    # capture time, never under the 2026-11-18 label.
    assert stats["newest"]["label"] == "2026-11-19T04:30:02Z capture (latest.csv)"
    assert stats["newest"]["both"] == 21
    assert {row["check"] for row in rows} == {
        "reserve list vs 2026-11-17T19:59:57Z capture",
        "reserve list vs 2026-11-18T04:42:01Z capture",
        "reserve list vs 2026-11-19T04:30:02Z capture (latest.csv)",
    }
