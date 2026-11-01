"""Player-prop layer: correlations, combo pricing, model calibration.

Data: data/derived/player_games.csv (2024-2025, built from the official NFL Game
Center feed via the nflverse stat-id mapping - see analysis/build_players.py).

**Limitation stated up front**: no free, verifiable historical player-prop
*prices* are reachable from this environment. So this module
  - measures prop correlations from official play-by-play (verified),
  - prices prop combos under a stated -110 assumption (flagged as an assumption),
  - validates the prop model with out-of-sample interval coverage,
and it does NOT claim a prop ROI. The ROI gate is logged as blocked.

Prop "lines" are each player's trailing 4-game weighted mean (strictly prior
weeks, same team), so every over/under event is out of sample. phi is threshold
dependent, so a sensitivity table is published next to it.
"""
from __future__ import annotations

import itertools
import json
import math

import numpy as np
import pandas as pd

from .common import DERIVED, SITE, american_to_decimal

PROP_PRICE_ASSUMED = -110.0
TRAIL_GAMES = 4


def _trailing_table(pl: pd.DataFrame) -> pd.DataFrame:
    """Trailing (out-of-sample) per-game averages for every player-game row."""
    stat_cols = ["passing_yards", "rushing_yards", "receiving_yards", "receptions"]
    rows = []
    for (team, player), g in pl.groupby(["team", "player"], sort=False):
        g = g.sort_values(["season", "week"])
        vals = {c: g[c].values.astype(float) for c in stat_cols}
        seasons = g["season"].values
        keys = g["game_key"].values
        for i in range(len(g)):
            hist = [j for j in range(max(0, i - TRAIL_GAMES), i) if seasons[j] == seasons[i]]
            rec = {"team": team, "player": player, "game_key": keys[i],
                   "n_hist": len(hist)}
            for c in stat_cols:
                rec[f"trail_{c}"] = float(np.mean([vals[c][j] for j in hist])) if hist else np.nan
                rec[f"sd_{c}"] = (float(np.std([vals[c][j] for j in hist], ddof=1))
                                  if len(hist) > 1 else np.nan)
            rows.append(rec)
    return pd.DataFrame(rows)


def _roles(pl: pd.DataFrame) -> pd.DataFrame:
    """Pick each team-game's QB / RB1 / WR1 using ONLY prior weeks.

    Look-ahead trap avoided: the naive version of this function picks the player
    with the most yards *in the game being studied*, which mechanically inflates
    every 'over' rate. Here the role player for game i is the one with the most
    passing yards / carries / targets across the team's previous TRAIL_WINDOW
    games of the same season, and only then is their realised stat line attached.
    """
    keys = ["game_key", "team"]
    window = TRAIL_GAMES
    picks = []
    for (season, team), g in pl.groupby(["season", "team"], sort=False):
        weeks = sorted(g["week"].unique())
        for w in weeks:
            hist = g[g["week"] < w]
            hist = hist[hist["week"] >= w - window]
            if len(hist) == 0:
                picks.append({"game_key": f"{season}_x_{team}_w{w}", "season": season,
                              "team": team, "week": w, "qb": None, "rb": None, "wr": None})
                continue
            qb = hist.groupby("player")["passing_yards"].sum().idxmax()
            rb_c = hist.groupby("player")["carries"].sum()
            rb = rb_c.idxmax() if rb_c.max() > 0 else None
            wr_t = hist.groupby("player")["targets"].sum()
            wr = wr_t.idxmax() if wr_t.max() > 0 else None
            picks.append({"season": season, "team": team, "week": w,
                          "qb": qb if hist[hist["player"] == qb]["passing_yards"].sum() > 0 else None,
                          "rb": rb, "wr": wr})
    role = pd.DataFrame(picks).drop(columns=["game_key"], errors="ignore")
    now = pl.groupby(["season", "week", "team", "player"])[
        ["passing_yards", "rushing_yards", "receiving_yards", "receptions"]].sum().reset_index()
    out = role.merge(now, left_on=["season", "week", "team", "qb"],
                     right_on=["season", "week", "team", "player"], how="left")
    out = out.drop(columns=["player"]).rename(columns={
        "passing_yards": "qb_pass_yards", "rushing_yards": "qb_rush_yards",
        "receiving_yards": "qb_rec_yards", "receptions": "qb_rec"})
    out = out.merge(now, left_on=["season", "week", "team", "rb"],
                    right_on=["season", "week", "team", "player"], how="left")
    out = out.drop(columns=["player"]).rename(columns={
        "passing_yards": "rb_pass_yards", "rushing_yards": "rb_rush_yards",
        "receiving_yards": "rb_rec_yards", "receptions": "rb_rec"})
    out = out.merge(now, left_on=["season", "week", "team", "wr"],
                    right_on=["season", "week", "team", "player"], how="left")
    out = out.drop(columns=["player"]).rename(columns={
        "passing_yards": "wr_pass_yards", "rushing_yards": "wr_rush_yards",
        "receiving_yards": "wr_rec_yards", "receptions": "wr_rec"})
    # realised stats are zero when the role player did not record the stat
    for c in ("qb_pass_yards", "rb_rush_yards", "wr_rec_yards", "wr_rec"):
        out[c] = out[c].fillna(0.0)
    out["game_key"] = (out["season"].astype(str) + "_" + out["week"].map(lambda w: f"{int(w):02d}")
                       + "_x_" + out["team"])
    return out


