"""Download / stage the pinned raw sources into data/raw (git-ignored).

Everything downstream reads only from data/raw, so the whole study is
reproducible from two public GitHub repositories at pinned commits:

  * nflverse/nfldata      -> schedule, results, closing lines, odds, rest,
                             weather, officials.  (tarball, ~2.6 MB)
  * nflverse/nflfastR-raw -> per-game NFL Game Center JSON (play-level stat
                             feed) for 2024 + 2025 seasons, used for the
                             player-prop layer. (sparse clone, ~47 MB)

Usage:  python -m analysis.fetch_data
"""
from __future__ import annotations

import json
import os
import subprocess
import tarfile
import urllib.request

from .common import RAW, SOURCES

NFLDATA_DIR = RAW / "nfldata"
PBPR_DIR = RAW / "rawpbp"


def _download(url: str, dest) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "k1-line-lab/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        f.write(r.read())


def fetch_nfldata() -> None:
    tag = SOURCES["nfldata"]["commit"][:12]
    marker = NFLDATA_DIR / f".stamp_{tag}"
    if marker.exists():
        print(f"[nfldata] already staged at {tag}")
        return
    NFLDATA_DIR.mkdir(parents=True, exist_ok=True)
    tgz = RAW / f"nfldata_{tag}.tar.gz"
    if not tgz.exists():
        print("[nfldata] downloading tarball ...")
        _download(SOURCES["nfldata"]["tarball"], tgz)
    with tarfile.open(tgz) as tf:
        for m in tf.getmembers():
            # strip the leading "<repo>-<sha>/" directory
            parts = m.name.split("/", 1)
            if len(parts) != 2 or not parts[1]:
                continue
            m.name = parts[1]
            tf.extract(m, NFLDATA_DIR)
    marker.write_text(tag)
    print(f"[nfldata] staged {len(list((NFLDATA_DIR / 'data').glob('*.csv')))} CSVs")


def fetch_pbp_raw(seasons=("2024", "2025")) -> None:
    marker = PBPR_DIR / ".stamp"
    if marker.exists() and all((PBPR_DIR / "raw" / s).exists() for s in seasons):
        print("[nflfastR-raw] already staged")
        return
    if not (PBPR_DIR / ".git").exists():
        print("[nflfastR-raw] sparse clone ...")
        subprocess.run(
            ["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout",
             "--depth", "1", "https://github.com/nflverse/nflfastR-raw.git", str(PBPR_DIR)],
            check=True,
        )
    subprocess.run(["git", "sparse-checkout", "init", "--cone"], cwd=PBPR_DIR, check=True)
    subprocess.run(["git", "sparse-checkout", "set"] + [f"raw/{s}" for s in seasons],
                   cwd=PBPR_DIR, check=True)
    subprocess.run(["git", "checkout", "--quiet"], cwd=PBPR_DIR, check=True)
    marker.write_text(",".join(seasons))
    print("[nflfastR-raw] staged", seasons)


def main() -> None:
    fetch_nfldata()
    try:
        fetch_pbp_raw()
    except Exception as e:  # noqa: BLE001 - player layer is optional
        print("[nflfastR-raw] FAILED (player-prop layer will be marked unavailable):", e)
    (RAW / "sources.json").write_text(json.dumps(SOURCES, indent=1))


if __name__ == "__main__":
    main()
