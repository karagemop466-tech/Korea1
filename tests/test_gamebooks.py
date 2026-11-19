"""Tests for the official game-centre and Game Book readers.

The parsers are pure: they take a document and return rows.  Each test below
plants a document, checks what the parser reads, and then **mutates** the
document and checks that the reading moves.  A test that only re-read a fixed
string would pass even if the comparison were inverted.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import official_games as og  # noqa: E402


SCHEDULE_HTML = """
<html><body>
<div class="schedule"><h3>Thursday Night Football, November 19th</h3>
<a href="https://www.nfl.com/games/colts-at-texans-2026-reg-11">Colts at Texans, Thursday, November 19th, 8:15 PM, PRIME</a>
<h3>Sunday, November 22nd</h3>
<a href="https://www.nfl.com/games/dolphins-at-bills-2026-reg-11">Dolphins at Bills, Sunday, November 22nd, 1:00 PM, CBS</a>
</div>
<script>var noise = "SHOULD NOT APPEAR";</script>
</body></html>
"""

CENTRE_HTML = """
<html><body>
<div class="game-info"><h2>Game Info</h2>
<div><span>Location</span><span>LOCATION</span>ARLINGTON, TX</div>
<div><span>Stadium</span><span>STADIUM</span>AT&amp;T STADIUM</div>
</div>
<div class="tabs"><a href="https://static.www.nfl.com/image/upload/v1794829724/gamecenter/ab78a748-4feb-11f1-abca-2c54536568a9.pdf">Download Game Book (PDF)</a></div>
<div class="standings">Standings</div>
</body></html>
"""

GAME_BOOK_TEXT = """
National Football League Game Summary

San Francisco 49ers at Dallas Cowboys
Date: Sunday, 11/15/2026
Start Time: 3:25 PM CST

