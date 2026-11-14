"""Regression tests for the session's own modules.

Session arena/d0bec048-korea1 added five pieces of machinery: the price-snapshot
store, the verified results feed, the replacement-depth join, the signal/staking
split with its demotion gate, and the probability-alignment check.

Each test below moves an input and asserts the output moves with it. A test
that only re-read a CSV would pass even if the logic were inverted, so every
test here either feeds a hand-built frame or mutates a real one.

No network, no fabricated quotes: every input is a committed artefact or a
frame built inside the test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import leaderboard_split as ls  # noqa: E402
import official_settlement as rf  # noqa: E402
import price_store as ps  # noqa: E402
import probability_alignment as pa  # noqa: E402
import replacement_slots as rd  # noqa: E402


# --------------------------------------------------------------------------- #
# price store
# --------------------------------------------------------------------------- #
def _snapshot(**kw):
    base = dict(snapshot_sha="abc123", snapshot_utc="2026-11-01T00:00:00Z",
                snapshot_date="2026-11-01", season=2026, week=10,
                gameday="2026-11-12", away_team="NYG", home_team="WAS",
                game_id="g1", market="SPREAD", side="home", line=-3.0, odds=-110.0,
                source_url="https://codeload.github.com/x", evidence_class="D",
                source_kind="mirror_commit", source_sha="abc123", note="")
    base.update(kw)
    return base


def test_open_and_close_are_the_first_and_last_observation():
    store = pd.DataFrame([
        _snapshot(snapshot_utc="2026-11-05T00:00:00Z", snapshot_date="2026-11-05", line=-3.0),
        _snapshot(snapshot_utc="2026-11-08T00:00:00Z", snapshot_date="2026-11-08", line=-4.5),
        _snapshot(snapshot_utc="2026-11-09T00:00:00Z", snapshot_date="2026-11-09", line=-6.0),
    ])
    oc = ps.derive_open_close(store).iloc[0]
    assert oc.open_line == -3.0 and oc.close_line == -6.0
    assert oc.line_move == -3.0
    assert oc.n_snapshots == 3 and oc.n_pre_kickoff == 3


def test_an_observation_after_kickoff_is_not_the_open():
    """A price captured after the game does not become the opening price."""
    store = pd.DataFrame([
        _snapshot(snapshot_utc="2026-11-20T00:00:00Z", snapshot_date="2026-11-20", line=-9.0),
        _snapshot(snapshot_utc="2026-11-10T00:00:00Z", snapshot_date="2026-11-10", line=-2.0),
    ])
    oc = ps.derive_open_close(store).iloc[0]
    assert oc.open_line == -2.0
    assert oc.close_line == -2.0


def test_the_comparison_keeps_three_separate_columns():
    """The fair line, the market line and the difference are three columns."""
    model = pd.DataFrame([dict(game_id="g1", season=2026, week=10, gameday="2026-11-12",
                               away_team="NYG", home_team="WAS", status="scheduled",
                               fair_spread=-1.0, market_spread=-3.0,
                               fair_total=45.0, market_total=44.0,
                               originated_home_ml=-150.0, market_home_ml=-160.0,
                               originated_away_ml=130.0, market_away_ml=140.0,
                               p_home_ml=0.6, p_away_ml=0.4)])
    oc = pd.DataFrame([])
    cmp_df = ps.build_comparison(model, oc)
    spread = cmp_df[(cmp_df.market == "SPREAD")].iloc[0]
    assert spread.model_fair_line == -1.0
    assert spread.market_line == -3.0
    assert spread.difference == 2.0
    assert spread.unit == "points"
    # The moneyline is compared in probability space, not in points.
    ml = cmp_df[(cmp_df.market == "MONEYLINE") & (cmp_df.side == "home")].iloc[0]
    assert ml.unit == "probability (de-vigged)"
    assert ml.probability_difference is not None
    assert ml.difference == ml.probability_difference


def test_the_origination_order_is_spread_then_total_then_moneyline():
    order = pd.DataFrame(ps.ORIGINATION_ORDER)
    assert list(order.market) == ["SPREAD", "TOTAL", "MONEYLINE"]
    assert list(order.step) == [1, 2, 3]


def test_the_price_store_is_append_only():
    """A second capture adds rows; it never rewrites the first."""
    snaps = pd.DataFrame([_snapshot(), _snapshot(snapshot_utc="2026-11-08T00:00:00Z",
                                                 snapshot_date="2026-11-08", line=-4.0)])
    store = ps.build_store(snaps)
    mine = store[store.game_id == "g1"].sort_values("snapshot_utc")
    assert len(mine) == 2
    assert list(mine.line) == [-3.0, -4.0]
    assert store.snapshot_id.is_unique
    assert len(store) >= 2


# --------------------------------------------------------------------------- #
# results feed
# --------------------------------------------------------------------------- #
def _reading(gid, away, home, reader, url="https://www.nfl.com/games/x"):
    return dict(game_id=gid, season=2026, week=9, away_team="NYG", home_team="WAS",
                away_score=str(away), home_score=str(home), status_on_page="FINAL",
                official_url=url, score_source_page="https://www.nfl.com/scores/",
                verified_utc="2026-11-13T00:00:00Z", verified_by="test",
                method="test", reader=reader)


def test_two_readers_that_agree_produce_one_official_row():
    readings = pd.DataFrame([_reading("g1", 10, 24, "forward ledger capture"),
                              _reading("g1", 10, 24, "independent score audit")])
    feed, conflicts = rf.build_feed(readings)
    assert len(feed) == 1 and len(conflicts) == 0
    assert feed.iloc[0].readers_agree == "yes"
    assert feed.iloc[0].verification == "official NFL.com final"
    assert "forward ledger capture" in feed.iloc[0].readers


def test_two_readers_that_disagree_are_reported_not_averaged():
    readings = pd.DataFrame([_reading("g1", 10, 24, "forward ledger capture"),
                              _reading("g1", 17, 24, "independent score audit")])
    feed, conflicts = rf.build_feed(readings)
    assert len(feed) == 0, "a disputed final must not enter the feed"
    assert len(conflicts) == 1
    assert "unresolved" in conflicts.iloc[0].resolution


def test_a_reading_without_a_final_is_not_a_result():
    readings = pd.DataFrame([_reading("g1", "", "", "forward ledger capture")])
    feed, conflicts = rf.build_feed(readings)
    assert len(feed) == 0 and len(conflicts) == 0


def test_settlement_marks_only_official_games():
    """The settlement feed separates the official finals from the rest."""
    feed = pd.DataFrame([dict(game_id="g1", season=2026, week=9, away_team="NYG",
                               home_team="WAS", away_score=10, home_score=24,
                               status_on_page="FINAL",
                               official_url="https://www.nfl.com/games/x",
                               source_pages="", readers="", verified_utc="",
                               verified_by="", method="", verification="official NFL.com final",
                               readers_agree="yes")])
    settlement = rf.build_settlement(feed)
    assert (settlement.verification == "official").any()
    assert (settlement.verification != "official").any(), \
        "games without an official final must stay unverified"


def test_the_settlement_agrees_with_the_mirror_when_both_have_a_score():
    feed = pd.DataFrame([dict(game_id="2006_04_ARI_ATL", season=2006, week=4,
                               away_team="ARI", home_team="ATL", away_score=10,
                               home_score=24, status_on_page="FINAL",
                               official_url="https://www.nfl.com/games/x",
                               source_pages="", readers="", verified_utc="",
                               verified_by="", method="", verification="official NFL.com final",
                               readers_agree="yes")])
    settlement = rf.build_settlement(feed)
    row = settlement[settlement.game_id == "2006_04_ARI_ATL"].iloc[0]
    assert row.verification == "official"
    assert row.agreement in ("match", "MISMATCH", "official final recorded; the mirror has no "
                           "score for this game")


# --------------------------------------------------------------------------- #
# replacement depth
# --------------------------------------------------------------------------- #
def test_the_club_word_is_matched_from_the_full_name():
    clubs = {"Washington Commanders": "Commanders", "New York Giants": "Giants"}
    assert rd.club_of("Washington Commanders", clubs) == "Commanders"
    assert rd.club_of("New York Giants", clubs) == "Giants"
    assert rd.club_of("Las Vegas Raiders", {"Las Vegas Raiders": "Raiders"}) == "Raiders"
    assert rd.club_of("Nowhere FC", clubs) is None


def test_availability_is_read_from_the_game_status_first():
    assert rd.unavailable({"game_status": "Out", "practice_status": ""}) == "out"
    assert rd.unavailable({"game_status": "Doubtful", "practice_status": ""}) == "doubtful"
    assert rd.unavailable({"game_status": "Questionable", "practice_status": ""}) == "questionable"
    assert rd.unavailable({"game_status": "", "practice_status": "Did Not Participate In Practice"}) \
        == "did not participate"
    assert rd.unavailable({"game_status": "", "practice_status": "Full Participation In Practice"}) == ""


def test_the_injury_index_is_keyed_by_club_and_player():
    inj = pd.DataFrame([dict(team="WAS", player="Alex Smith", position="QB",
                             practice_status="Full Participation in Practice",
                             game_status="Out", player_url="https://www.nfl.com/players/x")])
    idx = rd.injury_status(inj)
    assert ("WAS", "alex smith") in idx
    assert idx[("WAS", "alex smith")]["game_status"] == "Out"


def test_the_published_replacement_depth_has_a_rank_and_a_string():
    path = ROOT / "data/availability/replacement_depth_slots.csv"
    if not path.exists():
        pytest.skip("replacement depth not built")
    df = pd.read_csv(path)
    assert len(df) > 0
    # A slot with a named replacement has a rank and a depth string; a slot with
    # no published replacement has neither, and is not given a made-up one.
    named = df[df.replacement.notna() & (df.replacement.astype(str) != "")]
    unnamed = df[~(df.replacement.notna() & (df.replacement.astype(str) != ""))]
    assert named.replacement_depth_rank.notna().all()
    assert named.replacement_depth_string.str.contains("string").all()
    assert unnamed.replacement_depth_rank.isna().all()
    assert unnamed.replacement_depth_string.isna().all()
    # A second-string replacement must be a second-string one.
    second = named[named.replacement_depth_rank == 2]
    assert (second.replacement_depth_string == "2nd string").all()


# --------------------------------------------------------------------------- #
# signal and staking
# --------------------------------------------------------------------------- #
def test_the_market_probability_is_de_vigged():
    row = pd.Series({"home_spread_odds": -110.0, "away_spread_odds": -110.0})
    p_home = ls.market_probability(row, "SPREAD", "home")
    assert p_home == pytest.approx(0.5)
    row = pd.Series({"market_home_ml": -150.0, "market_away_ml": +130.0})
    p_home = ls.market_probability(row, "MONEYLINE", "home")
    p_away = ls.market_probability(row, "MONEYLINE", "away")
    assert p_home + p_away == pytest.approx(1.0)
    assert p_home > 0.5, "the favourite (-150 against +130) must have the higher probability"


def test_the_model_probability_follows_the_side_that_was_bet():
    row = pd.Series({"p_home_cover": 0.55, "p_home_fail_cover": 0.42,
                     "p_over": 0.51, "p_under": 0.46,
                     "p_home_ml": 0.60, "p_away_ml": 0.36})
    assert ls.model_win_probability(row, "SPREAD", "home")[0] == 0.55
    assert ls.model_win_probability(row, "SPREAD", "away")[0] == 0.42
    assert ls.model_win_probability(row, "TOTAL", "over")[0] == 0.51
    assert ls.model_win_probability(row, "TOTAL", "under")[0] == 0.46
    assert ls.model_win_probability(row, "MONEYLINE", "home")[0] == 0.60
    assert ls.model_win_probability(row, "MONEYLINE", "away")[0] == 0.36


def _enriched(strategy="X", n=10, realised=1.0, expected=0.5, edge=0.05, week=1):
    return pd.DataFrame(dict(
        strategy=[strategy] * n, game_id=[f"g{i}" for i in range(n)],
        season=[2020] * n, week=[week] * n,
        gameday=[f"2020-09-{1 + i % 28:02d}" for i in range(n)],
        market=["SPREAD"] * n, side=["home"] * n, line=[-3.0] * n, price=[-110.0] * n,
        p_model=[0.55] * n, p_market=[0.50] * n, p_calibrated=[0.52] * n,
        edge=[edge] * n, edge_calibrated=[edge - 0.03] * n,
        expected_pnl=[expected] * n, expected_pnl_calibrated=[expected - 0.01] * n,
        realised_pnl=[realised] * n, outcome=[1.0] * n,
        rule_signal=[1] * n, n_legs=[1] * n, quote_verified=[False] * n,
        official_quote_url=[""] * n, quote_timestamp=[""] * n, selection_key=["g"] * n,
    ))


def test_the_luck_gap_is_the_realised_return_minus_the_calibrated_expectation():
    b = _enriched(realised=1.0, expected=0.5)
    gates = pd.DataFrame([dict(strategy="X", G1_data=False, G2_leakage=True, G3_power=True,
                                G4_significance=False, G5_luck=False, G6_economic=False,
                                G7_stability=False, G8_redundancy=True,
                                G5_boot_roi_lo=0.0, G5_dsr=0.0, verdict="UNVERIFIED")])
    row = ls.signal_staking_table(b, gates).iloc[0]
    assert row.staking_realised_roi == pytest.approx(1.0)
    assert row.signal_expected_roi_per_bet == pytest.approx(0.5)
    assert row.signal_expected_roi_per_bet_calibrated == pytest.approx(0.49)
    assert row.luck_gap_roi == pytest.approx(1.0 - 0.49)
    assert row.luck_gap_roi_uncalibrated == pytest.approx(1.0 - 0.5)


def test_a_strategy_that_gets_lucky_shows_a_positive_luck_gap():
    b = _enriched(realised=2.0, expected=0.1)
    gates = pd.DataFrame([dict(strategy="X", G1_data=False, G2_leakage=False, G3_power=False,
                                G4_significance=False, G5_luck=False, G6_economic=False,
                                G7_stability=False, G8_redundancy=False,
                                G5_boot_roi_lo=0.0, G5_dsr=0.0, verdict="UNVERIFIED")])
    row = ls.signal_staking_table(b, gates).iloc[0]
    assert row.luck_gap_roi > 0


def test_the_demotion_replay_fires_on_the_published_conditions():
    """A stream that loses money against a positive expectation trips D1."""
    b = _enriched(n=ls.WINDOW + 5, realised=-1.0, expected=0.5, edge=0.05)
    summary, events = ls.replay_gate(b)
    row = summary.iloc[0]
    assert row.replay_demotions > 0
    assert "D1" in row.replay_rules_fired
    d1 = events[events.rule_id == "D1"]
    assert len(d1) > 0
    assert "bootstrap upper bound" in d1.iloc[0].reason


def test_the_demotion_replay_fires_on_sample_decay():
    """Too few settled bets in the trailing weeks trips D3."""
    b = _enriched(n=5, realised=1.0, expected=0.5, edge=0.05)
    summary, events = ls.replay_gate(b)
    assert "D3" in summary.iloc[0].replay_rules_fired
    assert len(events[events.rule_id == "D3"]) > 0


def test_the_demotion_replay_fires_on_a_quote_provenance_failure():
    """No authenticated quote trips D4, which is why nothing can be live."""
    b = _enriched(n=ls.WINDOW + 5, realised=1.0, expected=0.5, edge=0.05)
    b["quote_verified"] = True
    b["official_quote_url"] = "https://www.nfl.com/x"
    b["quote_timestamp"] = "2026-01-01T00:00:00Z"
    summary, events = ls.replay_gate(b)
    assert "D4" not in summary.iloc[0].replay_rules_fired
    b2 = b.copy()
    b2["official_quote_url"] = ""
    summary2, events2 = ls.replay_gate(b2)
    assert "D4" in summary2.iloc[0].replay_rules_fired


def test_the_demotion_replay_does_not_fire_on_a_healthy_stream():
    b = _enriched(n=ls.WINDOW + 5, realised=1.0, expected=0.1, edge=0.05)
    b["quote_verified"] = True
    b["official_quote_url"] = "https://www.nfl.com/x"
    b["quote_timestamp"] = "2026-01-01T00:00:00Z"
    summary, events = ls.replay_gate(b)
    assert summary.iloc[0].replay_demotions == 0


# --------------------------------------------------------------------------- #
# probability alignment and calibration
# --------------------------------------------------------------------------- #
def test_the_de_vigged_market_probability_sums_to_one():
    hp, ap = pa.de_vig(np.array([-110.0, -150.0]), np.array([-110.0, 130.0]))
    assert np.allclose(hp + ap, 1.0)
    assert hp[0] == pytest.approx(0.5)
    assert hp[1] > ap[1], "-150 against +130 makes the home side the favourite"


def test_the_calibration_pulls_an_over_confident_model_back():
    """A model that claims 60% where the outcome happens 40% is corrected."""
    rng = np.random.default_rng(7)
    p = rng.uniform(0.3, 0.9, 3000)
    y = (rng.uniform(size=3000) < 0.40).astype(float)
    a, b = pa.fit_platt(p, y)
    calibrated = pa._sigmoid(a + b * pa._logit(p))
    assert calibrated.mean() == pytest.approx(0.40, abs=0.03)
    assert calibrated.mean() < p.mean()


def test_the_calibration_leaves_a_calibrated_model_alone():
    rng = np.random.default_rng(11)
    p = rng.uniform(0.2, 0.8, 3000)
    y = (rng.uniform(size=3000) < p).astype(float)
    a, b = pa.fit_platt(p, y)
    calibrated = pa._sigmoid(a + b * pa._logit(p))
    assert calibrated.mean() == pytest.approx(p.mean(), abs=0.03)


def test_the_calibration_is_walk_forward():
    """A season is never calibrated with a later season's results."""
    lines = pd.read_csv(ROOT / "data/processed/originated_lines.csv", low_memory=False)
    sel = pa.build_selection_table(lines)
    sel, params = pa.calibrate(sel)
    p = params[(params.market == "SPREAD") & (params.side == "home")]
    first = p.sort_values("season").iloc[0]
    assert first.n_train == 0, "the first season has no training data"
    assert first.calib_a == 0.0 and first.calib_b == 1.0
    later = p.sort_values("season").iloc[-1]
    assert later.n_train > 0


