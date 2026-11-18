"""NR3/NR6 — the 2026-11-18 request register: coverage, vocabulary and the evidence contract.

The register is the decision surface, so these tests ask whether it can be trusted rather than whether it
renders: every status must come from an artefact that opens, every gap must be a gap the repository really
has, and no item may be marked built because a plan said it would be.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from request_register_20261118 import (  # noqa: E402
    OUT, absent, ev, register_rows, resolve, suggestion_rows,
)

STARTS = ("BUILT", "PARTLY", "OPEN", "BLOCKED", "NOT BUILT", "CLOSED", "HELD", "POLICY", "REFUSED",
          "REFERENCE", "CONFLICTS", "NOT AVAILABLE", "IN PROGRESS", "EXTENDED")


def test_covers_the_request():
    rows = register_rows()
    assert len(rows) >= 60, "the 2026-11-18 request lists about sixty items"
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    for r in rows:
        assert r["status"].startswith(STARTS), r["status"]
        assert r["blocking_gate"] and r["clears_when"] and r["theme"], r["id"]
        assert r["evidence"], r["id"]


def test_every_built_row_opens_an_artefact():
    for r in register_rows():
        present = [ok for _t, ok in r["evidence"]]
        if r["status"].startswith(("BUILT", "HELD", "CLOSED")):
            assert any(present), f"{r['id']} claims {r['status']} with nothing behind it"


def test_gap_rows_are_real_gaps():
    """Items recorded as not built must still be absent, or the register is stale and must fail."""
    for r in register_rows():
        if r["status"].startswith("NOT BUILT") and "HERE" not in r["status"]:
            for text, ok in r["evidence"]:
                if "not in the repository" in text:
                    assert not ok or resolve(Path(text.split(" —")[0]).name) is None, r["id"]


def test_evidence_helpers_are_fail_closed():
    text, ok = ev("data/processed/model_metrics.csv")
    assert ok and "rows" in text
    text, ok = ev("data/processed/no_such_artefact.csv")
    assert not ok and "MISSING" in text
    text, ok = absent("data/processed/no_such_artefact.csv")
    assert ok and "not in the repository" in text
    text, ok = absent("data/processed/model_metrics.csv")
    assert not ok and "register needs updating" in text


def test_csvs_are_published_downloads():
    for name, expected in (("request_register_items_2026_11_18.csv", len(register_rows())),
                           ("suggestions_2026_11_18.csv", len(suggestion_rows()))):
        path = OUT / name
        assert path.exists(), name
        with open(path, encoding="utf-8") as fh:
            assert len(list(csv.DictReader(fh))) == expected, name
        assert (ROOT / "assets/data" / name).exists(), name


def test_suggestions_offer_three_paths_and_commit_to_nothing():
    rows = suggestion_rows()
    assert len(rows) >= 8
    for s in rows:
        for key in ("path_a", "path_b", "path_c", "gate_it_opens", "cost", "risk"):
            assert s[key].strip(), f"{s['id']} missing {key}"
        assert "PROPOSED" in s["state"], s["state"]


def test_flagged_rows_are_generated_from_the_claims():
    flagged = OUT / "flagged_2026_11_18b.csv"
    assert flagged.exists()
    with open(flagged, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) >= 5
    assert any(r["source_url"].startswith("https://www.nfl.com") for r in rows)
    for r in rows:
        assert r["finding"].strip() and r["next"].strip(), r["id"]
        if not r["source_url"]:
            assert r["source_label"] == "", "a row without a URL must not claim a source"


def test_page_registered_and_self_consistent():
    page = ROOT / "request-register.html"
    assert page.exists()
    html = page.read_text(encoding="utf-8")
    for href in ("request_register_items_2026_11_18.csv", "claim_checks_2026_11_18.csv",
                 "suggestions_2026_11_18.csv"):
        assert href in html, href
    import re
    cells = re.findall(r"<td>(.*?)</td>", html, re.S)
    leaked = [c for c in cells if re.search(r"(?<![\w/])(nan|NaN|None|inf|-inf)(?![\w/-])", c)]
    assert not leaked, leaked[:3]
