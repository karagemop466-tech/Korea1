"""Regression tests for the forward-test ledger (FW1/FW2). No network access is needed.

Run:  python -m pytest -q tests/test_forward_ledger.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import backtest as bt  # noqa: E402
import forward_grade as fg  # noqa: E402
import forward_ledger as fl  # noqa: E402

UTC = dt.timezone.utc


# ---------------------------------------------------------------- hash chain
def _chain(tmp_path, n=4):
    path = tmp_path / "ledger.jsonl"
    fl.ensure_genesis("test", dt.datetime(2026, 1, 1, tzinfo=UTC), path)
    for i in range(n):
        fl.append_entry({"type": "NOTE", "i": i}, path)
    return path


def test_chain_accepts_untouched_file(tmp_path):
    assert fl.verify_chain(fl.read_ledger(_chain(tmp_path))) == []


def test_chain_detects_edit_reorder_and_deletion(tmp_path):
    entries = fl.read_ledger(_chain(tmp_path))
    edited = json.loads(json.dumps(entries))
    edited[2]["body"]["i"] = 99
    assert fl.verify_chain(edited)
    assert fl.verify_chain([entries[0], entries[2], entries[1], *entries[3:]])
    assert fl.verify_chain(entries[:2] + entries[3:])
    assert fl.verify_chain(entries[1:])                      # genesis removed


def test_chain_detects_rewritten_hash(tmp_path):
    """Recomputing one entry's own hash is not enough: the next entry still points at the old one."""
    entries = fl.read_ledger(_chain(tmp_path))
    forged = json.loads(json.dumps(entries))
    forged[2]["body"]["i"] = 99
    forged[2]["entry_hash"] = fl.chain_hash(forged[2]["prev_hash"], forged[2]["body"])
    assert fl.verify_chain(forged)


def test_append_refuses_broken_chain(tmp_path):
    path = _chain(tmp_path)
    lines = path.read_text().splitlines()
    lines[1] = lines[1].replace('"i":0', '"i":7')
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(RuntimeError):
        fl.append_entry({"type": "NOTE"}, path)


def test_canonical_json_is_order_independent_and_rejects_nan():
    assert fl.canonical({"b": 1, "a": [1, 2]}) == fl.canonical({"a": [1, 2], "b": 1})
    with pytest.raises(ValueError):
        fl.canonical({"x": float("nan")})
    assert fl.r6(float("nan")) is None and fl.r6(None) is None and fl.r6("x") is None
    assert fl.r6(1.23456789) == 1.234568


# ---------------------------------------------------------------- time handling
def test_kickoff_conversion_handles_daylight_saving_change():
    # US clocks went back on 1 November 2026.
    assert fl.kickoff_utc("2026-10-29", "20:15") == dt.datetime(2026, 10, 30, 0, 15, tzinfo=UTC)
    assert fl.kickoff_utc("2026-11-01", "13:00") == dt.datetime(2026, 11, 1, 18, 0, tzinfo=UTC)
    assert fl.kickoff_utc("2026-11-12", "20:15") == dt.datetime(2026, 11, 13, 1, 15, tzinfo=UTC)
    assert fl.kickoff_utc("2026-11-12", None) is None and fl.kickoff_utc(None, "13:00") is None


def _sched(rows):
    cols = ["game_id", "season", "week", "gameday", "gametime", "away_team", "home_team", "result"]
    return pd.DataFrame(rows, columns=cols)


