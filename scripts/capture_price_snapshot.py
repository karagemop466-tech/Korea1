"""Capture the price-snapshot store's mirror inputs (session arena/d0bec048-korea1).

The store needs, for every market this project originates, the *opening* and the
*closing* number. The pinned upstream mirror (nflverse/nfldata) publishes one
`games.csv` per commit, so each pinned commit is a genuine price snapshot with its
own capture time. The three snapshots already registered by the forward ledger
(`data/forward/snapshots/*.json`) each carry the sha256 of the `games.csv` they
describe, so this script can prove that what it downloads is byte-for-byte the file
that was registered.

Nothing is typed in by hand: the script downloads the archive from codeload, checks
the hash against the registered manifest, and refuses to write a row whose hash does
not match. It needs network access to codeload.github.com, exactly like
pipeline/fetch_data.py; it is therefore *not* part of `make build`.

Outputs
  data/prices/mirror_snapshots.csv          one row per (snapshot, game, market, side)
  data/prices/mirror_snapshots_manifest.json  what was downloaded, hashed and written

Run:  python scripts/capture_price_snapshot.py
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SNAP_DIR = ROOT / "data" / "forward" / "snapshots"
OUT_DIR = ROOT / "data" / "prices"
SEASON = 2026

# The market columns of the mirror's games.csv, in this project's sign convention:
#   spread_line  : home covers when (home_score - away_score) > spread_line
#   total_line   : over hits when (home_score + away_score) > total_line
MARKET_COLUMNS = [
    ("SPREAD", "home", "spread_line", "home_spread_odds"),
    ("SPREAD", "away", "spread_line", "away_spread_odds"),
    ("TOTAL", "over", "total_line", "over_odds"),
    ("TOTAL", "under", "total_line", "under_odds"),
    ("MONEYLINE", "home", "", "home_moneyline"),
    ("MONEYLINE", "away", "", "away_moneyline"),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download_games_csv(snapshot: dict) -> bytes:
    """Download the registered commit's games.csv and prove it matches the manifest."""
    url = snapshot["archive_url"]
    req = urllib.request.Request(url, headers={"User-Agent": "arena-agent/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        raw = resp.read()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        member = next(m for m in tf.getmembers() if m.name.endswith("/data/games.csv"))
        data = tf.extractfile(member).read()
    want = snapshot["files"]["games.csv"]
    got_sha, got_bytes = sha256_bytes(data), len(data)
    if got_sha != want["sha256"] or got_bytes != want["bytes"]:
        raise SystemExit(
            f"{snapshot['sha']}: games.csv does not match the registered manifest "
            f"(sha256 {got_sha} / {got_bytes} bytes vs {want['sha256']} / {want['bytes']})"
        )
    return data


def rows_from_snapshot(snapshot: dict, data: bytes) -> list[dict]:
    games = pd.read_csv(io.BytesIO(data), low_memory=False)
    games = games[(games.season == SEASON) & (games.game_type == "REG")]
    out: list[dict] = []
    for r in games.to_dict("records"):
        for market, side, line_col, odds_col in MARKET_COLUMNS:
            line = r.get(line_col) if line_col else None
            odds = r.get(odds_col)
            if line is None or (isinstance(line, float) and line != line):
                line = None
            if odds is None or (isinstance(odds, float) and odds != odds):
                odds = None
            if line is None and odds is None:
                continue
            out.append({
                "snapshot_sha": snapshot["sha"],
                "snapshot_utc": snapshot["commit_time_utc"],
                "season": int(r["season"]),
                "week": int(r["week"]),
                "gameday": r["gameday"],
                "away_team": r["away_team"],
                "home_team": r["home_team"],
                "game_id": r["game_id"],
                "market": market,
                "side": side,
                "line": "" if line is None else float(line),
                "odds": "" if odds is None else float(odds),
                "source_url": snapshot["browse_url"],
                "evidence_class": "C - community mirror, not an official NFL source",
            })
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshots = []
    for path in sorted(SNAP_DIR.glob("*.json")):
        snapshots.append(json.loads(path.read_text()))
    snapshots.sort(key=lambda s: s["commit_time_utc"])

    rows: list[dict] = []
    manifest = {"season": SEASON, "repo": "nflverse/nfldata", "snapshots": [], "rows": 0}
    for snap in snapshots:
        data = download_games_csv(snap)
        got = rows_from_snapshot(snap, data)
        rows.extend(got)
        manifest["snapshots"].append({
            "sha": snap["sha"],
            "commit_time_utc": snap["commit_time_utc"],
            "browse_url": snap["browse_url"],
            "archive_url": snap["archive_url"],
            "games_csv_sha256": snap["files"]["games.csv"]["sha256"],
            "games_csv_bytes": snap["files"]["games.csv"]["bytes"],
            "rows": len(got),
            "verified": "sha256 and byte length match the registered manifest",
        })
        print(f"  {snap['sha'][:12]} {snap['commit_time_utc']}  {len(got):,} rows  hash verified")

    df = pd.DataFrame(rows)
    df = df.sort_values(["snapshot_utc", "game_id", "market", "side"]).reset_index(drop=True)
    out = OUT_DIR / "mirror_snapshots.csv"
    df.to_csv(out, index=False)
    manifest["rows"] = len(df)
    manifest["generated_utc"] = "2026-11-14T00:00:00Z"
    (OUT_DIR / "mirror_snapshots_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {out.relative_to(ROOT)} ({len(df):,} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