Game Weather: Rainy    Temp: 49° F (9.4° C) Humidity: 86%, Wind: NE 3 mph
Retractable Roof - Closed on Field Turf
Officials
Referee: Hussey, John (35)
Lineups
San Francisco 49ers                 Dallas Cowboys
Offense          Defense            Offense            Defense
WR 19 D.Samuel    DL 97 N.Bosa       WR 88 C.Lamb        OLB 40
FB 44 K.Juszczyk  DL 99 D.Buckner    WR 19 R.Flournoy    DT 92
TE 85 G.Kittle    DL 92 O.Odighizuwa LT 60 T.Guyton      DT 97
QB 13 B.Purdy     CB 20 U.Stout      QB 4 D.Prescott    LB 53
Substitutions
WR 3 K.Allen, WR 4 J.Cowing, TE 9 B.Willis         LB 0 D.Overshown, CB 2 C.Durant
K 18 E.Pineiro, S 24 A.Davis, RB 26 K.Black         P 5 B.Anger, WR 9 K.Turpin
Did Not Play
QB 10 M.Jones                                        QB 16 S.Howell
Not Active
WR 5 M.Evans, 3QB 14 K.Rourke, LB 48 T.Bethune      S 1 P.Locke, CB 15 J.Kendrick
Paid Attendance: 90,763
"""


# --------------------------------------------------------------------------- #
# html_to_text
# --------------------------------------------------------------------------- #
def test_html_to_text_drops_scripts_and_keeps_words():
    txt = og.html_to_text(SCHEDULE_HTML)
    assert "SHOULD NOT APPEAR" not in txt
    assert "Colts at Texans" in txt


def test_html_to_text_keeps_block_rows_apart():
    txt = og.html_to_text(CENTRE_HTML)
    assert "ARLINGTON, TX" in txt
    assert "AT&T STADIUM" in txt          # the entity is decoded, not dropped


# --------------------------------------------------------------------------- #
# schedule page
# --------------------------------------------------------------------------- #
def test_schedule_page_yields_the_printed_fixture():
    rows = og.parse_schedule_page(SCHEDULE_HTML)
    assert len(rows) == 2
    r = rows[0]
    assert r["away_as_printed"] == "Colts"
    assert r["home_as_printed"] == "Texans"
    assert r["date_as_printed"] == "Thursday, November 19th"
    assert r["time_as_printed"] == "8:15 PM"
    assert r["network_as_printed"] == "PRIME"
    assert r["official_url"] == "https://www.nfl.com/games/colts-at-texans-2026-reg-11"


def test_schedule_page_keeps_the_section_heading():
    rows = og.parse_schedule_page(SCHEDULE_HTML)
    assert rows[0]["section_heading"] == "Thursday Night Football, November 19th"
    assert rows[1]["section_heading"] == "Sunday, November 22nd"


def test_schedule_page_notices_a_changed_kickoff():
    changed = SCHEDULE_HTML.replace("8:15 PM", "8:25 PM")
    rows = og.parse_schedule_page(changed)
    assert rows[0]["time_as_printed"] == "8:25 PM"


def test_schedule_page_notices_a_changed_fixture():
    changed = SCHEDULE_HTML.replace("Colts at Texans", "Colts at Jaguars")
    rows = og.parse_schedule_page(changed)
    assert rows[0]["home_as_printed"] == "Jaguars"


# --------------------------------------------------------------------------- #
# game centre
# --------------------------------------------------------------------------- #
def test_game_centre_reads_the_printed_venue():
    got = og.parse_game_centre(og.html_to_text(CENTRE_HTML))
    assert got["venue_location"] == "ARLINGTON, TX"
    assert got["venue_stadium"] == "AT&T STADIUM"


def test_game_centre_reads_the_game_book_link():
    got = og.parse_game_centre(og.html_to_text(CENTRE_HTML), raw_html=CENTRE_HTML)
    assert got["gamebook_url"].endswith("ab78a748-4feb-11f1-abca-2c54536568a9.pdf")


def test_game_centre_notices_a_changed_stadium():
    text = og.html_to_text(CENTRE_HTML).replace("AT&T STADIUM", "SOFI STADIUM")
    got = og.parse_game_centre(text)
    assert got["venue_stadium"] == "SOFI STADIUM"


def test_game_centre_venue_is_blank_when_the_page_prints_none():
    text = og.html_to_text(CENTRE_HTML).replace("ARLINGTON, TX", "")
    got = og.parse_game_centre(text)
    assert got["venue_location"] == ""


# --------------------------------------------------------------------------- #
# game book
# --------------------------------------------------------------------------- #
def test_game_book_reads_the_printed_conditions():
    got = og.parse_game_book(GAME_BOOK_TEXT)
    assert got["date_as_printed"] == "Sunday, 11/15/2026"
    assert got["start_time_as_printed"] == "3:25 PM CST"
    assert got["weather_as_printed"] == "Rainy"
    assert got["temp_f"] == "49"
    assert got["wind_as_printed"] == "NE 3"
    assert got["roof_as_printed"] == "Retractable Roof - Closed on Field Turf"
    assert got["attendance_as_printed"] == "90,763"
    assert got["referee_as_printed"] == "Hussey, John (35)"


def test_game_book_notices_a_changed_weather_line():
    got = og.parse_game_book(GAME_BOOK_TEXT.replace("Game Weather: Rainy",
                                                    "Game Weather: Clear"))
    assert got["weather_as_printed"] == "Clear"


def test_game_book_separates_the_four_roster_blocks():
    got = og.parse_game_book(GAME_BOOK_TEXT)
    assert "D.Samuel" in got["lineups"]
    assert "K.Allen" in got["substitutions"]
    assert "M.Jones" in got["did_not_play"]
    assert "M.Evans" in got["not_active"]
    assert "D.Samuel" not in got["not_active"]


def test_game_book_reads_the_venue_line():
    got = og.parse_game_book(GAME_BOOK_TEXT.replace(
        "Paid Attendance", "11/15/2026 at AT&T Stadium\nPaid Attendance"))
    assert "AT&T Stadium" in got["venue_as_printed"]


# --------------------------------------------------------------------------- #
# roster rows
# --------------------------------------------------------------------------- #
def test_roster_entries_are_read_as_printed():
    entries = og.parse_roster_entries(
        "WR 5 M.Evans, 3QB 14 K.Rourke, LB 48 T.Bethune")
    assert entries == [
        {"position": "WR", "jersey": "5", "player": "M.Evans"},
        {"position": "3QB", "jersey": "14", "player": "K.Rourke"},
        {"position": "LB", "jersey": "48", "player": "T.Bethune"},
    ]


def test_roster_entries_do_not_invent_a_jersey_number():
    entries = og.parse_roster_entries("WR M.Evans")
    assert entries[0]["player"] == "WR M.Evans"
    assert entries[0]["jersey"] == ""


def test_lineup_rows_keep_the_printed_column():
    got = og.parse_game_book(GAME_BOOK_TEXT)
    rows = og.parse_lineup_rows(got["lineups"])
    by_column = {}
    for r in rows:
        by_column.setdefault(r["column"], r)
    assert by_column[0]["player"] == "D.Samuel"
    assert by_column[1]["player"] == "N.Bosa"
    assert by_column[2]["player"] == "C.Lamb"
    assert by_column[3]["player"] == ""      # the official print leaves it empty


def test_lineup_rows_flag_a_row_that_does_not_split_into_four_columns():
    got = og.parse_game_book(GAME_BOOK_TEXT)
    rows = og.parse_lineup_rows(got["lineups"] + "\nQB 13 B.Purdy alone")
    assert any(r["column"] == -1 for r in rows)


def test_two_column_roster_keeps_the_two_clubs_apart():
    got = og.parse_game_book(GAME_BOOK_TEXT)
    cols = og.parse_two_column_roster(got["not_active"])
    assert [e["player"] for e in cols["left"]] == ["M.Evans", "K.Rourke", "T.Bethune"]
    assert [e["player"] for e in cols["right"]] == ["P.Locke", "J.Kendrick"]
    assert cols["unattributed"] == []


def test_two_column_roster_refuses_to_guess_a_single_column_line():
    cols = og.parse_two_column_roster("WR 5 M.Evans")
    assert cols["left"] == []
    assert cols["right"] == []
    assert cols["unattributed"][0]["player"] == "M.Evans"


def test_split_columns_uses_the_wide_gap_only():
    assert og.split_columns("WR 19 D.Samuel    DL 97 N.Bosa") == [
        "WR 19 D.Samuel", "DL 97 N.Bosa"]


# --------------------------------------------------------------------------- #
# 2026-11-19 capture repair (session arena/7cbb2e60-korea1, GC1)
#
# The committed runner capture showed three shapes the old parser could not
# read: relative hrefs, labels nested in <span class="sr-only">, and the
# final-score label the league prints for finished games.  Each test below
# plants the real shape and then mutates it, so a parser that ignored the
# document would fail.
# --------------------------------------------------------------------------- #
REAL_SHAPE_HTML = """
<html><body><div class="schedule">
<h3>Thursday Night Football, November 19th</h3>
<a class="relative" data-analytics="{&quot;gameId&quot;:&quot;ab997d97&quot;}" href="/games/colts-at-texans-2026-reg-11"><span class="sr-only">Colts at Texans, Thursday, November 19th, 8:15 PM, PRIME</span><span class="logo"></span></a>
<h3>Sunday, November 15th</h3>
<a href="https://www.nfl.com/games/commanders-at-giants-2026-reg-10"><span class="sr-only">Commanders 24, Giants 21, FINAL, Thursday, November 12th</span></a>
<a href="/games/other-noise">Some other link</a>
</div></body></html>
"""


def test_schedule_page_reads_relative_hrefs_and_nested_labels():
    rows = og.parse_schedule_page(REAL_SHAPE_HTML)
    assert len(rows) == 2
    r = rows[0]
    # the relative href is normalised to the official absolute URL
    assert r["official_url"] == "https://www.nfl.com/games/colts-at-texans-2026-reg-11"
    assert r["away_as_printed"] == "Colts"
    assert r["home_as_printed"] == "Texans"
    assert r["time_as_printed"] == "8:15 PM"
    assert r["network_as_printed"] == "PRIME"
    assert r["status_as_printed"] == ""


def test_schedule_page_reads_the_final_score_label():
    rows = og.parse_schedule_page(REAL_SHAPE_HTML)
    r = rows[1]
    assert r["away_as_printed"] == "Commanders"
    assert r["home_as_printed"] == "Giants"
    assert r["status_as_printed"] == "FINAL"
    assert r["away_score_as_printed"] == "24"
    assert r["home_score_as_printed"] == "21"
    assert r["date_as_printed"] == "Thursday, November 12th"
    assert r["time_as_printed"] == ""          # the final print carries no kickoff
    assert r["network_as_printed"] == ""


def test_schedule_page_notices_a_changed_final_score():
    changed = REAL_SHAPE_HTML.replace("Commanders 24, Giants 21",
                                      "Commanders 27, Giants 21")
    rows = og.parse_schedule_page(changed)
    assert rows[1]["away_score_as_printed"] == "27"


def test_schedule_page_skips_a_label_it_cannot_read():
    changed = REAL_SHAPE_HTML.replace(
        "Colts at Texans, Thursday, November 19th, 8:15 PM, PRIME",
        "Colts vs Texans sometime soon")
    rows = og.parse_schedule_page(changed)
    assert len(rows) == 1          # only the final-score row survives; no guessing
    assert rows[0]["status_as_printed"] == "FINAL"


def test_week_schedule_url_is_the_week_selecting_path():
    # /schedules/2026/REG10 was measured (2026-11-19) to ignore the week
    # (flag F-2026-11-19-08); the by-week path is the capture source.
    assert og.week_schedule_url(2026, 10) == "https://www.nfl.com/schedules/2026/by-week/week-10"
    assert og.scores_week_url(2026, 10) == "https://www.nfl.com/scores/2026/week-10"
    assert "REG10" not in og.week_schedule_url(2026, 10)


def test_fixture_week_reads_the_slugs_own_week():
    assert og.fixture_week("https://www.nfl.com/games/commanders-at-giants-2026-reg-10") == 10
    assert og.fixture_week("/games/colts-at-texans-2026-reg-11?tab=highlights") == 11
    assert og.fixture_week("https://www.nfl.com/schedules/2026") is None


def test_week_mismatches_flags_a_wrong_week_slug():
    rows = og.parse_schedule_page(REAL_SHAPE_HTML)   # slugs reg-11 and reg-10
    # requested week 11: the reg-11 row is clean, the reg-10 row is flagged
    bad11 = og.week_mismatches(rows, 11)
    assert len(bad11) == 1 and "reg-10" in bad11[0]
    # requested week 9: both rows are flagged
    bad9 = og.week_mismatches(rows, 9)
    assert len(bad9) == 2
    assert all("requested 9" in m for m in bad9)


def test_game_link_slugs_cross_checks_two_official_documents():
    sched = og.game_link_slugs(REAL_SHAPE_HTML)
    assert "colts-at-texans-2026-reg-11" in sched
    assert "commanders-at-giants-2026-reg-10" in sched
    # the scores page for week 11 must name the same week-11 fixture set
    week11 = {s for s in sched if s.endswith("-reg-11")}
    assert week11 == {"colts-at-texans-2026-reg-11"}


def test_slug_of_strips_query_and_slash():
    assert og.slug_of("https://www.nfl.com/games/was-at-nyg-2026-reg-10/?tab=x") == "was-at-nyg-2026-reg-10"
    assert og.slug_of("/games/was-at-nyg-2026-reg-10") == "was-at-nyg-2026-reg-10"


def test_book_matches_fixture_rejects_a_book_for_another_game():
    from fetch_official_games import book_matches_fixture
    book = dict(away_as_printed="Washington Commanders",
                home_as_printed="New York Giants")
    assert book_matches_fixture(book, "commanders-at-giants-2026-reg-10") == ""
    assert book_matches_fixture(book, "colts-at-texans-2026-reg-11") != ""
    assert book_matches_fixture(dict(away_as_printed="", home_as_printed=""),
                                "commanders-at-giants-2026-reg-10") != ""


def test_book_matches_fixture_requires_both_slug_tokens():
    from fetch_official_games import book_matches_fixture
    book = dict(away_as_printed="San Francisco 49ers",
                home_as_printed="Dallas Cowboys")
    assert book_matches_fixture(book, "49ers-at-cowboys-2026-reg-10") == ""
    assert book_matches_fixture(book, "not-a-fixture") != ""


def test_committed_reg10_capture_parses_to_a_single_week():
    """The 2026-11-19 runner capture (REG9/REG10, byte-identical, Week-11
    content — flag F-2026-11-19-08) must parse with the repaired parser, and
    every slug in one file must name one week.  The assertion is week-agnostic
    on purpose: after the by-week recapture the same test must hold for real
    Week-10 content."""
    import gzip as _gzip
    path = ROOT / "data" / "evidence" / "official_games" / "schedule" / "REG10.txt.gz"
    if not path.exists():          # pragma: no cover - capture absent
        import pytest as _pytest
        _pytest.skip("no committed schedule capture")
    text = _gzip.open(path, "rt", encoding="utf-8", errors="replace").read()
    # parse the html.gz (the parser reads markup, not flattened text)
    html_path = ROOT / "data" / "evidence" / "official_games" / "schedule" / "REG10.html.gz"
    rows = og.parse_schedule_page(_gzip.open(html_path, "rt", encoding="utf-8", errors="replace").read())
    assert len(rows) >= 1
    weeks = {og.fixture_week(r["official_url"]) for r in rows}
    assert None not in weeks
    assert len(weeks) == 1


# --------------------------------------------------------------------------- #
# GC3 — the repair is published where a reviewer will look for it
# --------------------------------------------------------------------------- #
def test_flagged_page_carries_the_capture_repair_rows():
    """Regression: PR #108 once silently shadowed a flagged-section function,
    so the rows existed in code but never reached the page.  Read the shipped
    page, not the generator."""
    path = ROOT / "flagged.html"
    if not path.exists():          # pragma: no cover - page absent
        import pytest as _pytest
        _pytest.skip("flagged.html not built")
    text = path.read_text(encoding="utf-8")
    assert "F-2026-11-19-08" in text
    assert "F-2026-11-19-09" in text


def test_gamecentre_page_is_built_and_registered():
    path = ROOT / "gamecentre.html"
    assert path.exists(), "gamecentre.html must ship (rendered by pipeline/render_gamecentre.py)"
    text = path.read_text(encoding="utf-8")
    assert "Official game centre &amp; Game Books" in text or "Official game centre & Game Books" in text
    # the page must be in exactly one of its two documented states: waiting for
    # the first week-selecting capture, or publishing captured fixtures.  (A
    # state-dependent pin on the first wording alone would go red the moment
    # the runner commits real evidence — the stale-pin defect this repo has
    # already hit twice.)
    waiting = "No week-selecting capture has been committed yet" in text
    publishing = "captured fixtures — venue as printed" in text
    assert waiting != publishing, "exactly one capture state must render"


# --------------------------------------------------------------------------- #
# GC-integration — real committed captures, not synthetic text only
# --------------------------------------------------------------------------- #
def _real_book_text() -> str:
    import gzip
    path = ROOT / "data/evidence/official_games/gamebooks/commanders-at-giants-2026-reg-10.p1.txt.gz"
    if not path.exists():          # pragma: no cover - capture absent
        import pytest as _pytest
        _pytest.skip("committed Game Book capture absent")
    return gzip.decompress(path.read_bytes()).decode("utf-8", "replace")


def test_real_game_book_yields_the_full_printed_lineup():
    """The captured PDF pads ``WR     14 A.Williams`` and prints the four-letter
    position ``EDGE``; both shapes must parse to four printed columns and 44
    readable starter cells (the grid holds 11 per column).  Before the fix the
    whole captured week parsed as ``lineup_unreadable`` — 0 starters."""
    bk = og.parse_game_book(_real_book_text())
    rows = og.parse_lineup_rows(bk["lineups"])
    good = [r for r in rows if r["column"] >= 0 and r["player"]]
    assert len(good) == 44, f"expected 44 printed starters, got {len(good)}"
    assert {r["column"] for r in good} == {0, 1, 2, 3}
    assert all(r["position"] and r["jersey"] for r in good)


def test_real_game_book_identification_strip_parses_cleanly():
    """Date, matchup and start time share ONE printed line in the real PDF
    (``Date: …  Club at Club  Start Time: …``) with the venue on the next.
    Each field must come back on its own, not swallowed by its neighbour."""
    bk = og.parse_game_book(_real_book_text())
    assert bk["away_as_printed"] == "Washington Commanders"
    assert bk["home_as_printed"] == "New York Giants"
    assert "11/12/2026" in bk["date_as_printed"]
    assert "8:15 PM" in bk["start_time_as_printed"]
    assert "MetLife Stadium" in bk["venue_as_printed"]


def test_synthetic_book_layout_still_parses():
    """The own-line synthetic layout (repository fixtures) must keep working:
    the combined-line form is preferred, not exclusive."""
    got = og.parse_game_book(GAME_BOOK_TEXT)
    assert got["away_as_printed"] == "San Francisco 49ers"
    assert got["home_as_printed"] == "Dallas Cowboys"
    assert got["date_as_printed"] == "Sunday, 11/15/2026"
    assert got["start_time_as_printed"] == "3:25 PM CST"


def test_game_centre_payload_rejects_a_non_gamebook_pdf():
    """The page for an unplayed fixture references the league's Record & Fact
    Book PDF; only ``/gamecenter/`` links may become a Game Book URL (the
    2026-11-19 capture stored thirteen future games as 'captured' because of
    the looser match)."""
    from pipeline.official_payload import parse_game_centre_info
    fact_book = ("https://static.www.nfl.com/league/apps/league-site/"
                 "media-guides/2026/2026-Record-and-Fact-Book.pdf")
    html_only_fact = f'<html><body><a href="{fact_book}">media guide</a></body></html>'
    info = parse_game_centre_info(html_only_fact)
    assert info["gamebook_url"] == "", info["gamebook_url"]
    real = ("https://static.www.nfl.com/image/upload/v1794570519/"
            "gamecenter/ab5828d9-4feb-11f1-abca-2c54536568a9.pdf")
    html_real = f'<html><body><a href="{fact_book}">guide</a><a href="{real}">book</a></body></html>'
    info = parse_game_centre_info(html_real)
    assert info["gamebook_url"] == real, info["gamebook_url"]


def test_fail_loud_pins_accept_the_real_capture_and_reject_the_defects():
    """The REQ-63 helpers: a book must name the fixture and the week; a date
    line must print the league's own M/D/YYYY."""
    from fetch_official_games import (book_matches_fixture, book_week_slug,
                                      date_fragment_printed)
    was_nyg = dict(away_as_printed="Washington Commanders",
                   home_as_printed="New York Giants")
    assert book_matches_fixture(was_nyg, "commanders-at-giants-2026-reg-10") == ""
    assert book_matches_fixture(was_nyg, "colts-at-texans-2026-reg-11") != ""
    assert book_matches_fixture(dict(away_as_printed="", home_as_printed=""),
                                "commanders-at-giants-2026-reg-10") != ""
    assert book_week_slug("commanders-at-giants-2026-reg-10", "10")
    assert not book_week_slug("commanders-at-giants-2026-reg-10", "9")
    assert date_fragment_printed("Thursday, 11/12/2026")
    assert not date_fragment_printed("no date here")


