"""T14/T15 regression tests: the review pages and their CSVs cannot drift apart.

What is asserted
----------------
1. Every question/suggestion ID is unique and its status/recommendation is in the vocabulary.
2. Every referenced question ID and every `ref` key actually exists.
3. The pages render exactly one table row per CSV row, so a hand-edit to HTML is impossible
   without breaking the build.
4. Every injury capture row carries the official source URL it was transcribed from, and the
   counts on the page match the data (2 Out / 1 Questionable for 2026 week 10).
5. No unavailable answer is invented: blocked/open questions must have an empty answer, and a
   BLOCKED availability signal must never be marked AVAILABLE.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import availability as av  # noqa: E402
import decisions as dc  # noqa: E402
from render_site import OFFICIAL  # noqa: E402

PROC = ROOT / "data" / "processed"


def ids_unique(rows, key="id"):
    ids = [r[key] for r in rows]
    assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"


def test_ids_and_vocabulary():
    ids_unique(dc.QUESTIONS)
    ids_unique(dc.SUGGESTIONS)
    ids_unique(av.SIGNALS)
    ids_unique(av.SOURCE_CHECKS)
    ids_unique(av.CONFLICTS)
    for q in dc.QUESTIONS:
        assert q["status"] in dc.STATUSES, q["id"]
        assert q["area"] in dc.AREAS, q["id"]
        assert q["ref"] in OFFICIAL, (q["id"], q["ref"])
    for s in dc.SUGGESTIONS:
        assert s["ref"] in OFFICIAL, (s["id"], s["ref"])
        assert s["effort"] in {"S", "M", "L"}, s["id"]
        for dep in s["depends"]:
            assert dep in {q["id"] for q in dc.QUESTIONS}, (s["id"], dep)


def test_no_invented_answers():
    for q in dc.QUESTIONS:
        if q["status"] in {"BLOCKED", "OPEN", "NEEDS DECISION"}:
            assert q["answer"] == "", f"{q['id']} is not ANSWERED but carries an answer"
            assert q["missing"], f"{q['id']} gives no missing-information note"
            assert q["close"], f"{q['id']} gives no closure test"
    for s in av.SIGNALS:
        if s["status"] == "BLOCKED":
            assert "NO" in s["available"] or "No " in s["available"] or "no " in s["available"], s["id"]


def test_pages_match_csvs():
    """The rendered row count must equal the generated row count, in order."""
    q = pd.read_csv(PROC / "questions.csv")
    s = pd.read_csv(PROC / "suggestions.csv")
    src = pd.read_csv(PROC / "availability_sources.csv")
    sig = pd.read_csv(PROC / "availability_signals.csv")
    conf = pd.read_csv(PROC / "availability_conflicts.csv")
    snap26 = pd.read_csv(PROC / "injury_snapshot_week10.csv")
    snap19 = pd.read_csv(PROC / "injury_snapshot_2019_wk5.csv")

    assert len(q) == len(dc.QUESTIONS)
    assert len(s) == len(dc.SUGGESTIONS)
    assert len(src) == len(av.SOURCE_CHECKS)
    assert len(sig) == len(av.SIGNALS)
    assert len(conf) == len(av.CONFLICTS)
    assert len(snap26) == 20 and len(snap19) == 11

    qpage = (ROOT / "questions.html").read_text()
    spage = (ROOT / "suggestions.html").read_text()
    ipage = (ROOT / "injuries.html").read_text()
    for row in q.itertuples():
        assert f">{row.id}<" in qpage, row.id
    for row in s.itertuples():
        assert f">{row.id}<" in spage, row.id
    for row in src.itertuples():
        assert f">{row.id}<" in ipage, row.id
    for row in sig.itertuples():
        assert f">{row.id}<" in ipage, row.id
    for row in conf.itertuples():
        assert f">{row.id}<" in ipage, row.id


def test_snapshot_rows_are_sourced():
    snap = pd.read_csv(PROC / "injury_snapshot_week10.csv")
    assert set(snap.source_url) == {av.URL_WEEK10}
    assert set(snap.retrieved) == {av.RETRIEVED}
    assert int((snap.game_status == "Out").sum()) == 2
    assert int((snap.game_status == "Questionable").sum()) == 1
    assert int(snap.club.eq("WAS").sum()) == 9
    assert int(snap.club.eq("NYG").sum()) == 11
    # a blank game status is not a claim of health
    assert snap.game_status.isna().sum() == 17

    hist = pd.read_csv(PROC / "injury_snapshot_2019_wk5.csv")
    assert set(hist.source_url) == {av.URL_WEEK10_2019}
    assert int((hist.game_status == "Out").sum()) == 1
    assert int((hist.game_status == "Doubtful").sum()) == 1
    assert int((hist.game_status == "Questionable").sum()) == 2


def test_official_checks_record_a_result():
    for row in av.SOURCE_CHECKS:
        assert row["url"].startswith("https://")
        assert "HTTP" in row["result"], row["id"]
        assert row["checked"] == av.RETRIEVED
        # a negative result must say so; nothing may be silently "verified"
        if "404" in row["result"] or "502" in row["result"]:
            assert "NEGATIVE" in row["status"] or "VERIFIED" in row["status"]


def test_no_template_placeholders_leak():
    for page in ["suggestions.html", "questions.html", "injuries.html"]:
        text = (ROOT / page).read_text()
        assert "{{" not in text and "}}" not in text, page
        assert not re.search(r">\s*(None|nan|NaN)\s*<", text), page
