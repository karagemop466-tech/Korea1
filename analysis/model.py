"""K1 line-origination model.

Two ridge regressions are re-fit *walk-forward* (for every game, only games that
kicked off before it are used):

    margin  = hfa + rating[home] - rating[away]                    (spread model)
    points  = mu + offence[i] + defence[j]  for each team, per game (total model)

Recency weighting: w = 0.5 ** (days_before / HALF_LIFE_DAYS).
The look-back window is the current season plus the two previous seasons, so
week 1 of a season is priced off last year's form (no leakage).

Outputs (data/derived/model_lines.csv):
    model_spread   line convention identical to upstream `spread_line`
                   (positive = home favoured; home covers iff result > line)
    model_total    combined points
    model_sd       residual sd of the spread model (for probability maths)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .common import DERIVED, write_csv

HALF_LIFE_DAYS = 55.0
RIDGE_SPREAD = 6.0
RIDGE_TOTAL = 6.0
LOOKBACK_SEASONS = 2


def _ridge_solve(X: np.ndarray, y: np.ndarray, w: np.ndarray, lam: float) -> np.ndarray:
    sw = np.sqrt(w)
    Xw = X * sw[:, None]
    yw = y * sw
    A = Xw.T @ Xw + lam * np.eye(X.shape[1])
    b = Xw.T @ yw
    return np.linalg.solve(A, b)


def _design(teams: list[str], away: np.ndarray, home: np.ndarray, with_hfa=True):
    n = len(away)
    idx = {t: i for i, t in enumerate(teams)}
    k = len(teams)
    X = np.zeros((n, k + 1))
    for i, (a, h) in enumerate(zip(away, home)):
        X[i, idx[h]] = 1.0
        X[i, idx[a]] = -1.0
    if with_hfa:
        X[:, -1] = 1.0          # home field advantage column
    return X, idx


def walk_forward_lines(g: pd.DataFrame) -> pd.DataFrame:
    """Return one row per REG game with model_spread / model_total attached."""
    reg = g[g["game_type"] == "REG"].copy()
    reg = reg.sort_values(["gameday", "game_id"]).reset_index(drop=True)
    teams = sorted(set(reg["home_team"]) | set(reg["away_team"]))
    out = []

    # Pre-index games by season for fast look-back slicing
    by_season = {s: d for s, d in reg.groupby("season")}

    for (season, week), cur in reg.groupby(["season", "week"], sort=True):
        cur_dates = cur["gameday"].min()
        hist_parts = []
        for back in range(0, LOOKBACK_SEASONS + 1):
            s = season - back
            if s not in by_season:
                continue
            d = by_season[s]
            if back == 0:
                d = d[d["week"] < week]
            hist_parts.append(d)
        hist = pd.concat(hist_parts) if hist_parts else cur.iloc[0:0]
        hist = hist[hist["home_score"].notna() & hist["spread_line"].notna()]
        if len(hist) < 40:
            for _, r in cur.iterrows():
                out.append({"game_id": r["game_id"], "model_spread": np.nan,
                            "model_total": np.nan, "model_sd": np.nan,
                            "hfa_est": np.nan, "model_n_hist": len(hist)})
            continue

        days = (cur_dates - hist["gameday"]).dt.days.clip(lower=1).values
        wts = 0.5 ** (days / HALF_LIFE_DAYS)

        # --- spread / margin model ---
        X, idx = _design(teams, hist["away_team"].values, hist["home_team"].values)
        y = hist["result"].values.astype(float)
        beta = _ridge_solve(X, y, wts, RIDGE_SPREAD)
        match = (X @ beta - y)
        sd = float(np.sqrt(np.average(match ** 2, weights=wts)))
        hfa = float(beta[-1])

        # --- total model: points = mu + off_i + def_j (long form) ---
        rows_t, y_t = [], []
        for away, home, a_pts, h_pts in zip(hist["away_team"].values, hist["home_team"].values,
                                           hist["away_score"].values, hist["home_score"].values):
            rows_t.append((away, home)); y_t.append(a_pts)
            rows_t.append((home, away)); y_t.append(h_pts)
        y_t = np.array(y_t, dtype=float)
        Xt = np.zeros((len(rows_t), 2 * len(teams) + 1))
        for i, (off_t, def_t) in enumerate(rows_t):
            Xt[i, idx[off_t]] = 1.0
            Xt[i, len(teams) + idx[def_t]] = 1.0
            Xt[i, -1] = 1.0
        w_t = np.repeat(wts, 2)
        bt = _ridge_solve(Xt, y_t, w_t, RIDGE_TOTAL)

        for _, r in cur.iterrows():
            h, a = r["home_team"], r["away_team"]
            pred_margin = beta[idx[h]] - beta[idx[a]] + hfa
            pred_total = (2 * bt[-1] + bt[idx[h]] + bt[idx[a]]
                          + bt[len(teams) + idx[h]] + bt[len(teams) + idx[a]])
            out.append({
                "game_id": r["game_id"],
                "model_spread": float(pred_margin),
                "model_total": float(pred_total),
                "model_sd": sd,
                "hfa_est": hfa,
                "model_n_hist": int(len(hist)),
            })
    m = pd.DataFrame(out)
    return reg.merge(m, on="game_id", how="left")


def evaluate_lines(d: pd.DataFrame) -> dict:
    """How good are the originated lines relative to the closing market?"""
    played = d[d["home_score"].notna() & d["model_spread"].notna()].copy()
    played["mkt_err_sp"] = (played["spread_line"] - played["result"]).abs()
    played["mod_err_sp"] = (played["model_spread"] - played["result"]).abs()
    played["mkt_err_tot"] = (played["total_line"] - played["total"]).abs()
    played["mod_err_tot"] = (played["model_total"] - played["total"]).abs()
    # "no-vig" market benchmark: the closing line is the market's forecast
    res = {
        "games_scored": int(len(played)),
        "seasons": [int(played["season"].min()), int(played["season"].max())],
        "spread_corr_model_market": round(float(played["model_spread"].corr(played["spread_line"])), 4),
        "spread_mae_model_vs_market": round(float((played["model_spread"] - played["spread_line"]).abs().mean()), 3),
        "spread_mae_vs_result_market": round(float(played["mkt_err_sp"].mean()), 3),
        "spread_mae_vs_result_model": round(float(played["mod_err_sp"].mean()), 3),
        "spread_rmse_vs_result_market": round(float(np.sqrt((played["mkt_err_sp"] ** 2).mean())), 3),
        "spread_rmse_vs_result_model": round(float(np.sqrt((played["mod_err_sp"] ** 2).mean())), 3),
        "spread_model_beats_market_pct": round(float((played["mod_err_sp"] < played["mkt_err_sp"]).mean()), 4),
        "total_corr_model_market": round(float(played["model_total"].corr(played["total_line"])), 4),
        "total_mae_model_vs_market": round(float((played["model_total"] - played["total_line"]).abs().mean()), 3),
        "total_mae_vs_result_market": round(float(played["mkt_err_tot"].mean()), 3),
        "total_mae_vs_result_model": round(float(played["mod_err_tot"].mean()), 3),
        "total_rmse_vs_result_market": round(float(np.sqrt((played["mkt_err_tot"] ** 2).mean())), 3),
        "total_rmse_vs_result_model": round(float(np.sqrt((played["mod_err_tot"] ** 2).mean())), 3),
        "total_model_beats_market_pct": round(float((played["mod_err_tot"] < played["mkt_err_tot"]).mean()), 4),
        "by_season_spread_mae_model": {
            int(s): round(float(x["mod_err_sp"].mean()), 2) for s, x in played.groupby("season")
        },
        "by_season_spread_mae_market": {
            int(s): round(float(x["mkt_err_sp"].mean()), 2) for s, x in played.groupby("season")
        },
        "note": ("A model that beats the closing line on MAE would be extraordinary; the honest "
                 "benchmark is that the market is sharper. We report both and never claim superiority "
                 "that the data does not support."),
    }
    return res


def calibrate(d: pd.DataFrame, train: tuple[int, int], test: tuple[int, int]) -> dict:
    """Logistic calibration of cover probability on the model's market edge.

    edge = market_spread - model_spread  (positive => model likes the home side
    more than the market does, i.e. model thinks home is better than priced).
    """
    p = d[d["home_score"].notna() & d["model_spread"].notna()].copy()
    p["edge"] = p["spread_line"] - p["model_spread"]
    p["home_cover"] = np.where(p["result"] > p["spread_line"], 1.0,
                               np.where(p["result"] < p["spread_line"], 0.0, 0.5))
    p = p[p["home_cover"] != 0.5]
    p["edge_bin"] = pd.cut(p["edge"], [-np.inf, -6, -4, -3, -2, -1, 1, 2, 3, 4, 6, np.inf])
    tab = []
    for b, x in p.groupby("edge_bin", observed=True):
        tab.append({"bin": str(b), "n": int(len(x)),
                    "home_cover_rate": round(float(x["home_cover"].mean()), 3),
                    "mean_edge": round(float(x["edge"].mean()), 2)})
    tr = p[(p["season"] >= train[0]) & (p["season"] <= train[1])]
    te = p[(p["season"] >= test[0]) & (p["season"] <= test[1])]

    def fit(df):
        X = np.column_stack([np.ones(len(df)), df["edge"].values])
        y = df["home_cover"].values
        b = np.zeros(2)
        for _ in range(60):  # Newton-Raphson
            eta = X @ b
            pr = 1 / (1 + np.exp(-eta))
            Wd = pr * (1 - pr)
            H = X.T @ (X * Wd[:, None]) + 1e-9 * np.eye(2)
            g = X.T @ (y - pr)
            b += np.linalg.solve(H, g)
        return b

    def predict(b, df):
        return 1 / (1 + np.exp(-(b[0] + b[1] * df["edge"].values)))

    b_tr = fit(tr)
    b_te = fit(te)
    b_all = fit(p)
    out = {
        "train_seasons": list(train), "test_seasons": list(test),
        "coef_train": {"intercept": round(float(b_tr[0]), 4), "slope": round(float(b_tr[1]), 4)},
        "coef_test": {"intercept": round(float(b_te[0]), 4), "slope": round(float(b_te[1]), 4)},
        "coef_all": {"intercept": round(float(b_all[0]), 4), "slope": round(float(b_all[1]), 4)},
        "interpretation": ("slope>0 means a bigger model-vs-market disagreement really does predict "
                           "covering; slope~0 means the disagreement is noise."),
        "bins": tab,
        "n_train": int(len(tr)), "n_test": int(len(te)),
    }
    # out-of-sample test: does the train-fitted slope predict test outcomes?
    te = te.copy()
    te["p_home"] = predict(b_tr, te)
    te["ll"] = -(te["home_cover"] * np.log(te["p_home"].clip(1e-9))
                 + (1 - te["home_cover"]) * np.log((1 - te["p_home"]).clip(1e-9)))
    te["ll_base"] = -(te["home_cover"] * np.log(0.5) + (1 - te["home_cover"]) * np.log(0.5))
    out["oos_logloss_model"] = round(float(te["ll"].mean()), 5)
    out["oos_logloss_coinflip"] = round(float(te["ll_base"].mean()), 5)
    out["oos_better_than_coinflip"] = bool(te["ll"].mean() < te["ll"].mean() * 0 + te["ll_base"].mean())
    return out


def main() -> None:
    g = pd.read_csv(DERIVED / "games.csv", parse_dates=["gameday"])
    d = walk_forward_lines(g)
    write_csv(d, "model_lines.csv")
    rep = {"model": evaluate_lines(d), "calibration": calibrate(d, (1999, 2016), (2017, 2026))}
    (DERIVED / "model_report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep["model"], indent=1))
    print(json.dumps(rep["calibration"]["coef_all"], indent=1))


if __name__ == "__main__":
    main()