# --------------------------------------------------------------------------- scores
# The fixture-set cross-check between the schedule page and the scores page
# (runs 44555092023 / 44556979069, 2026-11-19): the scores page for week 9 and
# week 10 also links every week-11 fixture, and the naive whole-page set
# equality rejected two documents that agree about the requested week.  Each
# test below plants the page shape and then mutates one side, so a comparison
# that was inverted or disabled would fail here.

def _scores_page(slugs: list[str]) -> str:
    return ("<html><body>" + "".join(
        f'<a href="https://www.nfl.com/games/{s}">game</a>' for s in slugs) +
        "</body></html>")


def test_scores_crosscheck_ignores_other_week_links_the_page_also_prints():
    from fetch_official_games import scores_week_diff
    sched = {"a-at-b-2026-reg-9", "c-at-d-2026-reg-9"}
    # measured shape: the week-9 scores page carries the week-9 fixtures AND
    # every week-11 fixture (13 slugs in the real failure annotation).
    html = _scores_page(["a-at-b-2026-reg-9", "c-at-d-2026-reg-9",
                         "x-at-y-2026-reg-11", "p-at-q-2026-reg-11"])
    only_sched, only_scores, other = scores_week_diff(sched, html, 9)
    assert only_sched == [] and only_scores == []
    assert other == ["p-at-q-2026-reg-11", "x-at-y-2026-reg-11"]