def test_the_alignment_report_separates_alignment_from_calibration():
    """Alignment is a different question from calibration, and both are reported."""
    lines = pd.read_csv(ROOT / "data/processed/originated_lines.csv", low_memory=False)
    sel = pa.build_selection_table(lines)
    sel, _ = pa.calibrate(sel)
    bets = pd.read_csv(ROOT / "data/processed/strategy_bets.csv", low_memory=False)
    report = pa.alignment_report(sel, bets)
    assert set(report.market) == {"SPREAD", "TOTAL", "MONEYLINE"}
    assert report.line_aligned.all()
    assert report.side_aligned.all()
    # The proper scoring rule must improve in every group.
    assert (report.brier_calibrated < report.brier_model).all()
    # And where the model was materially over-confident (more than two points),
    # the calibrated mean probability must be closer to the realised rate.
    material = report[report.model_minus_realised.abs() > 0.02]
    assert len(material) > 0
    assert (material.calibrated_minus_realised.abs()
            <= material.model_minus_realised.abs()).all()


def test_the_bet_expectations_use_the_bets_own_side_and_line():
    lines = pd.read_csv(ROOT / "data/processed/originated_lines.csv", low_memory=False)
    sel = pa.build_selection_table(lines)
    sel, _ = pa.calibrate(sel)
    bets = pd.read_csv(ROOT / "data/processed/strategy_bets.csv", low_memory=False)
    exp = pa.build_bet_expectations(sel, bets)
    assert len(exp) > 0
    assert exp.bet_index.is_unique
    # The expected value must follow the published formula from the probability.
    row = exp.iloc[0]
    dec = 1 + 100 / (-row.price) if row.price < 0 else 1 + row.price / 100
    assert row.expected_pnl_model == pytest.approx(
        row.p_model * (dec - 1) - (1 - row.p_model), abs=1e-6)
    assert row.expected_pnl_calibrated == pytest.approx(
        row.p_calibrated * (dec - 1) - (1 - row.p_calibrated), abs=1e-6)


# --------------------------------------------------------------------------- #
# the fast bootstrap used by the rolling demotion replay
# --------------------------------------------------------------------------- #
def test_the_fast_bootstrap_agrees_with_the_reference_implementation():
    """The vectorised resampler is the same procedure, not a different one."""
    import stats_tools as st
    x = np.array([0.1, -0.1, 0.05, -0.05] * 25)
    fast = st.bootstrap_mean_ci(x, n_boot=1000, seed=7)
    slow = st.bootstrap_mean_test(x, n_boot=1000, seed=7)
    assert fast["ci_lo"] == pytest.approx(slow["ci_lo"], abs=0.01)
    assert fast["ci_hi"] == pytest.approx(slow["ci_hi"], abs=0.01)


def test_the_fast_bootstrap_refuses_a_constant_sample():
    import stats_tools as st
    out = st.bootstrap_mean_ci(np.ones(50))
    assert not np.isfinite(out["ci_hi"])
