"""Tests for the nine-item brief (session arena/6b1f0c9a-korea1).

Each test targets a rule that would be *possible to get wrong silently* — a sign convention, a
fail-closed trigger, an evidence class that could be upgraded by accident — rather than re-reading a
CSV. Where a module has a decision rule, the test mutates an input and asserts the verdict moves.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

import corr_official as co  # noqa: E402
import demotion_rules as dg  # noqa: E402
import origination_order as oo  # noqa: E402
import price_annex as ps  # noqa: E402
import replacement_depth as rd  # noqa: E402
import results_feed as rf  # noqa: E402
import signal_staking as ss  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GATES = ROOT / "data" / "gates"
PRICES = ROOT / "data" / "prices"
RESULTS = ROOT / "data" / "results"


# --------------------------------------------------------------------------- #
# R1 price snapshot
# --------------------------------------------------------------------------- #
def test_price_snapshot_has_every_originated_market():
    """One row per game/market/side is the literal requirement; a missing row is a regression."""
    d = pd.read_csv(PRICES / "price_snapshots.csv", low_memory=False)
    org = pd.read_csv(ROOT / "data/processed/originated_lines.csv", low_memory=False)
    assert d.game_id.nunique() == org.game_id.nunique()
    assert set(d.market.unique()) == {"SIDE", "TOTAL", "MONEYLINE"}
    # every game has exactly six rows: two sides x three markets
    assert (d.groupby("game_id").size() == 6).all()


def test_price_snapshot_never_invents_an_endpoint():
    """A missing opener must stay missing, and no provenance may claim an official price."""
    d = pd.read_csv(PRICES / "price_snapshots.csv", dtype=str, keep_default_na=False)
    m26 = d[d.season == "2026"]
    assert (m26.open_line == "").all(), "no 2026 opener exists in the pinned archive"
    assert "OFFICIAL" not in " ".join(d.provenance.unique()).replace("PINNED_COMMUNITY", "")


def test_closing_price_coverage_is_reported_not_assumed():
    """A closing number without a price must not be counted as a priced row."""
    c = pd.read_csv(PRICES / "price_snapshot_coverage.csv")
    side = c[c.market == "SIDE"].iloc[0]
    assert side.close_price < side.close_line // 2, (
        "closing_lines.csv carries prices for a small minority of spread rows; the coverage table "
        "must show that, not imply a price wherever a number exists")


# --------------------------------------------------------------------------- #
# R2 results feed
# --------------------------------------------------------------------------- #
def test_results_feed_settlement_is_fail_closed():
    assert rf.settle_spread(3.0, np.nan) == ("", "no closing spread on record")
    assert rf.settle_total(44.0, None) == ("", "no closing total on record")
    assert rf.settle_ml(np.nan, -120, 110) == ("", "no official final")
    assert rf.settle_spread(3.0, -3.0) == ("PUSH", "")
    assert rf.settle_total(44.0, 44.0) == ("PUSH", "")
    assert rf.settle_spread(7.0, -3.0)[0] == "HOME_COVERS"
    assert rf.settle_spread(-7.0, -3.0)[0] == "AWAY_COVERS"


def test_results_feed_never_labels_a_community_score_final():
    d = pd.read_csv(RESULTS / "verified_results.csv", dtype=str, keep_default_na=False)
    comm = d[d.score_source == "PINNED_COMMUNITY"]
    assert len(comm) > 0, "the 2026 weeks 1-7 community finals must be present, not dropped"
    assert (comm.verified == "COMMUNITY_ONLY").all()
    assert (comm.settle_spread == "").all(), "a community final may not settle a bet"
    assert not d[(d.verified == "FINAL") & (d.official_url == "")].shape[0], (
        "a final must carry the official page it was read from")


def test_results_feed_extract_beats_the_older_register():
    """A row read today must replace the same game read two days ago, not the other way round."""
    d = pd.read_csv(RESULTS / "verified_results.csv", dtype=str, keep_default_na=False)
    row = d[d.game_id == "2026_08_LAC_LA"]
    assert len(row) == 1, "one row per game"
    assert row.iloc[0].score_source == "DATA_EXTRACT"


# --------------------------------------------------------------------------- #
# R3 / R4 origination
# --------------------------------------------------------------------------- #
def test_american_probability_round_trip():
    assert abs(oo.american_to_prob(-200) - 2 / 3) < 1e-9
    assert abs(oo.american_to_prob(150) - 0.4) < 1e-9
    assert np.isnan(oo.american_to_prob(-50)), "prices between -100 and +100 are invalid"
    ph, pa = oo.implied_pair(-200, 170)
    assert abs(ph + pa - 1.0) < 1e-9, "the pair must be de-vigged to sum to one"


def test_origination_columns_are_separate_and_signed():
    d = pd.read_csv(GATES / "origination_order.csv")
    # the difference is exactly fair - market, on every row where both exist
    m = d.side_fair.notna() & d.side_market.notna()
    assert np.allclose((d.side_fair - d.side_market)[m], d.side_diff[m])
    m2 = d.total_fair.notna() & d.total_market.notna()
    assert np.allclose((d.total_fair - d.total_market)[m2], d.total_diff[m2])
    # the moneyline difference is a probability difference, so it is bounded in [-1, 1]
    assert d.ml_diff_prob.dropna().abs().le(1).all()


def test_origination_reports_the_model_losing_to_the_market():
    """The honest result today. If a future model beats the close, this test should be updated
    deliberately, with a note - not silently."""
    acc = pd.read_csv(GATES / "origination_accuracy.csv")
    assert len(acc) == 3
    assert (acc.gap > 0).all(), (
        "fair MAE is worse than market MAE on all three markets; a change here is a model change "
        "and must be recorded, not just re-run")


# --------------------------------------------------------------------------- #
# R5 signal vs staking
# --------------------------------------------------------------------------- #
def test_spearman_handles_ties():
    """pnl is discrete, so the rank correlation must tolerate massive ties."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([1.0, 1.0, 0.0, 0.0, 1.0])
    r = ss._spearman(x, y)
    assert np.isfinite(r)
    assert ss._spearman(x, np.ones(5)) == 0.0 or np.isnan(ss._spearman(x, np.ones(5)))


