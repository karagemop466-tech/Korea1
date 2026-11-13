"""T41 guards: a forward ticket may settle only from an official NFL.com final.

These tests exist because the failure mode is silent. If settlement ever accepts a community
mirror, or rounds an unsettled ticket into a win, the site would publish a number that looks
authoritative and is not. Each test is written so that it fails on that specific mistake.

The settlement arithmetic itself is owned by `pipeline/forward_grade.py` and pinned by
`tests/test_forward_ledger.py`; nothing here re-implements it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

import forward_grade as fg  # noqa: E402

FWD = ROOT / "data" / "forward"


def _official() -> pd.DataFrame:
    return pd.read_csv(FWD / "official_results.csv", dtype=str, keep_default_na=False)


# --------------------------------------------------------------------------- official gate
def test_settled_game_score_matches_the_official_row():
    """The published settlement must equal the official results file, digit for digit."""
    o = _official()
    r = o[o.game_id == "2026_10_WAS_NYG"]
    assert len(r) == 1, "the official result for the first settled game must exist exactly once"
    r = r.iloc[0]
    assert (r.away_team, int(r.away_score)) == ("WAS", 24)
    assert (r.home_team, int(r.home_score)) == ("NYG", 21)
    assert r.status_on_page == "Final"
    assert r.official_url.startswith("https://www.nfl.com/"), "a settlement source must be nfl.com"


def test_official_finals_only_accept_nfl_urls():
    """`official_finals()` must ignore any row whose URL is not an official NFL.com page."""
    real = fg.OFFICIAL
    tmp = FWD / "_test_official_results.csv"
    df = _official()
    df.loc[df.game_id == "2026_10_WAS_NYG", "official_url"] = "https://example.com/mirror"
    df.to_csv(tmp, index=False)
    try:
        fg.OFFICIAL = tmp
        finals = fg.official_finals()
        assert "2026_10_WAS_NYG" not in finals, "a non-NFL URL must not settle a game"
    finally:
        fg.OFFICIAL = real
        tmp.unlink(missing_ok=True)


def test_non_final_status_never_settles():
    """A game the official page does not call 'Final' must not produce a score."""
    real = fg.OFFICIAL
    tmp = FWD / "_test_official_results.csv"
    df = _official()
    df.loc[df.game_id == "2026_10_WAS_NYG", "status_on_page"] = "In Progress"
    df.to_csv(tmp, index=False)
    try:
        fg.OFFICIAL = tmp
        assert "2026_10_WAS_NYG" not in fg.official_finals()
    finally:
        fg.OFFICIAL = real
        tmp.unlink(missing_ok=True)


# --------------------------------------------------------------------------- graded output
def test_every_graded_pick_has_a_status_and_settled_ones_have_numbers():
    picks = pd.read_csv(FWD / "graded_picks.csv", dtype=str, keep_default_na=False)
    assert set(picks.status) <= {"OFFICIAL", "PROVISIONAL", "OPEN", "VOID", "CONFLICT"}
    settled = picks[picks.status == "OFFICIAL"]
    assert len(settled) > 0, "this test is meaningless once the first game settles; keep it honest"
    for col in ("outcome", "pnl", "pnl_stress"):
        assert (settled[col].str.strip() != "").all(), f"settled picks must carry {col}"
    open_ = picks[picks.status == "OPEN"]
    for col in ("outcome", "pnl", "pnl_stress"):
        assert (open_[col].str.strip() == "").all(), "an OPEN pick must never carry an outcome"


def test_no_pick_is_settled_without_an_official_result():
    """The core rule: status OFFICIAL implies an official row exists for that game."""
    finals = fg.official_finals()
    picks = pd.read_csv(FWD / "graded_picks.csv", dtype=str, keep_default_na=False)
    for r in picks[picks.status == "OFFICIAL"].to_dict("records"):
        for gid in r["game_ids"].split("|"):
            assert gid in finals, f"{r['pick_id']} is OFFICIAL but {gid} has no official final"


def test_was_nyg_pick_outcomes_are_arithmetically_correct():
    """Hand-checked: WAS won 24-21, total 45, home team NYG, frozen lines 2.5 and 40.5."""
    picks = pd.read_csv(FWD / "graded_picks.csv", dtype=str, keep_default_na=False)
    p = picks[picks.pick_id.isin(["1-0", "1-8", "1-19", "1-43"])].set_index("pick_id")
    # NYG +2.5 lost by 3 -> LOSS
    assert float(p.at["1-0", "outcome"]) == 0.0
    # 45 points over a 40.5 total -> WIN
    assert float(p.at["1-8", "outcome"]) == 1.0
    assert float(p.at["1-19", "outcome"]) == 1.0
    # 45 points under a 40.5 total -> LOSS
    assert float(p.at["1-43", "outcome"]) == 0.0
    # a win at -118 returns decimal 1.847458 - 1
    assert abs(float(p.at["1-8", "pnl"]) - (1.847458 - 1.0)) < 1e-5
    assert float(p.at["1-0", "pnl"]) == -1.0


def test_settle_pick_returns_none_while_any_leg_is_unplayed():
    legs = [{"market": "SPREAD", "side": "home", "line": -2.5, "price": -110.0, "game_id": "A"},
            {"market": "TOTAL", "side": "over", "line": 44.5, "price": -110.0, "game_id": "B"}]
    assert fg.settle_pick(legs, {"A": (24, 21)}) is None, "one unfinished leg must not settle a ticket"
    assert fg.settle_pick(legs, {"A": (24, 21), "B": (20, 27)}) is not None


# --------------------------------------------------------------------------- scoreboard
def test_no_verdict_and_no_interim_significance_before_the_horizon():
    sb = pd.read_csv(FWD / "scoreboard.csv", dtype=str, keep_default_na=False)
    not_reached = sb[~sb.horizon_reached.astype(str).str.lower().isin(["true", "1"])]
    assert (not_reached.verdict == "NO VERDICT").all()
    for col in ("p_raw", "p_holm"):
        assert (not_reached[col].str.strip() == "").all(), \
            f"{col} must stay blank until the horizon is reached"


def test_settlement_source_for_each_graded_card_is_official():
    cards = pd.read_csv(FWD / "graded_cards.csv", dtype=str, keep_default_na=False)
    settled = cards[cards.status == "OFFICIAL"]
    assert len(settled) > 0
    for r in settled.to_dict("records"):
        assert r["official_url"].startswith("https://www.nfl.com/"), \
            f"{r['game_id']} settled from a non-official URL"


# --------------------------------------------------------------------------- page
def test_forward_page_states_that_nothing_is_validated():
    html = (ROOT / "forward.html").read_text()
    assert "NO VERDICT" in html
    assert "no guaranteed returns" in html.lower() or "Research and education only" in html
    # the page must not print a headline profit or a validated badge
    assert "VALIDATED</" not in html.replace("NOT VALIDATED", "")
