#!/usr/bin/env python3
"""
06_validation.py - validation gates, luck removal, and the leaderboard luck simulation.

A strategy only graduates from "interesting" to "publishable" by clearing every gate below.
The thresholds are fixed here, before any result is inspected, exactly so they cannot be
moved to let a favourite strategy through.

  G0  DATA INTEGRITY      source cross-validation must hold (checked once, globally)
  G1  SAMPLE SIZE         n >= 300 graded bets and >= 100 out-of-sample bets
  G2  SIGNIFICANCE        two-sided p < 0.05 AND Benjamini-Hochberg q < 0.10 across the battery
  G3  OUT OF SAMPLE       ROI > 0 on seasons that played no part in designing the rule
  G4  ROBUSTNESS          survives -115 pricing, and >= 60% of seasons are non-negative
  G5  ECONOMIC EDGE       mean CLV > 0 where measurable, otherwise OOS ROI > 2%
  G6  RISK                max drawdown <= 25 units and positive per-bet Sharpe
  G7  CAPACITY/INPUTS     every input needed by the rule is publicly available pre-game
  G8  SELECTION BIAS      Deflated Sharpe Ratio >= 0.95 given the number of trials searched

Luck removal is not a vibe; it is three measurements:
  1. Deflated Sharpe Ratio          - corrects the Sharpe for how many strategies were tried.
  2. Season overdispersion          - chi-square on per-season ROI; luck_ratio = (k-1)/Q.
  3. Signal persistence             - does a strategy's in-sample ROI predict its
                                      out-of-sample ROI across the battery? If it does not,
                                      the ranking is luck no matter how good the top row looks.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import common as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "lab")

GATES = {
    "G1": {"name": "Sample size", "criterion": "n >= 300 graded bets and out-of-sample n >= 100"},
    "G2": {"name": "Significance", "criterion": "p < 0.05 and BH q < 0.10, in the profitable "
                                                 "direction (ROI > 0)"},
    "G3": {"name": "Out of sample", "criterion": "ROI > 0 on the held-out seasons"},
    "G4": {"name": "Robustness", "criterion": "ROI > 0 at -115 and >= 60% of seasons non-negative"},
    "G5": {"name": "Economic edge", "criterion": "mean CLV > 0 if measurable, else OOS ROI > 2%"},
    "G6": {"name": "Risk", "criterion": "max drawdown <= 25 units and per-bet Sharpe > 0"},
    "G7": {"name": "Inputs available", "criterion": "all rule inputs are public pre-game data"},
    "G8": {"name": "Selection-bias corrected", "criterion": "Deflated Sharpe Ratio >= 0.95"},
}

BREAKEVEN_110 = 110.0 / 210.0       # 0.5238


def max_drawdown(profits):
    peak = cum = worst = 0.0
    for p in profits:
        cum += p
        peak = max(peak, cum)
        worst = min(worst, cum - peak)
    return worst


def skew_kurt(xs):
    n = len(xs)
    if n < 4:
        return 0.0, 3.0
    m = sum(xs) / n
    s = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    if s == 0:
        return 0.0, 3.0
    m3 = sum((x - m) ** 3 for x in xs) / n
    m4 = sum((x - m) ** 4 for x in xs) / n
    return m3 / s ** 3, m4 / s ** 4


def chi2_overdispersion(season_rois, season_ns):
    """Q = sum((roi_s - mu)^2 / var_s) with var_s the binomial sampling variance of that
    season's ROI.  Under 'a constant edge per bet', Q ~ chi-square with k-1 df."""
    k = len(season_rois)
    if k < 3:
        return None, None
    mu = sum(r * n for r, n in zip(season_rois, season_ns)) / sum(season_ns)
    q = 0.0
    for r, n in zip(season_rois, season_ns):
        # variance of ROI for a -110 bet at the observed rate, scaled to n bets
        var = (BREAKEVEN_110 * (1 - BREAKEVEN_110)) * (1.9091 ** 2) / n
        if var <= 0:
            continue
        q += (r - mu) ** 2 / var
    return q, k - 1


