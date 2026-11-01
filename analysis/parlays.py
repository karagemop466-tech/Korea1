"""Correlation + parlay pricing lab.

Everything here is measured on settled games with real two-sided prices, so the
numbers are empirical, not assumed:

  * within-game leg correlations (phi) across spread / total / moneyline
  * same-game parlay (SGP) EV when the book prices legs as independent
  * cross-game parlay EV (the 'parlay tax')
  * 3- and 4-leg combinations inside one game (where correlation compounds)
  * fair-vs-book payout comparison and Kelly sizing under correlation

Definitions
    phi = (P(A and B) - P(A)P(B)) / sqrt(P(A)(1-P(A))P(B)(1-P(B)))
    EV per 1u staked on a fixed-odds parlay = P_joint*(prod(decimal)-1) - (1-P_joint)
    'Book price'  = product of the quoted two-sided decimals (standard parlay rule)
    'Fair price'  = 1 / empirical P_joint
Pushes are removed from the joint-frequency calculation (they void that leg).
"""
from __future__ import annotations

import itertools
import json
import math

import numpy as np
import pandas as pd

from .common import DERIVED, SITE, american_to_decimal, american_to_prob, devig_two_way

LEGS = {
    "HOME_ATS": ("SPREAD", "home"),
    "AWAY_ATS": ("SPREAD", "away"),
    "OVER": ("TOTAL", "over"),
    "UNDER": ("TOTAL", "under"),
    "HOME_ML": ("ML", "home"),
    "AWAY_ML": ("ML", "away"),
}


def _leg_columns(g: pd.DataFrame) -> pd.DataFrame:
    d = g[g["home_score"].notna()].copy()
    d["home_cover"] = np.where(d["result"] > d["spread_line"], 1.0,
                               np.where(d["result"] < d["spread_line"], 0.0, np.nan))
    d["away_cover"] = 1 - d["home_cover"]
    d["over"] = np.where(d["total"] > d["total_line"], 1.0,
                         np.where(d["total"] < d["total_line"], 0.0, np.nan))
    d["under"] = 1 - d["over"]
    d["home_win"] = np.where(d["result"] > 0, 1.0, np.where(d["result"] < 0, 0.0, np.nan))
    d["away_win"] = 1 - d["home_win"]
    d["p_home_cover_fair"] = np.nan
    d["p_over_fair"] = np.nan
    d["p_home_win_fair"] = np.nan
    sp = d["home_spread_odds"].notna() & d["away_spread_odds"].notna()
    pa, ph = devig_two_way(d.loc[sp, "away_spread_odds"], d.loc[sp, "home_spread_odds"])
    d.loc[sp, "p_home_cover_fair"] = ph
    tt = d["over_odds"].notna() & d["under_odds"].notna()
    po, pu = devig_two_way(d.loc[tt, "over_odds"], d.loc[tt, "under_odds"])
    d.loc[tt, "p_over_fair"] = po
    ml = d["home_moneyline"].notna() & d["away_moneyline"].notna()
    pa2, ph2 = devig_two_way(d.loc[ml, "away_moneyline"], d.loc[ml, "home_moneyline"])
    d.loc[ml, "p_home_win_fair"] = ph2
    fair = {"HOME_ATS": "p_home_cover_fair", "AWAY_ATS": "p_home_cover_fair",
            "OVER": "p_over_fair", "UNDER": "p_over_fair",
            "HOME_ML": "p_home_win_fair", "AWAY_ML": "p_home_win_fair"}
    d.attrs["fair"] = fair
    return d


def _leg_frame(d: pd.DataFrame, leg: str) -> pd.DataFrame:
    mkt, side = LEGS[leg]
    if mkt == "SPREAD":
        out = d[["game_id", "season", "week", "home_team", "away_team"]].copy()
        out["outcome"] = d["home_cover" if side == "home" else "away_cover"]
        out["price"] = d["home_spread_odds" if side == "home" else "away_spread_odds"]
        out["p_fair"] = (d["p_home_cover_fair"] if side == "home" else 1 - d["p_home_cover_fair"])
    elif mkt == "TOTAL":
        out = d[["game_id", "season", "week", "home_team", "away_team"]].copy()
        out["outcome"] = d["over" if side == "over" else "under"]
        out["price"] = d["over_odds" if side == "over" else "under_odds"]
        out["p_fair"] = (d["p_over_fair"] if side == "over" else 1 - d["p_over_fair"])
    else:
        out = d[["game_id", "season", "week", "home_team", "away_team"]].copy()
        out["outcome"] = d["home_win" if side == "home" else "away_win"]
        out["price"] = d["home_moneyline" if side == "home" else "away_moneyline"]
        out["p_fair"] = (d["p_home_win_fair"] if side == "home" else 1 - d["p_home_win_fair"])
    out["leg"] = leg
    return out


