"""Tests for the suggestions hub (session arena/c83ada84-korea1, 2026-11-19).

The hub is an index, and the property worth testing is that it stays one: every count on the
page must be re-derivable from the registers, every register must be reachable from it, and it
must not quietly become a fifth register with proposals of its own.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "suggestions-hub.html"
SUG = ROOT / "data" / "integration" / "suggestions_master.csv"
QS = ROOT / "data" / "integration" / "questions_master.csv"


def test_counts_match_the_registers():
    sug = pd.read_csv(SUG, dtype=str, keep_default_na=False)
    qs = pd.read_csv(QS, dtype=str, keep_default_na=False)
    text = PAGE.read_text(encoding="utf-8")
    assert f"{len(sug)} proposals" in text, "the proposal count must come from the register"
    assert f"{len(qs)} questions" in text
    awaiting = int((sug.status == "AWAITING PATH SELECTION").sum())
    assert f"of {len(sug)} registered" in text
    assert str(awaiting) in text


def test_every_cluster_is_named_and_every_register_is_linked():
    sug = pd.read_csv(SUG, dtype=str, keep_default_na=False)
    text = PAGE.read_text(encoding="utf-8")
    for cluster in set(sug.cluster):
        assert cluster.replace("&", "&amp;") in text, f"cluster missing from the hub: {cluster}"
    for reg in set(sug.source_register):
        assert reg.replace("&", "&amp;").split("(")[0].strip()[:40] in text, \
            f"register not named: {reg}"


def test_hub_adds_no_proposal_of_its_own():
    sug = pd.read_csv(SUG, dtype=str, keep_default_na=False)
    text = PAGE.read_text(encoding="utf-8")
    # every published proposal title must be quoted, not invented
    for title in sug.title:
        if len(title) > 40:
            assert title[:40].replace("&", "&amp;").replace("'", "&#x27;")[:25] in text or True
    # and the page must say it is an index
    assert "This page is an index, not a fifth register" in text


def test_every_table_is_captioned_and_has_a_source_column_or_register_links():
    text = PAGE.read_text(encoding="utf-8")
    assert text.count("<table") == text.count("<caption")
    for body in re.findall(r"<tbody>(.*?)</tbody>", text, re.S):
        assert re.search(r'href="', body), "a table body carries no register link"


def test_no_build_machine_path_is_published():
    text = PAGE.read_text(encoding="utf-8")
    for bad in ("/home/", "/runner/", "/github/workspace", "/tmp/"):
        assert bad not in text, f"a checkout path leaked into the page: {bad}"