def test_scores_crosscheck_still_fails_when_a_fixture_is_missing():
    from fetch_official_games import scores_week_diff
    sched = {"a-at-b-2026-reg-9", "c-at-d-2026-reg-9"}
    # mutation: the scores page drops one week-9 fixture
    html = _scores_page(["a-at-b-2026-reg-9", "x-at-y-2026-reg-11"])
    only_sched, only_scores, other = scores_week_diff(sched, html, 9)
    assert only_sched == ["c-at-d-2026-reg-9"]
    assert only_scores == []
    assert other == ["x-at-y-2026-reg-11"]


def test_scores_crosscheck_still_fails_on_an_extra_same_week_fixture():
    from fetch_official_games import scores_week_diff
    sched = {"a-at-b-2026-reg-9"}
    # mutation: the scores page prints a week-9 fixture the schedule does not
    html = _scores_page(["a-at-b-2026-reg-9", "e-at-f-2026-reg-9"])
    only_sched, only_scores, other = scores_week_diff(sched, html, 9)
    assert only_sched == []
    assert only_scores == ["e-at-f-2026-reg-9"]


def test_scores_crosscheck_fails_loud_when_the_page_served_another_week():
    from fetch_official_games import scores_week_diff
    sched = {"a-at-b-2026-reg-9", "c-at-d-2026-reg-9"}
    # the scores URL ignored the week: only week-11 fixtures come back, so
    # every schedule fixture is missing from the page (the pin must fire —
    # ignoring other-week links must not turn a wrong-week page into a pass).
    html = _scores_page(["x-at-y-2026-reg-11", "p-at-q-2026-reg-11"])
    only_sched, only_scores, other = scores_week_diff(sched, html, 9)
    assert only_sched == ["a-at-b-2026-reg-9", "c-at-d-2026-reg-9"]
    assert only_scores == []
    assert len(other) == 2


