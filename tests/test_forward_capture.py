"""The capture helper may propose a score; it may never write evidence.

These tests target the one dangerous property of `pipeline/forward_fetch_official.py`: it runs
unattended on a schedule, so a bug that writes `official_results.csv` would silently manufacture
official finals and start settling tickets. Everything here is offline and synthetic.

The extraction rules have never been run against real NFL.com HTML (the sandbox cannot reach
nfl.com), which is exactly why promotion of a proposal is kept as a separate reviewed step.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import forward_fetch_official as ff  # noqa: E402

FINAL_PAGE = ('<div class="t">WAS</div><div class="s">24</div>'
              '<div class="t">NYG</div><div class="s">21</div><div>Final</div>')
UNPLAYED_PAGE = '<div>NE</div><div>5-4</div><div>DET</div><div>6-2</div><div>Nov 15 9:30 AM</div>'
GAME = {"game_id": "T1", "away_team": "WAS", "home_team": "NYG", "official_url": "https://www.nfl.com/games/t"}


def test_proposes_a_score_only_when_the_page_says_final():
    r = ff.propose(GAME, FINAL_PAGE)
    assert r["extraction_status"] == "PROPOSED"
    assert (r["candidate_away_score"], r["candidate_home_score"], r["final_marker_found"]) == (24, 21, 1)


def test_does_not_propose_a_score_for_an_unplayed_game():
    r = ff.propose(GAME, UNPLAYED_PAGE)
    assert r["extraction_status"] == "NOT_FINAL"
    assert r["candidate_away_score"] == "" and r["candidate_home_score"] == ""


def test_does_not_propose_from_a_page_with_no_marker():
    r = ff.propose(GAME, "<html>maintenance</html>")
    assert r["candidate_away_score"] == "" and r["extraction_status"] == "NOT_FINAL"


def test_never_writes_the_evidence_file(tmp_path, monkeypatch):
    """Point the module at a scratch directory and prove official_results.csv is untouched."""
    fwd = tmp_path / "forward"
    fwd.mkdir()
    (fwd / "official_schedule.csv").write_text(
        "game_id,away_team,home_team,official_url\nT1,WAS,NYG,https://www.nfl.com/games/t\n")
    evidence = fwd / "official_results.csv"
    evidence.write_text("game_id,status_on_page,official_url\n")
    before = evidence.read_bytes()

    monkeypatch.setattr(ff, "FWD", fwd)
    monkeypatch.setattr(ff, "RAW", fwd / "raw_captures")
    monkeypatch.setattr(ff, "CANDIDATES", fwd / "official_candidates.csv")
    monkeypatch.setattr(ff, "http_get", lambda url, tries=2: (200, FINAL_PAGE.encode(), ""))

    monkeypatch.setattr(sys, "argv", ["forward_fetch_official.py"])
    assert ff.main() == 0

    assert evidence.read_bytes() == before, "the capture step must never append to official_results.csv"
    cand = list(csv.DictReader((fwd / "official_candidates.csv").open()))
    assert len(cand) == 1 and cand[0]["extraction_status"] == "PROPOSED"
    assert cand[0]["http_status"] == "200" and len(cand[0]["sha256"]) == 64


def test_games_needing_official_excludes_settled_and_non_nfl_rows(tmp_path, monkeypatch):
    fwd = tmp_path / "forward"
    fwd.mkdir()
    (fwd / "official_schedule.csv").write_text(
        "game_id,away_team,home_team,official_url\n"
        "A,AAA,BBB,https://www.nfl.com/games/a\n"
        "B,CCC,DDD,https://www.nfl.com/games/b\n"
        "C,EEE,FFF,https://www.nfl.com/games/c\n")
    (fwd / "official_results.csv").write_text(
        "game_id,status_on_page,official_url\n"
        "A,Final,https://www.nfl.com/games/a\n"
        "B,Final,https://example.com/mirror\n")          # mirror row must not count as settled
    monkeypatch.setattr(ff, "FWD", fwd)
    assert [g["game_id"] for g in ff.games_needing_official()] == ["B", "C"]
