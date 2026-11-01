#!/usr/bin/env python3
"""
03_strategies.py - the single-bet strategy battery + honest backtests.

Every strategy is stated as a rule that uses only information available before kickoff.
Nothing is fitted to the outcome data: the rules come from published market-structure
research and standard betting practice, and they are fixed before the backtest is run.
That is what makes the multiple-testing correction in 06_validation.py meaningful.

PRICE ASSUMPTION (stated, not hidden): the archive carries no per-bet price, so spread and
total bets are settled at the standard -110.  06_validation.py re-runs every strategy at
-115 to check the result does not depend on getting -110.

SETTLEMENT: push = 0 profit, excluded from win-rate denominators.

CLV (closing line value): available only for strategies that bet the OPENING line.
  spread, home side: clv = open - close          (more positive = we beat the close)
  spread, away side: clv = close - open
  total,  over     : clv = close - open
  total,  under    : clv = open - close
Beating the closing line is the standard evidence of skill (see research/02-methodology.md).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import common as C
from lib.data import (load_games, add_rest_days, add_streaks, add_trailing_form,
                      home_margin, DIVISIONS)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "lab", "strategies.json")
STD_PRICE = -110.0
IN_SAMPLE = (2012, 2017)
OUT_SAMPLE = (2018, 2021)


def _bet(g, market, side, line, price, clv=None, **meta):
    """Settle one bet. market in {'spread','total','ml'}."""
    hs, as_ = g["home_score"], g["away_score"]
    if market == "spread":
        out = C.settle_spread(side, line, hs, as_)
    elif market == "total":
        out = C.settle_total(side, line, hs, as_)
    else:
        out = C.settle_ml(side, hs, as_)
    profit = C.payout_per_unit(out, price)
    return {
        "game_key": g["game_key"], "season": g["season"], "date": g["date"],
        "market": market, "side": side, "line": line, "price": price,
        "outcome": out, "profit": round(profit, 6),
        "clv": (round(clv, 3) if clv is not None else None),
        **meta,
    }


# ---------------------------------------------------------------- strategy definitions

# ---------------------------------------------------------------- bet constructors
def spread_bet(g, side, where="close", price=STD_PRICE, **meta):
    """Spread bet. where='open' also yields closing-line value (CLV)."""
    raw = g[f"{where}_spread"]
    if raw is None:
        return None
    line = raw if side == "home" else -raw
    clv = None
    if where == "open" and g["close_spread"] is not None:
        d = g["open_spread"] - g["close_spread"]
        clv = d if side == "home" else -d
    return _bet(g, "spread", side, line, price, clv=clv, execution=f"{where}_line", **meta)


def total_bet(g, side, where="close", price=STD_PRICE, **meta):
    """Total bet. Over wins more often when the closing line is higher than the price paid."""
    raw = g[f"{where}_total"]
    if raw is None:
        return None
    clv = None
    if where == "open" and g["close_total"] is not None:
        d = g["close_total"] - g["open_total"]
        clv = d if side == "over" else -d
    return _bet(g, "total", side, raw, price, clv=clv, execution=f"{where}_line", **meta)


def build_strategies(games):
    """Return a list of {id, name, family, description, rule_note, bets}."""
    S = []

    def add(sid, name, family, description, note, bets):
        S.append({"id": sid, "name": name, "family": family,
                  "description": description, "rule_note": note, "bets": bets})

    sd = [g for g in games if g["close_spread"] is not None]
    tot = [g for g in games if g["close_total"] is not None]

    # --- 1/2. Model edge against the closing spread -------------------------------
    for sid, thr in (("S01", 2.0), ("S02", 3.5)):
        bets = []
        for g in sd:
            if g["season"] == 2011 or g["model_spread"] is None:
                continue
            edge = g["model_spread"] - g["close_spread"]
            if abs(edge) < thr:
                continue
            side = "home" if edge > 0 else "away"
            line = g["close_spread"] if side == "home" else -g["close_spread"]
            bets.append(_bet(g, "spread", side, line, STD_PRICE,
                             clv=None, edge=round(abs(edge), 2)))
        add(sid, f"Model spread edge >= {thr:g} pts",
            "model_edge",
            "Bet the side the originated line favours when it differs from the closing "
            "spread by at least the threshold.",
            "Uses the walk-forward model line from 02_line_model.py; bet at the closing line, "
            "so no CLV is measurable.", bets)

    # --- 3/4. Line-move fade / follow ---------------------------------------------
    for sid, sign, label in (("S03", -1, "Fade the move"), ("S04", 1, "Follow the move")):
        bets = []
        for g in sd:
            if g["open_spread"] is None:
                continue
            move = g["close_spread"] - g["open_spread"]          # negative => home got more favoured
            if abs(move) < 1.5:
                continue
            # direction the market moved TOWARD: home if move < 0
            moved_toward_home = move < 0
            bet_home = moved_toward_home if sign > 0 else (not moved_toward_home)
            side = "home" if bet_home else "away"
            line = g["close_spread"] if side == "home" else -g["close_spread"]
            bets.append(_bet(g, "spread", side, line, STD_PRICE,
                             clv=None, move=round(move, 2)))
        add(sid, f"{label} >= 1.5 pts of opening-to-closing movement", "market_microstructure",
            "Bet against (fade) or with (follow) a spread that moved at least 1.5 points "
            "between the opening and closing number.",
            "The bet is placed at the closing line, which is the realistic execution point "
            "for a retail bettor reacting to a move.", bets)

    # --- 5. Home underdogs ---------------------------------------------------------
    bets = []
    for g in sd:
        if g["open_spread"] is None:
            continue
        if 3.0 <= g["open_spread"] <= 7.0:       # SBR: positive = home is the underdog
            b = spread_bet(g, "home", "open")
            if b:
                bets.append(b)
    add("S05", "Home underdog +3 to +7 (opening line)", "situational",
        "Back the home team when the opening spread puts it between +3 and +7.",
        "Bet at the opening line, so closing-line value is measurable. Tested because it is "
        "widely claimed, not because it looked good in this data.", bets)

    # --- 6. Team off a bye ---------------------------------------------------------
    bets = []
    for g in sd:
        for side in ("home", "away"):
            rest = g.get(f"{side}_rest")
            if rest is not None and rest >= 13:
                b = spread_bet(g, side, "open", rest=rest)
                if b:
                    bets.append(b)
    add("S06", "Back the team coming off a bye (opening line)", "situational",
        "Any team whose previous game was 13+ days earlier is backed ATS.",
        "Bye weeks are detected from the gap between consecutive game dates, not from a "
        "schedule file, so it cannot leak future information.", bets)

    # --- 7. Short-rest road team ---------------------------------------------------
    bets = []
    for g in sd:
        ar = g.get("away_rest")
        if ar is not None and ar <= 6:
            b = spread_bet(g, "home", "open", away_rest=ar)
            if b:
                bets.append(b)
    add("S07", "Fade the short-rest road team (opening line)", "schedule_spot",
        "Back the home team when the visitor played 6 or fewer days earlier "
        "(Thursday games and short weeks).", "Rest is computed from prior game dates only.", bets)

    # --- 8. Rest differential ------------------------------------------------------
    bets = []
    for g in sd:
        hr, ar = g.get("home_rest"), g.get("away_rest")
        if hr is None or ar is None:
            continue
        if abs(hr - ar) < 4:
            continue
        side = "home" if hr > ar else "away"
        b = spread_bet(g, side, "open", rest_diff=hr - ar)
        if b:
            bets.append(b)
    add("S08", "Back the team with 4+ extra rest days (opening line)", "schedule_spot",
        "Bet the side with at least four more rest days than its opponent.",
        "Bet at the opening line so CLV is measurable.", bets)

    # --- 9. Fade 3+ win streaks ----------------------------------------------------
    bets = []
    for g in sd:
        for side in ("home", "away"):
            if g.get(f"{side}_streak", 0) >= 3:
                opp = "away" if side == "home" else "home"
                b = spread_bet(g, opp, "open", faded_team=g[side])
                if b:
                    bets.append(b)
    add("S09", "Fade a 3+ game win streak (opening line)", "behavioural",
        "Bet against any team entering the game on a run of three or more straight wins.",
        "Tests the recency/overreaction hypothesis.", bets)

    # --- 10. Totals: model edge ----------------------------------------------------
    bets = []
    for g in tot:
        if g["season"] == 2011 or g.get("model_total") is None:
            continue
        edge = g["model_total"] - g["close_total"]
        if abs(edge) < 3.0:
            continue
        side = "over" if edge > 0 else "under"
        bets.append(_bet(g, "total", side, g["close_total"], STD_PRICE, edge=round(abs(edge), 2)))
    add("S10", "Model total edge >= 3 pts", "model_edge",
        "Bet Over/Under when the pace model's total differs from the closing total by 3+ points.",
        "Bet at the closing total.", bets)

    # --- 11/12. Totals at the extremes of the season distribution -------------------
    season_totals = {}
    for g in tot:
        season_totals.setdefault(g["season"], []).append(g["close_total"])
    cut = {s: (sorted(v)[max(0, int(0.10 * len(v)) - 1)], sorted(v)[min(len(v) - 1, int(0.90 * len(v)))])
           for s, v in season_totals.items()}
    for sid, side, pick, label in (("S11", "under", 1, "Under the highest-decile totals"),
                                   ("S12", "over", 0, "Over the lowest-decile totals")):
        bets = []
        for g in tot:
            lo, hi = cut[g["season"]]
            if g["open_total"] is None:
                continue
            if (pick == 1 and g["open_total"] >= hi) or (pick == 0 and g["open_total"] <= lo):
                b = total_bet(g, side, "open")
                if b:
                    bets.append(b)
        add(sid, label, "behavioural",
            "Bet the contrarian side of the season's most extreme totals, testing the "
            "public preference for high-scoring games.", "Deciles are computed within season.", bets)

    # --- 13/14. Moneyline price buckets (favourite-longshot bias) ------------------
    ml_games = [g for g in games if g["home_ml"] is not None]
    for sid, lo, hi, side_sel, label in (
            ("S13", 200, 400, "dog", "Underdogs priced +200 to +400 (win only)"),
            ("S14", -250, -150, "fav", "Favourites priced -150 to -250 (win only)")):
        bets = []
        for g in ml_games:
            for side in ("home", "away"):
                price = g[f"{side}_ml"]
                other = g["away_ml" if side == "home" else "home_ml"]
                if side_sel == "dog" and not (price > 0 and lo <= price <= hi):
                    continue
                if side_sel == "fav" and not (lo <= price <= hi):
                    continue
                if price is None or other is None:
                    continue
                bets.append(_bet(g, "ml", side, None, price, opponent_price=other))
        add(sid, label, "price_structure",
            "Flat-stake moneyline bets inside a single price bucket, used to measure the "
            "favourite-longshot bias directly on realised returns.",
            "Priced at the actual archived moneyline, so the vig is included exactly as traded.",
            bets)

    # --- 15. Moneyline model edge vs the de-margined market ------------------------
    bets = []
    for g in ml_games:
        if g["season"] == 2011 or g.get("model_p_home") is None:
            continue
        p_h, p_a = C.american_to_prob(g["home_ml"]), C.american_to_prob(g["away_ml"])
        fair_h, fair_a = C.no_vig_proportional(p_h, p_a)
        for side, model_p, fair_p, price in (("home", g["model_p_home"], fair_h, g["home_ml"]),
                                             ("away", 1 - g["model_p_home"], fair_a, g["away_ml"])):
            if model_p - fair_p >= 0.05:
                bets.append(_bet(g, "ml", side, None, price, model_p=round(model_p, 4),
                                 fair_p=round(fair_p, 4)))
    add("S15", "Moneyline edge >= 5 pts over the de-margined price", "model_edge",
        "Bet the moneyline when the model's win probability exceeds the proportional "
        "no-vig market probability by at least 5 percentage points.",
        "This is the strictest model test: it must clear the full bookmaker margin.", bets)

    # --- 16. Over after a shootout -------------------------------------------------
    bets = []
    for g in tot:
        hs, as_ = g.get("home_scored"), g.get("away_scored")
        if None in (hs, as_):
            continue
        if hs + as_ >= 55:      # both teams' trailing scoring form averages 55+ combined
            b = total_bet(g, "under", "open", form_total=round(hs + as_, 1))
            if b:
                bets.append(b)
    add("S16", "Under when both offences are running hot (opening line)", "behavioural",
        "Bet Under when the two teams' exponentially weighted scoring form averages 55+ "
        "combined points per game entering the week.",
        "Form is computed from prior games only (half-life 6 games).", bets)

    # --- 17. Model edge measured against the OPENING line --------------------------
    bets = []
    for g in sd:
        if g["season"] == 2011 or g["model_spread"] is None or g["open_spread"] is None:
            continue
        edge = g["model_spread"] - g["open_spread"]
        if abs(edge) < 2.0:
            continue
        side = "home" if edge > 0 else "away"
        b = spread_bet(g, side, "open", edge=round(abs(edge), 2))
        if b:
            bets.append(b)
    add("S17", "Model spread edge >= 2 pts vs the OPENING line", "model_edge",
        "Same edge rule as S01 but executed at the opening number, which is the only way to "
        "earn closing-line value on a model signal.", "CLV is measured against the close.", bets)

    # --- 18. Divisional underdog --------------------------------------------------
    bets = []
    for g in sd:
        if DIVISIONS.get(g["home"]) != DIVISIONS.get(g["away"]):
            continue
        if g["open_spread"] is None:
            continue
        side = "home" if g["open_spread"] > 0 else "away"
        if abs(g["open_spread"]) < 1.0:
            continue                     # pick'em: no underdog
        b = spread_bet(g, side, "open")
        if b:
            bets.append(b)
    add("S18", "Divisional underdog (opening line)", "situational",
        "Back the underdog in a divisional game, where familiarity and short travel are "
        "often claimed to compress the market's edge.",
        "Divisions are the 2026 NFL alignment (see SOURCES: NFL-DIVISIONS).", bets)

    return S


# ---------------------------------------------------------------- summary metrics
def summarise(bets, price_override=None):
    if not bets:
        return {"n": 0}
    profits = [b["profit"] if price_override is None
               else (C.payout_per_unit(b["outcome"], price_override)) for b in bets]
    graded = [b for b in bets if b["outcome"] != 0]
    wins = sum(1 for b in graded if b["outcome"] == 1)
    losses = sum(1 for b in graded if b["outcome"] == -1)
    pushes = len(bets) - len(graded)
    staked = len(bets)
    roi = sum(profits) / staked
    clvs = [b["clv"] for b in bets if b.get("clv") is not None]
    return {
        "n": len(bets), "wins": wins, "losses": losses, "pushes": pushes,
        "win_rate": round(wins / (wins + losses), 4) if wins + losses else None,
        "roi": round(roi, 4),
        "units_profit": round(sum(profits), 2),
        "mean_clv_pts": round(sum(clvs) / len(clvs), 3) if clvs else None,
        "clv_n": len(clvs),
        "clv_positive_rate": round(sum(1 for c in clvs if c > 0) / len(clvs), 4) if clvs else None,
        "seasons": sorted({b["season"] for b in bets}),
    }


def main():
    games = load_games()
    games = add_rest_days(games)
    games = add_streaks(games)
    games = add_trailing_form(games)
    # attach model lines produced by 02_line_model.py
    with open(os.path.join(ROOT, "data", "lab", "lines.json")) as f:
        lines = json.load(f)
    model = {r["game_key"]: r for r in lines["board"]}
    # the board only covers one season; recompute the model on the full history instead
    import importlib.util
    spec = importlib.util.spec_from_file_location("line_model", os.path.join(ROOT, "scripts", "02_line_model.py"))
    lm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lm)
    games = lm.elo_series(games)
    games = lm.originate(games)

    strategies = build_strategies(games)
    payload = {
        "price_assumption": {"spread_total_price": STD_PRICE,
                             "note": "archive stores no per-bet price; -110 is the standard, and "
                                     "06_validation.py re-runs everything at -115"},
        "in_sample": list(IN_SAMPLE), "out_of_sample": list(OUT_SAMPLE),
        "n_strategies": len(strategies),
        "strategies": [],
    }
    for s in strategies:
        bets = s["bets"]
        ins = [b for b in bets if IN_SAMPLE[0] <= b["season"] <= IN_SAMPLE[1]]
        outs = [b for b in bets if OUT_SAMPLE[0] <= b["season"] <= OUT_SAMPLE[1]]
        rec = {
            "id": s["id"], "name": s["name"], "family": s["family"],
            "description": s["description"], "rule_note": s["rule_note"],
            "overall": summarise(bets),
            "in_sample": summarise(ins),
            "out_of_sample": summarise(outs),
            "at_minus_115": summarise(bets, price_override=-115.0),
            "per_season": {},
            "profits": [b["profit"] for b in bets],
            "clv": [b["clv"] for b in bets if b.get("clv") is not None],
            "graded_outcomes": [b["outcome"] for b in bets if b["outcome"] != 0],
        }
        for season in sorted({b["season"] for b in bets}):
            rec["per_season"][str(season)] = summarise([b for b in bets if b["season"] == season])
        payload["strategies"].append(rec)

    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"{'id':4} {'n':>4} {'win%':>6} {'ROI':>8} {'CLV':>7}  name")
    for r in payload["strategies"]:
        o = r["overall"]
        print(f"{r['id']:4} {o['n']:>4} {o.get('win_rate') or 0:>6.3f} {o['roi']:>8.4f} "
              f"{('%.2f' % o['mean_clv_pts']) if o['mean_clv_pts'] is not None else '   -':>7}  {r['name']}")


if __name__ == "__main__":
    main()