def test_slate_excludes_started_games_and_stale_inputs():
    raw = _sched([
        ["2026_09_A_B", 2026, 9, "2026-11-08", "13:00", "A", "B", 3.0],            # played
        ["2026_09_C_D", 2026, 9, "2026-11-09", "20:15", "C", "D", np.nan],          # MNF not settled yet
        ["2026_10_A_C", 2026, 10, "2026-11-12", "20:15", "A", "C", np.nan],         # C still has week 9 open
        ["2026_10_B_E", 2026, 10, "2026-11-15", "13:00", "B", "E", np.nan],         # clean
        ["2026_10_F_G", 2026, 10, "2026-11-15", None, "F", "G", np.nan],            # no kickoff time
        ["2026_11_B_F", 2026, 11, "2026-11-22", "13:00", "B", "F", np.nan],         # later week
    ])
    now = dt.datetime(2026, 11, 10, 15, 0, tzinfo=UTC)
    s = fl.select_slate(raw, now)
    assert (s["season"], s["week"]) == (2026, 10)
    assert s["eligible"] == ["2026_10_B_E"]
    reasons = {x["game_id"]: x["reason"] for x in s["excluded"]}
    assert reasons == {"2026_10_A_C": "STALE_INPUTS_EARLIER_GAME_UNPLAYED", "2026_10_F_G": "NO_KICKOFF_TIME"}


def test_slate_respects_the_margin_before_kickoff():
    raw = _sched([["2026_10_A_C", 2026, 10, "2026-11-12", "20:15", "A", "C", np.nan],
                  ["2026_10_B_E", 2026, 10, "2026-11-15", "13:00", "B", "E", np.nan]])
    ko = dt.datetime(2026, 11, 13, 1, 15, tzinfo=UTC)
    early = fl.select_slate(raw, ko - dt.timedelta(minutes=31))
    assert early["eligible"] == ["2026_10_A_C", "2026_10_B_E"]
    late = fl.select_slate(raw, ko - dt.timedelta(minutes=29))
    assert late["eligible"] == ["2026_10_B_E"]
    assert late["excluded"] == [{"game_id": "2026_10_A_C", "reason": "KICKOFF_PASSED_OR_INSIDE_MARGIN"}]
    assert fl.select_slate(raw, dt.datetime(2026, 12, 1, tzinfo=UTC)) is None


# ---------------------------------------------------------------- the committed ledger
ENTRIES = fl.read_ledger()
FREEZES = [e for e in ENTRIES if e["body"].get("type") == "SLATE_FREEZE"]


def test_committed_ledger_chain_is_intact():
    assert ENTRIES, "the ledger must exist"
    assert fl.verify_chain(ENTRIES) == []
    genesis = ENTRIES[0]["body"]
    assert genesis["type"] == "GENESIS"
    assert genesis["protocol_sha256"] == fl.sha256_text(fl.canonical(genesis["protocol"]))


def test_no_game_is_frozen_twice_and_every_card_precedes_kickoff():
    seen = set()
    for e in FREEZES:
        created = fg.parse_utc(e["body"]["created_utc"])
        for c in e["body"]["cards"]:
            assert c["game_id"] not in seen
            seen.add(c["game_id"])
            lead = fg.parse_utc(c["kickoff_utc"]) - created
            assert lead >= dt.timedelta(minutes=fl.FREEZE_MARGIN_MIN), c["game_id"]
            assert c["model"]["fair_spread"] is not None and c["model"]["fair_total"] is not None


def test_picks_only_reference_frozen_games_and_registered_strategies():
    for e in FREEZES:
        b = e["body"]
        games = {c["game_id"] for c in b["cards"]}
        registered = set(b["strategies_registered"])
        assert len(registered) == len(b["strategies_registered"])
        for p in b["picks"]:
            assert p["strategy"] in registered
            assert {l["game_id"] for l in p["legs"]} <= games
            assert all(l["price"] is not None for l in p["legs"])
            assert (p["market"] == "PARLAY") == (len(p["legs"]) > 1)


def test_frozen_week10_kickoffs_match_the_official_schedule():
    official = fg.official_kickoffs()
    cards = [c for e in FREEZES for c in e["body"]["cards"] if (c["season"], c["week"]) == (2026, 10)]
    assert len(cards) == 14
    for c in cards:
        assert c["game_id"] in official
        assert fg.parse_utc(c["kickoff_utc"]) == official[c["game_id"]]["kickoff_utc"]


