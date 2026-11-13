"""The committed evidence manifest must describe the evidence it names.

Defect this pins (found 2026-11-13 by `arena/8a322b62-korea1`): `pipeline/fetch_injuries.py`
hashed only `files[0]` and used `setdefault("sha256", None)` for the rest, so every `make build`
rewrote the committed `data/evidence/nfl_injuries/week10_2026/manifest.json` and recorded
`"sha256": null` for `news_register.md`. That is an evidence-integrity problem, not a cosmetic
one: the manifest exists to prove the captured bytes were not altered, and a null digest cannot.

`tests/check_rebuild.py` did not catch it because it only compares `assets/`, `data/processed/`,
`data/sources_pbp.json` and `*.html` — `data/evidence/` is outside its scope.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "evidence" / "nfl_injuries" / "week10_2026" / "manifest.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_every_manifest_file_has_a_real_sha256():
    man = json.loads(MANIFEST.read_text())
    for f in man["files"]:
        assert f.get("sha256"), f"{f['logical']} has no sha256"
        assert len(f["sha256"]) == 64, f"{f['logical']} sha256 is not a full digest"
        assert f["sha256"] != "null"


def test_manifest_hashes_match_the_committed_bytes():
    man = json.loads(MANIFEST.read_text())
    for f in man["files"]:
        local = ROOT / f["local"]
        assert local.exists(), f"manifest names a missing file: {f['local']}"
        assert f["sha256"] == _sha256(local), f"{f['logical']} digest does not match its bytes"
        assert f["bytes"] == local.stat().st_size, f"{f['logical']} byte count does not match"


def test_build_does_not_rewrite_the_evidence_manifest():
    """A rebuild must be a no-op for committed evidence, so the tree cannot drift on every run."""
    before = MANIFEST.read_bytes()
    r = subprocess.run([str(ROOT / ".venv" / "bin" / "python"), "pipeline/fetch_injuries.py"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0 and not (ROOT / ".venv").exists():
        import pytest
        pytest.skip("needs the build environment")
    assert r.returncode == 0, r.stderr[-2000:]
    assert MANIFEST.read_bytes() == before, "fetch_injuries.py rewrote the committed evidence manifest"


def test_capture_manifest_for_the_settled_game_is_complete():
    """Same rule for the settlement capture added in T41."""
    cap = ROOT / "data" / "forward" / "captures" / "2026_10_WAS_NYG"
    man = json.loads((cap / "manifest.json").read_text())
    assert man["status_on_page"] == "Final"
    assert man["official_url"].startswith("https://www.nfl.com/")
    assert (man["away_team"], man["away_score"], man["home_team"], man["home_score"]) == ("WAS", 24, "NYG", 21)
    assert man["files"], "the capture must declare at least one file"
    for name, meta in man["files"].items():
        assert (cap / name).exists(), f"capture names a missing file: {name}"
        assert meta["sha256"] == _sha256(cap / name), f"{name} digest does not match its bytes"
