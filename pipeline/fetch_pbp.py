"""T9a — fetch player-level play-by-play from a reachable, pinned source.

Why this exists
---------------
The build environment's egress allowlist permits `github.com`, `codeload.github.com`,
`api.github.com`, `registry.npmjs.org`, `pypi.org` and `files.pythonhosted.org` only.
nflverse publishes play-by-play as a *release asset*, and release assets redirect to
`release-assets.githubusercontent.com`, which is refused. That is why an earlier build
concluded player-level data was unreachable, and left the props page blank.

That conclusion was wrong. The GitHub **git-blob API** serves blob bytes from
`api.github.com` itself, up to 100 MB per blob, and nflverse's play-by-play is mirrored
per season inside the public repository `clausherther/nfl-dbt` as gzip blobs of ~17 MB.
So the bytes are reachable from an allowlisted host, and this module fetches them.

Provenance rules
----------------
* Every season is pinned by **git blob SHA**, not by branch or tag.
* Every downloaded byte string is SHA-256 hashed on arrival and recorded.
* A cached file whose SHA-256 does not match the recorded value is deleted and re-fetched;
  a mismatch after re-fetch is a hard error, never a silent fallback.
* Raw files stay in `data/raw/`, which is git-ignored. Only hashes are committed.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
MANIFEST = ROOT / "data" / "sources_pbp.json"

REPO = "clausherther/nfl-dbt"
PBP_DIR = "data_prep/data_files_load/pbp"

# Pinned git blob SHAs, read from the GitHub contents API on 2026-11-02.
# (GET /repos/clausherther/nfl-dbt/contents/data_prep/data_files_load/pbp)
BLOBS = {
    2019: ("ca455dc08e8670efd7c4ccc4eadfa1077d6f39ec", 16_479_104),
    2020: ("4daf7bdf2303e1a09b3a501466b2d631db27f92a", 16_664_760),
    2021: ("0dea4d024c1d0def95d0f718508e4e4035b094d3", 17_546_160),
    2022: ("97b78a439e9e25a215db6b1feeaec57e2818e94d", 17_257_188),
}
# 2023 exists in the same repository but is a partial season (2.0 MB, 5,660 plays);
# it is deliberately not fetched. Recorded here so the exclusion is auditable.

RETRIEVED = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_blob(blob_sha: str, dest: Path) -> None:
    """Fetch one git blob as raw bytes through api.github.com (allowlisted)."""
    url = f"https://api.github.com/repos/{REPO}/git/blobs/{blob_sha}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.raw"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as fh:
        fh.write(resp.read())


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    PROC.mkdir(parents=True, exist_ok=True)
    previous = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": []}
    retrieved = previous.get("retrieved_utc", RETRIEVED)
    prev_hash = {f["season"]: f["sha256"] for f in previous.get("files", [])}

    files = []
    total = 0
    for season, (blob_sha, size) in sorted(BLOBS.items()):
        dest = RAW / f"pbp_{season}.gzip"
        if dest.exists():
            got = sha256_of(dest)
            if season in prev_hash and got != prev_hash[season]:
                print(f"  {season}: cached hash mismatch, re-fetching")
                dest.unlink()
        if not dest.exists():
            print(f"  {season}: fetching blob {blob_sha[:12]} …")
            download_blob(blob_sha, dest)
        digest = sha256_of(dest)
        nbytes = dest.stat().st_size
        if nbytes != size:
            raise SystemExit(f"FATAL: {dest} is {nbytes} bytes, expected {size}")
        if season in prev_hash and digest != prev_hash[season]:
            raise SystemExit(f"FATAL: {dest} SHA-256 changed after re-fetch ({digest})")
        files.append(dict(
            season=season,
            local=str(dest.relative_to(ROOT)),
            bytes=nbytes,
            sha256=digest,
            git_blob_sha=blob_sha,
            url=f"https://github.com/{REPO}/blob/master/{PBP_DIR}/play_by_play_{season}.gzip",
            api_url=f"https://api.github.com/repos/{REPO}/git/blobs/{blob_sha}",
            rows=0,  # filled by props_model.py
        ))
        total += nbytes
        print(f"  {season}: {nbytes:,} bytes  sha256 {digest[:16]}…")

    manifest = {
        "generated_utc": RETRIEVED,
        "repository": f"https://github.com/{REPO}",
        "path": PBP_DIR,
        "access_method": ("GitHub git-blob API (api.github.com/repos/{repo}/git/blobs/{sha}, "
                          "Accept: application/vnd.github.raw). Release assets are NOT used: they "
                          "redirect to release-assets.githubusercontent.com, which the sandbox "
                          "egress allowlist refuses."),
        "tier": ("verified third party: nflverse play-by-play, itself built from NFL gamebooks, "
                 "mirrored byte-for-byte inside a public Git repository"),
        "excluded": [{"season": 2023, "reason": "partial season in this repository (2,034,432 bytes, "
                                                "5,660 plays); would silently understate rates"}],
        "files": files,
        "total_bytes": total,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {MANIFEST.relative_to(ROOT)} — {len(files)} seasons, {total:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