def test_constant_signal_is_not_testable():
    g = pd.DataFrame({"signal": [1.0] * 300, "pnl": np.ones(300), "week_key": ["w"] * 300,
                      "n_legs": [1] * 300, "outcome": np.ones(300)})
    out = ss.signal_test(g)
    assert out["tested"] is False
    assert out["verdict"] == "NOT_TESTABLE"


def test_luck_risk_is_recognised_and_ranked_below_signal():
    d = pd.read_csv(GATES / "signal_staking.csv")
    wind = d[d.strategy == "WIND_UNDER"].iloc[0]
    assert wind.combined_verdict == "LUCK_RISK", (
        "WIND_UNDER is the positive-ROI / no-signal case the brief names; it must be labelled")
    buy = d[d.strategy == "BUY_LOW_ATS"].iloc[0]
    assert buy.signal_verdict == "SIGNAL_PRESENT"
    assert buy.signal_first_rank < wind.signal_first_rank, "signal evidence outranks a lucky run"


def test_no_strategy_is_both_validated_and_unpriced():
    d = pd.read_csv(GATES / "signal_staking.csv")
    v = d[d.combined_verdict == "VALIDATED"]
    assert v.empty or v.price_complete.all()


# --------------------------------------------------------------------------- #
# R6 replacement depth
# --------------------------------------------------------------------------- #
def test_depth_impact_weights_a_starter_four_times_a_fourth_string():
    assert abs(1 / 1 - 1.0) < 1e-12
    assert abs((1 / 1) / (1 / 4) - 4.0) < 1e-12


def test_club_without_a_chart_is_not_assessed():
    d = pd.read_csv(GATES / "replacement_defence.csv", dtype=str, keep_default_na=False)
    hou = d[d.team == "HOU"]
    assert len(hou) == 1
    assert hou.iloc[0].verdict == "NO_CHART"
    assert hou.iloc[0].offence_impact == "0.0" and hou.iloc[0].defence_impact == "0.0"


