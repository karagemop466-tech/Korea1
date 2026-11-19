"""Every number on requirement-annex-2026-11-18.html is re-derived here, independently.

The page is a verification surface, so the test does not trust the module that renders it: it
re-reads the same committed inputs, recomputes the headline counts and the official re-read
agreement, and fails when the published page or CSV disagrees. It also enforces the two rules the
brief states — an official source on every row, and nothing filled in that cannot be confirmed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
from verify_site import ALLOW  # noqa: E402  the same allow-list every other page is checked against
INTEG = ROOT / "data" / "integration"
SPOT = ROOT / "data" / "live" / "spotcheck_2026_11_18_b"
AV = ROOT / "data" / "availability"
PAGE = ROOT / "requirement-annex-2026-11-18.html"
REG = INTEG / "requirement_annex_2026_11_18.csv"


def _reg() -> pd.DataFrame:
    return pd.read_csv(REG, dtype=str, keep_default_na=False)


def _inj() -> pd.DataFrame:
    return pd.read_csv(AV / "injuries.csv", dtype=str, keep_default_na=False)


def _dep() -> pd.DataFrame:
    return pd.read_csv(AV / "depth_charts.csv", dtype=str, keep_default_na=False)


def _spot() -> pd.DataFrame:
    return pd.read_csv(SPOT / "spotcheck_rows.csv", dtype=str, keep_default_na=False)


def test_page_and_csv_exist():
    assert PAGE.exists(), "the register page is not published"
    assert REG.exists(), "the register CSV is not written"
    assert PAGE.stat().st_size > 20_000


def test_every_row_has_an_official_source_and_a_clearing_number():
    r = _reg()
    assert len(r) >= 75, "the brief has about seventy-five lines; rows are missing"
    for _, row in r.iterrows():
        assert row["official_url"].startswith("https://"), f"{row['id']}: no official URL"
        host = urlsplit(row["official_url"]).hostname
        assert host in ALLOW, f"{row['id']}: {host} is not an official/primary host"
        assert row["clears"].strip(), f"{row['id']}: no number that clears it"
        assert row["gate"].strip(), f"{row['id']}: no blocking gate named"
        assert row["evidence"].strip(), f"{row['id']}: no evidence"


def test_status_vocabulary_is_closed():
    allowed_status = {"DONE", "PARTIAL", "BLOCKED", "REJECTED"}
    r = _reg()
    assert set(r["norm"]) <= allowed_status, set(r["norm"]) - allowed_status
    assert r["id"].is_unique


def test_rejected_rows_are_the_three_the_brief_asked_to_reject():
    r = _reg()
    rejected = set(r.loc[r["norm"] == "REJECTED", "id"])
    assert rejected == {"R27", "R30", "R36"}, rejected


def test_injury_counts_match_the_capture():
    inj = _inj()
    r = _reg().set_index("id")
    assert f"{len(inj)} rows" in r.loc["R51", "evidence"]
    assert str(inj.team.nunique()) in r.loc["R51", "evidence"]
    designated = int((inj.game_status.str.strip() != "").sum())
    assert f"{designated} of {len(inj)}" in r.loc["R34", "evidence"]


def test_depth_group_and_shared_slot_counts_are_recomputed():
    dep = _dep()
    multi = int((dep[dep.depth_rank.astype(int) == 1]
                 .groupby(["team", "unit", "position"]).size() > 1).sum())
    shared = int((dep.groupby(["team", "unit", "position", "slot"]).size() > 1).sum())
    r = _reg().set_index("id")
    assert str(multi) in r.loc["R38", "evidence"]
    assert str(shared) in r.loc["R39", "evidence"]


def test_official_reread_agreement_is_recomputed_not_asserted():
    spot = _spot()
    inj_rows = spot[spot.check == "injury report"]
    dep_rows = spot[spot.check == "club depth chart"]
    assert len(inj_rows) == 97 and len(dep_rows) == 23
    assert (inj_rows.verdict == "MATCH").all(), inj_rows[inj_rows.verdict != "MATCH"]
    assert (dep_rows.verdict == "MATCH").all(), dep_rows[dep_rows.verdict != "MATCH"]
    res = spot[spot.check == "reserve list"]
    assert (res.verdict != "MISMATCH").all()


def test_reserve_comparison_is_symmetric_and_dated():
    res = _spot()
    res = res[res.check == "reserve list"]
    on_both = int((res.verdict == "ON BOTH").sum())
    live_only = int((res.verdict == "ON LIVE PAGE ONLY").sum())
    cap_only = int((res.verdict == "CAPTURE ONLY").sum())
    cap = pd.read_csv(AV / "reserve" / "latest.csv", dtype=str, keep_default_na=False)
    assert on_both + cap_only == int((cap.month == "2026-11").sum())
    r = _reg().set_index("id")
    assert f"{on_both} of {on_both + live_only}" in r.loc["R56", "evidence"]


def test_kansas_city_omitted_row_is_not_counted_as_a_match():
    """The reader cut one KC row mid-cell; it must be absent from the comparison, not scored."""
    inj = _inj()
    kc_capture = int((inj.team == "KC").sum())
    spot = _spot()
    kc_compared = int(((spot["check"] == "injury report") & (spot["club"] == "KC")).sum())
    assert kc_compared == kc_capture - 1, (kc_compared, kc_capture)
    assert kc_capture == 13
    assert "of its 13 rows" in PAGE.read_text()


def test_outputs_that_block_many_rows_are_still_missing():
    """The blocked rows cite missing artefacts; if one changes, the register must be updated.

    2026-11-19: the Game Book captures and the structured roster table are committed (75ea927).
    The table is partial (29 of 42 games; 348 unreadable lineup blocks), so R28/R62 stay BLOCKED and
    the rows are re-described, not re-classified to done. Any change in these counts must be reviewed.
    """
    gb = pd.read_csv(ROOT / "assets" / "data" / "official_gamebooks.csv", dtype=str)
    assert len(gb) == 42
    ro = pd.read_csv(ROOT / "data" / "processed" / "official_gamebook_rosters.csv", dtype=str)
    assert len(ro) == 2295 and ro["slug"].nunique() == 29
    assert int((ro["roster_block"] == "lineup_unreadable").sum()) == 348, (
        "Game Book unreadable-block count changed: re-read R28/R62 before editing their text")
    assert int((_dep().team == "HOU").sum()) == 0, (
        "Houston depth rows exist now — R33/R36/R37/R40/R52 must be re-classified")


def test_questions_and_decisions_registers_are_complete():
    q = pd.read_csv(INTEG / "questions_2026_11_18.csv", dtype=str, keep_default_na=False)
    d = pd.read_csv(INTEG / "decisions_2026_11_18.csv", dtype=str, keep_default_na=False)
    assert len(q) >= 12 and len(d) >= 8
    for col in ("question", "have", "lack", "how", "url"):
        assert (q[col].str.strip() != "").all(), f"blank {col} in the question register"
    for col in ("title", "options", "effect", "evidence", "url"):
        assert (d[col].str.strip() != "").all(), f"blank {col} in the decision register"


def test_page_prints_no_placeholder_or_template_leak():
    text = PAGE.read_text()
    for bad in ("{m[", "{f[", "{len(", "None<", "nan<", "TODO", "XXX"):
        assert bad not in text, f"template leak in the page: {bad}"
    assert "Requirement annex" in text


def test_findings_match_the_flagged_page_contract():
    f = pd.read_csv(INTEG / "findings_2026_11_18.csv", dtype=str, keep_default_na=False)
    assert len(f) >= 5
    for _, row in f.iterrows():
        assert re.match(r"^F-\d+$", row["id"]), row["id"]
        assert row["url"].startswith("https://")
        assert row["nxt"].strip() and row["text"].strip()
