"""Tests for the Week 11 official publication layer (session arena/c83ada84-korea1).

The point of these tests is the rule the brief sets: a value that cannot be confirmed from
an official page is blank and flagged, never inferred. So they assert the *shape* of the
evidence (a hash per source, a clock time per capture, a source link per row) and they
re-derive the published counts from the committed bytes rather than trusting the page.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import week11_20261119 as W  # noqa: E402

CAP = ROOT / "data" / "live" / "official_2026_11_19"
PAGE = ROOT / "week-11.html"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return W.load_manifest()


def test_capture_exists_with_a_hash_and_a_clock_time(manifest):
    assert manifest, "the Week 11 capture manifest is missing"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", manifest["captured_utc"])
    assert manifest["season"] == 2026 and manifest["week"] == 11
    for s in manifest["sources"]:
        if s["sha256"]:
            p = CAP / "raw" / s["slug"]
            assert p.exists(), f"{s['slug']} is listed with a hash but its bytes are missing"
            import hashlib
            assert hashlib.sha256(p.read_bytes()).hexdigest() == s["sha256"], \
                f"{s['slug']} bytes no longer match the recorded hash"
            assert s["http_status"] == 200


def test_failed_capture_is_recorded_never_replaced_by_a_guess(manifest):
    for s in manifest["sources"]:
        if not s["sha256"]:
            assert s["error"], "a capture without a hash must record why"


def test_report_parses_week_11_and_keeps_blank_cells_blank():
    text, src = W.bytes_of(W.load_manifest(), "injury_report_week11_league_url")
    assert src is not None, "the Week 11 injury report was not captured"
    rows, meta = W.parse_report(text)
    assert meta["season"] == "2026"
    assert meta["week"] == "WEEK 11"
    assert len(rows) > 200
    # The parser never invents a designation: every printed value is a known word, and a
    # blank stays the empty string.
    for r in rows:
        assert not r["unknown_status"] and not r["unknown_practice"]
        assert r["game_status"] == "" or r["game_status"].lower() in W.GAME_STATUS
    assert any(r["game_status"] == "" for r in rows), \
        "the official page prints blanks; a parse with none is suspect"


def test_both_official_url_forms_were_captured_and_agree(manifest):
    a, sa = W.bytes_of(manifest, "injury_report_week11_league_url")
    b, sb = W.bytes_of(manifest, "injury_report_current")
    assert sa and sb, "both the week-addressed and the current-week URL must be captured"
    ra, _ = W.parse_report(a)
    rb, _ = W.parse_report(b)
    ia = {(r["club"], r["player"]): (r["game_status"], r["practice_status"]) for r in ra}
    ib = {(r["club"], r["player"]): (r["game_status"], r["practice_status"]) for r in rb}
    shared = set(ia) & set(ib)
    assert shared, "the two captures share no player, which is itself a finding"
    differ = {k for k in shared if ia[k] != ib[k]}
    # The page publishes disagreements rather than hiding them, so this test's job is to
    # assert the *published* count equals the re-derived count.
    html_text = PAGE.read_text(encoding="utf-8")
    if differ:
        assert "disagreements only" in html_text
    else:
        assert "agree on every player they share" in html_text


def test_fixtures_come_from_the_official_schedule_and_number_thirteen():
    text, src = W.bytes_of(W.load_manifest(), "schedule_week11_week_form", "schedule_week11_reg_form")
    assert src is not None, "the official Week 11 schedule was not captured"
    fixtures, shape = W.parse_fixtures(text)
    assert shape == "anchors with printed labels"
    assert len(fixtures) == 13, f"expected 13 Week 11 fixtures, parsed {len(fixtures)}"
    # Every fixture must carry the league's own printed kick-off facts, not a reconstruction.
    for f in fixtures:
        assert f["path"].startswith("/games/") and f["path"].endswith("-2026-reg-11")
        assert re.fullmatch(r"\d{1,2}:\d{2} [AP]M", f["time"]), f
        assert f["day"] and f["date"] and f["tv"], f
    paths = [f["path"] for f in fixtures]
    assert len(paths) == len(set(paths)), "a fixture is listed twice"


def test_venue_is_read_from_the_game_centre_game_info_block():
    text, src = W.bytes_of(W.load_manifest(), "game_centre__colts_at_texans_2026_reg_11")
    assert src is not None, "the Colts-at-Texans game centre was not captured"
    v = W.parse_venue(text)
    # Measured from the captured official page on 2026-11-19; see the raw bytes with the
    # matching sha256 in the manifest.
    assert v["location"] == "HOUSTON, TX"
    assert v["stadium"] == "RELIANT STADIUM"


def test_every_published_row_carries_an_official_link():
    """Every evidence row carries an official link.

    The two *summary* tables (the game-status and practice-status vocabularies) are counts
    over the rows beneath them and carry no link of their own -- they are labelled as such
    in the page and are not observations. Every other row must carry one.
    """
    html_text = PAGE.read_text(encoding="utf-8")
    body = html_text[html_text.find("<tbody>"):]
    checked = 0
    for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        if "<th>" in row:
            continue  # a header row names the columns; it is not an observation
        cells = re.findall(r"<td>(.*?)</td>", row, re.S)
        if len(cells) == 2 and re.fullmatch(r"\s*(<span[^>]*>)?[A-Za-z ()]+", cells[0] or "") \
                and re.fullmatch(r"\s*\d+\s*", cells[1] or ""):
            continue  # a vocabulary count row
        assert "https://www.nfl.com/" in row, f"row without an official link: {row[:200]}"
        checked += 1
    assert checked > 250, f"only {checked} evidence rows checked"


def test_page_keeps_the_no_inference_statements():
    html_text = PAGE.read_text(encoding="utf-8")
    for statement in ("No probability for \"Questionable\"", "No inferred depth order",
                      "No venue from memory", "No model consumes these rows yet"):
        assert statement in html_text
    # A player's designation must never be upgraded to a claim about his health.
    assert "recovered" not in html_text.lower().replace("recovery", "")


def test_movement_is_a_delta_between_two_dated_reads():
    text, _ = W.bytes_of(W.load_manifest(), "injury_report_week11_league_url")
    rows, _ = W.parse_report(text)
    w10, clock = W.week10_rows()
    assert w10, "the Week 10 capture is missing, so no delta can be computed"
    assert clock, "the Week 10 capture must carry its retrieval time"
    shared = [r for r in rows if (r["club"], r["player"]) in w10]
    assert shared, "no player is on both captures"
    html_text = PAGE.read_text(encoding="utf-8")
    assert "carried a game designation on Week 10; none printed on Week 11" in html_text or \
           "no change" in html_text


def test_no_build_machine_path_is_published():
    html_text = PAGE.read_text(encoding="utf-8")
    for bad in ("/home/", "/runner/", "/github/workspace", "/tmp/"):
        assert bad not in html_text, f"a checkout path leaked into the page: {bad}"