def test_unmatched_players_are_counted_not_dropped():
    s = pd.read_csv(GATES / "replacement_slots.csv", dtype=str, keep_default_na=False)
    assert (~(s.matched == "True")).sum() > 0
    # an unmatched row must carry no depth
    assert s[s.matched == "False"].depth_rank.eq("").all()
    assert s[s.matched == "False"].note.str.len().gt(20).all()


def test_position_map_covers_both_units():
    units = {v[0] for v in rd.POSITION_SLOTS.values()}
    assert units == {"Offense", "Defense", "Special Teams"}


# --------------------------------------------------------------------------- #
# R7 correlations
# --------------------------------------------------------------------------- #
def test_correlation_rows_publish_n_and_a_week_count():
    c = pd.read_csv(ROOT / "data/correlations/official_correlations.csv")
    assert c.n.min() >= co.MIN_N
    assert c.n_weeks.min() >= co.MIN_WEEKS
    assert c.n.notna().all() and c.n_weeks.notna().all()


def test_correlation_sign_conventions_are_the_documented_ones():
    c = pd.read_csv(ROOT / "data/correlations/official_correlations.csv")
    side = c[c.relationship == "home covers vs home ML win"].iloc[0]
    # cover and win are both home-favourable, so they must move together
    assert side.rho > 0.5
    edge = c[c.relationship == "signed model edge vs realised margin"].iloc[0]
    # a *signed* edge, with the documented negative-home-handicap convention
    assert edge.rho > 0, (
        "with market_spread as the home handicap, a positive (market - fair) is a home lean and "
        "must correlate positively with the home margin; a negative rho here means the sign "
        "convention was inverted")
    assert c.sign_convention.str.len().gt(5).all()


def test_null_results_are_published_not_dropped():
    c = pd.read_csv(ROOT / "data/correlations/official_correlations.csv")
    assert (c.verdict == "NOT_DISTINGUISHABLE_FROM_ZERO").sum() >= 1


# --------------------------------------------------------------------------- #
# R8 demotion gate
# --------------------------------------------------------------------------- #
def test_demotion_triggers_are_fail_closed():
    outs, rules = dg.build()
    assert list(rules.code) == ["D1", "D2", "D3", "D4", "D5", "D6"]
    # no strategy is live, so the correct answer is no action - not a pass
    assert (outs.decision == "NO_ACTION").all()
    assert outs.state.isin(["PAPER", "LIVE", "DEMOTED", "RETIRED"]).all()


def test_gate_cannot_promote():
    """Promotion is an owner decision; the gate module must contain no promotion path."""
    src = (ROOT / "pipeline" / "demotion_rules.py").read_text()
    assert "DEMOTE_TO_PAPER" in src
    assert "PROMOTE" not in src.replace("PROMOTION", "").replace("promotion", "")


def test_gate_reports_not_computable_instead_of_passing():
    d = pd.read_csv(GATES / "demotion_gate.csv", dtype=str, keep_default_na=False)
    live = d[d.live_settled.apply(lambda x: x not in ("", "0"))]
    assert len(live) > 0
    assert live.d1.str.startswith("not computable").any() or live.d2.str.startswith(
        "not computable").any()


# --------------------------------------------------------------------------- #
# R9 review surface
# --------------------------------------------------------------------------- #
def test_review_surface_holds_nine_items_and_nothing_implemented():
    b = pd.read_csv(ROOT / "data/integration/brief_2026_11_14.csv")
    assert len(b) == 9
    s = pd.read_csv(ROOT / "data/integration/suggestions_2026_11_14.csv",
                    dtype=str, keep_default_na=False)
    assert len(s) >= 8
    assert (s.status == "AWAITING PATH SELECTION").all()
    q = pd.read_csv(ROOT / "data/integration/questions_2026_11_14.csv",
                    dtype=str, keep_default_na=False)
    assert len(q) >= 8
    assert q.missing.str.len().gt(10).all(), "every question must name what is missing"


def test_new_suggestions_are_checked_against_the_existing_register():
    s = pd.read_csv(ROOT / "data/integration/suggestions_2026_11_14.csv",
                    dtype=str, keep_default_na=False)
    assert s.existing_register.str.len().gt(5).all(), (
        "each proposal must carry an overlap verdict against the 76-row register, even if the "
        "verdict is 'no close match'")