def test_amendment_blocks_any_verdict_until_the_owner_decides():
    kinds = [e["body"]["type"] for e in ENTRIES]
    assert "PROTOCOL_AMENDMENT" in kinds
    if "OWNER_DECISION" not in kinds:
        sb = pd.read_csv(ROOT / "data" / "forward" / "scoreboard.csv")
        assert (sb.verdict == "NO VERDICT").all()
        assert (sb.F6_quote_provenance == "FAIL").all()


def test_derived_views_match_the_ledger():
    cards = pd.read_csv(ROOT / "data" / "forward" / "cards.csv")
    picks = pd.read_csv(ROOT / "data" / "forward" / "picks.csv")
    assert len(cards) == sum(len(e["body"]["cards"]) for e in FREEZES)
    assert len(picks) == sum(len(e["body"]["picks"]) for e in FREEZES)
    pd.testing.assert_frame_equal(cards, fl.flat_cards(ENTRIES).pipe(_roundtrip), check_dtype=False)


def _roundtrip(df):
    import io
    return pd.read_csv(io.StringIO(df.to_csv(index=False)))


# ---------------------------------------------------------------- settlement
@pytest.mark.parametrize("home,away", [(27, 24), (24, 27), (20, 20), (31, 10), (17, 20), (23, 20)])
@pytest.mark.parametrize("line", [-7.0, -3.0, 0.0, 2.5, 3.0, 43.5, 47.0])
def test_leg_outcome_equals_canonical_settlement(home, away, line):
    row = {"result": home - away, "total": home + away, "market_spread": line, "market_total": line}
    for market, sides in (("SPREAD", ("home", "away")), ("TOTAL", ("over", "under")), ("MONEYLINE", ("home", "away"))):
        for side in sides:
            assert fg.leg_outcome(market, side, line, home, away) == bt.settle_row(row, market, side, -110.0)[0]


def test_spread_convention_positive_line_means_home_favoured():
    # Home favoured by 3 and wins by 7 -> home covers; wins by 3 -> push; wins by 2 -> away covers.
    assert fg.leg_outcome("SPREAD", "home", 3.0, 27, 20) == 1.0
    assert fg.leg_outcome("SPREAD", "home", 3.0, 23, 20) == 0.5
    assert fg.leg_outcome("SPREAD", "away", 3.0, 22, 20) == 1.0
    assert fg.leg_outcome("TOTAL", "under", 43.5, 20, 23) == 1.0


def _leg(gid, market, side, line, price=-110.0):
    return {"game_id": gid, "market": market, "side": side, "line": line, "price": price}


def test_single_pick_settlement_and_price_stress():
    finals = {"G1": (27, 20)}
    win = fg.settle_pick([_leg("G1", "SPREAD", "home", 3.0)], finals)
    assert win["outcome"] == 1.0 and win["pnl"] == pytest.approx(100 / 110)
    stressed = fg.settle_pick([_leg("G1", "SPREAD", "home", 3.0)], finals, cents=5)
    assert stressed["pnl"] == pytest.approx(100 / 115)
    lose = fg.settle_pick([_leg("G1", "SPREAD", "away", 3.0)], finals)
    assert (lose["outcome"], lose["pnl"]) == (0.0, -1.0)
    push = fg.settle_pick([_leg("G1", "SPREAD", "home", 7.0)], finals)
    assert (push["outcome"], push["pnl"]) == (0.5, 0.0)
    assert fg.settle_pick([_leg("G2", "SPREAD", "home", 3.0)], finals) is None


