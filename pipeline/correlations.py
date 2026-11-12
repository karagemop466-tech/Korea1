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



def block_corr_ci(x, y, groups, n_boot=1000, seed=20261101):
    """Cluster bootstrap by NFL week; no iid Fisher assumption for binary legs."""
    x,y,groups=np.asarray(x,float),np.asarray(y,float),np.asarray(groups)
    unique=np.unique(groups)
    if len(unique)<4 or len(x)<4:
        return float("nan"),float("nan")
    indices=[np.flatnonzero(groups==u) for u in unique]
    rng=np.random.default_rng(seed); vals=[]
    for _ in range(n_boot):
        idx=np.concatenate([indices[i] for i in rng.integers(len(indices),size=len(indices))])
        if np.std(x[idx])>0 and np.std(y[idx])>0:
            vals.append(np.corrcoef(x[idx],y[idx])[0,1])
    return (float(np.percentile(vals,2.5)),float(np.percentile(vals,97.5))) if vals else (float("nan"),float("nan"))


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
        groups=(g.loc[sub.index,"season"].astype(str)+"_"+g.loc[sub.index,"week"].astype(str)).to_numpy()
        lo, hi = block_corr_ci(sub[a],sub[b],groups)
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
        groups=(g.loc[sub.index,"season"].astype(str)+"_"+g.loc[sub.index,"week"].astype(str)).to_numpy()
        lo, hi = block_corr_ci(sub[a],sub[b],groups)
        # independence benchmark
        p_joint = float(((sub[a] == 1) & (sub[b] == 1)).mean())
        p_indep = float((sub[a] == 1).mean() * (sub[b] == 1).mean())
        sgp.append(dict(pair=label, n=n, phi=ph, ci_lo=lo, ci_hi=hi,
                        p_joint=p_joint, p_if_independent=p_indep,
                        lift=p_joint / p_indep if p_indep else np.nan))
    pd.DataFrame(sgp).to_csv(PROC / "corr_same_game.csv", index=False)

    # --------------------------------------------------------- cross-game
    # All unordered distinct-game pairs within a slate, not an arbitrary adjacent
    # pairing. Cluster uncertainty by slate because pairs share games. This is a
    # pooled association diagnostic, not proof of independence or tail independence.
    cross=[]
    for col,label in [("result","margin"),("total","total")]:
        xs,ys,wk=[],[],[]
        for (season,week),grp in g.groupby(["season","week"]):
            v=grp.sort_values("game_id")[col].dropna().to_numpy()
            for i in range(len(v)):
                for j in range(i+1,len(v)):
                    xs.append(v[i]);ys.append(v[j]);wk.append(f"{season}_{week}")
        xs,ys=np.asarray(xs),np.asarray(ys)
        r=float(np.corrcoef(xs,ys)[0,1]) if len(xs)>3 else float("nan")
        lo,hi=block_corr_ci(xs,ys,np.asarray(wk))
        cross.append(dict(quantity=label,n_pairs=len(xs),n_slates=len(set(wk)),corr=r,
                          ci_lo=lo,ci_hi=hi,method="all within-slate pairs; slate-cluster bootstrap",
                          interval_excludes_zero=bool(np.isfinite(lo) and np.isfinite(hi) and (lo>0 or hi<0))))
    pd.DataFrame(cross).to_csv(PROC/"corr_cross_game.csv",index=False)

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
                        spread_overround=hold("home_spread_odds", "away_spread_odds"),
                        total_overround=hold("over_odds", "under_odds"),
                        ml_overround=hold("market_home_ml", "market_away_ml")))
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
        dict(component="Player game logs (2019-2022 PBP passing/rushing/receiving/receptions)",
             available="PARTIAL", status="RESEARCH ESTIMATE — 21,033 PBP player-games (props_model.py); 2023-2026 omitted",
             note=("2019-2022 regular-season play-by-play logs (4 hash-pinned git blobs from "
                   "clausherther/nfl-dbt in data/sources_pbp.json) feed props_model.py. 2023-2026 "
                   "release-asset player_stats remain blocked by egress allowlist.")),
        dict(component="Team scoring totals", available="YES",
             status="INTERNALLY CONSISTENT; official verification partial", note="games.csv score arithmetic reconciles; 59 NFL.com rows officially checked"),
        dict(component="Game total lines", available="YES", status="UNVERIFIED — community market observations",
             note="games.csv total_line is present but has no authenticated bookmaker quote provenance"),
        dict(component="Team total lines", available="NO",
             status="UNVERIFIED — not present in any retrieved source",
             note="nflverse game-level files carry only the full-game total, not the 8-way team total market."),
        dict(component="Player prop prices", available="NO",
             status="UNVERIFIED — not present in any retrieved source",
             note="No retrieved source carries prop prices, so no prop ROI can be computed."),
        dict(component="Injuries & 1st-4th string depth charts", available="PARTIAL",
             status="2026 WEEK 10 OFFICIAL SNAPSHOT VERIFIED (27/28 clubs); historical weekly archive missing",
             note=("Week 10 2026 NFL.com injuries + 27 club HTML depth charts ingested (HOU image-only blank); "
                   "historical timestamped weekly inactive/depth feeds remain missing.")),
        dict(component="Correlation of team scoring", available="YES", status="RESEARCH ESTIMATE; official verification partial",
             note="computed in corr_team_totals.csv from the pinned community archive"),
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
