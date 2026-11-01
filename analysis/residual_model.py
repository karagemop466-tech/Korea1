"""Residual (edge) models: predict cover / over probability directly.

Instead of rating teams in absolute points, this models the *residual* against
the closing number:

    P(home covers | X)  = logit(b0 + b'X)
    P(game goes over | Y) = logit(c0 + c'Y)

fitted strictly walk-forward: predictions for season S use only games from
seasons < S. Features are all pre-game and leak-free (rest, entering form,
prior-season form, venue/weather, model-vs-market disagreement).

Outputs columns appended to data/derived/model_lines.csv:
    p_home_cover, p_over  (out-of-sample, NaN where no history)
and data/derived/residual_report.json (log-loss, AUC, Brier, calibration bins).
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from .common import DERIVED

FEATS_COVER = ["rest_diff", "form_diff", "prior_diff_diff", "model_edge", "div_game",
               "dome", "wind", "temp", "week", "primetime", "short_rest"]
FEATS_TOTAL = ["model_total_edge", "total_line", "week", "dome", "wind", "temp",
               "primetime", "form_total", "prior_total"]


def _prep(g: pd.DataFrame) -> pd.DataFrame:
    d = g.copy()
    d["rest_diff"] = (d["home_rest"] - d["away_rest"]).fillna(0)
    d["form_diff"] = (d["home_w5_diff"] - d["away_w5_diff"]) / 10.0
    d["prior_diff_diff"] = (d["home_prior_season_diff"] - d["away_prior_season_diff"]) / 10.0
    d["model_edge"] = (d["spread_line"] - d["model_spread"]) / 3.0
    d["model_total_edge"] = (d["model_total"] - d["total_line"]) / 3.0
    d["div_game"] = d["div_game"].fillna(0).astype(float)
    d["dome"] = d["roof"].isin(["dome", "closed"]).astype(float)
    d["wind"] = d["wind"].fillna(0) / 10.0
    d["temp"] = d["temp"].fillna(60) / 10.0
    d["week"] = d["week"].astype(float)
    gtime = pd.to_numeric(d["gametime"].astype(str).str.slice(0, 2), errors="coerce").fillna(0)
    d["primetime"] = (((gtime >= 20) | (d["weekday"] != "Sunday"))).astype(float)
    d["short_rest"] = ((d[["home_rest", "away_rest"]].min(axis=1) <= 4)).astype(float)
    d["form_total"] = (d["home_w5_pts"] + d["away_w5_pts"] - d["home_w5_pa"] - d["away_w5_pa"]) / 10.0
    d["prior_total"] = (d["home_prior_season_pts"] + d["away_prior_season_pts"]) / 20.0
    return d


def _fit_logit(X: np.ndarray, y: np.ndarray, w: np.ndarray | None = None,
               lam: float = 1.0, iters: int = 40) -> np.ndarray:
    n, k = X.shape
    b = np.zeros(k)
    if w is None:
        w = np.ones(n)
    for _ in range(iters):
        eta = X @ b
        p = 1 / (1 + np.exp(-eta))
        W = p * (1 - p) * w
        H = X.T @ (X * W[:, None]) + lam * np.eye(k)
        g = X.T @ (w * (y - p)) - lam * b
        step = np.linalg.solve(H, g)
        b += step
        if np.max(np.abs(step)) < 1e-7:
            break
    return b


def _add_ones(X: pd.DataFrame) -> np.ndarray:
    return np.column_stack([np.ones(len(X)), X.values.astype(float)])


def build(g: pd.DataFrame) -> pd.DataFrame:
    d = _prep(g)
    d["home_cover"] = np.where(d["result"] > d["spread_line"], 1.0,
                               np.where(d["result"] < d["spread_line"], 0.0, np.nan))
    d["over"] = np.where(d["total"] > d["total_line"], 1.0,
                         np.where(d["total"] < d["total_line"], 0.0, np.nan))
    d["p_home_cover"] = np.nan
    d["p_over"] = np.nan

    played = d[d["home_score"].notna()].copy()
    for season in sorted(d["season"].unique()):
        tr = played[(played["season"] < season) & played["home_cover"].notna()]
        cur_idx = d.index[d["season"] == season]
        if len(tr) < 400 or len(cur_idx) == 0:
            continue
        w = 0.9 ** (season - tr["season"].values)      # recency across seasons
        b_cov = _fit_logit(_add_ones(tr[FEATS_COVER].fillna(0)), tr["home_cover"].values, w)
        trt = tr[tr["over"].notna()]
        b_tot = _fit_logit(_add_ones(trt[FEATS_TOTAL].fillna(0)), trt["over"].values,
                           0.9 ** (season - trt["season"].values))
        Xc = _add_ones(d.loc[cur_idx, FEATS_COVER].fillna(0))
        Xo = _add_ones(d.loc[cur_idx, FEATS_TOTAL].fillna(0))
        d.loc[cur_idx, "p_home_cover"] = 1 / (1 + np.exp(-(Xc @ b_cov)))
        d.loc[cur_idx, "p_over"] = 1 / (1 + np.exp(-(Xo @ b_tot)))
    # IMPORTANT: return the ORIGINAL frame plus predictions. `d` holds rescaled
    # modelling features and must never be written back over the source table.
    out = g.copy()
    out["p_home_cover"] = d["p_home_cover"].values
    out["p_over"] = d["p_over"].values
    return out


def evaluate(d: pd.DataFrame) -> dict:
    p = d[d["home_cover"].notna() & d["p_home_cover"].notna()].copy()
    out = {}
    if len(p) == 0:
        return {"available": False}

    def logloss(y, pr):
        pr = np.clip(pr, 1e-6, 1 - 1e-6)
        return float(-np.mean(y * np.log(pr) + (1 - y) * np.log(1 - pr)))

    def auc(y, pr):
        order = np.argsort(pr)
        ranks = np.empty(len(pr))
        ranks[order] = np.arange(1, len(pr) + 1)
        n1 = y.sum()
        n0 = len(y) - n1
        if n1 == 0 or n0 == 0:
            return float("nan")
        return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))

    y = p["home_cover"].values
    pr = p["p_home_cover"].values
    out["cover"] = {
        "n": int(len(p)), "seasons": [int(p["season"].min()), int(p["season"].max())],
        "logloss_model": round(logloss(y, pr), 5),
        "logloss_coinflip": round(logloss(y, np.full(len(y), 0.5)), 5),
        "brier_model": round(float(np.mean((pr - y) ** 2)), 5),
        "brier_coinflip": round(float(np.mean((0.5 - y) ** 2)), 5),
        "auc": round(auc(y, pr), 4),
        "mean_pred": round(float(pr.mean()), 4), "mean_actual": round(float(y.mean()), 4),
    }
    p2 = d[d["over"].notna() & d["p_over"].notna()]
    if len(p2):
        out["total"] = {
            "n": int(len(p2)),
            "logloss_model": round(logloss(p2["over"].values, p2["p_over"].values), 5),
            "logloss_coinflip": round(logloss(p2["over"].values, np.full(len(p2), 0.5)), 5),
            "brier_model": round(float(np.mean((p2["p_over"].values - p2["over"].values) ** 2)), 5),
            "auc": round(auc(p2["over"].values, p2["p_over"].values), 4),
            "mean_pred": round(float(p2["p_over"].mean()), 4),
            "mean_actual": round(float(p2["over"].mean()), 4),
        }
    return out


def main() -> None:
    g = pd.read_csv(DERIVED / "model_lines.csv", parse_dates=["gameday"])
    out = build(g)
    out.to_csv(DERIVED / "model_lines.csv", index=False)
    rep = evaluate(_prep(out).assign(home_cover=np.where(out["result"] > out["spread_line"], 1.0,
                                np.where(out["result"] < out["spread_line"], 0.0, np.nan)),
                          over=np.where(out["total"] > out["total_line"], 1.0,
                                np.where(out["total"] < out["total_line"], 0.0, np.nan))))
    (DERIVED / "residual_report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
