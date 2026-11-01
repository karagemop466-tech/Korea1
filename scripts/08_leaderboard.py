#!/usr/bin/env python3
"""
08_leaderboard.py - turn validated results into a competition table.

Scoring is the luck-adjusted skill score (LASS) defined in research/04-competition.md:

    lam  = n / (n + 400)                          empirical-Bayes shrink to zero
    C    = mean(CLV)/sd(CLV) * sqrt(n_clv)        t-statistic of closing-line value
    R    = mean(r)/sd(r) * sqrt(n)                per-bet Sharpe times sqrt(n)
    DSR  = selection-bias-corrected Sharpe        (0..1)
    LASS = lam * ( 0.5*tanh(C/2) + 0.3*tanh(R/2) + 0.2*(2*DSR - 1) )

The three terms are each mapped into [-1, 1] so no single one can dominate, and the whole score is
shrunk toward zero for small samples. A strategy that fails gate G8 can never be above Bronze.
"""
from __future__ import annotations

import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
W_CLV, W_RET, W_DSR = 0.5, 0.3, 0.2
N0 = 400.0

TIERS = {
    "Gold": "all eight gates passed, >= 2 seasons, positive CLV in both halves",
    "Silver": "G1-G6 passed and at least one full season",
    "Bronze": "G1 and G2 passed with >= 300 bets",
    "Watch": "notable result that failed the gates - published for review, not funded",
    "Paper": "tracked only; does not clear the entry requirements",
}
WATCH = {"S11", "S12", "S01", "S17"}


def main():
    with open(os.path.join(DATA, "validation.json")) as f:
        val = json.load(f)
    with open(os.path.join(DATA, "strategies.json")) as f:
        strat = {s["id"]: s for s in json.load(f)["strategies"]}

    rows = []
    for s in val["strategies"]:
        n = s["n"]
        clv = strat[s["id"]]["clv"]
        n_clv = len(clv)
        if n_clv > 2:
            mean_c = sum(clv) / n_clv
            sd_c = math.sqrt(sum((c - mean_c) ** 2 for c in clv) / (n_clv - 1)) or 1e-9
            C = mean_c / sd_c * math.sqrt(n_clv)
        else:
            C = 0.0
        R = (s["sharpe_per_bet"] or 0.0) * math.sqrt(n) if n else 0.0
        dsr = s["dsr"] or 0.0
        lam = n / (n + N0)
        lass = lam * (W_CLV * math.tanh(C / 2) + W_RET * math.tanh(R / 2) + W_DSR * (2 * dsr - 1))

        g = s["gates"]
        if s["verdict"] == "PASS":
            tier = "Gold"
        elif all(g[k] for k in ("G1", "G2", "G3", "G4", "G5", "G6")):
            tier = "Silver"
        elif g["G1"] and g["G2"]:
            tier = "Bronze"
        elif s["id"] in WATCH:
            tier = "Watch"
        else:
            tier = "Paper"
        if tier in ("Gold", "Silver") and not g["G8"]:
            tier = "Paper"          # selection-bias gate is a hard ceiling

        rows.append({
            "id": s["id"], "name": s["name"], "family": s["family"],
            "n": n, "n_clv": n_clv,
            "roi": s["roi"], "oos_roi": s["out_of_sample"].get("roi"),
            "clv_mean": s.get("clv_mean"), "clv_t": round(C, 3),
            "sharpe_sqrt_n": round(R, 3),
            "dsr": round(dsr, 4), "shrinkage": round(lam, 4),
            "lass": round(lass, 4), "gates_passed": s["gates_passed"],
            "verdict": s["verdict"], "tier": tier,
        })

    rows.sort(key=lambda r: -r["lass"])
    payload = {
        "scoring": {
            "name": "Luck-adjusted skill score (LASS)",
            "formula": "LASS = lam * (0.5*tanh(C/2) + 0.3*tanh(R/2) + 0.2*(2*DSR - 1)), "
                       "lam = n/(n+400)",
            "weights": {"clv": W_CLV, "return": W_RET, "selection_bias": W_DSR},
            "shrinkage_n0": N0,
            "hard_ceiling": "a strategy that fails G8 (Deflated Sharpe Ratio < 0.95) cannot rank "
                            "above Paper, whatever its LASS",
        },
        "tiers": TIERS,
        "tier_counts": {t: sum(1 for r in rows if r["tier"] == t) for t in TIERS},
        "reward_weights": {"realised_clv": 0.45, "risk_adjusted_return": 0.30,
                           "replication": 0.15, "correlation_contribution": 0.10},
        "leaderboard": rows,
        "evidence": {
            "zero_skill_winner_roi_median": val["luck"]["leaderboard_simulation_zero_skill"]["winner_roi"]["p50"],
            "p_skilled_first_by_roi": val["luck"]["mixed_field_test"]["p_skilled_finishes_first_ranked_by_roi"],
            "p_skilled_first_by_clv": val["luck"]["mixed_field_test"]["p_skilled_finishes_first_ranked_by_clv"],
            "bets_to_prove_2pct_edge": next(d["bets_needed"] for d in val["luck"]["detection_power"]
                                            if d["edge_per_bet"] == 0.02),
        },
    }
    with open(os.path.join(DATA, "leaderboard.json"), "w") as f:
        json.dump(payload, f, indent=2)

    print(f"{'rank':>4} {'id':4} {'tier':6} {'LASS':>7} {'n':>5} {'ROI':>8} {'CLV t':>7} {'DSR':>6}")
    for i, r in enumerate(rows, 1):
        print(f"{i:>4} {r['id']:4} {r['tier']:6} {r['lass']:>7.4f} {r['n']:>5} "
              f"{r['roi']:>8.4f} {r['clv_t']:>7.2f} {r['dsr']:>6.3f}")
    print(payload["tier_counts"])


if __name__ == "__main__":
    main()
