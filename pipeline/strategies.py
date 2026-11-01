"""T3 — the strategy library.

Every strategy is declared here **before** it is run, with its rule, its economic
rationale and its data requirement. The library is executed in full and every
result is published — including the failures. Nothing is dropped after the fact
and no threshold is tuned on the backtest.

Families
--------
`model`   uses the originated line (spread / total / moneyline) against the close
`angle`   a classic, publicly-known situational rule, deliberately naive
`parlay`  combined tickets priced from the legs' real closing prices

Parlay pricing uses the actual leg prices (product of decimals). Push handling is
"ties reduce": a pushed leg is removed and the rest of the ticket keeps its price.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, implied_prob, novig_probs  # noqa: E402


@dataclass
class Spec:
    id: str
    name: str
    family: str
    market: str
    rule: str
    rationale: str
    select: Callable[[pd.DataFrame], list[dict]]
    min_bets: int = 100
    params: dict = field(default_factory=dict)


def _mk(rows, market, side, signal):
    out = []
    for r in rows:
        sig = float(signal(r))
        if not np.isfinite(sig):
            continue
        out.append({**r, "_market": market, "_side": side(r), "_signal": sig})
    return out


# ---------------------------------------------------------------------------
# derived, still pre-game, signals used by the angle family
# ---------------------------------------------------------------------------
def add_prev_form(df: pd.DataFrame) -> pd.DataFrame:
    """Each team's margin in its previous game (pre-game information)."""
    df = df.sort_values(["season", "week", "game_id"]).reset_index(drop=True)
    last = {}
    prev_h, prev_a = [], []
    for r in df.itertuples(index=False):
        prev_h.append(last.get(r.home_team, np.nan))
        prev_a.append(last.get(r.away_team, np.nan))
        last[r.home_team] = r.result
        last[r.away_team] = -r.result
    df["prev_margin_h"] = prev_h
    df["prev_margin_a"] = prev_a
    return df


def add_market_probs(df: pd.DataFrame) -> pd.DataFrame:
    """No-vig market probabilities for spread, total and moneyline."""
    sp = [novig_probs(a, b) if np.isfinite(a) and np.isfinite(b) else (np.nan, np.nan)
          for a, b in zip(df.home_spread_odds, df.away_spread_odds)]
    df["mkt_p_home_spread"] = [p[0] for p in sp]
    df["mkt_p_away_spread"] = [p[1] for p in sp]
    tt = [novig_probs(a, b) if np.isfinite(a) and np.isfinite(b) else (np.nan, np.nan)
          for a, b in zip(df.over_odds, df.under_odds)]
    df["mkt_p_over"] = [p[0] for p in tt]
    df["mkt_p_under"] = [p[1] for p in tt]
    ml = [novig_probs(a, b) if np.isfinite(a) and np.isfinite(b) else (np.nan, np.nan)
          for a, b in zip(df.market_home_ml, df.market_away_ml)]
    df["mkt_p_home_ml"] = [p[0] for p in ml]
    df["mkt_p_away_ml"] = [p[1] for p in ml]
    return df


def _edge_spread(df, thr):
    rows = df[df.edge_spread.abs() >= thr]
    return _mk(rows.to_dict("records"), "SPREAD",
               lambda r: "home" if r["edge_spread"] > 0 else "away",
               lambda r: abs(r["edge_spread"]))


def _edge_total(df, thr):
    rows = df[df.edge_total.abs() >= thr]
    return _mk(rows.to_dict("records"), "TOTAL",
               lambda r: "over" if r["edge_total"] > 0 else "under",
               lambda r: abs(r["edge_total"]))


def _ml_edge(df, thr):
    d = df.copy()
    d["ml_edge_home"] = d.p_home_ml - d.mkt_p_home_ml
    d["ml_edge_away"] = d.p_away_ml - d.mkt_p_away_ml
    d["ml_edge"] = np.where(d.ml_edge_home >= d.ml_edge_away, d.ml_edge_home, d.ml_edge_away)
    rows = d[(d.ml_edge >= thr) & d.market_home_ml.notna()]
    return _mk(rows.to_dict("records"), "MONEYLINE",
               lambda r: "home" if r["ml_edge_home"] >= r["ml_edge_away"] else "away",
               lambda r: r["ml_edge"])


def _fixed(rows, market, side, signal_name):
    if isinstance(rows, pd.DataFrame):
        recs = rows.to_dict("records")
    else:
        recs = rows
    return _mk(recs, market, lambda r: side, lambda r: r[signal_name])