def test_parlay_push_reduces_the_ticket_and_a_loss_kills_it():
    finals = {"G1": (27, 20), "G2": (10, 13)}
    both = fg.settle_pick([_leg("G1", "SPREAD", "home", 3.0), _leg("G2", "MONEYLINE", "away", None, 150.0)], finals)
    assert both["outcome"] == 1.0 and both["pnl"] == pytest.approx((1 + 100 / 110) * 2.5 - 1)
    pushed = fg.settle_pick([_leg("G1", "SPREAD", "home", 7.0), _leg("G2", "MONEYLINE", "away", None, 150.0)], finals)
    assert pushed["pnl"] == pytest.approx(1.5)
    all_push = fg.settle_pick([_leg("G1", "SPREAD", "home", 7.0), _leg("G2", "SPREAD", "home", -3.0)], finals)
    assert (all_push["outcome"], all_push["pnl"]) == (0.5, 0.0)
    lost = fg.settle_pick([_leg("G1", "SPREAD", "home", 3.0), _leg("G2", "MONEYLINE", "home", None, -180.0)], finals)
    assert (lost["outcome"], lost["pnl"]) == (0.0, -1.0)


def test_closing_line_value_signs():
    card = {"market_unverified": {"market_home_ml": -150.0, "market_away_ml": 130.0}}
    # Took the home side laying 3; the number closed at 4.5 -> we hold the better number.
    assert fg.leg_clv(_leg("G", "SPREAD", "home", 3.0), card, {"spread_line": 4.5}) == pytest.approx(1.5)
    assert fg.leg_clv(_leg("G", "SPREAD", "away", 3.0), card, {"spread_line": 4.5}) == pytest.approx(-1.5)
    assert fg.leg_clv(_leg("G", "TOTAL", "over", 44.0), card, {"total_line": 46.0}) == pytest.approx(2.0)
    assert fg.leg_clv(_leg("G", "TOTAL", "under", 44.0), card, {"total_line": 46.0}) == pytest.approx(-2.0)
    up = fg.leg_clv(_leg("G", "MONEYLINE", "home", None, -150.0), card, {"home_moneyline": -200.0, "away_moneyline": 170.0})
    assert up > 0
    assert fg.leg_clv(_leg("G", "MONEYLINE", "away", None, 130.0), card,
                      {"home_moneyline": -200.0, "away_moneyline": 170.0}) == pytest.approx(-up)
    assert fg.leg_clv(_leg("G", "SPREAD", "home", 3.0), card, None) is None
    assert fg.leg_clv(_leg("G", "SPREAD", "home", 3.0), card, {"spread_line": float("nan")}) is None


# ---------------------------------------------------------------- grading statuses
@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """A scratch ledger with one frozen game and one pick on it."""
    monkeypatch.setattr(fl, "LEDGER", tmp_path / "ledger.jsonl")
    for name in ("OFFICIAL", "SCHEDULE", "ANCHORS"):
        monkeypatch.setattr(fg, name, tmp_path / f"{name.lower()}.csv")
    fl.ensure_genesis("test", dt.datetime(2026, 11, 10, tzinfo=UTC))
    card = {"game_id": "2026_10_AAA_BBB", "season": 2026, "week": 10, "away_team": "AAA", "home_team": "BBB",
            "kickoff_utc": "2026-11-15T18:00:00Z",
            "model": {"fair_spread": 2.0, "fair_total": 44.0, "p_home_ml": 0.55},
            "market_unverified": {"market_spread": 3.0, "market_total": 45.5, "market_home_ml": -150.0,
                                  "market_away_ml": 130.0}}
    pick = {"strategy": "S1", "family": "model", "market": "SPREAD", "signal": 1.0,
            "legs": [_leg("2026_10_AAA_BBB", "SPREAD", "away", 3.0, -110.0)]}
    entry = fl.append_entry({"type": "SLATE_FREEZE", "created_utc": "2026-11-12T13:00:00Z", "season": 2026, "week": 10,
                             "cards": [card], "picks": [pick], "strategies_registered": ["S1", "S2"]})
    return tmp_path, entry


def _official(tmp_path, home, away, status="Final"):
    pd.DataFrame([{"game_id": "2026_10_AAA_BBB", "home_score": home, "away_score": away, "status_on_page": status,
                   "official_url": "https://www.nfl.com/games/x-at-y-2026-reg-10"}]).to_csv(fg.OFFICIAL, index=False)


