#!/usr/bin/env python3
"""
04_correlations.py - correlation values and parlay mathematics.

Three separate questions, kept separate on purpose:

  A. GAME-LEVEL correlations that decide how a same-game parlay (SGP) must be priced:
     margin vs total, home vs away scoring, and the joint behaviour of the standard
     bet legs (moneyline, spread, total).  Measured on 2,945 real games.

  B. BINARY LEG PAIRS: for each pair of legs a bettor might combine in one game we measure
     the empirical joint probability, compare it with the independent product, and report
     the correlation (phi coefficient).  The gap between the two is exactly the pricing
     error an independent-leg parlay price makes.

  C. CROSS-GAME parlays: legs from different games are independent by construction, so the
     payout is the product of the prices and the whole problem reduces to variance and
     bankroll sizing.  We quantify that instead of pretending there is an edge in it.

Nothing here is estimated from an external model: every number is computed from the games
file produced by 00_ingest.py.
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import common as C
from lib.data import load_games, home_margin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "lab", "correlations.json")


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def pearson_ci(r, n, z=1.959963985):
    """Fisher z confidence interval for a correlation."""
    if r is None or n < 4 or abs(r) >= 1:
        return (None, None)
    zr = 0.5 * math.log((1 + r) / (1 - r))
    se = 1 / math.sqrt(n - 3)
    lo, hi = zr - z * se, zr + z * se
    return (math.tanh(lo), math.tanh(hi))


def phi(joint, p1, p2):
    """Correlation of two binary variables from their joint probability."""
    if p1 in (0, 1) or p2 in (0, 1):
        return None
    return (joint - p1 * p2) / math.sqrt(p1 * (1 - p1) * p2 * (1 - p2))


def leg_pair(rows, leg1, leg2, label1, label2):
    """Empirical joint probability vs independent product for two binary legs."""
    n = len(rows)
    if n == 0:
        return None
    a = sum(1 for r in rows if leg1(r))
    b = sum(1 for r in rows if leg2(r))
    both = sum(1 for r in rows if leg1(r) and leg2(r))
    p1, p2, pj = a / n, b / n, both / n
    return {
        "leg_a": label1, "leg_b": label2, "n": n,
        "p_a": round(p1, 4), "p_b": round(p2, 4),
        "p_joint_empirical": round(pj, 4),
        "p_joint_if_independent": round(p1 * p2, 4),
        "pricing_error_pct": round(100 * (pj - p1 * p2) / (p1 * p2), 2) if p1 * p2 else None,
        "phi": round(phi(pj, p1, p2), 4) if phi(pj, p1, p2) is not None else None,
        "fair_decimal_payout": round(1 / pj, 4) if pj else None,
        "independent_decimal_payout": round(1 / (p1 * p2), 4) if p1 * p2 else None,
    }


def main():
    games = [g for g in load_games() if g["home_score"] is not None]
    valid = [g for g in games if g["close_spread"] is not None and g["close_total"] is not None]

    # ---------------- A. continuous game-level correlations
    margins = [home_margin(g) for g in games]
    totals = [g["home_score"] + g["away_score"] for g in games]
    home_pts = [g["home_score"] for g in games]
    away_pts = [g["away_score"] for g in games]
    abs_margins = [abs(m) for m in margins]

    cont = []
    for label, xs, ys, note in (
            ("home margin vs game total", margins, totals, "does the favourite's edge grow with scoring?"),
            ("home points vs away points", home_pts, away_pts, "shootout effect"),
            ("home margin vs |home margin|", margins, abs_margins, "does the winner tend to win big?"),
            ("home points vs game total", home_pts, totals, "share of total captured by the home side"),
    ):
        r = pearson(xs, ys)
        lo, hi = pearson_ci(r, len(xs))
        cont.append({"pair": label, "n": len(xs), "pearson_r": round(r, 4),
                     "ci95": [round(lo, 4), round(hi, 4)], "note": note})

    # ---------------- B. binary leg pairs inside one game
    pairs = []
    def closed(g):
        return g["close_spread"] is not None and g["close_total"] is not None and g["home_ml"] is not None
    v = [g for g in valid if closed(g)]

    pairs.append(leg_pair(v,
        lambda g: g["home_score"] > g["away_score"],
        lambda g: C.settle_spread("home", g["close_spread"], g["home_score"], g["away_score"]) == 1,
        "Home moneyline", "Home spread"))

    pairs.append(leg_pair(v,
        lambda g: g["home_score"] > g["away_score"],
        lambda g: g["away_score"] > g["home_score"],
        "Home moneyline", "Away moneyline"))

    pairs.append(leg_pair(v,
        lambda g: g["home_score"] + g["away_score"] > g["close_total"],
        lambda g: C.settle_spread("home", g["close_spread"], g["home_score"], g["away_score"]) == 1,
        "Over total", "Home spread"))

    pairs.append(leg_pair(v,
        lambda g: g["home_score"] + g["away_score"] > g["close_total"],
        lambda g: g["home_score"] > g["away_score"],
        "Over total", "Home moneyline"))

    pairs.append(leg_pair(v,
        lambda g: g["home_score"] + g["away_score"] > g["close_total"],
        lambda g: g["home_score"] + g["away_score"] < g["close_total"],
        "Over total", "Under total"))

    pairs.append(leg_pair(v,
        lambda g: g["home_score"] + g["away_score"] > g["close_total"],
        lambda g: g["home_score"] > g["close_spread"] * -1,
        "Over total", "Home team over its implied team total"))
    pairs = [p for p in pairs if p]

    # ---------------- pricing kernel: what a parlay SHOULD cost
    # For two 50/50 legs the exact bivariate-normal joint is 1/4 + arcsin(rho)/(2*pi).
    kernel = []
    for rp in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        p = C.bivariate_normal_joint(0.5, 0.5, rp)
        kernel.append({
            "rho": rp,
            "p_both_legs": round(p, 5),
            "fair_decimal_2leg": round(1 / p, 4),
            "independent_decimal_2leg": 4.0,
            "independent_price_implied_prob": 0.25,
            "book_error_if_priced_independent_pct": round(100 * (0.25 - p) / p, 2),
        })

    # ---------------- C. cross-game parlay variance and sizing
    # A 2-leg cross-game parlay at -110 each pays about +264; we compute the return
    # distribution under the *true* (independent) 50/50 assumption and compare staking
    # the parlay against two singles, using Kelly for the underlying edge.
    def parlay_return(legs, price=-110.0):
        dec = 1.0
        for _ in range(legs):
            dec *= C.american_to_decimal(price)
        return dec

    cross = []
    for n_legs in (2, 3, 4, 5):
        dec = parlay_return(n_legs)
        p_win = 0.5 ** n_legs
        ev = p_win * (dec - 1) - (1 - p_win)
        var = p_win * (dec - 1) ** 2 + (1 - p_win) - ev ** 2
        cross.append({
            "legs": n_legs, "decimal_payout": round(dec, 3),
            "american_payout": C.prob_to_american(1 / dec),
            "implied_break_even_prob": round(1 / dec, 5),
            "true_prob_fair_50_50_legs": round(p_win, 5),
            "expected_return_per_unit": round(ev, 4),
            "sd_per_unit": round(math.sqrt(max(var, 0)), 4),
            "kelly_stake_if_no_edge": 0.0,
        })

    # ---------------- D. market margin and favourite-longshot calibration
    # Evidence that the price a bettor pays contains a real, measurable cost, and a direct
    # test of the favourite-longshot bias on realised NFL moneylines.
    ml_games = [g for g in games if g["home_ml"] is not None]
    margins = []
    for g in ml_games:
        ph, pa = C.american_to_prob(g["home_ml"]), C.american_to_prob(g["away_ml"])
        margins.append(ph + pa - 1.0)
    margins.sort()
    n = len(margins)

    buckets = [(-10000, -400), (-400, -250), (-250, -150), (-150, -110), (-110, 110),
               (110, 150), (150, 250), (250, 400), (400, 10000)]
    calib = []
    for lo, hi in buckets:
        rows_b = []
        for g in ml_games:
            for side in ("home", "away"):
                price = g[f"{side}_ml"]
                if price is None or not (lo <= price < hi):
                    continue
                other = g["away_ml" if side == "home" else "home_ml"]
                p = C.american_to_prob(price)
                p_o = C.american_to_prob(other)
                fair, _ = C.no_vig_proportional(p, p_o)
                won = (g["home_score"] > g["away_score"]) if side == "home" else (g["away_score"] > g["home_score"])
                rows_b.append((fair, 1.0 if won else 0.0, price))
        if not rows_b:
            calib.append({"bucket": f"{lo}..{hi}", "n": 0})
            continue
        k = len(rows_b)
        implied = sum(r[0] for r in rows_b) / k
        realised = sum(r[1] for r in rows_b) / k
        calib.append({
            "bucket": ("shorter than -400" if lo == -10000 else
                       "longer than +400" if hi == 10000 else f"{lo} to {hi}"),
            "n": k,
            "mean_no_vig_implied_prob": round(implied, 4),
            "realised_win_rate": round(realised, 4),
            "gap_realised_minus_implied": round(realised - implied, 4),
        })

    market = {
        "n_games": len(ml_games),
        "mean_overround": round(sum(margins) / n, 5),
        "median_overround": round(margins[n // 2], 5),
        "p10_overround": round(margins[int(0.10 * n)], 5),
        "p90_overround": round(margins[int(0.90 * n)], 5),
        "break_even_win_rate_two_way_standard_price": round(110 / 210, 5),
        "source": "SBR-10Y closing moneylines (home and away, both priced)",
        "price_bucket_calibration": calib,
        "note": "overround = implied_home + implied_away - 1, computed straight from the "
                "archived closing prices, so it is the margin actually charged, not a textbook figure",
    }

    payload = {
        "market_margin": market,
        "sources": ["SBR-10Y (2,945 games, 2011-2021)"],
        "n_games": len(games), "n_games_with_close_lines": len(v),
        "continuous": cont,
        "binary_leg_pairs": pairs,
        "parlay_pricing_kernel": {
            "formula": "P(both 50/50 legs) = 1/4 + arcsin(rho)/(2*pi)",
            "verification": "scripts/tests/test_math.py (Monte-Carlo check of the closed form)",
            "table": kernel,
        },
        "cross_game_parlays": {
            "assumption": "legs in different games are independent; this is the ONE case where "
                          "multiplying prices is correct",
            "table": cross,
        },
    }
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)

    print(json.dumps(cont, indent=1))
    print()
    for p in pairs:
        print(f"{p['leg_a']:24} x {p['leg_b']:34} joint={p['p_joint_empirical']:.4f} "
              f"indep={p['p_joint_if_independent']:.4f} phi={p['phi']}")
    print()
    for k in kernel:
        print(f"rho={k['rho']:.1f}  P(both)={k['p_both_legs']:.4f}  fair 2-leg={k['fair_decimal_2leg']:.3f} "
              f"vs independent 4.000  (error {k['book_error_if_priced_independent_pct']:+.1f}%)")


if __name__ == "__main__":
    main()
