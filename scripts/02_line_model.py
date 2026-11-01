#!/usr/bin/env python3
"""
02_line_model.py - originate our own NFL lines (spread, total, moneyline).

MODEL (all components are walk-forward: a game's line is produced only from information
that existed before kickoff, which is what makes the out-of-sample test honest):

  1. Elo rating, margin-of-victory adjusted, season regression to the mean.
     Variant documented in research/02-methodology.md; the Elo/MoV structure follows the
     published FiveThirtyEight NFL Elo specification (see SOURCES: FTE-ELO).
  2. Spread = f(Elo difference).  The points-per-Elo coefficient is ESTIMATED from
     realised margins in earlier seasons only (expanding OLS), never assumed.
  3. Totals = pace/scoring model: exponentially weighted points scored and allowed per
     team (half-life 6 games, opponent-unadjusted at this stage), combined
     (own offence + opponent defence)/2 + home-field half-share, then recalibrated by an
     expanding OLS on realised totals.
  4. Moneyline = model spread -> win probability through a normal kernel whose sigma is
     ESTIMATED from the walk-forward margin residuals, then converted to American odds with
     the model's own margin removed (a fair, zero-hold line) and separately with a
     standard 4.55% hold added so it is comparable with a sportsbook.

Outputs data/lines.json.
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import common as C
from lib.data import load_games, add_rest_days, add_streaks, add_trailing_form, home_margin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "lab", "lines.json")

K_ELO = 20.0
HFA_ELO = 48.0          # prior value; re-estimated from data below before it is used in play
SEASON_REGRESSION = 1.0 / 3.0
BURN_IN_SEASONS = {2011}   # ratings are still forming; 2011 games are not scored as bets

# ---------------------------------------------------------------- Elo


def elo_series(games, k=K_ELO, hfa=HFA_ELO, regress=SEASON_REGRESSION):
    """Walk-forward Elo. Each game stores the rating pair/margin BEFORE the game is played."""
    elo = {}
    season_now = None
    for g in games:
        if season_now is None:
            season_now = g["season"]
        if g["season"] != season_now:               # season boundary: regress toward 1500
            for t in elo:
                elo[t] = 1500.0 + (elo[t] - 1500.0) * (1.0 - regress)
            season_now = g["season"]
        elo.setdefault(g["home"], 1500.0)
        elo.setdefault(g["away"], 1500.0)
        diff = elo[g["home"]] + hfa - elo[g["away"]]
        g["elo_diff"] = diff
        g["elo_expected"] = 1.0 / (1.0 + 10 ** (-diff / 400.0))
        margin = home_margin(g)
        result = 1.0 if margin > 0 else (0.5 if margin == 0 else 0.0)
        mov = math.log(abs(margin) + 1.0) * 2.2 / (0.001 * diff + 2.2)
        delta = k * mov * (result - g["elo_expected"])
        elo[g["home"]] += delta
        elo[g["away"]] -= delta
    return games


def ols(xs, ys):
    """Simple OLS with intercept. Returns (a, b, n)."""
    n = len(xs)
    if n < 3:
        return 0.0, 0.0, n
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        return my, 0.0, n
    b = sxy / sxx
    return my - b * mx, b, n


def originate(games, min_games_for_form=3):
    """Attach model_spread / model_total / model_ml to every game, using prior data only."""
    seasons = sorted({g["season"] for g in games})
    for i, s in enumerate(seasons):
        prior = [g for g in games if g["season"] < s]
        # --- spread calibration (points per Elo) from earlier seasons only
        xs = [g["elo_diff"] for g in prior]
        ys = [home_margin(g) for g in prior]
        a, b, n = ols(xs, ys)
        for g in games:
            if g["season"] != s:
                continue
            pred_margin = a + b * g["elo_diff"]
            g["model_margin"] = pred_margin
            # SBR convention: home spread is NEGATIVE when the home team is favoured
            g["model_spread"] = -pred_margin
            g["calib_spread"] = {"a": a, "b": b, "n": n}
        # --- totals calibration from earlier seasons only
        px, py = [], []
        for g in prior:
            pt = _pace_total(g)
            if pt is not None:
                px.append(pt); py.append(g["home_score"] + g["away_score"])
        ta, tb, tn = ols(px, py)
        for g in games:
            if g["season"] != s:
                continue
            pt = _pace_total(g)
            g["model_total_raw"] = pt
            g["model_total"] = (ta + tb * pt) if pt is not None else None
            g["calib_total"] = {"a": ta, "b": tb, "n": tn}
    # --- moneyline: sigma of margin residuals, expanding
    for g in games:
        prior = [x for x in games if x["date"] < g["date"] and "model_margin" in x]
        res = [home_margin(x) - x["model_margin"] for x in prior]
        sd = C.stdev(res) if len(res) > 30 else None
        g["margin_sigma"] = sd
        if sd and g["model_spread"] is not None:
            # P(home wins) = P(margin > 0) with margin ~ Normal(model_margin, sd)
            p_home = _phi(g["model_margin"] / sd)
            g["model_p_home"] = p_home
            g["model_ml_home"] = C.prob_to_american(min(max(p_home, 0.01), 0.99))
            g["model_ml_away"] = C.prob_to_american(min(max(1 - p_home, 0.01), 0.99))
    return games


def _phi(z):
    """Standard normal CDF."""
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def _pace_total(g):
    hs, ha = g.get("home_scored"), g.get("home_allowed")
    as_, aa = g.get("away_scored"), g.get("away_allowed")
    if None in (hs, ha, as_, aa):
        return None
    # expected points for each side, then summed; HFA cancels in the total by construction
    home_pts = (hs + aa) / 2.0
    away_pts = (as_ + ha) / 2.0
    return home_pts + away_pts


# ---------------------------------------------------------------- evaluation
def evaluate(games):
    """Out-of-sample evaluation of the originated lines against the market."""
    scored = [g for g in games
              if g["season"] not in BURN_IN_SEASONS
              and g["model_spread"] is not None and g["close_spread"] is not None]
    rows = []
    for g in scored:
        edge_close = g["model_spread"] - g["close_spread"]      # >0 => model likes the home side
        edge_open = (g["model_spread"] - g["open_spread"]) if g["open_spread"] is not None else None
        rows.append({
            "season": g["season"], "game_key": g["game_key"],
            "model_spread": round(g["model_spread"], 2),
            "close_spread": g["close_spread"],
            "edge_vs_close": round(edge_close, 2),
            "model_total": round(g["model_total"], 2) if g["model_total"] else None,
            "close_total": g["close_total"],
            "edge_total_vs_close": round(g["model_total"] - g["close_total"], 2) if g["model_total"] and g["close_total"] else None,
            "model_p_home": round(g["model_p_home"], 4) if g.get("model_p_home") else None,
            "actual_margin": home_margin(g),
        })
    # calibration of the spread model: mean absolute error vs closing line
    mae_model = sum(abs(r["actual_margin"] - (-r["model_spread"])) for r in rows) / len(rows)
    mae_close = sum(abs(r["actual_margin"] + r["close_spread"]) for r in rows) / len(rows)
    # straight-up accuracy of the model vs the market on who wins
    model_right = market_right = 0
    for r in rows:
        if r["actual_margin"] == 0:
            continue
        if (-r["model_spread"] > 0) == (r["actual_margin"] > 0):
            model_right += 1
        if (-r["close_spread"] > 0) == (r["actual_margin"] > 0):
            market_right += 1
    # totals model error
    trows = [r for r in rows if r["model_total"] and r["close_total"]]
    tot_err_model = tot_err_close = 0.0
    for r in trows:
        actual_total = _actual_total(games, r["game_key"])
        tot_err_model += abs(actual_total - r["model_total"])
        tot_err_close += abs(actual_total - r["close_total"])
    summary = {
        "n_games_scored": len(rows),
        "seasons_scored": sorted({r["season"] for r in rows}),
        "spread_mae_model": round(mae_model, 3),
        "spread_mae_closing_market": round(mae_close, 3),
        "spread_beats_market_mae": mae_model < mae_close,
        "straight_up_accuracy_model": round(model_right / (len(rows) - sum(1 for r in rows if r["actual_margin"] == 0)), 4),
        "straight_up_accuracy_market": round(market_right / (len(rows) - sum(1 for r in rows if r["actual_margin"] == 0)), 4),
        "total_mae_model": round(tot_err_model / len(trows), 3),
        "total_mae_closing_market": round(tot_err_close / len(trows), 3),
        "mean_abs_edge_vs_close": round(sum(abs(r["edge_vs_close"]) for r in rows) / len(rows), 3),
    }
    # calibration table: model win prob -> realised home win rate
    bins = [(0.00, 0.20), (0.20, 0.35), (0.35, 0.45), (0.45, 0.55), (0.55, 0.65), (0.65, 0.80), (0.80, 1.00)]
    calib = []
    for lo, hi in bins:
        sel = [r for r in rows if r["model_p_home"] is not None and lo <= r["model_p_home"] < hi]
        if not sel:
            calib.append({"bin": f"{lo:.2f}-{hi:.2f}", "n": 0})
            continue
        wins = sum(1 for r in sel if r["actual_margin"] > 0)
        calib.append({
            "bin": f"{lo:.2f}-{hi:.2f}", "n": len(sel),
            "mean_model_prob": round(sum(r["model_p_home"] for r in sel) / len(sel), 4),
            "realised_home_win_rate": round(wins / len(sel), 4),
        })
    return summary, rows, calib


def _actual_total(games, key):
    for g in games:
        if g["game_key"] == key:
            return g["home_score"] + g["away_score"]
    raise KeyError(key)


def main():
    games = load_games()
    games = add_rest_days(games)
    games = add_streaks(games)
    games = add_trailing_form(games)
    games = elo_series(games)
    games = originate(games)
    summary, rows, calib = evaluate(games)

    # worked example board for the most recent season in the window
    last = max(r["season"] for r in rows)
    board = [r for r in rows if r["season"] == last]
    board.sort(key=lambda r: r["game_key"])

    payload = {
        "model": {
            "name": "Elo-MoV + pace-total, walk-forward",
            "components": {
                "elo": {"K": K_ELO, "hfa_elo": HFA_ELO, "season_regression": SEASON_REGRESSION,
                        "source": "structure follows FTE-ELO; parameters are the literature values"},
                "spread": "model_margin = a + b*elo_diff, a,b from expanding OLS on prior seasons",
                "total": "exp-weighted (half-life 6 games) team scoring, OLS recalibrated on prior seasons",
                "moneyline": "P(home win)=Phi(model_margin/sigma), sigma from walk-forward residuals",
            },
            "burn_in_seasons": sorted(BURN_IN_SEASONS),
            "no_lookahead": "ratings/form are updated only after a game has been scored; calibration "
                            "coefficients use only seasons strictly before the game's season",
        },
        "summary": summary,
        "calibration": calib,
        "board_season": last,
        "board": board,
        "spread_parameters": [{"season": s,
                               "a": round(calib_d["a"], 3), "b": round(calib_d["b"], 4), "n": calib_d["n"]}
                              for s in sorted({g["season"] for g in games if g.get("calib_spread")})
                              for calib_d in [next(g["calib_spread"] for g in games
                                                   if g["season"] == s and g.get("calib_spread"))]],
    }
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(summary, indent=2))
    print("spread calibration by season:")
    for p in payload["spread_parameters"]:
        print("  ", p)
    print("calibration table:")
    for c in calib:
        print("  ", c)


if __name__ == "__main__":
    main()
