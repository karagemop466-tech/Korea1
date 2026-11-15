"""Guards for the control baselines (CB5): settlement sign convention, push handling, and the
committed outputs. Controls are benchmarks only; these tests never give them a verdict.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import control_baseline as cb  # noqa: E402

OUT_CSV = ROOT / "data" / "processed" / "control_baseline.csv"
OUT_JSON = ROOT / "data" / "processed" / "control_baseline.json"


def _g(cover, dec_home=1.91, dec_away=1.91):
    return pd.DataFrame({"home_cover": cover, "dec_home": dec_home, "dec_away": dec_away})


def test_home_cover_when_home_is_the_favourite_wins():
    # margin 7, market spread 3 (home favoured by 3): home covers by 4.
    g = _g([4.0])
    profit, outcome = cb.settle(g, np.array([True]))
    assert outcome.tolist() == [1]
    assert round(profit[0], 2) == 0.91


def test_away_side_loses_when_home_covers():
    g = _g([4.0])
    profit, outcome = cb.settle(g, np.array([False]))
    assert outcome.tolist() == [-1]
    assert profit.tolist() == [-1.0]


def test_exact_margin_is_a_push_with_zero_profit():
    g = _g([0.0])
    profit, outcome = cb.settle(g, np.array([True]))
    assert outcome.tolist() == [0]
    assert profit.tolist() == [0.0]


def test_universe_home_cover_formula_is_the_documented_convention():
    """Home covers when margin - market_spread > 0 (market_spread positive = home favoured).

    Checked against the source text so the test does not import the backtest module.
    """
    src = (ROOT / "pipeline" / "control_baseline.py").read_text(encoding="utf-8")
    assert 'g["home_cover"] = g["margin"] - g["market_spread"]' in src
    bt = (ROOT / "pipeline" / "backtest.py").read_text(encoding="utf-8")
    assert "spread_line" in bt


def test_committed_outputs_are_internally_consistent():
    rows = list(csv.DictReader(OUT_CSV.open(encoding="utf-8")))
    assert {r["control"] for r in rows} >= {"RANDOM_SIDE", "FAVORITE_ONLY", "HOME_ONLY", "AWAY_ONLY"}
    for r in rows:
        n = int(r["n_bets"])
        parts = int(r["wins"]) + int(r["pushes"]) + int(r["losses"])
        if r["control"] == "RANDOM_SIDE":
            # Columns hold the average of 2000 draws, each rounded on its own, so they may
            # differ from n by the rounding (documented in the row description).
            assert abs(n - parts) <= 1, r["control"]
        else:
            assert n == parts, r["control"]
        assert int(r["universe_games"]) == 5403
        lo, hi = float(r["roi_lo95"]), float(r["roi_hi95"])
        assert lo <= hi
        assert r["evidence_tier"].startswith("COMMUNITY")


def test_favourite_cover_rate_including_pushes_is_the_published_0_473():
    rows = {r["control"]: r for r in csv.DictReader(OUT_CSV.open(encoding="utf-8"))}
    fav = rows["FAVORITE_ONLY"]
    cover_incl_push = int(fav["wins"]) / int(fav["n_bets"])
    assert round(cover_incl_push, 3) == 0.473
    assert int(fav["n_bets"]) == 5398


def test_json_summary_matches_the_csv_random_band():
    d = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    rows = {r["control"]: r for r in csv.DictReader(OUT_CSV.open(encoding="utf-8"))}
    rnd = rows["RANDOM_SIDE"]
    assert d["random_luck_band"] == [float(rnd["roi_lo95"]), float(rnd["roi_hi95"])]
    assert "not eligible" in d["note"].lower() or "not strategies" in d["note"].lower()