def _mirror(home, away):
    return pd.DataFrame([{"game_id": "2026_10_AAA_BBB", "home_score": home, "away_score": away, "result": home - away,
                          "spread_line": 1.5, "total_line": 44.0, "home_moneyline": -130.0, "away_moneyline": 110.0}])


def test_grade_is_open_until_a_result_exists(sandbox):
    cards, picks = fg.grade()
    assert cards.status.tolist() == ["OPEN"] and picks.status.tolist() == ["OPEN"]
    assert picks.outcome.tolist() == [""]


def test_mirror_only_result_is_provisional_and_not_counted(sandbox):
    cards, picks = fg.grade(_mirror(24, 23))
    assert cards.status.tolist() == ["PROVISIONAL"] and picks.status.tolist() == ["PROVISIONAL"]
    assert cards.abs_err_spread.tolist() == [""]                 # no model error without the official score
    sb = fg.scoreboard(picks, ["S1", "S2"])
    assert sb.set_index("strategy").loc["S1", ["counted", "provisional"]].tolist() == [0, 1]
    assert sb.set_index("strategy").loc["S1", "F2_official_settlement"] == "PENDING"


def test_official_result_settles_and_records_model_error(sandbox):
    tmp, _ = sandbox
    _official(tmp, 24, 23)
    cards, picks = fg.grade(_mirror(24, 23))
    assert cards.status.tolist() == ["OFFICIAL"]
    assert cards.abs_err_spread.tolist() == [1.0] and cards.abs_err_total.tolist() == [3.0]
    assert picks.status.tolist() == ["OFFICIAL"] and picks.outcome.tolist() == [1.0]
    assert picks.clv.tolist() == [1.5]                            # took away +3, closed +1.5
    sb = fg.scoreboard(picks, ["S1", "S2"]).set_index("strategy")
    assert sb.loc["S1", ["counted", "wins", "losses"]].tolist() == [1, 1, 0]
    assert sb.loc["S2", "declared"] == 0


def test_a_page_that_is_not_final_does_not_settle(sandbox):
    tmp, _ = sandbox
    _official(tmp, 14, 10, status="Q3 4:12")
    cards, _ = fg.grade()
    assert cards.status.tolist() == ["OPEN"]


def test_disagreement_between_official_and_mirror_is_a_conflict(sandbox):
    tmp, _ = sandbox
    _official(tmp, 24, 23)
    cards, picks = fg.grade(_mirror(24, 20))
    assert cards.status.tolist() == ["CONFLICT"] and picks.status.tolist() == ["CONFLICT"]
    sb = fg.scoreboard(picks, ["S1"]).set_index("strategy")
    assert sb.loc["S1", "counted"] == 0 and sb.loc["S1", "F1_commitment"] == "CHECK"


def test_entry_that_reached_github_after_kickoff_is_void(sandbox):
    tmp, entry = sandbox
    _official(tmp, 24, 23)
    pd.DataFrame([{"game_id": "2026_10_AAA_BBB", "official_game_date": "2026-11-15",
                   "official_time_as_printed": "1:00 PM", "official_url": "https://www.nfl.com/games/x"}]
                 ).to_csv(fg.SCHEDULE, index=False)
    pd.DataFrame([{"seq": "1", "entry_hash": entry["entry_hash"], "commit": "c", "ref": "main",
                   "server_time_utc": "2026-11-15T18:00:01Z", "activity_type": "push", "evidence_url": "u",
                   "recorded_utc": "x"}]).to_csv(fg.ANCHORS, index=False)
    cards, picks = fg.grade()
    assert cards.status.tolist() == ["VOID"] and picks.status.tolist() == ["VOID"]
    pd.DataFrame([{"seq": "1", "entry_hash": entry["entry_hash"], "commit": "c", "ref": "main",
                   "server_time_utc": "2026-11-15T17:59:59Z", "activity_type": "push", "evidence_url": "u",
                   "recorded_utc": "x"}]).to_csv(fg.ANCHORS, index=False)
    cards, _ = fg.grade()
    assert cards.status.tolist() == ["OFFICIAL"] and cards.lead_hours.tolist() == [0.0]


