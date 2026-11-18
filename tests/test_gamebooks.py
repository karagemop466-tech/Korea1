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