def build_library() -> list[Spec]:
    L: list[Spec] = []

    for thr in (1.0, 2.0, 3.0):
        L.append(Spec(
            id=f"SP_EDGE_{str(thr).replace('.', '_')}",
            name=f"Spread — model edge ≥ {thr} pt",
            family="model", market="SPREAD",
            rule=f"Bet the side where |originated spread − closing spread| ≥ {thr}.0 points",
            rationale=("If the originated (market-free) line is a better predictor than the "
                       "close, discrepancies are positive expected value."),
            select=(lambda t: lambda df: _edge_spread(df, t))(thr),
            params={"threshold_points": thr}))

    for thr in (2.0, 3.5):
        L.append(Spec(
            id=f"TOT_EDGE_{str(thr).replace('.', '_')}",
            name=f"Total — model edge ≥ {thr} pt",
            family="model", market="TOTAL",
            rule=f"Bet over/under where |originated total − closing total| ≥ {thr} points",
            rationale="Same logic as the spread edge, applied to the game total.",
            select=(lambda t: lambda df: _edge_total(df, t))(thr),
            params={"threshold_points": thr}))

    for thr in (0.05, 0.10):
        L.append(Spec(
            id=f"ML_EDGE_{int(thr*100)}",
            name=f"Moneyline — model probability edge ≥ {int(thr*100)} pts",
            family="model", market="MONEYLINE",
            rule=(f"Bet the moneyline side where model win probability exceeds the "
                  f"de-vigged closing probability by ≥ {int(thr*100)} percentage points"),
            rationale="Prices a mispriced tail; the de-vig makes the comparison like-for-like.",
            select=(lambda t: lambda df: _ml_edge(df, t))(thr),
            params={"threshold_prob": thr}))

    L.append(Spec(
        id="HOME_DOG_ATS", name="Home underdog ATS", family="angle", market="SPREAD",
        rule="Every home underdog (closing line against the home team) takes the points",
        rationale="The most heavily studied public-bias angle in NFL betting.",
        select=lambda df: _fixed(df[df.market_spread < 0], "SPREAD", "home", "market_spread")))

    L.append(Spec(
        id="ROAD_FAV_ATS", name="Road favourite ATS", family="angle", market="SPREAD",
        rule="Every road favourite lays the points",
        rationale=("Exact mirror of the home-dog angle (same games, opposite side). The two "
                   "ROIs must sum to about minus the vig if settlement is correct — a built-in "
                   "arithmetic check on the backtest engine."),
        # spread_line > 0 means the HOME team is favoured, so a road favourite is
        # spread_line < 0 and the bet is on the away side.
        select=lambda df: _fixed(df[df.market_spread < 0], "SPREAD", "away", "market_spread")))

    L.append(Spec(
        id="WIND_UNDER", name="Wind ≥ 15 mph → under", family="angle", market="TOTAL",
        rule="Games with recorded kickoff wind ≥ 15 mph: bet the under",
        rationale="Passing efficiency falls in wind; if the market under-adjusts, unders pay.",
        select=lambda df: _fixed(df[(df.wind >= 15) & (df.wind_missing == 0)], "TOTAL", "under", "wind")))

    L.append(Spec(
        id="COLD_UNDER", name="Kickoff ≤ 32°F → under", family="angle", market="TOTAL",
        rule="Games with recorded kickoff temperature ≤ 32°F: bet the under",
        rationale="Cold-weather scoring suppression versus market adjustment.",
        select=lambda df: _fixed(df[(df.temp <= 32) & (df.temp_missing == 0)], "TOTAL", "under", "temp")))

    L.append(Spec(
        id="DIV_UNDER", name="Divisional games → under", family="angle", market="TOTAL",
        rule="Divisional matchups: bet the under",
        rationale="Familiarity is widely claimed to depress scoring.",
        select=lambda df: _fixed(df[df.div_game == 1], "TOTAL", "under", "div_game")))

    L.append(Spec(
        id="REST_ADV_ATS", name="Rest advantage ≥ 7 days ATS", family="angle", market="SPREAD",
        rule="Back the team with ≥ 7 more days of rest (home if rest_diff ≥ 7, away if ≤ −7)",
        rationale="Bye-week and short-week effects are a standard situational angle.",
        select=lambda df: _mk(
            df[df.rest_diff.abs() >= 7].to_dict("records"), "SPREAD",
            lambda r: "home" if r["rest_diff"] > 0 else "away", lambda r: abs(r["rest_diff"]))))

    L.append(Spec(
        id="FADE_BLOWOUT_ATS", name="Fade a 21+ point winner", family="angle", market="SPREAD",
        rule="Bet against any team that won its previous game by ≥ 21 points",
        rationale="Tests public overreaction to a single blowout.",
        select=lambda df: _fade(df, threshold=21.0, fade_winner=True)))

    L.append(Spec(
        id="BUY_LOW_ATS", name="Back a 17+ point loser", family="angle", market="SPREAD",
        rule="Bet on any team that lost its previous game by ≥ 17 points",
        rationale="Mirror of the fade angle: tests mean reversion after a bad beat.",
        select=lambda df: _fade(df, threshold=-17.0, fade_winner=False)))

    # ---- parlays ----------------------------------------------------------
    L.append(Spec(
        id="PARLAY2_EDGE", name="2-leg parlay — top spread edges", family="parlay",
        market="PARLAY",
        rule="Each week, combine the two largest |spread edge| bets on the slate",
        rationale="Compounding independent edges; the legs come from different games, so "
                  "cross-game correlation should be ≈ 0 and the naive price should be fair.",
        select=lambda df: _parlay(df, 2, "edge_spread"),
        params={"legs": 2}))

    L.append(Spec(
        id="PARLAY3_EDGE", name="3-leg parlay — top spread edges", family="parlay",
        market="PARLAY",
        rule="Each week, combine the three largest |spread edge| bets on the slate",
        rationale="As above with a third leg; shows how variance scales with leg count.",
        select=lambda df: _parlay(df, 3, "edge_spread"),
        params={"legs": 3}))

    L.append(Spec(
        id="PARLAY2_ML", name="2-leg moneyline parlay — top ML edges", family="parlay",
        market="PARLAY",
        rule="Each week, combine the two largest moneyline probability edges",
        rationale="Moneyline legs offer bigger prices; tests whether the ML edges compound.",
        select=lambda df: _parlay(df, 2, "ml_edge"),
        params={"legs": 2}))

    return L


