"""A dated comparison must read a dated capture, never the rolling one.

Why this file exists (session arena/c83ada84-korea1, 2026-11-19)
---------------------------------------------------------------
`data/availability/injuries.csv` is a **rolling** file: `.github/workflows/availability.yml`
overwrites it with the newest week, together with `manifest.json`, `depth_charts.csv` and the
join outputs. At least eight separate modules and four test modules read that path as though
it were a fixed capture, each of them comparing a *dated* official read against it.

That defect is invisible while the rolling file happens to hold the week each reader was
written against, and it fails all at once when it does not. On 2026-11-19 it did fail:

  * `pipeline/req_annex_2026_11_18.py` aborted with "KC omission count is 3, expected 1",
    so the scheduled availability capture died at `make -o injuries site` on every run after
    2026-11-18T19:24Z (runs 44456709594, 44445480402, 44380205336) and no new week could
    enter the repository at all;
  * `pipeline/live_verify.py` reported every row as MISSING_FROM_PUBLISHED and emitted a
    zero-byte `internal_consistency.csv`, which then broke `render_live.py`;
  * `pipeline/claim_checks_20261118.py`, `pipeline/request_register.py` and
    `pipeline/reread_2026_11_19.py` answered different questions than their own prose states.

These tests are the guard. They do not depend on which week the rolling file currently holds;
they force it to a *different* week and assert every dated reader still gives the same answer.
"""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = ROOT / "data" / "availability"
ROLLING = AV / "injuries.csv"
DATED = AV / "history" / "2026-11-18" / "injuries.csv"


@pytest.fixture()
def rolling_moved_to_week_11():
    """Simulate the availability workflow capturing a *different* week.

    The rolling file is replaced with a same-shape frame whose week and clock differ, which is
    exactly the state that broke the build. The real file is restored afterwards.
    """
    if not ROLLING.exists() or not DATED.exists():
        pytest.skip("the availability capture is not present")
    backup = ROLLING.with_suffix(".pytest-backup")
    shutil.copy2(ROLLING, backup)
    try:
        with open(DATED, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())
        for r in rows:
            r["week"] = "WEEK 11"
            r["retrieved_utc"] = "2030-01-01T00:00:00Z"   # deliberately not any real capture
        with open(ROLLING, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        yield
    finally:
        shutil.move(str(backup), str(ROLLING))


def test_the_dated_week10_capture_is_still_held(rolling_moved_to_week_11):
    """The repository must keep the capture every dated reader compares against."""
    assert DATED.exists(), (
        "data/availability/history/2026-11-18/injuries.csv is the capture the Week 10 and "
        "2026-11-18/19 registers compare against; without it they cannot be re-run")
    rows = list(csv.DictReader(open(DATED, newline="", encoding="utf-8")))
    assert rows and {r["week"] for r in rows} == {"WEEK 10"}
    assert len(rows) == 347, "the 2026-11-18 capture is 347 rows; a different count is a finding"


def test_week11_layer_ignores_the_rolling_file(rolling_moved_to_week_11):
    """The Week 11 page's Week 10 movement column must not follow the rolling file."""
    import sys
    sys.path.insert(0, str(ROOT / "pipeline"))
    import week11_20261119 as W
    w10, clock = W.week10_rows()
    assert w10, "the Week 10 delta source vanished when the rolling file moved"
    assert clock == "2026-11-18T04:24:05Z"
    assert all(v["week"] == "WEEK 10" for v in w10.values())


def test_live_verify_pins_a_dated_capture(rolling_moved_to_week_11):
    import sys
    sys.path.insert(0, str(ROOT / "pipeline"))
    import live_verify as lv
    assert lv.PUBLISHED != lv.ROLLING, "live_verify must not read the rolling capture"
    assert lv.PUBLISHED.exists()
    rows = list(csv.DictReader(open(lv.PUBLISHED, newline="", encoding="utf-8")))
    assert rows and {r["week"] for r in rows} == {"WEEK 10"}


def test_requirement_annex_is_reproducible_when_the_rolling_file_moves(rolling_moved_to_week_11):
    """The exact failure that stopped the scheduled capture: the KC omission check."""
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "pipeline/req_annex_2026_11_18.py"],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-2000:]
    assert "KC omission count" not in out.stdout + out.stderr


def test_depth_status_refuses_to_join_two_captures(rolling_moved_to_week_11):
    """A fresh injury report must never be joined to an older depth capture."""
    import sys
    sys.path.insert(0, str(ROOT / "pipeline"))
    import depth_status as ds
    inj, depth = ds._same_capture_pair()
    clocks = lambda rows: {r.get("retrieved_utc", "") for r in rows}  # noqa: E731
    assert inj and depth
    assert clocks(inj) == clocks(depth), (
        "depth_status paired two different captures; the derived slot table would then be "
        "unreproducible and the snapshot audit cannot verify it")


def test_snapshot_audit_reproduces_the_committed_join(rolling_moved_to_week_11):
    import sys
    sys.path.insert(0, str(ROOT / "pipeline"))
    import current_snapshot_audit as audit
    result = audit.audit_snapshot()
    assert result["injury_rows"] > 0 and result["slots"] > 0
