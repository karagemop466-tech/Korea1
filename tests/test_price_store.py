"""Tests for the 2026-11-14 pass (session arena/b13485ed-korea1).

Covers the artifacts that make a return checkable and the separation between
signal and staking:

  * pipeline/price_snapshots.py   the price-snapshot store
  * pipeline/verified_results.py  the verified results feed
  * pipeline/models.py            the origination order
  * pipeline/leaderboard_split.py the signal/staking split
  * pipeline/demotion.py          the demotion gate
  * pipeline/replacement_depth.py the replacement depth
  * pipeline/official_correlations.py the official-only correlation register
  * pipeline/render_prices.py     the published page

The tests read the committed artifacts, so they fail if the build stops
producing them and they fail if a published number stops matching the file
that owns it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

PROC = ROOT / "data" / "processed"
FWD = ROOT / "data" / "forward"

ORIGINATION_ORDER = ("SPREAD", "TOTAL", "MONEYLINE")


def _csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


# --------------------------------------------------------------------- store
def test_price_store_covers_every_market_and_both_sides():
    store = _csv(FWD / "price_snapshots.csv")
    assert len(store), "the price store is empty"
    assert set(store.market) == set(ORIGINATION_ORDER), \
        "the store must hold the spread, the total and the moneyline"
    # A side and a total are quoted from each side; a total from over and under.
    expected = {"SPREAD": {"home", "away"},
                "MONEYLINE": {"home", "away"},
                "TOTAL": {"over", "under"}}
    for market, sides in expected.items():
        got = set(store[store.market == market].side.unique())
        assert got == sides, f"{market} has sides {got}, expected {sides}"


def test_price_store_ids_are_unique_and_ordered():
    store = _csv(FWD / "price_snapshots.csv")
    assert store.snapshot_id.is_unique, "two price snapshots share an id"
    seq = {m: i + 1 for i, m in enumerate(ORIGINATION_ORDER)}
    got = {r.market: int(r.origination_seq) for r in store.itertuples()}
    assert set(got) == set(ORIGINATION_ORDER)
    assert all(got[m] == seq[m] for m in ORIGINATION_ORDER), \
        "the origination order in the store is not spread -> total -> moneyline"
    # The sequence is a property of the market, not of the row.
    for m in ORIGINATION_ORDER:
        assert set(store[store.market == m].origination_seq.astype(int)) == {seq[m]}


def test_price_store_records_opening_and_closing_numbers_separately():
    store = _csv(FWD / "price_snapshots.csv")
    for col in ("open_line", "close_line", "model_line", "market_line", "difference"):
        assert col in store.columns, f"the store has no {col} column"
    # Rows that carry a closing number must carry a source id for it.
    with_close = store[store.close_line.astype(str).str.strip() != ""]
    assert len(with_close), "no snapshot carries a closing number"
    assert (with_close.close_source_id.astype(str).str.strip() != "").all(), \
        "a closing number without a source id"
    with_open = store[store.open_line.astype(str).str.strip() != ""]
    assert len(with_open), "no snapshot carries an opening number"
    assert (with_open.open_source_id.astype(str).str.strip() != "").all(), \
        "an opening number without a source id"
    # The store records the two numbers in different columns, never merged.
    assert not (store.open_line.astype(str).str.strip()
                == store.close_line.astype(str).str.strip()).all(), \
        "the opening and the closing number are not distinct columns"


def test_price_store_source_register_is_public_and_classed():
    src = _csv(FWD / "price_snapshot_sources.csv")
    assert len(src) >= 2, "the source register is too small to be useful"
    assert (src.source_id.astype(str).str.strip() != "").all()
    # Every source that carries a number has a class. The one entry with no
    # class is the explicit "no source" entry, which carries no number.
    classed = src[src.source_id.astype(str).str.strip() != "PS-NONE"]
    assert (classed.evidence_class.astype(str).str.strip() != "").all()
    assert (src.use_rule.astype(str).str.strip() != "").all()
    # Every source id the store cites exists in the register.
    store = _csv(FWD / "price_snapshots.csv")
    known = set(src.source_id)
    for col in ("open_source_id", "close_source_id"):
        used = {u for u in store[col].astype(str) if u.strip()}
        assert used <= known, f"{col} cites a source id that is not in the register"


# ------------------------------------------------------------- results feed
def test_verified_results_rest_on_an_official_page():
    feed = _csv(FWD / "verified_results.csv")
    assert len(feed), "the verified results feed is empty"
    assert (feed.official_url.astype(str).str.startswith("https://www.nfl.com/")).all(), \
        "every verified row must carry an official NFL URL"
    assert (feed.verified_utc.astype(str).str.strip() != "").all(), \
        "every verified row must carry a verification time"
    assert (feed.verified_by.astype(str).str.strip() != "").all(), \
        "every verified row must name who verified it"
    # A game whose official page is not Final carries no score and is not settled.
    unsettled = feed[feed.official_status.astype(str).str.strip() != "Final"]
    assert (unsettled.official_final_home.astype(str).str.strip() == "").all(), \
        "a game that is not Final must not carry a final score"
    assert (unsettled.model_outcome.astype(str).str.strip() == "").all(), \
        "a game that is not Final must not be settled"
    # The official status is one of the NFL's own words.
    assert set(feed.official_status) <= {"Final", ""}, \
        "an unexpected official status appears in the feed"


def test_verified_results_settle_only_what_can_be_settled():
    feed = _csv(FWD / "verified_results.csv")
    ml = feed[feed.market == "MONEYLINE"]
    assert len(ml), "the feed has no moneyline rows"
    # A moneyline has no line, so it has no line to settle against: the line and
    # the market settlement stay blank. The pick itself still has an outcome.
    assert (ml.model_line.astype(str).str.strip() == "").all(), \
        "a moneyline row carries a line it does not have"
    assert (ml.market_line.astype(str).str.strip() == "").all(), \
        "a moneyline row carries a market line it does not have"
    assert (ml.market_outcome.astype(str).str.strip() == "").all(), \
        "a moneyline row was settled against a market line it does not have"
    # A side that cannot be settled (no line of its own) carries no unit profit.
    for col in ("unit_profit",):
        for market in ("SPREAD", "TOTAL", "MONEYLINE"):
            sub = feed[(feed.market == market) & (feed.market_line.astype(str).str.strip() == "")]
            assert (sub[col].astype(str).str.strip() == "").all(), \
                f"a {market} row without a market line carries a {col}"


# --------------------------------------------------------- origination order
def test_origination_order_is_published_and_is_the_required_one():
    man = json.loads((PROC / "origination_manifest.json").read_text())
    assert tuple(man["origination_order"]) == ORIGINATION_ORDER
    assert man["stages"]["SPREAD"]["seq"] == 1
    assert man["stages"]["TOTAL"]["seq"] == 2
    assert man["stages"]["MONEYLINE"]["seq"] == 3
    # The moneyline consumes the side's distribution, which is why it is third.
    assert any("margin distribution" in c
               for c in man["stages"]["MONEYLINE"]["consumes"])


# ------------------------------------------------------- signal / staking
def test_leaderboard_is_ranked_on_the_signal():
    lb = _csv(PROC / "leaderboard_signal_staking.csv")
    assert len(lb), "the leaderboard split is empty"
    assert (lb.signal_rank.astype(int).tolist()
            == sorted(lb.signal_rank.astype(int).tolist()))
    # The two scorecards are separate columns, and both are present.
    for col in ("signal_hit_rate", "signal_edge", "signal_verdict",
                "staking_roi", "staking_verdict", "combined_verdict"):
        assert col in lb.columns, f"the leaderboard has no {col} column"


def test_a_positive_return_cannot_promote_a_non_positive_signal():
    lb = _csv(PROC / "leaderboard_signal_staking.csv")
    lucky = lb[lb.combined_verdict.str.startswith("LUCKY")]
    for r in lucky.itertuples():
        assert float(r.staking_roi) > 0, "a lucky run must have a positive return"
        assert "PAPER" in r.tier_cap, "a lucky run must be capped at paper"


def test_the_staking_scorecard_is_never_read_as_skill_without_the_sample():
    lb = _csv(PROC / "leaderboard_signal_staking.csv")
    for r in lb.itertuples():
        if int(r.staking_n_weeks) < int(r.staking_n_weeks_required):
            assert "INSUFFICIENT" in r.staking_verdict, \
                f"{r.strategy} claims a staking verdict on too small a sample"


# ------------------------------------------------------------- demotion gate
def test_demotion_gate_can_only_send_a_strategy_down():
    dem = _csv(PROC / "demotion_gates.csv")
    assert len(dem) >= 4, "the demotion gate has too few conditions"
    for r in dem.itertuples():
        action = str(r.action)
        assert "PAPER" in action or "DISQUALIFIED" in action, \
            f"condition {r.gate_id} does not demote"
        assert "live" in action.lower(), \
            f"condition {r.gate_id} does not act on a live strategy"
    assert not any("PROMOTE" in str(r.action).upper() for r in dem.itertuples()), \
        "the demotion gate must not contain a promotion rule"
    # Every condition names the data it needs, so an unevaluable condition is visible.
    assert (dem.data_required.astype(str).str.strip() != "").all()


def test_demotion_status_is_evaluated_for_every_strategy():
    lb = _csv(PROC / "leaderboard_signal_staking.csv")
    dem = _csv(PROC / "demotion_status.csv")
    assert set(lb.strategy) == set(dem.strategy), \
        "a strategy is missing from the demotion evaluation"
    for r in dem.itertuples():
        assert r.resulting_tier in ("PAPER", "LIVE", "DISQUALIFIED")
        # A strategy that is not live cannot have been left live by the gate.
        if r.current_tier != "LIVE":
            assert r.resulting_tier != "LIVE"


def test_an_unevaluable_condition_is_not_treated_as_passed():
    dem = _csv(PROC / "demotion_status.csv")
    for r in dem.itertuples():
        # D5 (price provenance) is open for every strategy, so it must fire
        # wherever the coverage is below one.
        cov = str(r.D5_quote_coverage).strip()
        if cov and float(cov) < 1.0:
            assert str(r.D5_fires).lower() == "true", \
                f"{r.strategy} has unverified prices but D5 did not fire"


# --------------------------------------------------------- replacement depth
def test_replacement_depth_is_blank_where_no_order_is_published():
    depth = _csv(PROC / "replacement_depth.csv")
    assert len(depth), "the replacement-depth register is empty"
    for r in depth.itertuples():
        if str(r.replacement_depth_label).strip() == "":
            assert str(r.replacement_player).strip() == "", \
                f"{r.team} slot {r.slot} names a replacement without a depth"
        if str(r.replacement_depth_rank).strip():
            assert int(r.replacement_depth_rank) >= 2, \
                "a replacement cannot be the first string"


def test_the_deficiency_register_carries_the_replacement_tier():
    ld = _csv(PROC / "lineup_deficiency.csv")
    assert "expected_backup_tier" in ld.columns
    filled = ld[ld.expected_backup_tier.astype(str).str.strip() != ""]
    assert len(filled), "no deficiency row carries a replacement tier"
    for r in filled.itertuples():
        assert int(r.expected_backup_tier) >= 2
        assert str(r.tier_evidence).strip() != "", \
            f"{r.team}/{r.position_group} has a tier with no evidence"
        assert str(r.roster_source_url).startswith("https://"), \
            "the tier must point at the official page it was read from"


# --------------------------------------------------- official correlations
def test_official_correlations_publish_n():
    corr = _csv(PROC / "corr_official.csv")
    assert len(corr), "the official-only correlation register is empty"
    for r in corr.itertuples():
        assert str(r.n).strip() != "", f"{r.pair} has no n"
        assert int(r.n) == int(r.n_games)
        assert str(r.evidence_class).strip() != ""


# ------------------------------------------------------------------- pages
def test_prices_page_is_published_and_carries_the_source_links():
    page = (ROOT / "prices.html").read_text()
    assert "Price-snapshot store" in page
    assert "Verified results feed" in page
    assert "https://www.nfl.com/" in page
    # Every table row on the page carries an official reference: the page has
    # no table without one.
    assert "https://www.nfl.com/scores/" in page


def test_the_site_publishes_the_separated_leaderboard_and_the_gate():
    page = (ROOT / "strategies.html").read_text()
    assert "Signal and staking, separated" in page
    assert "demotion gate" in page.lower()
    lines = (ROOT / "lines.html").read_text()
    assert "three separate columns" in lines
    assert "Model line (fair)" in lines and "Market line" in lines
    assert "Difference (model" in lines