def test_scores_crosscheck_treats_an_unstamped_games_link_as_comparable():
    from fetch_official_games import scores_week_diff
    # A /games/ link the league's slug does not stamp with a week cannot be
    # attributed to another week, so it stays in the comparison: if it is not
    # on the schedule, the pin fires rather than the link being ignored.
    sched = {"a-at-b-2026-reg-9"}
    html = _scores_page(["a-at-b-2026-reg-9", "some-promo-game"])
    only_sched, only_scores, other = scores_week_diff(sched, html, 9)
    assert only_sched == []
    assert only_scores == ["some-promo-game"]
    assert other == []


def test_scores_crosscheck_attributes_preseason_and_postseason_slugs():
    from fetch_official_games import scores_week_diff, slug_week
    assert slug_week("a-at-b-2026-pre-2") == 2
    assert slug_week("a-at-b-2026-post-1") == 1
    assert slug_week("commanders-at-giants-2026-reg-10") == 10
    assert slug_week("no-week-stamp") is None
    # a score strip showing next week's preseason game is as foreign to this
    # week's fixture set as a regular-season slug from another week
    sched = {"a-at-b-2026-pre-1"}
    html = _scores_page(["a-at-b-2026-pre-1", "c-at-d-2026-pre-2"])
    only_sched, only_scores, other = scores_week_diff(sched, html, 1)
    assert only_sched == [] and only_scores == []
    assert other == ["c-at-d-2026-pre-2"]
