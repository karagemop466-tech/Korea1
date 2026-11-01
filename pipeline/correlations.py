"""T5 — measured correlation structure and market-efficiency diagnostics.

Everything on this page is *measured* from the settlement data (7,384 played
games, priced subset from 2006). No correlation is assumed or imported.

Outputs
-------
data/processed/corr_market.csv        dependence between spread / total / moneyline
data/processed/corr_same_game.csv     same-game leg pairs (the SGP table)
data/processed/corr_cross_game.csv    cross-game leg pairs (the parlay assumption)
data/processed/corr_team_totals.csv   variance decomposition of team scoring
data/processed/key_numbers.csv        margin/total frequency and push rates
data/processed/vig_by_season.csv      two-way hold by market, per season
data/processed/fav_longshot.csv       moneyline ROI by price bucket
data/processed/prop_inputs.csv        inputs a prop model needs, and their status
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, american_to_decimal, implied_prob  # noqa: E402


def ci_r(r: float, n: int) -> tuple[float, float]:
    """Fisher z 95% interval for a correlation."""
    if n <= 3 or not np.isfinite(r):
        return (np.nan, np.nan)
    z = np.arctanh(r)
    se = 1.0 / np.sqrt(n - 3)
    return (float(np.tanh(z - 1.96 * se)), float(np.tanh(z + 1.96 * se)))


def phi(x: np.ndarray, y: np.ndarray) -> float:
    """Correlation between two binary vectors."""
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok].astype(float), y[ok].astype(float)
    if len(x) < 3 or x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def main() -> None:
    g = pd.read_csv(PROC / "originated_lines.csv")
    g = g.sort_values(["season", "week", "game_id"]).reset_index(drop=True)

    # binary outcomes at each game's own closing line
    g["home_covers"] = np.where(g.result > g.market_spread, 1.0,
                                np.where(g.result < g.market_spread, 0.0, np.nan))
    g["over_hits"] = np.where(g.total > g.market_total, 1.0,
                              np.where(g.total < g.market_total, 0.0, np.nan))
    g["home_ml_wins"] = np.where(g.result > 0, 1.0, np.where(g.result < 0, 0.0, np.nan))

    # ---------------------------------------------------------------- market
    rows = []
    for a, b, label in [
        ("result", "total", "margin vs total (continuous)"),
        ("home_covers", "over_hits", "home covers vs over (binary, same game)"),
        ("home_covers", "home_ml_wins", "home covers vs home ML win"),
        ("home_score", "away_score", "home points vs away points"),
        ("result", "home_score", "margin vs home points"),
        ("total", "home_score", "total vs home points"),
        ("result", "market_spread", "margin vs closing spread (market efficiency)"),
        ("total", "market_total", "total vs closing total (market efficiency)"),
    ]:
        sub = g[[a, b]].dropna()
        r = float(np.corrcoef(sub[a], sub[b])[0, 1])
        lo, hi = ci_r(r, len(sub))
        rho = float(stats.spearmanr(sub[a], sub[b]).statistic)
        rows.append(dict(pair=label, x=a, y=b, n=len(sub), pearson=r, ci_lo=lo, ci_hi=hi,
                         spearman=rho))
    pd.DataFrame(rows).to_csv(PROC / "corr_market.csv", index=False)

    # --------------------------------------------------------------- SGP legs
    sgp = []
    pairs = [
        ("home_covers", "over_hits", "Home −line & Over"),
        ("home_covers", "home_ml_wins", "Home −line & Home ML"),
        ("over_hits", "home_ml_wins", "Over & Home ML"),
    ]
    for a, b, label in pairs:
        sub = g[[a, b]].dropna()
        ph = phi(sub[a].to_numpy(), sub[b].to_numpy())
        n = len(sub)
        lo, hi = ci_r(ph, n)
        # independence benchmark
        p_joint = float(((sub[a] == 1) & (sub[b] == 1)).mean())
        p_indep = float((sub[a] == 1).mean() * (sub[b] == 1).mean())
        sgp.append(dict(pair=label, n=n, phi=ph, ci_lo=lo, ci_hi=hi,
                        p_joint=p_joint, p_if_independent=p_indep,
                        lift=p_joint / p_indep if p_indep else np.nan))
    pd.DataFrame(sgp).to_csv(PROC / "corr_same_game.csv", index=False)

    # --------------------------------------------------------- cross-game
    # Two games in the same week are different teams, so they cannot be aligned
    # game-by-game across weeks. Instead: inside each (season, week) slate we pair
    # consecutive games, giving one (x, y) pair per slate, and estimate the pooled
    # correlation with a week-block bootstrap CI. Under independence the estimate
    # is ~0 whatever the pairing rule is.
    cross = []
    for col, label in [("result", "margin"), ("total", "total")]:
        xs, ys, wk = [], [], []
        for (s, w), grp in g.groupby(["season", "week"]):
            v = grp[[col]].dropna()[col].to_numpy()
            if len(v) < 4:
                continue
            for i in range(0, len(v) - 1, 2):
                xs.append(v[i]); ys.append(v[i + 1]); wk.append(f"{s}_{w}")
        xs, ys = np.array(xs), np.array(ys)
        r = float(np.corrcoef(xs, ys)[0, 1]) if len(xs) > 3 else np.nan
        # week-block bootstrap for the CI
        rng = np.random.default_rng(20261101)
        wk_arr = np.array(wk)
        uniq = np.unique(wk_arr)
        boots = []
        for _ in range(2000):
            pick = rng.choice(uniq, len(uniq), replace=True)
            idx = np.concatenate([np.where(wk_arr == u)[0] for u in pick])
            if len(idx) > 3 and xs[idx].std() > 0 and ys[idx].std() > 0:
                boots.append(np.corrcoef(xs[idx], ys[idx])[0, 1])
        boots = np.array([b for b in boots if np.isfinite(b)])
        cross.append(dict(quantity=label, n_pairs=int(len(xs)), n_slates=int(len(uniq)),
                          corr=r, ci_lo=float(np.percentile(boots, 2.5)) if len(boots) else np.nan,
                          ci_hi=float(np.percentile(boots, 97.5)) if len(boots) else np.nan,
                          p_independence_fails=bool(
                              len(boots) and (np.percentile(boots, 2.5) > 0 or np.percentile(boots, 97.5) < 0))))
    pd.DataFrame(cross).to_csv(PROC / "corr_cross_game.csv", index=False)

    # ------------------------------------------------------- team totals
    vh, va = g.home_score.var(ddof=1), g.away_score.var(ddof=1)
    cov = float(np.cov(g.home_score, g.away_score, ddof=1)[0, 1])
    r = cov / np.sqrt(vh * va)
    share = vh / (vh + va + 2 * cov)
    pd.DataFrame([
        dict(quantity="var(home points)", value=float(vh)),
        dict(quantity="var(away points)", value=float(va)),
        dict(quantity="cov(home, away)", value=cov),
        dict(quantity="corr(home, away)", value=float(r)),
        dict(quantity="var(total)", value=float((vh + va + 2 * cov))),
        dict(quantity="home share of total variance", value=float(share)),
        dict(quantity="mean total", value=float(g.total.mean())),
        dict(quantity="sd total", value=float(g.total.std(ddof=1))),
        dict(quantity="mean |margin|", value=float(g.result.abs().mean())),
        dict(quantity="sd margin", value=float(g.result.std(ddof=1))),
    ]).to_csv(PROC / "corr_team_totals.csv", index=False)

    # --------------------------------------------------------- key numbers
    kn = []
    for k in range(0, 15):
        kn.append(dict(number=k,
                       margin_eq=float((g.result == k).mean()),
                       margin_eq_neg=float((g.result == -k).mean()),
                       spread_landed=float((g.market_spread == k).mean()),
                       spread_push=float((g.market_spread == g.result).mul(g.market_spread == k).mean()),
                       total_landed=float((g.market_total == k).mean()),
                       total_push=float((g.market_total == g.total).mul(g.market_total == k).mean())))
    pd.DataFrame(kn).to_csv(PROC / "key_numbers.csv", index=False)

    # ------------------------------------------------------- vig / hold
    vig = []
    for (season,), grp in g[g.home_spread_odds.notna()].groupby(["season"]):
        def hold(a, b):
            """Two-way overround: implied(a) + implied(b) − 1, averaged over games."""
            vals = [implied_prob(x) + implied_prob(y) - 1
                    for x, y in zip(grp[a], grp[b]) if np.isfinite(x) and np.isfinite(y)]
            return float(np.mean(vals)) if vals else np.nan
        vig.append(dict(season=int(season),
                        n=int(len(grp)),
                        spread_hold=hold("home_spread_odds", "away_spread_odds"),
                        total_hold=hold("over_odds", "under_odds"),
                        ml_hold=hold("market_home_ml", "market_away_ml")))
    pd.DataFrame(vig).to_csv(PROC / "vig_by_season.csv", index=False)

    # -------------------------------------------------- favourite/longshot
    fl = []
    m = g[g.market_home_ml.notna() & g.market_away_ml.notna()].copy()
    for side in ["home", "away"]:
        m["price"] = m[f"market_{side}_ml"]
        m["dec"] = m["price"].map(american_to_decimal)
        m["won"] = (m.result > 0) if side == "home" else (m.result < 0)
        m["push"] = m.result == 0
        for lo, hi, label in [(-100000, -200, "heavy favourite (< -200)"),
                              (-200, -120, "favourite (-200 to -121)"),
                              (-120, -101, "slight favourite (-120 to -101)"),
                              (-100, 101, "pick'em (-100 to +100)"),
                              (101, 150, "slight dog (+101 to +150)"),
                              (150, 300, "dog (+151 to +300)"),
                              (300, 100000, "big dog (> +300)")]:
            sub = m[(m.price > lo) & (m.price <= hi)]
            if len(sub) < 20:
                continue
            pnl = np.where(sub.push, 0.0, np.where(sub.won, sub.dec - 1, -1.0))
            se = float(np.std(pnl, ddof=1) / np.sqrt(len(pnl))) if len(pnl) > 1 else np.nan
            roi = float(pnl.mean())
            fl.append(dict(side=side, bucket=label, n=len(sub), roi=roi,
                           ci_lo=roi - 1.96 * se, ci_hi=roi + 1.96 * se,
                           significant=bool(np.isfinite(se) and abs(roi) > 1.96 * se),
                           win_rate=float(sub.won[~sub.push].mean()) if (~sub.push).any() else np.nan,
                           avg_price=float(sub.price.mean())))
    pd.DataFrame(fl).to_csv(PROC / "fav_longshot.csv", index=False)

    # ------------------------------------------------------- prop inputs
    prop = pd.DataFrame([
        dict(component="Player game logs (passing/rushing/receiving yards, receptions, TDs)",
             available="NO", status="UNVERIFIED — source not reachable in this build",
             note=("nflverse release assets (`player_stats`, `stats_player`) are served from "
                   "release-assets.githubusercontent.com, which this environment's egress "
                   "blocklist refuses; every GitHub mirror checked stores these files as "
                   "132-byte Git-LFS pointers. No value was estimated to fill the gap.")),
        dict(component="Team scoring totals", available="YES",
             status="VERIFIED", note="games.csv home_score/away_score, reconciled 7,384/7,384"),
        dict(component="Game total lines", available="YES", status="VERIFIED",
             note="games.csv total_line, 100% present 1999–2025"),
        dict(component="Team total lines", available="NO",
             status="UNVERIFIED — not present in any retrieved source",
             note="nflverse game-level files carry only the full-game total, not the 8-way team total market."),
        dict(component="Player prop prices", available="NO",
             status="UNVERIFIED — not present in any retrieved source",
             note="No retrieved source carries prop prices, so no prop ROI can be computed."),
        dict(component="Correlation of team scoring", available="YES", status="VERIFIED",
             note="computed in corr_team_totals.csv"),
    ])
    prop.to_csv(PROC / "prop_inputs.csv", index=False)

    print("market correlations:")
    print(pd.read_csv(PROC / "corr_market.csv")[["pair", "n", "pearson", "ci_lo", "ci_hi"]]
          .round(4).to_string(index=False))
    print("\nsame-game leg pairs:")
    print(pd.read_csv(PROC / "corr_same_game.csv")[["pair", "n", "phi", "lift"]].round(4).to_string(index=False))
    print("\ncross-game:")
    print(pd.read_csv(PROC / "corr_cross_game.csv").round(4).to_string(index=False))
    print("\nteam totals:")
    print(pd.read_csv(PROC / "corr_team_totals.csv").round(4).to_string(index=False))


if __name__ == "__main__":
    main()