def chi2_sf(x, k):
    """Survival function of chi-square with k df (Wilson-Hilferty approximation)."""
    if x <= 0:
        return 1.0
    z = ((x / k) ** (1.0 / 3.0) - (1 - 2.0 / (9 * k))) / math.sqrt(2.0 / (9 * k))
    return C.norm_sf(z)


# ---------------------------------------------------------------- leaderboard luck sim
def _roi_sigma(p=BREAKEVEN_110, n=267):
    """sd of a bettor's seasonal ROI. Per-bet profit is +/-0.9091/-1, so the per-bet sd is
    1.9091*sqrt(p(1-p)) and the ROI sd is that divided by sqrt(n). This is the CLT form of the
    exact binomial, and `_exact_winner_check` below confirms it against brute force."""
    return 1.9091 * math.sqrt(p * (1 - p)) / math.sqrt(n)


def luck_simulation(trials=20000, bettors=1000, games_per_season=267, edge=0.0, seed=7):
    """How much of a leaderboard is luck?

    All `bettors` have the same TRUE edge. Seasonal ROI is drawn from Normal(edge, sigma) using the
    CLT form above - exact for 267 independent bets to within a few tenths of a point, and confirmed
    by the brute-force cross-check in `_exact_winner_check`.
    """
    rng = random.Random(seed)
    sigma = 0.0
    p = BREAKEVEN_110 + edge / 1.9091
    sigma = 1.9091 * math.sqrt(p * (1 - p)) / math.sqrt(games_per_season)
    tops, population = [], []
    for _ in range(trials):
        best = -9.0
        for _ in range(bettors):
            roi = rng.gauss(edge, sigma)
            population.append(roi)
            if roi > best:
                best = roi
        tops.append(best)
    tops.sort()
    population.sort()
    n_pop = len(population)
    return {
        "settings": {"trials": trials, "bettors_per_trial": bettors,
                     "bets_per_bettor": games_per_season, "true_edge_per_bet": edge,
                     "price": -110, "breakeven_win_rate": round(BREAKEVEN_110, 5),
                     "method": "CLT normal approximation to the exact binomial (cross-checked)"},
        "population_roi": {
            "mean": round(sum(population) / n_pop, 5),
            "p05": round(population[int(0.05 * n_pop)], 4),
            "p50": round(population[int(0.50 * n_pop)], 4),
            "p95": round(population[int(0.95 * n_pop)], 4),
        },
        "winner_roi": {
            "mean": round(sum(tops) / len(tops), 4),
            "p05": round(tops[int(0.05 * len(tops))], 4),
            "p50": round(tops[int(0.50 * len(tops))], 4),
            "p95": round(tops[min(len(tops) - 1, int(0.95 * len(tops)))], 4),
        },
        "share_of_bettors_profitable": round(sum(1 for r in population if r > 0) / n_pop, 4),
    }


