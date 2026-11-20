"""Tests for the per-team view and the 'No Injuries Reported' parser fix.

Session `arena/46f0a137-korea1`, 2026-11-20.

What these pin:
* exactly one row per NFL club (32), none invented, none dropped;
* the net injury count is Out + Doubtful + Questionable, computed from the 2026-11-18 capture;
* the four clubs re-read line by line on 2026-11-20 keep their row counts (57 rows);
* a club with no committed depth chart (Houston) shows blanks, not "none flagged";
* every replacement the page names is a player the club's own depth data lists in that slot;
* the parser keeps a club whose block reads "No Injuries Reported" (it used to drop it silently).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import fetch_injuries  # noqa: E402

VIEW = ROOT / "assets" / "data" / "team_view.csv"
SLOTS = ROOT / "data" / "availability" / "slot_status.csv"
INJ = ROOT / "data" / "availability" / "injuries.csv"

ALL_32 = {"ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB",
          "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
          "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS"}


def _rows():
    return list(csv.DictReader(VIEW.open(encoding="utf-8")))


def test_one_row_per_nfl_club():
    rows = _rows()
    clubs = [r["club"] for r in rows]
    assert len(clubs) == 32
    assert len(set(clubs)) == 32
    assert set(clubs) == ALL_32


def test_bye_clubs_are_blank_not_zero():
    by = {r["club"]: r for r in _rows()}
    for club in ("CHI", "DEN", "PHI", "TB"):
        assert by[club]["official_report_status"].startswith("Not on the report"), club
        for col in ("players_listed", "out", "doubtful", "questionable", "net_injury_count"):
            assert by[club][col] == "", (club, col)


def test_net_injury_count_is_out_plus_doubtful_plus_questionable():
    for r in _rows():
        if r["net_injury_count"] == "":
            continue
        net = int(r["out"]) + int(r["doubtful"]) + int(r["questionable"])
        assert int(r["net_injury_count"]) == net, r["club"]


def test_counts_match_the_2026_11_18_capture():
    inj = list(csv.DictReader(INJ.open(encoding="utf-8")))
    by = {r["club"]: r for r in _rows()}
    for club in ALL_32:
        team = "LA" if club == "LAR" else club
        rows = [x for x in inj if x["team"] == team]
        if not rows:
            continue
        assert int(by[club]["players_listed"]) == len(rows), club
        assert int(by[club]["out"]) == sum(x["game_status"] == "Out" for x in rows), club


def test_four_clubs_rechecked_live_keep_their_row_counts():
    # Typed from the live official page on 2026-11-20 (see team_view.LIVE_REREAD): 57 rows total.
    by = {r["club"]: r for r in _rows()}
    expected = {"BAL": 10, "CIN": 9, "LAC": 19, "DAL": 19}
    for club, n in expected.items():
        assert int(by[club]["players_listed"]) == n, club
        assert by[club]["live_reread_2026_11_20"].startswith("Matches the live page"), club


def test_houston_has_no_invented_starters():
    hou = next(r for r in _rows() if r["club"] == "HOU")
    assert hou["depth_slots_published"] == ""
    assert hou["starters_out_first_listed"] == ""
    assert hou["starters_out_detail"] == ""
    assert hou["replacements_named"] == ""


def test_every_replacement_is_a_player_the_depth_chart_lists():
    slots = list(csv.DictReader(SLOTS.open(encoding="utf-8")))
    listed = {}
    for s in slots:
        team = "LAR" if s["team"] == "LA" else s["team"]
        if s["next_listed"]:
            listed.setdefault(team, set()).add(s["next_listed"])
    for r in _rows():
        if not r["replacements_named"]:
            continue
        for part in r["replacements_named"].split("; "):
            name = part.split(" (")[0]
            assert name in listed.get(r["club"], set()), (r["club"], name)


def test_starters_out_never_exceed_the_slots_published():
    for r in _rows():
        if r["depth_slots_published"] == "":
            continue
        assert int(r["starters_out_first_listed"]) <= int(r["depth_slots_published"]), r["club"]


def test_every_row_carries_an_official_source_url():
    for r in _rows():
        assert r["injury_source_url"].startswith("https://www.nfl.com/"), r["club"]
        assert r["schedule_source_url"].startswith("https://www.nfl.com/"), r["club"]


def test_parser_keeps_a_no_injuries_reported_club():
    # Synthetic page in the same layout as the official capture: a club whose block says
    # "No Injuries Reported" must come back in noreport_teams, not vanish.
    text = "\n".join([
        "## MONDAY, NOVEMBER 16TH",
        "8:15 PMEST",
        "LAC Chargers (1-8)",
        "BAL Ravens (4-6)",
        "Chargers",
        "No Injuries Reported",
        "Ravens",
        "| Player | Position | Injuries | Practice Status | Game Status |",
        "| --- | --- | --- | --- | --- |",
        "| [Jaylinn Hawkins](https://www.nfl.com/players/jaylinn-hawkins/) | S | Knee | "
        "Limited Participation in Practice | Out |",
    ])
    games, rows, name_map, noreport = fetch_injuries.parse_markdown(text)
    assert noreport == ["LAC"]
    assert [r["team"] for r in rows] == ["BAL"]
    assert rows[0]["game_status"] == "Out"
