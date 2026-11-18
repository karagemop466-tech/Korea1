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