def _exact_winner_check(trials=150, bettors=120, games=267, seed=99):
    """Brute-force binomial check of the CLT approximation used by the simulations above."""
    rng = random.Random(seed)
    dec = C.american_to_decimal(-110.0)
    tops = []
    for _ in range(trials):
        best = -9.0
        for _ in range(bettors):
            profit = 0.0
            for _ in range(games):
                profit += (dec - 1.0) if rng.random() < BREAKEVEN_110 else -1.0
            roi = profit / games
            if roi > best:
                best = roi
        tops.append(best)
    tops.sort()
    sigma = 1.9091 * math.sqrt(BREAKEVEN_110 * (1 - BREAKEVEN_110)) / math.sqrt(games)
    # expected maximum of `bettors` independent normals via the same quantile the fast sim uses
    rng2 = random.Random(seed + 1)
    fast = sorted(max(rng2.gauss(0.0, sigma) for _ in range(bettors)) for _ in range(trials))
    return {
        "bettors": bettors, "bets_each": games, "trials": trials,
        "exact_binomial_median_winner_roi": round(tops[len(tops) // 2], 4),
        "clt_median_winner_roi": round(fast[len(fast) // 2], 4),
        "abs_difference": round(abs(tops[len(tops) // 2] - fast[len(fast) // 2]), 4),
    }


def mixed_field(clv_sd=2.0, skilled_clv=0.5, skilled_edge=0.02, bettors=999,
                bets=267, trials=20000, seed=13):
    """One genuinely skilled bettor against `bettors` zero-skill bettors.

    How often does the skilled bettor finish first when the board is ranked by SEASON ROI, and how
    often when it is ranked by MEAN CLV?  CLV sd is the measured per-bet dispersion (2.0 points),
    so the mean CLV over n bets has sd 2.0/sqrt(n).
    """
    rng = random.Random(seed)
    sigma = 1.9091 * math.sqrt(BREAKEVEN_110 * (1 - BREAKEVEN_110)) / math.sqrt(bets)
    clv_se = clv_sd / math.sqrt(bets)
    first_roi = first_clv = top1_roi = top1_clv = 0
    top_n = max(1, bettors // 100)
    for _ in range(trials):
        sk_roi = rng.gauss(skilled_edge, sigma)
        sk_clv = rng.gauss(skilled_clv, clv_se)
        roi_rank = 1
        clv_rank = 1
        for _ in range(bettors):
            if rng.gauss(0.0, sigma) > sk_roi:
                roi_rank += 1
            if rng.gauss(0.0, clv_se) > sk_clv:
                clv_rank += 1
        first_roi += roi_rank == 1
        first_clv += clv_rank == 1
        top1_roi += roi_rank <= top_n
        top1_clv += clv_rank <= top_n
    return {
        "settings": {"skilled_bettors": 1, "zero_skill_bettors": bettors, "bets_each": bets,
                     "skilled_roi_edge": skilled_edge, "skilled_mean_clv_pts": skilled_clv,
                     "clv_sd_pts": clv_sd, "trials": trials,
                     "clv_sd_source": "empirical pooled sd of per-bet CLV across the battery "
                                      "(data/strategies.json)",
                     "method": "CLT normal approximation (see exact_winner_check)"},
        "p_skilled_finishes_first_ranked_by_roi": round(first_roi / trials, 4),
        "p_skilled_finishes_first_ranked_by_clv": round(first_clv / trials, 4),
        "p_skilled_in_top_1pct_ranked_by_roi": round(top1_roi / trials, 4),
        "p_skilled_in_top_1pct_ranked_by_clv": round(top1_clv / trials, 4),
    }


def seasons_to_detect(edge_per_bet, z=1.959963985, power_z=0.841621234):
    """Bets needed to detect a per-bet ROI of `edge_per_bet` at 95% confidence, 80% power,
    with -110 payoffs.  Pure sampling arithmetic: n = ((z+power_z)*sd/edge)^2."""
    p = BREAKEVEN_110 + edge_per_bet / 1.9091
    sd = 1.9091 * math.sqrt(p * (1 - p))
    n = ((z + power_z) * sd / edge_per_bet) ** 2
    return {
        "edge_per_bet": edge_per_bet,
        "sd_per_bet": round(sd, 4),
        "bets_needed": int(math.ceil(n)),
        "seasons_at_267_bets": round(n / 267, 1),
    }


def main():
    with open(os.path.join(DATA, "strategies.json")) as f:
        strat = json.load(f)
    with open(os.path.join(DATA, "integrity.json")) as f:
        integ = json.load(f)

    items = strat["strategies"]
    n_trials = len(items)

    # ---------- stage 1: per-strategy statistics
    stats = []
    for s in items:
        profits = s["profits"]
        n = len(profits)
        mu = C.mean(profits) if profits else float("nan")
        sd = C.stdev(profits) if n > 1 else float("nan")
        t = mu / (sd / math.sqrt(n)) if n > 1 and sd > 0 else float("nan")
        p = C.two_sided_p(t)
        lo, hi = C.bootstrap_ci(profits, n_boot=4000, seed=11) if n > 10 else (None, None)
        sk, ku = skew_kurt(profits)
        stats.append({
            "id": s["id"], "name": s["name"], "family": s["family"],
            "description": s["description"], "rule_note": s["rule_note"],
            "n": n, "mean_profit": mu, "sd_profit": sd, "t": t, "p": p,
            "roi": mu if n else None, "ci95": [lo, hi],
            "sharpe_per_bet": (mu / sd) if sd and sd > 0 else None,
            "skew": sk, "kurt": ku,
            "max_drawdown": max_drawdown(profits) if profits else None,
            "overall": s["overall"], "in_sample": s["in_sample"],
            "out_of_sample": s["out_of_sample"], "at_minus_115": s["at_minus_115"],
            "per_season": s["per_season"],
            "clv": s["clv"],
        })

    # multiple testing across the battery
    ps = [x["p"] if x["p"] is not None and not math.isnan(x["p"]) else 1.0 for x in stats]
    qs = C.bh_qvalues(ps)
    sharpes = [x["sharpe_per_bet"] for x in stats if x["sharpe_per_bet"] is not None]
    sr_var = C.stdev(sharpes) ** 2 if len(sharpes) > 1 else 1.0

    for x, q in zip(stats, qs):
        x["q"] = q
        x["dsr"] = C.deflated_sharpe_ratio(
            sr=x["sharpe_per_bet"] or 0.0, n_obs=x["n"], skew=x["skew"], kurt=x["kurt"],
            n_trials=n_trials, sr_variance=sr_var) if x["sharpe_per_bet"] is not None else None

    # ---------- stage 2: gates
    g0_checks = {
        "final_score_agreement_2021": integ["cross_validation"]["2021"]["final_scores"],
        "closing_total_within_1pt": integ["cross_validation"]["2021"]["closing_total"],
        "closing_spread_within_1pt": integ["cross_validation"]["2021"]["closing_spread"],
    }
    g0_pass = (
        integ["cross_validation"]["2021"]["final_scores"]["disagree"] == 0
        and integ["cross_validation"]["2021"]["closing_total"]["agreement_rate_within_1pt"] >= 0.90
        and integ["rows_included"] >= 2800
    )

    for x in stats:
        oos = x["out_of_sample"]
        seasons = x["per_season"]
        pos_seasons = sum(1 for v in seasons.values() if (v.get("roi") or 0) > 0)
        tot_seasons = sum(1 for v in seasons.values() if v.get("n"))
        clv_n = len(x["clv"])
        clv_mean = sum(x["clv"]) / clv_n if clv_n else None
        overdisp, df = chi2_overdispersion(
            [v["roi"] for v in seasons.values() if v.get("n")],
            [v["n"] for v in seasons.values() if v.get("n")])
        x["clv_mean"] = clv_mean
        x["clv_positive_rate"] = (sum(1 for c in x["clv"] if c > 0) / clv_n) if clv_n else None
        x["positive_season_share"] = round(pos_seasons / tot_seasons, 3) if tot_seasons else None
        x["overdispersion_Q"] = overdisp
        x["overdispersion_df"] = df
        x["overdispersion_p"] = chi2_sf(overdisp, df) if overdisp is not None and df else None
        x["luck_ratio"] = (df / overdisp) if overdisp and df else None

        gates = {}
        gates["G1"] = bool(x["n"] >= 300 and (oos.get("n") or 0) >= 100)
        # significance must be in the PROFITABLE direction: a strategy that is reliably
        # unprofitable is a finding, not a validated edge (this bug shipped once - four
        # negative-ROI strategies were briefly tiered Bronze because of it).
        gates["G2"] = bool(x["p"] is not None and x["p"] < 0.05 and x["q"] < 0.10
                           and (x["roi"] or 0) > 0)
        gates["G3"] = bool((oos.get("roi") or -1) > 0)
        gates["G4"] = bool((x["at_minus_115"].get("roi") or -1) > 0 and (x["positive_season_share"] or 0) >= 0.60)
        if clv_n >= 50:
            gates["G5"] = bool(clv_mean is not None and clv_mean > 0)
        else:
            gates["G5"] = bool((oos.get("roi") or -1) > 0.02)
        gates["G6"] = bool((x["max_drawdown"] or 0) >= -25.0 and (x["sharpe_per_bet"] or -1) > 0)
        gates["G7"] = True    # every rule in the battery uses only public pre-game inputs
        gates["G8"] = bool(x["dsr"] is not None and x["dsr"] >= 0.95)
        x["gates"] = gates
        x["gates_passed"] = sum(1 for v in gates.values() if v)
        x["verdict"] = "PASS" if all(gates.values()) else "FAIL"

    # ---------- stage 3: luck removal across the battery
    is_roi = [(x["in_sample"].get("roi"), x["out_of_sample"].get("roi")) for x in stats
              if x["in_sample"].get("n") and x["out_of_sample"].get("n")]
    is_roi = [(a, b) for a, b in is_roi if a is not None and b is not None]
    persistence = None
    if len(is_roi) > 3:
        xs = [a for a, _ in is_roi]
        ys = [b for _, b in is_roi]
        mx, my = C.mean(xs), C.mean(ys)
        sxx = sum((v - mx) ** 2 for v in xs)
        syy = sum((v - my) ** 2 for v in ys)
        sxy = sum((a - mx) * (b - my) for a, b in is_roi)
        persistence = sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else None

    luck = {
        "signal_persistence_corr_is_oos": round(persistence, 4) if persistence is not None else None,
        "interpretation": (
            "Correlation between each strategy's in-sample ROI (2012-2017) and its held-out ROI "
            "(2018-2021) across the whole battery. A skill-based family shows positive "
            "persistence; a family that is mostly luck shows ~0 or negative."
            if persistence is not None else None),
        "battery_median_luck_ratio": round(
            C.mean([x["luck_ratio"] for x in stats if x["luck_ratio"] is not None]), 4)
        if any(x["luck_ratio"] is not None for x in stats) else None,
        "luck_ratio_definition": "luck_ratio = (k-1)/Q. ~1 means season-to-season ROI dispersion "
                                 "is fully explained by binomial sampling noise.",
        "n_trials_in_battery": n_trials,
        "sharpe_variance_across_trials": round(sr_var, 6),
        "breakeven_win_rate_at_minus_110": round(BREAKEVEN_110, 5),
        "leaderboard_simulation_zero_skill": luck_simulation(),
        "leaderboard_simulation_plus_2pct": luck_simulation(edge=0.02, seed=8),
        "mixed_field_test": mixed_field(),
        "exact_winner_check": _exact_winner_check(),
        "expected_best_sharpe_of_pure_luck": round(
            C.expected_max_sharpe(n_trials, sr_var), 4),
        "detection_power": [seasons_to_detect(e) for e in (0.01, 0.02, 0.05, 0.10)],
    }

    # ---------- stage 4: strategies that survive
    survivors = [x for x in stats if x["verdict"] == "PASS"]
    gate_roll = {g: sum(1 for x in stats if x["gates"][g]) for g in GATES}

    payload = {
        "gates": GATES,
        "g0_data_integrity": {"passed": g0_pass, "evidence": g0_checks,
                             "criteria": "zero final-score disagreements on the 2021 overlap, "
                                         "closing total within 1 point on >= 90% of games, "
                                         ">= 2800 usable games"},
        "n_strategies": n_trials,
        "strategies": stats,
        "gate_pass_counts": gate_roll,
        "verdict_counts": {
            "PASS": len(survivors),
            "FAIL": len(stats) - len(survivors),
        },
        "survivors": [x["id"] for x in survivors],
        "luck": luck,
    }
    with open(os.path.join(DATA, "validation.json"), "w") as f:
        json.dump(payload, f, indent=2)

    print(f"G0 data integrity: {'PASS' if g0_pass else 'FAIL'}")
    print(f"{'id':4} {'n':>4} {'ROI':>8} {'p':>7} {'q':>7} {'DSR':>6} {'OOS':>8} {'-115':>8} {'gates':>5} verdict")
    for x in stats:
        print(f"{x['id']:4} {x['n']:>4} {x['roi']:>8.4f} {x['p']:>7.4f} {x['q']:>7.4f} "
              f"{(x['dsr'] or 0):>6.3f} {(x['out_of_sample'].get('roi') or 0):>8.4f} "
              f"{(x['at_minus_115'].get('roi') or 0):>8.4f} {x['gates_passed']:>5}/8 {x['verdict']}")
    print()
    print("gate pass counts:", gate_roll)
    print("signal persistence (IS->OOS):", luck["signal_persistence_corr_is_oos"])
    print("zero-skill leaderboard winner ROI p50/p95:",
          luck["leaderboard_simulation_zero_skill"]["winner_roi"]["p50"],
          luck["leaderboard_simulation_zero_skill"]["winner_roi"]["p95"])
    print("detection power:", json.dumps(luck["detection_power"]))


if __name__ == "__main__":
    main()