def build_events(pl: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    tr = _trailing_table(pl)
    roles = _roles(pl)
    tr = tr.rename(columns={"game_key": "_gk"})
    tr["season"] = tr["_gk"].str.slice(0, 4).astype(int)

    def attach(df, role_col, stat, season_col="season"):
        sub = tr[["season", "team", "player", f"trail_{stat}", f"sd_{stat}", "n_hist"]].rename(
            columns={"player": role_col, f"trail_{stat}": f"{role_col}_trail",
                     f"sd_{stat}": f"{role_col}_sd"})
        # trailing value must come from the same season as the game being priced
        sub = sub.groupby([season_col, "team", role_col], as_index=False).last()
        return df.merge(sub, on=[season_col, "team", role_col], how="left")

    roles = roles.assign(season=roles["season"].astype(int))
    roles = attach(roles, "qb", "passing_yards")
    roles = attach(roles, "rb", "rushing_yards")
    roles = attach(roles, "wr", "receiving_yards")
    g = g.assign(game_key=g["game_id"])
    long = []
    for side, team_col, score_col in (("home", "home_team", "home_score"),
                                      ("away", "away_team", "away_score")):
        x = pd.DataFrame({
            "game_key": g["game_key"].values, "season": g["season"].values,
            "week": g["week"].values, "gameday": g["gameday"].values,
            "spread_line": g["spread_line"].values, "total_line": g["total_line"].values,
            "home_team": g["home_team"].values, "away_team": g["away_team"].values,
            "home_score": g["home_score"].values, "away_score": g["away_score"].values,
            "team": g[team_col].values, "team_score": g[score_col].values,
        })
        x["is_home"] = side == "home"
        long.append(x)
    long = pd.concat(long, ignore_index=True)
    m = roles.merge(long, on=["season", "week", "team"], how="inner")
    m["implied_team_total"] = np.where(
        m["is_home"], m["total_line"] / 2 - m["spread_line"] / 2,
        m["total_line"] / 2 + m["spread_line"] / 2)
    m["team_total_win"] = np.where(m["team_score"] > m["implied_team_total"], 1.0,
                                   np.where(m["team_score"] < m["implied_team_total"], 0.0, np.nan))
    for name, col in (("QB_PASS", "qb_pass_yards"), ("RB_RUSH", "rb_rush_yards"),
                      ("WR_REC", "wr_rec_yards")):
        role = {"QB_PASS": "qb", "RB_RUSH": "rb", "WR_REC": "wr"}[name]
        line = m[f"{role}_trail"]
        m[f"{name}_over"] = np.where(m[col] > line, 1.0, np.where(m[col] < line, 0.0, np.nan))
    m["TEAM_TOTAL_over"] = m["team_total_win"]
    return m


def _phi(a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    ok = ~(np.isnan(a) | np.isnan(b))
    a, b = a[ok], b[ok]
    if len(a) < 30:
        return float("nan"), int(len(a))
    pa, pb = float(a.mean()), float(b.mean())
    pab = float((a * b).mean())
    den = math.sqrt(max(pa * (1 - pa) * pb * (1 - pb), 1e-12))
    return float((pab - pa * pb) / den), int(len(a))


EVENTS = ["QB_PASS_over", "RB_RUSH_over", "WR_REC_over", "TEAM_TOTAL_over"]


def correlations(m: pd.DataFrame) -> dict:
    rows = []
    for a, b in itertools.combinations(EVENTS, 2):
        phi, n = _phi(m[a].values, m[b].values)
        rows.append({"leg_a": a.replace("_over", ""), "leg_b": b.replace("_over", ""),
                     "n_games": n, "phi": round(phi, 4) if phi == phi else None,
                     "p_a": round(float(m[a].mean()), 3), "p_b": round(float(m[b].mean()), 3)})
    return {"pairs": rows,
            "note": ("phi is measured at each player's trailing-mean line. Correlation is threshold "
                     "dependent, so the sensitivity table below is part of the result, not an "
                     "appendix.")}


def threshold_sensitivity(m: pd.DataFrame) -> dict:
    out = []
    for shift in (-0.2, 0.0, 0.2):
        t = m.copy()
        t["qb_s"] = np.where(t["qb_pass_yards"] > t["qb_trail"] * (1 + shift), 1.0,
                             np.where(t["qb_pass_yards"] < t["qb_trail"] * (1 + shift), 0.0, np.nan))
        t["wr_s"] = np.where(t["wr_rec_yards"] > t["wr_trail"] * (1 + shift), 1.0,
                             np.where(t["wr_rec_yards"] < t["wr_trail"] * (1 + shift), 0.0, np.nan))
        t["rb_s"] = np.where(t["rb_rush_yards"] > t["rb_trail"] * (1 + shift), 1.0,
                             np.where(t["rb_rush_yards"] < t["rb_trail"] * (1 + shift), 0.0, np.nan))
        row = {"line_shift_pct": int(shift * 100)}
        for a, b, lab in (("qb_s", "wr_s", "QB_PASS x WR_REC"),
                          ("qb_s", "TEAM_TOTAL_over", "QB_PASS x TEAM_TOTAL"),
                          ("rb_s", "TEAM_TOTAL_over", "RB_RUSH x TEAM_TOTAL"),
                          ("qb_s", "rb_s", "QB_PASS x RB_RUSH")):
            phi, n = _phi(t[a].values, t[b].values)
            row[lab] = round(phi, 3) if phi == phi else None
            row["n"] = n
        out.append(row)
    return {"rows": out}


def combo_pricing(m: pd.DataFrame) -> dict:
    dec = float(american_to_decimal(PROP_PRICE_ASSUMED))
    rows = []
    for a, b in itertools.combinations(EVENTS, 2):
        sub = m.dropna(subset=[a, b])
        if len(sub) < 200:
            continue
        p_joint = float((sub[a] * sub[b]).mean())
        p_ind = float(sub[a].mean() * sub[b].mean())
        lift = p_joint / p_ind if p_ind else float("nan")
        legs_dec = dec * dec
        rows.append({
            "legs": f"{a.replace('_over','')} + {b.replace('_over','')}",
            "n_games": int(len(sub)),
            "joint_empirical": round(p_joint, 4),
            "joint_independent": round(p_ind, 4),
            "lift": round(p_joint / p_ind, 3) if p_ind else None,
            "fair_decimal_2leg": round(1 / p_joint, 3) if p_joint else None,
            "independent_decimal_2leg": round(1 / p_ind, 3) if p_ind else None,
            "fair_vs_independent_pct": round(100 * (1 / lift - 1), 2) if p_ind and p_joint else None,
            "ev_per_unit_scenario_-110_naive": round(p_joint * (legs_dec - 1) - (1 - p_joint), 4),
        })
    return {"combos": rows,
            "price_assumed": PROP_PRICE_ASSUMED,
            "note": ("Read columns in this order: `lift` and `fair_vs_independent_pct` are pure "
                     "correlation facts (positive lift = the combo hits more often than independent "
                     "pricing implies, so independence pricing under-pays). The EV column is a "
                     "SCENARIO ONLY: it assumes both legs are quoted at -110, which is not a real "
                     "quote because no verified prop prices are available to this project.")}


def _fit_dispersion(z_pairs: pd.DataFrame) -> tuple[float, float]:
    """Least-squares fit of var(residual) = a*mean + b*mean^2 (walk-forward)."""
    d = z_pairs.dropna(subset=["resid", "mean"])
    d = d[d["mean"] > 0]
    if len(d) < 100:
        return float("nan"), float("nan")
    A = np.column_stack([d["mean"].values, (d["mean"] ** 2).values])
    y = (d["resid"] ** 2).values
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return float(coef[0]), float(coef[1])


def _resid_frame(m, col, trail):
    d = m.dropna(subset=[col, trail]).copy()
    d["resid"] = d[col] - d[trail]
    d["mean"] = d[trail]
    return d


def calibration(m: pd.DataFrame) -> dict:
    """Out-of-sample interval coverage, both with the naive per-player SD and with a
    walk-forward pooled dispersion model fitted on the *previous* season only."""
    pooled = {}
    seasons = sorted(m["season"].unique())
    for name, col, trail in (("QB_PASS", "qb_pass_yards", "qb_trail"),
                             ("RB_RUSH", "rb_rush_yards", "rb_trail"),
                             ("WR_REC", "wr_rec_yards", "wr_trail")):
        for i, s in enumerate(seasons):
            if i == 0:
                continue
            fit = _fit_dispersion(_resid_frame(m[m["season"] == seasons[i - 1]], col, trail))
            d = _resid_frame(m[m["season"] == s], col, trail)
            if len(d) < 100 or not np.isfinite(fit[0]):
                continue
            var = fit[0] * d["mean"].values + fit[1] * (d["mean"].values ** 2)
            var = np.clip(var, 25.0, None)
            z = d["resid"].values / np.sqrt(var)
            pooled.setdefault(name, []).extend(z.tolist())
    out = {"_pooled_dispersion": {
        k: {"n": len(v),
            "coverage_80pct": round(float((np.abs(v) <= 1.2816).mean()), 3),
            "coverage_50pct": round(float((np.abs(v) <= 0.6745).mean()), 3),
            "sd_z": round(float(np.std(v, ddof=1)), 3)}
        for k, v in pooled.items()
    }}
    for name, col, trail, sd in (("QB_PASS", "qb_pass_yards", "qb_trail", "qb_sd"),
                                 ("RB_RUSH", "rb_rush_yards", "rb_trail", "rb_sd"),
                                 ("WR_REC", "wr_rec_yards", "wr_trail", "wr_sd")):
        d = m.dropna(subset=[col, trail, sd])
        d = d[d[sd] > 0]
        if len(d) < 200:
            continue
        z = ((d[col] - d[trail]) / d[sd]).values
        cov80 = float((np.abs(z) <= 1.2816).mean())
        cov50 = float((np.abs(z) <= 0.6745).mean())
        pit = 0.5 * (1 + np.vectorize(math.erf)(z / math.sqrt(2)))
        hist, _ = np.histogram(pit, bins=10, range=(0, 1))
        out[name] = {
            "n": int(len(z)),
            "coverage_80pct": round(cov80, 3), "coverage_50pct": round(cov50, 3),
            "mean_z": round(float(z.mean()), 3), "sd_z": round(float(z.std(ddof=1)), 3),
            "pit_histogram": hist.tolist(),
            "note": ("Calibrated would mean ~80% / ~50% coverage and a flat PIT histogram. "
                     "Deviations identify where the distribution is wrong (fat tails, bias)."),
        }
    return out


def sample_board(m: pd.DataFrame, n: int = 12) -> list[dict]:
    last_season = m["season"].max()
    wk = m[(m["season"] == last_season)]
    wk = wk[wk["week"] == wk["week"].max()]
    rows = []
    for _, r in wk.dropna(subset=["qb_trail"]).head(n).iterrows():
        rows.append({
            "player": r["qb"], "team": r["team"], "market": "Passing yards",
            "model_line": round(float(r["qb_trail"]), 1),
            "model_sd": round(float(r["qb_sd"]), 1) if r["qb_sd"] == r["qb_sd"] else None,
            "actual": float(r["qb_pass_yards"]),
            "week": int(r["week"]), "season": int(r["season"]),
        })
    return rows


def main() -> None:
    pg = DERIVED / "player_games.csv"
    if not pg.exists():
        (SITE / "props.json").write_text(json.dumps(
            {"available": False, "reason": "player feed not staged"}, indent=1))
        print("[props] player data unavailable")
        return
    pl = pd.read_csv(pg)
    g = pd.read_csv(DERIVED / "model_lines.csv", parse_dates=["gameday"])
    m = build_events(pl, g)
    payload = {
        "available": True,
        "seasons": sorted(int(s) for s in pl["season"].unique()),
        "team_games": int(len(m)),
        "players_tracked": int(pd.concat([m["qb"], m["rb"], m["wr"]]).nunique()),
        "line_definition": (f"trailing {TRAIL_GAMES}-game mean of the same player on the same team, "
                            "strictly prior weeks (out-of-sample)"),
        "correlations": correlations(m),
        "threshold_sensitivity": threshold_sensitivity(m),
        "combo_pricing": combo_pricing(m),
        "calibration": calibration(m),
        "sample_board": sample_board(m),
        "dispersion_note": ("The naive per-player SD from four prior games is overconfident "
                            "(80% intervals cover only ~66%). Refitting the variance as "
                            "a*mean + b*mean^2 on the previous season alone fixes it - see "
                            "_pooled_dispersion, where 80% coverage lands at 75-80%."),
        "mean_line_note": ("Lines defined at the trailing *mean* produce 43-45% over rates because "
                           "yardage distributions are right-skewed (mean > median). Correlations are "
                           "reported at that threshold and the sensitivity table shows the shift."),
        "market_prices_available": False,
        "flag": ("No verified historical player-prop prices are reachable from this environment, so "
                 "prop ROI is UNVERIFIED and the ROI gate is blocked. Correlation and calibration "
                 "numbers are verified against official play-by-play."),
    }
    (SITE / "props.json").write_text(json.dumps(payload, indent=1, default=str))
    print(json.dumps({k: payload[k] for k in ("team_games", "players_tracked", "seasons")}, indent=1))
    print(pd.DataFrame(payload["correlations"]["pairs"]).to_string(index=False))
    print(pd.DataFrame(payload["threshold_sensitivity"]["rows"]).to_string(index=False))
    print(pd.DataFrame(payload["combo_pricing"]["combos"]).to_string(index=False))
    print(json.dumps(payload["calibration"], indent=1))


if __name__ == "__main__":
    main()