def _fade(df: pd.DataFrame, threshold: float, fade_winner: bool) -> list[dict]:
    recs = []
    for r in df.to_dict("records"):
        prev_h, prev_a = r.get("prev_margin_h"), r.get("prev_margin_a")
        if fade_winner:
            if np.isfinite(prev_h) and prev_h >= threshold:
                recs.append({**r, "_market": "SPREAD", "_side": "away", "_signal": prev_h})
            elif np.isfinite(prev_a) and prev_a >= threshold:
                recs.append({**r, "_market": "SPREAD", "_side": "home", "_signal": prev_a})
        else:
            if np.isfinite(prev_h) and prev_h <= threshold:
                recs.append({**r, "_market": "SPREAD", "_side": "home", "_signal": -prev_h})
            elif np.isfinite(prev_a) and prev_a <= threshold:
                recs.append({**r, "_market": "SPREAD", "_side": "away", "_signal": -prev_a})
    return recs


def _parlay(df: pd.DataFrame, legs: int, edge_col: str) -> list[dict]:
    """One ticket per (season, week): the biggest edges on that slate."""
    d = df.copy()
    if edge_col == "ml_edge":
        d["ml_edge_home"] = d.p_home_ml - d.mkt_p_home_ml
        d["ml_edge_away"] = d.p_away_ml - d.mkt_p_away_ml
        d["_e"] = np.where(d.ml_edge_home >= d.ml_edge_away, d.ml_edge_home, d.ml_edge_away)
        d["_side"] = np.where(d.ml_edge_home >= d.ml_edge_away, "home", "away")
        d["_market"] = "MONEYLINE"
    else:
        d["_e"] = d[edge_col].abs()
        d["_side"] = np.where(d[edge_col] > 0, "home", "away")
        d["_market"] = "SPREAD"
    d = d[np.isfinite(d._e)]
    out = []
    for (season, week), g in d.groupby(["season", "week"]):
        g = g.sort_values("_e", ascending=False)
        picks = g.head(legs)
        if len(picks) < legs:
            continue
        if picks.game_id.nunique() < legs:
            continue
        out.append({"_parlay_legs": picks.to_dict("records"), "_season": season, "_week": week})
    return out


def price_parlay(legs: list[dict]) -> tuple[float, list[dict]]:
    """Multiply leg decimals; pushed legs drop out (ties reduce)."""
    from common import american_to_decimal
    dec = 1.0
    kept = []
    for leg in legs:
        if leg["_market"] == "MONEYLINE":
            price = leg["market_home_ml"] if leg["_side"] == "home" else leg["market_away_ml"]
        elif leg["_market"] == "SPREAD":
            price = leg["home_spread_odds"] if leg["_side"] == "home" else leg["away_spread_odds"]
        else:
            price = leg["over_odds"] if leg["_side"] == "over" else leg["under_odds"]
        if not np.isfinite(price):
            return float("nan"), []
        dec *= american_to_decimal(price)
        kept.append({**leg, "_price": float(price)})
    return dec, kept
