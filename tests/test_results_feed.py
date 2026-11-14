"""Fail-closed tests for the R7-02 verified results feed."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import results_feed as rf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "data" / "results" / "results_feed.csv"
AUDIT = ROOT / "data" / "results" / "results_audit.csv"


@pytest.fixture(scope="module")
def feed():
    return pd.read_csv(FEED)


def test_tier_vocabulary_is_closed(feed):
    assert set(feed.tier.unique()) <= set(rf.TIERS)


def test_an_unverified_row_never_carries_a_score(feed):
    un = feed[feed.tier == rf.TIER_NONE]
    assert len(un) > 0
    assert un.away_score.isna().all() and un.home_score.isna().all()


def test_settlement_arithmetic_only_uses_official_scores(feed):
    ok = feed[feed.settleable == "YES"]
    assert ((ok.official_result - (ok.home_score - ok.away_score)).abs() < 1e-9).all()
    assert ((ok.official_total - (ok.home_score + ok.away_score)).abs() < 1e-9).all()


def test_nothing_is_dropped_for_lack_of_a_source(feed):
    """Every played game in the archive must appear, settled or not — plus the
    verified games that settled after the pin, which are labelled, not dropped."""
    g = pd.read_csv(ROOT / "data" / "raw" / "games.csv", low_memory=False)
    g["altid"] = (g.season.astype(str) + "_" + g.week.astype(str).str.zfill(2)
                  + "_" + g.away_team + "_" + g.home_team)
    played = set(g[g.home_score.notna() & g.away_score.notna()].altid)
    assert played <= set(feed.game_id), "a played game in the archive is missing from the feed"
    beyond = feed[feed.beyond_pin == "YES"]
    assert len(beyond) > 0
    assert not (set(beyond.game_id) & played), "a row labelled beyond_pin is in the pinned archive"


def test_every_verified_row_names_an_evidence_url(feed):
    ok = feed[feed.settleable == "YES"]
    assert ok.evidence_url.str.startswith("https://").all()
    assert ok.read_utc.ne("").all()


def test_blank_archive_cell_is_not_a_conflict():
    a = pd.read_csv(AUDIT)
    labels = set(a.agreement.unique())
    assert "ARCHIVE BLANK" in labels
    # and the specific defect this test guards: a NaN comparison must never be
    # reported as DIFFERENT
    diff = a[a.agreement == "DIFFERENT"]
    assert diff.archive_home.notna().all() and diff.archive_away.notna().all()


def test_game_book_tier_rows_are_the_ones_read_this_session(feed):
    book = feed[feed.tier == rf.TIER_BOOK]
    assert len(book) == 3
    assert set(book.game_id) == {r["game_id"] for r in rf.SESSION_READ_2026_11_14}
    for r in book.itertuples():
        assert r.evidence_url.endswith(".pdf")


def test_week10_result_matches_the_game_book_it_cites(feed):
    """WAS 24 - NYG 21, read from the Game Book score table."""
    r = feed[feed.game_id == "2026_10_WAS_NYG"].iloc[0]
    assert (int(r.away_score), int(r.home_score)) == (24, 21)
    assert int(r.official_total) == 45


def test_games_settled_after_the_pin_are_labelled(feed):
    """2026 weeks 8-10 settled after the pinned snapshot; the archive has no score
    for them, so they must carry an official tier and a beyond_pin flag."""
    b = feed[feed.beyond_pin == "YES"]
    assert b.season.eq(2026).all()
    assert b.tier.ne(rf.TIER_NONE).all()
    assert b.settleable.eq("YES").all()


def test_a_prior_session_score_is_carried_not_retyped(feed):
    prior = pd.read_csv(ROOT / "data" / "forward" / "official_results.csv", dtype=str, keep_default_na=False)
    prior = prior[prior.away_score.ne("")]
    m = feed[feed.tier == rf.TIER_PRIOR].merge(prior, on="game_id", suffixes=("", "_p"))
    assert len(m) > 0
    assert (m.away_score.astype(int) == m.away_score_p.astype(int)).all()
    assert (m.home_score.astype(int) == m.home_score_p.astype(int)).all()