def _phi(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 20:
        return float("nan")
    pa, pb = a.mean(), b.mean()
    pab = (a * b).mean()
    den = math.sqrt(max(pa * (1 - pa) * pb * (1 - pb), 1e-12))
    return float((pab - pa * pb) / den)


def within_game(d: pd.DataFrame) -> dict:
    frames = {L: _leg_frame(d, L).set_index("game_id") for L in LEGS}
    rows = []
    exclusive = {frozenset({"HOME_ATS", "AWAY_ATS"}), frozenset({"OVER", "UNDER"}),
                 frozenset({"HOME_ML", "AWAY_ML"})}
    for a, b in itertools.combinations(LEGS, 2):
        if frozenset({a, b}) in exclusive:
            continue   # cannot both win - not a parlay, it is a losing ticket
        ja = frames[a][["outcome", "price", "p_fair"]].rename(
            columns={"outcome": "oa", "price": "pa", "p_fair": "fa"})
        jb = frames[b][["outcome", "price", "p_fair"]].rename(
            columns={"outcome": "ob", "price": "pb", "p_fair": "fb"})
        j = ja.join(jb, how="inner").dropna()
        if len(j) < 100:
            continue
        p_joint = float((j["oa"] * j["ob"]).mean())
        p_ind = float((j["fa"] * j["fb"]).mean())
        dec = american_to_decimal(j["pa"].values) * american_to_decimal(j["pb"].values)
        fair_dec = 1 / p_joint if p_joint > 0 else float("inf")
        ev = p_joint * (float(np.mean(dec)) - 1) - (1 - p_joint)
        rows.append({
            "leg_a": a, "leg_b": b, "n_games": int(len(j)),
            "p_a": round(float(j["oa"].mean()), 4), "p_b": round(float(j["ob"].mean()), 4),
            "p_joint_empirical": round(p_joint, 4),
            "p_joint_independent": round(p_ind, 4),
            "lift": round(p_joint / p_ind, 4) if p_ind else float("nan"),
            "phi": round(_phi(j["oa"].values, j["ob"].values), 4),
            "book_decimal": round(float(np.mean(dec)), 3),
            "fair_decimal": round(fair_dec, 3) if math.isfinite(fair_dec) else None,
            "hold_vs_fair": round(float(np.mean(dec)) / fair_dec - 1, 4) if math.isfinite(fair_dec) else None,
            "ev_per_unit": round(ev, 4),
            "same_game": True,
            "pricing_note": ("Same-game legs: books run correlation-adjusted SGP pricing, so "
                             "ev_per_unit is the value ONLY if the book paid product-of-decimals. "
                             "Read it as 'how much correlation moves the price', not as an arb."),
        })
    return {"pairs": rows}


def across_game(d: pd.DataFrame, n_draws: int = 40000, seed: int = 5) -> dict:
    """Parlays whose legs come from *different* games.

    Books price cross-game parlays as the product of leg decimals, so this is the
    one place where an independence assumption is economically accurate and the
    measured EV is directly actionable.
    """
    f = _leg_frame(d, "HOME_ATS").rename(
        columns={"outcome": "o1", "price": "pr1", "p_fair": "f1"})[
        ["game_id", "o1", "pr1", "f1"]]
    o = _leg_frame(d, "OVER").rename(
        columns={"outcome": "o2", "price": "pr2", "p_fair": "f2"})[
        ["game_id", "o2", "pr2", "f2"]]
    j = f.merge(o, on="game_id", how="inner").dropna().reset_index(drop=True)
    rng = np.random.default_rng(seed)
    n = len(j)
    o1, o2 = j["o1"].values, j["o2"].values
    pr1, pr2 = american_to_decimal(j["pr1"].values), american_to_decimal(j["pr2"].values)
    f1, f2 = j["f1"].values, j["f2"].values
    rows = []
    for k in (2, 3, 4):
        joint, indep, dec = [], [], []
        for _ in range(n_draws):
            idx = rng.integers(0, n, size=k)     # with replacement => independent draws
            leg_out = np.where(np.arange(k) % 2 == 0, o1[idx], o2[idx])
            leg_pr = np.where(np.arange(k) % 2 == 0, pr1[idx], pr2[idx])
            leg_f = np.where(np.arange(k) % 2 == 0, f1[idx], f2[idx])
            joint.append(float(np.prod(leg_out)))
            indep.append(float(np.prod(leg_f)))
            dec.append(float(np.prod(leg_pr)))
        joint, indep, dec = np.array(joint), np.array(indep), np.array(dec)
        ev = joint * (dec - 1) - (1 - joint)
        rows.append({
            "legs": k, "draws": n_draws,
            "mean_ev_per_unit": round(float(ev.mean()), 4),
            "empirical_joint_rate": round(float(joint.mean()), 4),
            "independence_joint_rate": round(float(indep.mean()), 4),
            "lift": round(float(joint.mean() / indep.mean()), 4) if indep.mean() else None,
            "mean_book_decimal": round(float(dec.mean()), 3),
            "mean_fair_decimal": round(float(1 / max(joint.mean(), 1e-9)), 3),
            "share_positive_ev": round(float((ev > 0).mean()), 4),
        })
    return {"combos": rows, "n_games_pool": int(n),
            "note": ("Legs are drawn independently across games (HOME_ATS from one game, OVER from "
                     "another, alternating). Independence means lift ~ 1.00 and the EV is set by the "
                     "compounded vig: this is the 'parlay tax'.")}


def within_game_multi(d: pd.DataFrame) -> dict:
    """3-leg and 4-leg combos *inside one game* where correlation compounds."""
    f = {L: _leg_frame(d, L).set_index("game_id") for L in LEGS}
    combos = [
        ("HOME_ATS", "OVER", "HOME_ML"),
        ("HOME_ATS", "UNDER", "HOME_ML"),
        ("AWAY_ATS", "OVER", "AWAY_ML"),
        ("AWAY_ATS", "UNDER", "AWAY_ML"),
        ("HOME_ATS", "OVER"),
        ("HOME_ATS", "UNDER"),
    ]
    rows = []
    for combo in combos:
        j = f[combo[0]][["outcome", "price", "p_fair"]].rename(
            columns={"outcome": "o0", "price": "p0", "p_fair": "f0"})
        ok = True
        for i, L in enumerate(combo[1:], start=1):
            j = j.join(f[L][["outcome", "price", "p_fair"]].rename(
                columns={"outcome": f"o{i}", "price": f"p{i}", "p_fair": f"f{i}"}), how="inner")
        j = j.dropna()
        if len(j) < 100:
            continue
        oc = np.prod([j[f"o{i}"].values for i in range(len(combo))], axis=0)
        pf = np.prod([j[f"f{i}"].values for i in range(len(combo))], axis=0)
        dec = np.prod([american_to_decimal(j[f"p{i}"].values) for i in range(len(combo))], axis=0)
        p_joint = float(oc.mean())
        p_ind = float(pf.mean())
        rows.append({
            "legs": " + ".join(combo), "n_games": int(len(j)),
            "p_joint_empirical": round(p_joint, 4),
            "p_joint_independent": round(p_ind, 4),
            "lift": round(p_joint / p_ind, 3) if p_ind else None,
            "book_decimal": round(float(dec.mean()), 2),
            "fair_decimal": round(1 / p_joint, 2) if p_joint else None,
            "ev_per_unit": round(p_joint * (float(dec.mean()) - 1) - (1 - p_joint), 4),
            "same_game": True,
            "pricing_note": ("Naive product pricing only. Real SGP engines price the correlation, "
                             "so this is a measure of correlation strength, not free money."),
        })
    return {"combos": rows}


def kelly(ev_table: list[dict]) -> dict:
    """Kelly fraction for a parlay given empirical win probability and book decimal."""
    out = []
    for r in ev_table:
        p = r["p_joint_empirical"]
        d = r["book_decimal"]
        if not p or not d:
            continue
        b = d - 1
        f = (p * b - (1 - p)) / b if b > 0 else 0.0
        out.append({"legs": r.get("legs") or f'{r["leg_a"]}+{r["leg_b"]}',
                    "full_kelly": round(max(f, 0.0), 4),
                    "quarter_kelly": round(max(f, 0.0) / 4, 4)})
    return {"sizing": out,
            "note": "Positive Kelly requires positive edge. A zero or tiny fraction means the bet is not worth placing."}


def main() -> None:
    g = pd.read_csv(DERIVED / "model_lines.csv", parse_dates=["gameday"])
    d = _leg_columns(g)
    wg = within_game(d)
    ag = across_game(d)
    wm = within_game_multi(d)
    payload = {
        "n_games_scored": int(d["home_cover"].notna().sum()),
        "seasons": [int(d["season"].min()), int(d["season"].max())],
        "within_game": wg, "across_game": ag, "within_game_multi": wm,
        "kelly": kelly(wg["pairs"]),
        "method": ("phi and joint frequencies are measured on settled games with two-sided quotes. "
                   "Book parlay price = product of quoted decimals (the standard rule, no correlation "
                   "adjustment for cross-game parlays; some books do adjust SGPs)."),
    }
    (SITE / "parlays.json").write_text(json.dumps(payload, indent=1, default=str))
    print(pd.DataFrame(wg["pairs"])[["leg_a", "leg_b", "n_games", "p_joint_empirical",
                                     "p_joint_independent", "lift", "phi", "ev_per_unit"]].to_string(index=False))
    print(pd.DataFrame(wm["combos"]).to_string(index=False))
    print(pd.DataFrame(ag["combos"]).to_string(index=False))


if __name__ == "__main__":
    main()
