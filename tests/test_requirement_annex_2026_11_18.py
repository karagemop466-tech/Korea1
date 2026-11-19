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
# The register describes the 2026-11-18 snapshot the dated official read was checked
# against, so every re-derived count here reads the same DATED capture the builder is
# pinned to (pipeline/req_annex_2026_11_18.py::DATED_CAPTURE) — never the rolling
# top-level capture, which the availability tracker overwrites with the newest week.
# The Week-11 rollover of 2026-11-18T19:24Z made the rolling KC row count move and
# failed four scheduled availability runs before this pin existed.
Dated = AV / "history" / "2026-11-18"
RES_DATED = AV / "reserve" / "history" / "2026-11-18T044201Z" / "reserve_list.csv"
PAGE = ROOT / "requirement-annex-2026-11-18.html"
REG = INTEG / "requirement_annex_2026_11_18.csv"


def _reg() -> pd.DataFrame:
    return pd.read_csv(REG, dtype=str, keep_default_na=False)


def _inj() -> pd.DataFrame:
    return pd.read_csv(Dated / "injuries.csv", dtype=str, keep_default_na=False)


def _dep() -> pd.DataFrame:
    return pd.read_csv(Dated / "depth_charts.csv", dtype=str, keep_default_na=False)


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
    # The same dated capture the builder pins its comparison to; the rolling
    # reserve/latest.csv moves on every scheduled capture and cannot be a reference.
    cap = pd.read_csv(RES_DATED, dtype=str, keep_default_na=False)
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

    Reviewed 2026-11-19 (GC integration): the roster table was re-read with the repaired
    lineup parser (padded position-to-jersey gaps, four-letter EDGE positions, two-word
    surnames), so 2,295 rows / 348 unreadable became 3,252 rows / 29 unreadable (one
    club-header line per game).  Thirteen of the former 42 "Game Books" were the league's
    Record & Fact Book mis-captured for unplayed fixtures and were removed, leaving the 29
    genuine books.  The expected-vs-actual join exists, so R28/R62 were re-classified to
    DONE and F-54 closed.  Any change in these counts must be reviewed again.

    Re-pinned 2026-11-19 (W1, `arena/35c0fd93-korea1`): the hardcoded 29 / 3,252 / 29 pins
    could not survive the next scheduled capture — the gamebooks bot adds week-11 books as
    their games finish, which is correct behaviour, and GC-INT's own note warned the pin
    would "go red by design".  The page text is already computed from the same files
    (R28/F-54 build their sentences from the counts), so the review trigger is now
    structural instead of numeric: every captured book must have a roster table, the
    unreadable rows must stay exactly one club-header line per game, and the published
    page must quote the current counts.  A capture that breaks one of those invariants
    still fails here; a capture that merely grows does not redden `main`.
    """
    gb = pd.read_csv(ROOT / "assets" / "data" / "official_gamebooks.csv", dtype=str)
    ro = pd.read_csv(ROOT / "data" / "processed" / "official_gamebook_rosters.csv", dtype=str)
    games = int(ro["slug"].nunique())
    unreadable = int((ro["roster_block"] == "lineup_unreadable").sum())
    assert games == len(gb), (
        "every captured Game Book must have a roster table; if not, re-read R28/R62/F-54")
    assert unreadable == games, (
        "the unreadable roster blocks must remain exactly the one club-header line per "
        "game; a different shape means the lineup parser or the PDFs changed — re-read "
        "R28/R62 before editing their text")
    evidence = _reg().set_index("id").loc["R28", "evidence"]
    for count in (len(gb), len(ro), games, unreadable):
        assert str(count) in evidence, (
            f"the register page quotes {count} nowhere — the published text is stale "
            "against the committed capture")
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


def test_dated_comparators_never_read_the_rolling_capture():
    """Source-level guard (the test_reread pattern): a comparator pinned to a dated
    official read must read the dated capture folder, not the rolling top-level file.

    The Week-11 rollover of 2026-11-18T19:24Z moved the rolling KC row count and the
    pinned omission arithmetic raised SystemExit inside `make -o injuries site`, failing
    four scheduled availability runs (44380205336, 44445480402, 44456709590, 44598915891)
    until the reads were pinned to data/availability/history/2026-11-18/. This test fails
    if either comparator is ever pointed back at the rolling file, and fails if the dated
    folder itself disappears (the pin must point at a committed snapshot).
    """
    src = (ROOT / "pipeline" / "req_annex_2026_11_18.py").read_text(encoding="utf-8")
    assert 'DATED_CAPTURE = AVAIL / "history" / "2026-11-18"' in src, (
        "the dated capture pin is gone from req_annex_2026_11_18.py")
    for fn in ("def compare_official", "def measure"):
        body = src.split(fn, 1)[1].split("\ndef ", 1)[0]
        assert 'AVAIL / "injuries.csv"' not in body and 'AVAIL / "depth_charts.csv"' not in body, (
            f"{fn} reads the rolling capture again — it must read DATED_CAPTURE")
    assert 'reserve" / "latest.csv"' not in src, (
        "the annex reads the rolling reserve file again — dated comparisons must use the "
        "history/2026-11-18T044201Z capture")
    assert (Dated / "injuries.csv").exists() and (Dated / "depth_charts.csv").exists(), (
        "the dated capture folder the register is pinned to is missing")
    # The rolling file must exist too (the tracker and the newest-week pages read it),
    # but nothing in this module may derive a dated claim from it.
    assert (AV / "injuries.csv").exists()
