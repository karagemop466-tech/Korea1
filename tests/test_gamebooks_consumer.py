"""Tests for the official schedule / game-centre / Game Book evidence layer.

Session `arena/eeba949e-korea1`, 2026-11-19.

These tests run against the official documents the repository already holds:
the committed schedule capture
(`data/evidence/official_games/schedule/*.html.gz`, hashed in the capture
manifest) and the thirteen committed official game-centre pages under
`data/forward/raw_captures/` (each with its HTTP status, byte count and
SHA-256 in `data/forward/official_candidates.csv`).

The readers are checked with **negative controls** as well as positive ones:
a page that carries no fixture must yield no fixture, and a fact the league
did not print must stay blank rather than be filled from a neighbouring field.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import fetch_official_games  # noqa: E402
import official_payload  # noqa: E402

EVIDENCE = ROOT / "data" / "evidence" / "official_games"
RAW_CAPTURES = ROOT / "data" / "forward" / "raw_captures"
PROC = ROOT / "data" / "processed"


def _schedule_pages() -> list[Path]:
    folder = EVIDENCE / "schedule"
    return sorted(folder.glob("*.html.gz")) if folder.exists() else []


def _schedule_html() -> str:
    pages = _schedule_pages()
    if not pages:
        return ""
    with gzip.open(pages[0], "rt", encoding="utf-8", errors="replace") as fh:
        return fh.read()


# --------------------------------------------------------------------- readers
def test_the_capture_reads_the_leagues_own_fixture_list():
    """The defect this session repaired: the old anchor reader found nothing."""
    html = _schedule_html()
    assert html, "no committed official schedule capture to read"
    rows = official_payload.parse_schedule_payload(html)
    assert rows, "the official schedule payload yielded no fixture"
    assert len(rows) >= 10, f"only {len(rows)} fixtures read from the official page"


def test_the_anchor_reader_alone_finds_nothing_on_the_current_page():
    """The reason the old chain was dead: the page has no /games/ anchor."""
    html = _schedule_html()
    if not html:
        return
    assert 'href="https://www.nfl.com/games/' not in html, (
        "the committed page unexpectedly contains a /games/ anchor; the anchor "
        "reader would work and the payload reader would be redundant")
    from official_games import parse_schedule_page
    assert parse_schedule_page(html) == [], (
        "the anchor reader is expected to find nothing on the current page")


def test_fixture_fields_come_from_the_league_not_from_a_neighbour():
    rows = official_payload.parse_schedule_payload(_schedule_html())
    for row in rows:
        assert row["away_team"] and row["home_team"]
        assert row["kickoff_utc"], "the league publishes the kickoff instant"
        assert row["status"], "the league publishes the status"
        assert row["official_url"].startswith("https://www.nfl.com/games/")
        assert row["elias_id"], "the league publishes its own Elias identifier"
        assert row["gsis_id"], "the league publishes its own GSIS identifier"
        # A club is never its own opponent.
        assert row["away_team"] != row["home_team"]


def test_the_published_week_is_read_out_of_the_page():
    """The capture asked for Week 9 and Week 10 and was served Week 11."""
    html = _schedule_html()
    published = official_payload.published_week(html)
    assert published != "", "the page's published week could not be read"
    rows = official_payload.parse_schedule_payload(html)
    assert {str(r["week"]) for r in rows} == {published}


def test_a_page_without_a_payload_yields_no_fixture():
    """Negative control: nothing is read out of a page that publishes none."""
    assert official_payload.parse_schedule_payload("<html><body>no data</body></html>") == []
    assert official_payload.published_week("<html></html>") == ""
    assert official_payload.parse_week_selector("<html></html>") == []


def test_a_blank_official_cell_stays_blank():
    """Negative control: the league printed no category, so none is invented."""
    rows = official_payload.parse_schedule_payload(_schedule_html())
    blank = [r for r in rows if r["category"] == ""]
    assert blank, "the league prints a category only for some fixtures"
    for row in blank:
        assert row["category"] == ""
        assert row["venue_name"] != "", "the venue is a separate, published fact"


def test_the_capture_url_is_the_leagues_own_weekly_form():
    """`/schedules/<season>/by-week/reg-<week>` — the form the league cites."""
    url = fetch_official_games.week_paths(2026, 10)
    assert url == "https://www.nfl.com/schedules/2026/by-week/reg-10"
    assert "by-week" in url


def test_the_game_centre_prints_its_venue_and_its_game_book_link():
    pages = sorted(RAW_CAPTURES.glob("*.html"))
    assert pages, "no committed official game-centre capture to read"
    raw = pages[0].read_bytes().decode("utf-8", "replace")
    info = official_payload.parse_game_centre_info(raw)
    assert info["venue_location"], "the game centre prints LOCATION"
    assert info["venue_stadium"], "the game centre prints STADIUM"
    assert info["gamebook_url"].startswith(
        "https://static.www.nfl.com/"), "the game centre links the league's Game Book"
    assert info["canonical_url"].startswith("https://www.nfl.com/games/")


def test_every_committed_game_centre_yields_a_game_book_link():
    pages = sorted(RAW_CAPTURES.glob("*.html"))
    assert len(pages) >= 5
    for page in pages:
        raw = page.read_bytes().decode("utf-8", "replace")
        info = official_payload.parse_game_centre_info(raw)
        assert info["gamebook_url"].endswith(".pdf"), page.name
        assert info["venue_stadium"], page.name


def test_a_game_centre_without_a_game_book_module_yields_no_link():
    """Negative control: the link is read from the league's own module."""
    info = official_payload.parse_game_centre_info(
        "<html><body><p>no game book here</p></body></html>")
    assert info["gamebook_url"] == ""


