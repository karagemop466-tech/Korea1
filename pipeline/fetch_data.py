"""T1 — deterministic data acquisition.

Network reality of this build environment (measured, not assumed):

  reachable  : github.com, codeload.github.com, api.github.com,
               registry.npmjs.org, pypi.org, files.pythonhosted.org
  blocked    : raw.githubusercontent.com, release-assets.githubusercontent.com,
               objects.githubusercontent.com, www.nfl.com, operations.nfl.com
               (TLS handshake refused from the shell)

Therefore we pin the upstream **commit SHA** and pull the repository archive from
`codeload.github.com`, which is reachable and serves the identical bytes for a
given SHA. Release assets (the other distribution path for this same data) are
*not* used because they redirect to a blocked host.

Run:  python pipeline/fetch_data.py
Out:  data/raw/*.csv, data/sources.json
"""
from __future__ import annotations

import datetime as dt
import io
import json
import subprocess
import sys
import tarfile
import urllib.request

import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import RAW, ROOT, SOURCES, sha256_of, write_json  # noqa: E402

REPO = "nflverse/nfldata"
BRANCH = "master"
FILES = [
    "data/games.csv",
    "data/closing_lines.csv",
    "data/initial_lines.csv",
    "data/sc_lines.csv",
    "data/win_totals.csv",
    "data/predictions.csv",
    "DATASETS.md",
]


def resolve_sha() -> str:
    """Pin the exact upstream commit with git (github.com is reachable)."""
    out = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{REPO}", f"refs/heads/{BRANCH}"],
        capture_output=True, text=True, timeout=120, check=True,
    ).stdout.strip()
    if not out:
        raise RuntimeError("could not resolve upstream ref")
    return out.split()[0]


def download_archive(sha: str) -> bytes:
    url = f"https://codeload.github.com/{REPO}/tar.gz/{sha}"
    req = urllib.request.Request(url, headers={"User-Agent": "arena-agent/1.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


def main() -> None:
    sha = resolve_sha()
    print(f"pinned {REPO}@{sha}")
    blob = download_archive(sha)
    print(f"archive bytes: {len(blob):,}")

    extracted = {}
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        for member in tf.getmembers():
            parts = member.name.split("/", 1)
            if len(parts) != 2 or parts[1] not in FILES or not member.isfile():
                continue
            fh = tf.extractfile(member)
            data = fh.read()
            target = RAW / parts[1].replace("data/", "")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            extracted[parts[1]] = target
            print(f"  {parts[1]:28s} {len(data):>10,} bytes -> {target.relative_to(ROOT)}")

    missing = [f for f in FILES if f not in extracted]
    if missing:
        raise RuntimeError(f"archive missing expected files: {missing}")

    # ---- provenance record -------------------------------------------------
    record = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "upstream": {
            "repo": REPO,
            "branch": BRANCH,
            "commit_sha": sha,
            "commit_url": f"https://github.com/{REPO}/commit/{sha}",
            "archive_url": f"https://codeload.github.com/{REPO}/tar.gz/{sha}",
            "browse_url": f"https://github.com/{REPO}/tree/{sha}",
        },
        "network_policy": {
            "reachable": ["github.com", "codeload.github.com", "api.github.com",
                          "registry.npmjs.org", "pypi.org", "files.pythonhosted.org"],
            "blocked_observed": ["raw.githubusercontent.com",
                                 "release-assets.githubusercontent.com",
                                 "objects.githubusercontent.com",
                                 "www.nfl.com", "operations.nfl.com"],
            "note": ("Cited nfl.com pages are read with the agent's page-fetch tool, not the "
                     "shell; the shell's TLS handshake to nfl.com is refused by the sandbox "
                     "egress allowlist."),
        },
        "files": [],
        "definitions": SOURCES,
    }
    for logical, path in sorted(extracted.items()):
        entry = {
            "logical": logical,
            "local": str(path.relative_to(ROOT)),
            "bytes": path.stat().st_size,
            "sha256": sha256_of(path),
            "url": f"https://github.com/{REPO}/blob/{sha}/{logical}",
        }
        if path.suffix == ".csv":
            df = pd.read_csv(path)
            entry["rows"] = int(len(df))
            entry["columns"] = list(df.columns)
        record["files"].append(entry)

    write_json(ROOT / "data" / "sources.json", record)
    print("wrote data/sources.json")


if __name__ == "__main__":
    main()