def test_void_entry_withdraws_a_game(sandbox):
    tmp, _ = sandbox
    _official(tmp, 24, 23)
    fl.void(["2026_10_AAA_BBB"], "test", "tester")
    cards, picks = fg.grade()
    assert cards.status.tolist() == ["VOID"] and picks.status.tolist() == ["VOID"]
    with pytest.raises(ValueError):
        fl.void(["2026_10_NOT_FROZEN"], "test", "tester")


# ---------------------------------------------------------------- scoreboard and gates
def _synthetic_picks(n_weeks, per_week, clv, win_share=0.6, strategy="S1"):
    rows, rng = [], np.random.default_rng(7)
    for w in range(n_weeks):
        for k in range(per_week):
            won = rng.random() < win_share
            rows.append({"strategy": strategy, "season": 2027 + w // 18, "week": 1 + w % 18, "market": "SPREAD",
                         "status": "OFFICIAL", "outcome": 1.0 if won else 0.0, "pnl": 0.909 if won else -1.0,
                         "pnl_stress": 0.87 if won else -1.0, "clv": clv + rng.normal(0, 0.3)})
    return pd.DataFrame(rows)


def test_no_verdict_and_no_p_value_before_the_horizon():
    sb = fg.scoreboard(_synthetic_picks(10, 5, clv=1.0), ["S1", "S2"], owner_decided=True).set_index("strategy")
    assert sb.loc["S1", "verdict"] == "NO VERDICT" and sb.loc["S1", "F3_sample"] == "NOT REACHED"
    assert np.isnan(sb.loc["S1", "p_raw"]) and np.isnan(sb.loc["S1", "p_holm"])
    assert sb.loc["S1", "F4_skill"] == "NOT EVALUATED"


def test_horizon_alone_never_validates_while_quotes_are_unverified():
    picks = _synthetic_picks(36, 5, clv=1.0)
    undecided = fg.scoreboard(picks, ["S1", "S2"], owner_decided=False).set_index("strategy")
    assert undecided.loc["S1", "F3_sample"] == "PASS" and undecided.loc["S1", "F4_skill"] == "PASS"
    assert undecided.loc["S1", "verdict"] == "NO VERDICT"            # amendment A1
    decided = fg.scoreboard(picks, ["S1", "S2"], owner_decided=True).set_index("strategy")
    assert decided.loc["S1", "F6_quote_provenance"] == "FAIL"
    assert decided.loc["S1", "verdict"] == "NOT VALIDATED"


def test_zero_edge_strategy_fails_the_skill_gate():
    sb = fg.scoreboard(_synthetic_picks(36, 5, clv=0.0, win_share=0.5), ["S1"], owner_decided=True).set_index("strategy")
    assert sb.loc["S1", "F3_sample"] == "PASS" and sb.loc["S1", "F4_skill"] == "FAIL"


def test_holm_counts_every_registered_strategy():
    picks = _synthetic_picks(36, 5, clv=1.0)
    few = fg.scoreboard(picks, ["S1"], owner_decided=True).set_index("strategy")
    many = fg.scoreboard(picks, ["S1"] + [f"X{i}" for i in range(17)], owner_decided=True).set_index("strategy")
    assert many.loc["S1", "p_holm"] == pytest.approx(min(1.0, 18 * few.loc["S1", "p_raw"]))


def test_weekly_series_is_in_calendar_order():
    df = pd.DataFrame({"season": [2026, 2026, 2026, 2027], "week": [10, 9, 2, 1], "clv": [10.0, 9.0, 2.0, 100.0]})
    assert fg.weekly_series(df, "clv").tolist() == [2.0, 9.0, 10.0, 100.0]


