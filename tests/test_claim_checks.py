"""NR2 — the 2026-11-18 claim checks: the verbatim official reads must be real, and the comparison must
be capable of detecting a change (mutation control), not just report agreement.

These tests re-run the claim builder against the committed artefacts. They are the guard against the two
failure modes this project keeps hitting: a claim that was verified once and then went stale, and a checker
that prints a pass because it never actually compared anything.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from claim_checks_20261118 import (  # noqa: E402
    READS, build_claims, parse_injury_excerpt, parse_schedule_excerpt,
)

VERDICTS = {"MATCHES", "DIFFERS_SOURCE_MOVED", "DIFFERS_REPOSITORY_MOVED", "CONFIRMED", "SUPERSEDED",
            "CLOSED", "OPEN", "PARTLY", "PARTLY_MATCHES", "NOT_CHECKABLE", "EXPLAINED"}


@pytest.fixture(scope="module")
def claims() -> list[dict]:
    return build_claims()


def test_one_row_per_brief_claim(claims):
    assert len(claims) >= 14, "the 2026-11-18 brief states more claims than this register checks"
    ids = [c["claim_id"] for c in claims]
    assert len(ids) == len(set(ids))
    for c in claims:
        assert c["verdict"] in VERDICTS, c
        assert c["repo_evidence"], c
        assert c["note"], "every claim has to say what its value means"
        assert c["claim_as_written"], "the claim must be quoted, not paraphrased from memory"


def test_live_reads_cite_their_excerpt_and_time(claims):
    """A live value is only a live value if the verbatim read is committed and dated."""
    checked = [c for c in claims if c["live_value"]]
    assert checked, "no official re-read was registered at all"
    for c in checked:
        path = ROOT / c["live_evidence"]
        assert path.exists(), c["live_evidence"]
        text = path.read_text(encoding="utf-8")
        assert c["official_url"] in text, f"{c['claim_id']}: the excerpt does not carry the URL it cites"
        assert c["live_read_utc"].startswith("2026-11-18"), c["claim_id"]


def test_no_official_link_is_fabricated(claims):
    """Repository-only claims are not given a decorative official link to satisfy the row check."""
    for c in claims:
        if not c["live_value"] and not c["repo_value"].strip():
            assert c["official_url"] == "", c["claim_id"]


def test_the_lions_designations_are_not_blank_anymore(claims):
    by = {c["claim_id"]: c for c in claims}
    assert by["C-07"]["verdict"] == "CLOSED"
    for name in ("Kerby Joseph", "Cade Mays", "D.J. Reed"):
        assert f"{name} = Out" in by["C-07"]["live_value"]
        assert f"{name} = Out" in by["C-07"]["repo_value"]


def test_the_bye_explanation_is_derived_not_asserted(claims):
    """The coverage gap is only 'explained' if the missing clubs are exactly the bye clubs."""
    by = {c["claim_id"]: c for c in claims}
    missing = by["C-11"]["repo_value"].split("clubs with no row:")[1]
    missing = {t.strip() for t in missing.split(",")}
    games, byes = parse_schedule_excerpt(READS / "nfl_schedule_week10_2026_games_and_byes.md")
    assert {b["abbr"] for b in byes} == missing, "the bye list and the coverage gap no longer agree"
    assert by["C-11"]["verdict"] == "EXPLAINED"
    assert len(games) == 14, "the official Week 10 game count changed; the register text must follow"


def test_packers_numbers_are_stripped_but_retained(claims):
    by = {c["claim_id"]: c for c in claims}
    assert by["C-06"]["verdict"] == "CONFIRMED"
    assert "0 still have a leading number" in by["C-06"]["repo_value"]


def test_ravens_capture_agrees_with_the_live_chart(claims):
    by = {c["claim_id"]: c for c in claims}
    assert "Jacoby Brissett" in by["C-09"]["repo_value"]
    assert "Jacoby Brissett" in by["C-09"]["live_value"]
    assert "Lamar Jackson" not in by["C-09"]["repo_value"]


def test_detroit_table_comparison_can_detect_a_change(tmp_path):
    """Mutation control: alter one cell of the verbatim read and the parsed value must move.

    Without this, '9 of 9 rows agree' could be printed by a comparison that ignores the cells.
    """
    src = (READS / "nfl_injuries_week10_DET.md").read_text(encoding="utf-8")
    before = parse_injury_excerpt(READS / "nfl_injuries_week10_DET.md")
    assert len(before) == 9
    assert sum(1 for r in before if r["game"] == "Out") == 3

    mutated = src.replace("Knee | Did Not Participate In Practice | Out",
                          "Knee | Did Not Participate In Practice |")
    assert mutated != src, "the excerpt no longer has the shape the test mutates"
    path = tmp_path / "mutated.md"
    path.write_text(mutated, encoding="utf-8")
    after = parse_injury_excerpt(path)
    assert sum(1 for r in after if r["game"] == "Out") == 2, "the parser is not reading the game-status cell"


def test_schedule_excerpt_scores_are_parsed_exactly():
    games, _ = parse_schedule_excerpt(READS / "nfl_schedule_week10_2026_games_and_byes.md")
    assert {g["away"]: (g["away_score"], g["home"], g["home_score"]) for g in games}["Commanders"] == (
        24, "Giants", 21)
    assert all(g["url"].startswith("https://www.nfl.com/games/") for g in games)


def test_claim_csv_is_the_published_copy(tmp_path):
    """The page prints the CSV that ships, so the download and the table cannot diverge."""
    published = ROOT / "data/integration/claim_checks_2026_11_18.csv"
    assert published.exists()
    with open(published, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == len(build_claims())
    asset = ROOT / "assets/data/claim_checks_2026_11_18.csv"
    assert asset.exists() and asset.read_text(encoding="utf-8") == published.read_text(encoding="utf-8")
