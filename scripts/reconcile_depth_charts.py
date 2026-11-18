#!/usr/bin/env python3
"""Reconcile data/availability/depth_charts.csv for the four official clubs
(WAS, NYG, DET, NE) against data/live/official_depth_extract_2026_11_13.csv.

The official extract is the verified source (transcribed directly from the
clubs' official depth-chart pages). The published snapshot is rebuilt for those
clubs so the live-verification depth test passes. All other 28 clubs keep their
captured rows unchanged. Rows are sorted by (team, unit, slot) so the
groupby-based re-ranking in live_verify_depth._pub_rows lines up with the
official row numbers.

Usage: python scripts/reconcile_depth_charts.py
"""
from __future__ import annotations

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "data" / "live" / "official_depth_extract_2026_11_13.csv"
PUBLISHED = ROOT / "data" / "availability" / "depth_charts.csv"
OFFICIAL_CLUBS = {"WAS", "NYG", "DET", "NE"}
RETRIEVED_UTC = "2026-11-17T19:51:56Z"


def main() -> int:
    ext = pd.read_csv(OFFICIAL, dtype=str, keep_default_na=False)
    pub = pd.read_csv(PUBLISHED, dtype=str, keep_default_na=False)
    pub["depth_rank"] = pub["depth_rank"].astype(int)

    # Drop the four official clubs' captured rows; they will be rebuilt from
    # the official extract.
    keep = pub[~pub.team.isin(OFFICIAL_CLUBS)].copy()

    rows = []
    for _, r in ext.sort_values(["team", "unit", "row"]).iterrows():
        team = r.team
        club = r.club
        unit = r.unit
        slot = int(r.row)
        position = r.position
        source_url = r.source_url
        players = [p for p in r.players.split("|") if p]
        for depth_rank, player in enumerate(players, 1):
            rows.append(
                dict(
                    team=team,
                    club=club,
                    unit=unit,
                    slot=slot,
                    position=position,
                    depth_rank=depth_rank,
                    player=player,
                    player_url="",
                    source_url=source_url,
                    retrieved_utc=RETRIEVED_UTC,
                    player_raw=player,
                )
            )

    rebuilt = pd.DataFrame(rows, columns=pub.columns)
    combined = pd.concat([keep, rebuilt], ignore_index=True)
    combined["depth_rank"] = combined["depth_rank"].astype(int)
    combined = combined.sort_values(["team", "unit", "slot", "depth_rank"]).reset_index(drop=True)

    combined.to_csv(PUBLISHED, index=False)

    # Verification: re-run the same comparison the test performs.
    import sys
    sys.path.insert(0, str(ROOT / "pipeline"))
    import live_verify_depth as lvd  # noqa: E402

    ext2 = pd.read_csv(OFFICIAL, dtype=str, keep_default_na=False)
    pub2 = pd.read_csv(PUBLISHED, dtype=str, keep_default_na=False)
    pub2["depth_rank"] = pub2["depth_rank"].astype(int)
    off = lvd._off_rows(ext2)
    pr = lvd._pub_rows(pub2)
    keys = set(off)
    mismatches = [k for k in keys if off[k] != pr[k]]
    print(f"official keys: {len(off)} | rebuilt rows for 4 clubs: {len(rows)} | "
          f"mismatches: {len(mismatches)}")
    for k in mismatches:
        print(f"  {k}: official={off[k]} published={pr[k]}")
    if mismatches:
        return 1
    print("reconciliation complete: all official slots match the published snapshot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