# ---------------------------------------------------------------- FW1 audit and official inputs
def test_official_results_rows_are_final_scores_with_game_centre_links():
    df = pd.read_csv(ROOT / "data" / "forward" / "official_results.csv", dtype=str, keep_default_na=False)
    assert df.game_id.is_unique and len(df) >= 29
    assert df.official_url.str.startswith("https://www.nfl.com/games/").all()
    assert df.source_page.str.startswith("https://www.nfl.com/scores/").all()
    assert (df.status_on_page == "Final").all()
    assert df.home_score.str.fullmatch(r"\d+").all() and df.away_score.str.fullmatch(r"\d+").all()
    assert (df.verified_utc != "").all() and (df.verified_by != "").all()
    for r in df.to_dict("records"):                                   # the id and the teams agree
        season, week, away, home = r["game_id"].split("_")
        assert (season, int(week), away, home) == (r["season"], int(r["week"]), r["away_team"], r["home_team"])


def test_prereg_audit_classification():
    audit, summary = fg.prereg_audit()
    s = summary.set_index("set")
    assert s.loc["A", "published_utc"] < s.loc["C", "published_utc"] < s.loc["D", "published_utc"]
    for name in ("C", "D"):                                           # canonical boards, published 2 Nov
        a = audit[audit.set == name]
        sunday = a[a.official_game_date == "2026-11-01"]
        assert len(sunday) == 12 and (sunday.published_before_kickoff == "NO").all()
        monday = a[a.game_id == "2026_08_CHI_SEA"].iloc[0]
        assert monday.published_before_kickoff == "YES" and float(monday.lead_hours) > 4
        assert (a[a.week == 9].published_before_kickoff == "YES").all()
        assert (a[a.week == 9].inputs_current == 0).all()
        assert s.loc[name, "before_kickoff_with_current_inputs"] == 1
    a = audit[audit.set == "A"]
    assert (a[a.official_game_date == "2026-11-01"].published_before_kickoff == "TIME NOT VERIFIED").all()
    assert (audit.mirror_score_agrees == 1).all()
    stored = pd.read_csv(ROOT / "data" / "forward" / "prereg_audit.csv")
    assert len(stored) == len(audit) == 84
    assert stored.abs_err_spread.round(4).tolist() == pd.to_numeric(audit.abs_err_spread).round(4).tolist()


def test_audit_never_scores_a_line_without_an_official_final():
    audit, _ = fg.prereg_audit()
    scored = audit[audit.abs_err_spread != ""]
    assert (scored.official_url.str.startswith("https://www.nfl.com/games/")).all()


def test_published_line_extract_matches_git_history_when_available():
    """Re-read the three historical files from git; skipped in a shallow clone."""
    import io
    import subprocess
    pub = pd.read_csv(ROOT / "data" / "forward" / "published_lines.csv")
    for s in fg.SETS:
        got = subprocess.run(["git", "show", f"{s['commit']}:{s['path']}"], cwd=ROOT, capture_output=True, text=True)
        if got.returncode != 0:
            pytest.skip("git history for the audited commits is not available in this clone")
        table = pd.read_csv(io.StringIO(got.stdout)).set_index("game_id")
        mine = pub[pub.set == s["set"]]
        assert len(mine) == 28
        np.testing.assert_allclose(mine.line_spread, table.loc[mine.game_id, s["spread"]], atol=1e-6)
        np.testing.assert_allclose(mine.line_total, table.loc[mine.game_id, s["total"]], atol=1e-6)


def test_reproduce_published_board_from_the_pin_when_staged():
    """The freeze engine must regenerate the published board exactly from the pinned files."""
    pin = json.loads((ROOT / "data" / "sources.json").read_text())["upstream"]["commit_sha"]
    staged = (fl.RAWF / pin / "games.csv").exists() or (ROOT / "data" / "raw" / "games.csv").exists()
    if not staged:
        pytest.skip("pinned inputs are not staged (run `make data` first)")
    result = fl.reproduce()
    assert result["ok"], result
    assert result["rows"] == 164 and result["max_abs_difference"] <= 1e-8
