#!/usr/bin/env python3
"""Read-only comparison of the 2026-11-13 official depth extract.

This utility intentionally does not reconcile or rewrite the current depth
snapshot. Historical captures are immutable and must never be relabelled with a
new retrieval timestamp. It compares the transcribed official extract with the
capture from the same date; use the scheduled capture workflow for new data.

Usage: python scripts/reconcile_depth_charts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "data" / "live" / "official_depth_extract_2026_11_13.csv"
# Compare only with the capture from the same day. Comparing against the latest
# file confounds transcription errors with legitimate subsequent chart changes.
PUBLISHED = ROOT / "data" / "availability" / "history" / "2026-11-13" / "depth_charts.csv"


def main() -> int:
    if not OFFICIAL.is_file() or not PUBLISHED.is_file():
        print("required dated inputs are missing; no files were changed", file=sys.stderr)
        return 2

    # Import the repository's canonical comparison functions without duplicating
    # their slot/group semantics here.
    sys.path.insert(0, str(ROOT / "pipeline"))
    import live_verify_depth as lvd  # noqa: E402

    ext = pd.read_csv(OFFICIAL, dtype=str, keep_default_na=False)
    pub = pd.read_csv(PUBLISHED, dtype=str, keep_default_na=False)
    pub["depth_rank"] = pub["depth_rank"].astype(int)
    official_rows = lvd._off_rows(ext)
    published_rows = lvd._pub_rows(pub)

    missing = sorted(set(official_rows) - set(published_rows))
    mismatches = sorted(
        key for key in set(official_rows) & set(published_rows)
        if official_rows[key] != published_rows[key]
    )
    print(
        f"read-only comparison: {len(official_rows)} official slots; "
        f"{len(missing)} missing; {len(mismatches)} mismatched"
    )
    for key in missing:
        print(f"  missing {key}: official={official_rows[key]}")
    for key in mismatches:
        print(f"  mismatch {key}: official={official_rows[key]} published={published_rows[key]}")
    print("No capture was written or modified.")
    return 1 if missing or mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