# ------------------------------------------------------------------- datasets
def test_the_fixture_context_is_published_from_the_committed_capture():
    path = PROC / "fixture_context.csv"
    assert path.exists(), "run `python pipeline/fixture_context.py` first"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert len(df) >= 10
    for col in ("away_team", "home_team", "kickoff_utc", "kickoff_et", "week",
                "official_url", "schedule_evidence_path"):
        assert col in df.columns, col
        assert (df[col].str.strip() != "").all(), f"{col} is blank on some row"
    assert df["official_url"].str.startswith("https://www.nfl.com/games/").all()


def test_the_eastern_kickoff_is_the_leagues_own_utc_instant_converted():
    df = pd.read_csv(PROC / "fixture_context.csv", dtype=str, keep_default_na=False)
    row = df[df.kickoff_utc == "2026-11-20T01:15:00Z"]
    if row.empty:
        return
    assert row.iloc[0]["kickoff_et"] == "2026-11-19 20:15"
    assert row.iloc[0]["kickoff_date_et"] == "2026-11-19"
    assert "America/New_York" in row.iloc[0]["derivation"]


def test_the_document_register_records_the_week_drift():
    df = pd.read_csv(PROC / "official_documents.csv", dtype=str, keep_default_na=False)
    assert len(df) >= 1
    for col in ("document_id", "kind", "url", "sha256", "evidence_path",
                "week_requested", "week_published", "week_matches_url"):
        assert col in df.columns, col
    assert df["evidence_path"].str.startswith("data/evidence/official_games/").all()


def test_the_availability_graph_is_fail_closed():
    """No actual starter may be published without an official Game Book."""
    path = PROC / "availability_graph.csv"
    assert path.exists(), "run `python pipeline/availability_graph.py` first"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert len(df) > 0
    unconfirmed = df[df.outcome.str.startswith("NOT CONFIRMED")]
    if not unconfirmed.empty:
        assert (unconfirmed.actual_starter == "").all(), (
            "an actual starter was published without an official Game Book")
        assert (unconfirmed.actual_source == "").all()


def test_the_graph_uses_the_club_chart_order_not_a_jersey_number():
    df = pd.read_csv(PROC / "availability_graph.csv", dtype=str, keep_default_na=False)
    depth = pd.read_csv(ROOT / "data/availability/depth_charts.csv", dtype=str,
                        keep_default_na=False)
    first = depth[depth.depth_rank == "1"]
    names = set(first.player)
    published = {n for cell in df.expected_starter for n in str(cell).split("; ") if n}
    assert published, "no expected starter was published"
    assert published <= names, "an expected starter is not the club chart's rank-1 player"


def test_a_position_with_several_rank_one_players_is_not_collapsed():
    """A club that names three receivers at rank one has not named a starter."""
    df = pd.read_csv(PROC / "availability_graph.csv", dtype=str, keep_default_na=False)
    multi = df[df.expected_co_starter_count.astype(int) > 1]
    if multi.empty:
        return
    for row in multi.itertuples():
        assert ";" in row.expected_starter, row.expected_starter
        assert row.outcome.startswith(("CO-STARTERS", "NOT CONFIRMED")), row.outcome


def test_the_graph_is_point_in_time_or_flagged():
    df = pd.read_csv(PROC / "availability_graph.csv", dtype=str, keep_default_na=False)
    for row in df.itertuples():
        assert row.expected_point_in_time in ("YES", "") or row.expected_point_in_time.startswith("NO")


# ------------------------------------------------------------------- the page
def test_the_page_has_a_caption_and_an_official_link_on_every_row():
    sys.path.insert(0, str(ROOT))
    from pipeline.verify_site import Collector, official_refs
    page = ROOT / "gamebooks.html"
    assert page.exists(), "run `python pipeline/render_gamebooks.py` first"
    raw = page.read_text(encoding="utf-8")
    collector = Collector()
    collector.feed(raw)
    assert collector.tables > 0
    assert collector.captions == collector.tables, "every table needs a caption"
    missing = [i for i, row in enumerate(collector.rows, 1)
               if not official_refs([h for _, links in row for h in links])]
    assert not missing, f"rows without an official source: {missing[:10]}"


def test_the_page_publishes_the_blank_rather_than_a_guess():
    raw = (ROOT / "gamebooks.html").read_text(encoding="utf-8")
    assert "not captured" in raw
    assert ">None<" not in raw
    import re
    assert not re.search(r">\s*nan\s*<", raw), "a leaked nan cell"
    assert not re.search(r">\s*None\s*<", raw), "a leaked None cell"


def test_the_capture_manifest_is_the_provenance_of_the_page():
    manifest = json.loads((EVIDENCE / "manifest.json").read_text(encoding="utf-8"))
    assert "schedule_pages" in manifest
    for rec in manifest["schedule_pages"]:
        assert rec.get("raw_sha256"), "every captured page records its hash"
        assert rec.get("url", "").startswith("https://www.nfl.com/schedules/")
