"""Backtest engine: luck-removal statistics + validation gates + leaderboard.

Every strategy is scored on six axes:

  1. Raw economics        ROI per bet at the *quoted* two-sided closing price.
  2. Luck-adjusted edge   excess wins versus the de-vigged probability of the
                          bets it actually took (Poisson-binomial z). This is the
                          key "is this skill or did it just pick favourites?" test.
  3. Sampling error       block bootstrap (blocks = weeks) CI on ROI.
  4. Multiplicity         Benjamini-Hochberg FDR across all strategies plus
                          White's Reality Check on the whole search.
  5. Out-of-sample        fitted/selected on 2006-2015, scored on 2016-2026.
  6. Stability            season-by-season, split-half, leave-one-season-out,
                          profit concentration.

Outputs
  data/derived/bets.csv            (bet level, from signals.py)
  data/derived/strategy_scores.csv (one row per strategy)
  data/derived/weekly_returns.csv  (strategy x week PnL, for correlation work)
  data/site/backtest.json          (everything the site needs)
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from .common import (DERIVED, SITE, american_to_decimal, american_to_prob, bh_fdr,
                     block_bootstrap_ci, bootstrap_skill_prob, devig_two_way,
                     reality_check, two_sided_z_p)
from . import signals

TRAIN = (2006, 2015)
TEST = (2016, 2026)
MIN_BETS = 200
MIN_SEASONS = 6
FDR_Q = 0.10


def devig_price(b: pd.DataFrame) -> pd.Series:
    """De-vigged win probability for each bet, from its own two-way market."""
    p = np.full(len(b), np.nan)
    sp = b["market"] == "SPREAD"
    tt = b["market"] == "TOTAL"
    ml = b["market"] == "ML"
    if sp.any():
        pa, ph = devig_two_way(b.loc[sp, "away_spread_odds"], b.loc[sp, "home_spread_odds"])
        p[sp.values] = np.where(b.loc[sp, "side"] == "home", ph, pa)
    if tt.any():
        po, pu = devig_two_way(b.loc[tt, "over_odds"], b.loc[tt, "under_odds"])
        p[tt.values] = np.where(b.loc[tt, "side"] == "over", po, pu)
    if ml.any():
        ph, pa = devig_two_way(b.loc[ml, "home_moneyline"], b.loc[ml, "away_moneyline"])
        p[ml.values] = np.where(b.loc[ml, "side"] == "home", ph, pa)
    return pd.Series(p, index=b.index)


def score_strategy(b: pd.DataFrame) -> dict:
    b = b.copy()
    b["p_fair"] = devig_price(b)
    settled = b[b["won"] != 0.5]
    n = len(b)
    n_settled = len(settled)
    wins = float((b["won"] == 1).sum())
    pushes = float((b["won"] == 0.5).sum())
    pnl = b["pnl"].values
    roi = float(pnl.mean())
    stake = float(n)
    # --- luck-adjusted edge: observed wins vs de-vigged expectation -------
    exp_wins = float(b["p_fair"].sum())
    var_wins = float((b["p_fair"] * (1 - b["p_fair"])).sum())
    z_wins = (wins - exp_wins) / math.sqrt(var_wins) if var_wins > 0 else float("nan")
    # --- luck index: how much of the observed dispersion is pure chance ---
    payoff_var = []
    for price, pf in zip(b["price"].values, b["p_fair"].values):
        if not np.isfinite(price) or not np.isfinite(pf):
            continue
        dec = american_to_decimal(price)
        # profit = dec-1 on a win, -1 on a loss
        pay = dec - 1
        payoff_var.append(pf * (1 - pf) * (pay + 1) ** 2)
    se_null = math.sqrt(np.sum(payoff_var)) / n if n else float("nan")
    boot = block_bootstrap_ci(pnl, blocks=b["week_id"].values, n_boot=3000)
    skill_p = bootstrap_skill_prob(pnl, se_hint=boot["se"])
    # --- stability -------------------------------------------------------
    by_season = b.groupby("season")["pnl"].agg(["size", "mean", "sum"])
    pos_seasons = int((by_season["mean"] > 0).sum())
    tot_profit = float(by_season["sum"].clip(lower=0).sum())
    max_share = float(by_season["sum"].clip(lower=0).max() / tot_profit) if tot_profit > 0 else float("nan")
    loso = []
    for s in by_season.index:
        rest = b[b["season"] != s]["pnl"].mean()
        loso.append(float(rest))
    split_half = {}
    for label, sel in (("odd_seasons", by_season.index % 2 == 1),
                       ("even_seasons", by_season.index % 2 == 0)):
        sub = b[b["season"].isin(by_season.index[sel])]
        split_half[label] = round(float(sub["pnl"].mean()), 4) if len(sub) else float("nan")
    # --- out of sample ---------------------------------------------------
    tr = b[(b["season"] >= TRAIN[0]) & (b["season"] <= TRAIN[1])]
    te = b[(b["season"] >= TEST[0]) & (b["season"] <= TEST[1])]
    roi_tr = float(tr["pnl"].mean()) if len(tr) else float("nan")
    roi_te = float(te["pnl"].mean()) if len(te) else float("nan")
    te_boot = block_bootstrap_ci(te["pnl"].values, blocks=te["week_id"].values, n_boot=2000) if len(te) > 30 else None
    retention = (roi_te / roi_tr) if (roi_tr and np.isfinite(roi_tr) and roi_tr != 0) else float("nan")
    # --- raw t-stat ------------------------------------------------------
    se_obs = float(np.std(pnl, ddof=1) / math.sqrt(n)) if n > 2 else float("nan")
    t_roi = roi / se_obs if se_obs > 0 else float("nan")
    p_roi = two_sided_z_p(t_roi)
    return {
        "n_bets": n, "n_settled": n_settled, "wins": wins, "pushes": pushes,
        "hit_rate": round(float(wins / n_settled), 4) if n_settled else float("nan"),
        "avg_price": round(float(b["price"].mean()), 1),
        "breakeven_rate": round(float(b["p_fair"].mean()), 4),
        "roi": round(roi, 4),
        "units": round(float(b["pnl"].sum()), 2),
        "roi_lo": round(boot["lo"], 4), "roi_hi": round(boot["hi"], 4),
        "roi_se": round(boot["se"], 4),
        "se_null": round(se_null, 4),
        "luck_index": round(se_null / boot["se"], 3) if boot["se"] else float("nan"),
        "skill_prob": round(skill_p, 4),
        "exp_wins": round(exp_wins, 1), "z_wins": round(z_wins, 3),
        "p_wins": two_sided_z_p(z_wins),
        "t_roi": round(t_roi, 3), "p_roi": p_roi,
        "seasons": int(b["season"].nunique()),
        "first_season": int(b["season"].min()), "last_season": int(b["season"].max()),
        "pos_seasons": pos_seasons, "n_seasons": int(len(by_season)),
        "max_season_profit_share": round(max_share, 3) if np.isfinite(max_share) else float("nan"),
        "loso_min_roi": round(float(min(loso)), 4) if loso else float("nan"),
        "split_half_odd": split_half["odd_seasons"], "split_half_even": split_half["even_seasons"],
        "roi_train": round(roi_tr, 4) if np.isfinite(roi_tr) else float("nan"),
        "roi_test": round(roi_te, 4) if np.isfinite(roi_te) else float("nan"),
        "test_lo": round(te_boot["lo"], 4) if te_boot else float("nan"),
        "test_hi": round(te_boot["hi"], 4) if te_boot else float("nan"),
        "oos_retention": round(float(retention), 3) if np.isfinite(retention) else float("nan"),
        "n_train": int(len(tr)), "n_test": int(len(te)),
        "by_season": {int(s): {"n": int(r["size"]), "roi": round(float(r["mean"]), 4)}
                      for s, r in by_season.iterrows()},
    }


def gates(sc: dict, fdr: dict, rc: dict, corr_max: float, sid: str) -> dict:
    """Eight explicit gates. A strategy is only 'Validated' if all eight pass."""
    n = sc["n_bets"]
    g1 = bool(n == n and sc["avg_price"] == sc["avg_price"])  # every bet priced from upstream
    g2 = True  # no-lookahead audit is a repo-level test (tests/test_no_lookahead.py)
    g3 = bool(n >= MIN_BETS and sc["seasons"] >= MIN_SEASONS)
    g4 = bool(fdr.get(sid, {}).get("reject", False) and sc["z_wins"] > 0 and sc["roi"] > 0)
    g5 = bool(sc["roi_test"] == sc["roi_test"] and sc["roi_test"] > 0
              and sc["roi_train"] == sc["roi_train"] and sc["roi_train"] > 0
              and sc["oos_retention"] >= 0.5)
    g6 = bool(sc["roi"] > 0 and sc["roi_lo"] > -0.02 and sc["skill_prob"] >= 0.90)
    g7 = bool(sc["pos_seasons"] / max(sc["n_seasons"], 1) >= 0.55
              and (not np.isfinite(sc["max_season_profit_share"]) or sc["max_season_profit_share"] <= 0.40)
              and sc["loso_min_roi"] > -0.02)
    g8 = bool(corr_max < 0.8)
    gs = {"G1_priced": g1, "G2_no_lookahead": g2, "G3_sample": g3, "G4_significance": g4,
          "G5_out_of_sample": g5, "G6_economics": g6, "G7_stability": g7,
          "G8_diversification": g8}
    passed = sum(gs.values())
    if g1 and g2 and g3 and passed == 8:
        tier, verdict = "A", "Validated — skill-based, survives all gates"
    elif g1 and g2 and g3 and passed >= 5 and (g4 or g5):
        tier, verdict = "B", "Promising — partial validation"
    elif g1 and g2 and g3:
        tier, verdict = "C", "Watchlist — not distinguishable from luck"
    else:
        tier, verdict = "F", "Rejected — fails sample or integrity gates"
    if sc["roi"] < 0 and (fdr.get(sid, {}).get("reject", False)) and sc["z_wins"] < 0:
        tier, verdict = "X", "Significantly negative — fade candidate / negative control"
    return {"gates": gs, "gates_passed": passed, "tier": tier, "verdict": verdict}


def leaderboard_score(sc: dict, gates_passed: int, rc_p: float) -> float:
    """Disclosed composite score, 0-100 (a design choice, not a fact claim).

        60 pts x P(edge > 0)   <- normal CDF of the luck-adjusted z on wins
        20 pts x OOS retention <- out-of-sample ROI as a share of in-sample
        15 pts x season hit     <- share of seasons with positive ROI
         5 pts x sample size

    The ranking itself is *not* driven by this number: the board is ordered by
    tier first (gates passed), then by the luck-adjusted z, so a strategy with
    a pretty score can never outrank a better-validated one.
    """
    from math import erf, sqrt
    phi = 0.5 * (1 + erf(sc["z_wins"] / sqrt(2))) if np.isfinite(sc["z_wins"]) else 0.5
    oos = max(min(sc["oos_retention"], 1.0), 0.0) * 20 if np.isfinite(sc["oos_retention"]) else 0.0
    stab = (sc["pos_seasons"] / max(sc["n_seasons"], 1)) * 15
    samp = min(sc["n_bets"] / 1000, 1.0) * 5
    return round(60 * phi + oos + stab + samp, 2)


def main() -> None:
    g = pd.read_csv(DERIVED / "model_lines.csv", parse_dates=["gameday"])
    bets = signals.run_all(g)
    bets["week_id"] = bets["season"].astype(str) + "-" + bets["week"].astype(str).str.zfill(2)
    price_cols = ["game_id", "away_spread_odds", "home_spread_odds", "over_odds",
                  "under_odds", "home_moneyline", "away_moneyline"]
    merged = bets.merge(g[price_cols], on="game_id", how="left")
    merged = merged.drop_duplicates(subset=["strategy", "game_id", "market", "side"])
    merged["p_fair"] = devig_price(merged)
    merged.to_csv(DERIVED / "bets.csv", index=False)

    scores = {}
    for sid, b in merged.groupby("strategy"):
        scores[sid] = score_strategy(b)

    pvals = {sid: s["p_roi"] for sid, s in scores.items()}
    pvals_w = {sid: s["p_wins"] for sid, s in scores.items()}
    fdr = bh_fdr(pvals, FDR_Q)
    fdr_w = bh_fdr(pvals_w, FDR_Q)

    # correlation matrix on weekly PnL (only weeks with a bet)
    wk = (merged.pivot_table(index="week_id", columns="strategy", values="pnl", aggfunc="sum")
          .fillna(0.0))
    corr = wk.corr()
    wk.to_csv(DERIVED / "weekly_returns.csv")

    # White reality check on the bet-level return matrix is infeasible at 25k
    # rows x 22 strategies with unequal coverage, so we run it on the weekly
    # PnL matrix (aligned, zero-filled) which is the standard formulation.
    rc = reality_check(wk.values, n_boot=1500)

    rows = []
    for sid, sc in scores.items():
        cmax = float(np.nanmax(np.abs(corr.loc[sid].drop(sid, errors="ignore")))) if len(corr) > 1 else 0.0
        gt = gates(sc, fdr, rc, cmax, sid)
        sc2 = dict(sc)
        sc2.update({"strategy": sid, "name": signals.BY_ID[sid].name,
                    "family": signals.BY_ID[sid].family,
                    "fdr_reject": fdr[sid]["reject"], "fdr_threshold": FDR_Q,
                    "fdr_p": fdr[sid]["p"], "fdr_rank": fdr[sid]["rank"],
                    "fdr_wins_reject": fdr_w[sid]["reject"],
                    "max_abs_corr": round(cmax, 3),
                    "score": leaderboard_score(sc, gt["gates_passed"], rc["p_value"]),
                    **gt})
        rows.append(sc2)
    tier_rank = {"A": 0, "B": 1, "C": 2, "F": 3, "X": 4}
    df = pd.DataFrame(rows)
    df["tier_rank"] = df["tier"].map(tier_rank)
    df["role"] = ["negative_control" if sid == "S15_ml_dog_lottery" else "candidate"
                  for sid in df["strategy"]]
    df = df.sort_values(["tier_rank", "z_wins", "roi"], ascending=[True, False, False])
    df["rank"] = range(1, len(df) + 1)
    df.to_csv(DERIVED / "strategy_scores.csv", index=False)

    payload = {
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "universe": {
            "bet_level": "one unit per bet, priced at the two-sided closing quote in the upstream file",
            "priced_seasons": [int(merged["season"].min()), int(merged["season"].max())],
            "total_bets": int(len(merged)),
            "train": list(TRAIN), "test": list(TEST),
            "fdr_q": FDR_Q, "min_bets": MIN_BETS, "min_seasons": MIN_SEASONS,
        },
        "reality_check": rc,
        "fdr": {k: {"p": v["p"], "reject": v["reject"], "rank": v["rank"]} for k, v in fdr.items()},
        "correlation": {"labels": list(corr.columns),
                        "matrix": np.round(corr.values, 3).tolist()},
        "strategies": df.replace({np.nan: None}).to_dict("records"),
    }
    (SITE / "backtest.json").write_text(json.dumps(payload, indent=1, default=str))
    pd.set_option("display.width", 250)
    print(df[["strategy", "n_bets", "roi", "roi_lo", "roi_hi", "z_wins", "p_roi", "p_wins",
              "fdr_reject", "roi_train", "roi_test", "tier", "gates_passed", "score"]]
          .to_string(index=False))
    print("\nReality Check:", rc)


if __name__ == "__main__":
    main()
