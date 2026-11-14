"""U3 (arena/fcba7eb5-korea1): the price-snapshot store.

Checks: every originated game has exactly three market rows in the fixed order
side -> total -> moneyline; opening and closing cells are blank everywhere because no
official or operator-timestamped quote exists; the 14 frozen forward games carry their
ledger freeze time and hash; the coverage register agrees with the store.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import price_snapshots as ps  # noqa: E402


def _store() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "forward" / "price_snapshots.csv", dtype=str, keep_default_na=False)


def test_three_markets_per_game_in_origination_order():
    s = _store()
    assert s.groupby("game_id").size().eq(3).all()
    order = s.groupby("game_id").origination_order.apply(lambda x: tuple(x))
    assert set(order) == {("1", "2", "3")}
    assert list(s[s.origination_order == "1"].market.unique()) == ["SPREAD"]
    assert list(s[s.origination_order == "2"].market.unique()) == ["TOTAL"]
    assert list(s[s.origination_order == "3"].market.unique()) == ["MONEYLINE"]


def test_every_originated_game_is_covered():
    lines = pd.read_csv(ROOT / "data" / "processed" / "originated_lines.csv", usecols=["game_id"])
    up = pd.read_csv(ROOT / "data" / "processed" / "originated_upcoming.csv", usecols=["game_id"])
    want = set(lines.game_id) | set(up.game_id)
    assert set(_store().game_id) == want


def test_opening_and_closing_are_blank_everywhere_until_an_official_quote_exists():
    s = _store()
    for col in ["opening_value", "opening_utc", "opening_source", "closing_value", "closing_utc", "closing_source"]:
        assert (s[col] == "").all(), col
    assert (s.opening_status == ps.UNVERIFIED_OPEN).all()
    assert (s.closing_status == ps.UNVERIFIED_CLOSE).all()


def test_the_repository_states_no_official_quote_source():
    import json
    cfg = json.loads((ROOT / "data" / "processed" / "validation_config.json").read_text())
    assert cfg["official_quote_source_available"] is False


def test_frozen_forward_games_carry_their_ledger_time_and_hash():
    s = _store()
    cards = pd.read_csv(ROOT / "data" / "forward" / "cards.csv", dtype=str, keep_default_na=False)
    frozen = s[s.originated_utc != ps.NOT_RECORDED]
    assert set(frozen.game_id) == set(cards.game_id)
    assert (frozen.ledger_entry_hash != "").all()
    assert frozen.originated_utc.str.endswith("Z").all()


def test_walk_forward_values_say_their_time_was_not_recorded():
    s = _store()
    rest = s[~s.game_id.isin(pd.read_csv(ROOT / "data" / "forward" / "cards.csv", dtype=str).game_id)]
    assert (rest.originated_utc == ps.NOT_RECORDED).all()
    assert (rest.ledger_entry_hash == "").all()


def test_coverage_register_matches_the_store():
    s = _store()
    cov = pd.read_csv(ROOT / "data" / "governance" / "price_snapshot_coverage.csv")
    assert int(cov.markets_originated.sum()) == len(s)
    assert int(cov.games_originated.sum()) == s.game_id.nunique()
    assert int(cov.opening_verified.sum()) == 0 and int(cov.closing_verified.sum()) == 0
    assert (cov.community_close_copied_to_store == 0).all()


def test_moneyline_row_has_both_prices_and_no_spread_value():
    s = _store()
    ml = s[s.market == "MONEYLINE"]
    assert (ml.originated_value == "").all()
    assert (ml.originated_home_ml != "").all() and (ml.originated_away_ml != "").all()
