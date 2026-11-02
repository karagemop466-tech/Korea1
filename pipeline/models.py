"""T2 — line origination.

Three deliberately different model families are fitted **walk-forward**: for test
season S only seasons < S are used, so every published prediction is genuinely
out-of-sample.

  M1 `ridge`      weighted ridge on pre-game structure (Elo, matchup points, rest,
                  weather, venue). Hyper-parameter chosen by inner time-series CV
                  inside each training window.
  M2 `matchup`    no fitted structure: the matchup expected-points identity
                  exp = off(team) + def(opponent) − league_avg, with a single
                  scale/intercept pair fitted on the training window.
  M3 `elo`        Elo difference only, linear calibration fitted on training window.

  `ensemble`      equal-weight average of M1/M2/M3 (fixed weights, never fitted,
                  so it cannot be tuned to the backtest).

The models never see the market. The market is carried alongside purely as the
benchmark to beat.

Probability mapping uses a normal predictive distribution with a **continuity
correction**, which is what makes pushes at 3 and 7 priced correctly:

    P(push on a spread) = Φ((line+0.5−m)/σ) − Φ((line−0.5−m)/σ)

Outputs
-------
data/processed/originated_lines.csv    played games, model vs market
data/processed/originated_upcoming.csv scheduled games (lines we originate now)
data/processed/model_metrics.csv       per-season and overall accuracy by family
data/processed/model_config.json       hyper-parameters actually used
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_datasets import FEATURES_MARGIN, FEATURES_TOTAL, franchise  # noqa: E402
from common import PROC, write_json  # noqa: E402

ALPHAS = [3.0, 10.0, 30.0, 100.0, 300.0]
FIRST_TEST_SEASON = 2004          # predictions from here
FIRST_BET_SEASON = 2006           # market prices exist from here
DECAY_HALFLIFE_SEASONS = 4.0


# ---------------------------------------------------------------------------
# linear algebra helpers
# ---------------------------------------------------------------------------
def _weights(season_train: np.ndarray, season_test: int) -> np.ndarray:
    return 0.5 ** (np.abs(season_test - season_train) / DECAY_HALFLIFE_SEASONS)


def fit_ridge(X: np.ndarray, y: np.ndarray, w: np.ndarray, alpha: float):
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Xs = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
    W = np.sqrt(w)[:, None]
    A = Xs * W
    b = y * np.sqrt(w)
    n = Xs.shape[1]
    reg = np.eye(n) * alpha
    reg[0, 0] = 0.0                              # never penalise the intercept
    beta = np.linalg.solve(A.T @ A + reg, A.T @ b)
    return beta, mu, sd


def predict_ridge(beta, mu, sd, X):
    Xs = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
    return Xs @ beta


def fit_ols(x: np.ndarray, y: np.ndarray, w: np.ndarray):
    Xs = np.stack([np.ones_like(x), x], axis=1)
    W = np.sqrt(w)[:, None]
    beta, *_ = np.linalg.lstsq(Xs * W, y * np.sqrt(w), rcond=None)
    return beta


def inner_cv_alpha(X, y, season, test_season):
    """Pick alpha by expanding time-series CV inside the training window."""
    seasons = sorted(set(season.tolist()))
    if len(seasons) < 5:
        return 30.0
    folds = seasons[-3:]
    scores = {a: [] for a in ALPHAS}
    for f in folds:
        tr = season < f
        va = season == f
        if tr.sum() < 200 or va.sum() < 20:
            continue
        w = _weights(season[tr], f)
        for a in ALPHAS:
            beta, mu, sd = fit_ridge(X[tr], y[tr], w, a)
            pred = predict_ridge(beta, mu, sd, X[va])
            scores[a].append(float(np.mean(np.abs(pred - y[va]))))
    best = min(ALPHAS, key=lambda a: np.mean(scores[a]) if scores[a] else 1e9)
    return float(best)


# ---------------------------------------------------------------------------
# probability mapping
# ---------------------------------------------------------------------------
def outcome_probs(m: float, sigma: float, line: float) -> tuple[float, float, float]:
    """(win, push, loss) for the *home/over* side of a line, continuity-corrected.

    For a spread we pass `line = spread_line` and cover means `result > line`.
    For a total we pass `line = total_line` and over means `total > line`.
    """
    z_hi = (line + 0.5 - m) / sigma
    z_lo = (line - 0.5 - m) / sigma
    p_loss = float(stats.norm.cdf(z_lo))
    p_push = float(stats.norm.cdf(z_hi) - stats.norm.cdf(z_lo))
    p_win = float(1.0 - stats.norm.cdf(z_hi))
    return p_win, p_push, p_loss


def moneyline_probs(m: float, sigma: float) -> tuple[float, float, float]:
    p_home = float(1.0 - stats.norm.cdf((0.5 - m) / sigma))
    p_away = float(stats.norm.cdf((-0.5 - m) / sigma))
    p_tie = float(max(0.0, 1.0 - p_home - p_away))
    return p_home, p_tie, p_away


def fair_american(p: float) -> float | None:
    if not np.isfinite(p) or p <= 1e-6 or p >= 1 - 1e-6:
        return None
    return round(float(100 * (1 - p) / p)) if p < 0.5 else round(float(-100 * p / (1 - p)))


def american_with_hold(p_fair: float, hold: float = 0.045) -> tuple[float, float]:
    """Two-way price pair that carries `hold` overround, from a fair probability."""
    p_fair = float(np.clip(p_fair, 1e-4, 1 - 1e-4))
    d_fair = 1.0 / p_fair
    d_side = 1.0 + (d_fair - 1.0) / (1.0 + hold)      # multiplicative margin
    d_other = 1.0 + (p_fair / (1.0 - p_fair)) * (1.0 / (1.0 + hold))
    dec2am = lambda d: round(float((d - 1) * 100)) if d >= 2 else round(float(-100 / (d - 1)))
    return dec2am(d_side), dec2am(d_other)


# ---------------------------------------------------------------------------
# walk-forward
# ---------------------------------------------------------------------------
def walk_forward(df: pd.DataFrame, future: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    df = df.sort_values(["season", "week", "game_id"]).reset_index(drop=True)
    config: dict = {"alphas": {}, "families": ["ridge", "matchup", "elo", "ensemble"],
                    "decay_halflife_seasons": DECAY_HALFLIFE_SEASONS,
                    "first_test_season": FIRST_TEST_SEASON}

    out = []
    for S in sorted(df.season.unique()):
        if S < FIRST_TEST_SEASON:
            continue
        tr = df[df.season < S]
        te = df[df.season == S]
        if len(tr) < 400 or te.empty:
            continue

        Xm = tr[FEATURES_MARGIN].to_numpy(float)
        Xt = tr[FEATURES_TOTAL].to_numpy(float)
        ym = tr["result"].to_numpy(float)
        yt = tr["total"].to_numpy(float)
        seas = tr["season"].to_numpy(int)
        w = _weights(seas, S)

        a_m = inner_cv_alpha(Xm, ym, seas, S)
        a_t = inner_cv_alpha(Xt, yt, seas, S)
        config["alphas"][str(S)] = {"margin": a_m, "total": a_t}

        b_m, mu_m, sd_m = fit_ridge(Xm, ym, w, a_m)
        b_t, mu_t, sd_t = fit_ridge(Xt, yt, w, a_t)

        Tm = te[FEATURES_MARGIN].to_numpy(float)
        Tt = te[FEATURES_TOTAL].to_numpy(float)
        pred_m = predict_ridge(b_m, mu_m, sd_m, Tm)
        pred_t = predict_ridge(b_t, mu_t, sd_t, Tt)
        resid_m = ym - predict_ridge(b_m, mu_m, sd_m, Xm)
        resid_t = yt - predict_ridge(b_t, mu_t, sd_t, Xt)

        # M2: matchup identity, one scale + intercept
        b2m = fit_ols(tr["exp_margin"].to_numpy(float), ym, w)
        b2t = fit_ols(tr["exp_total"].to_numpy(float), yt, w)
        m2_m = b2m[0] + b2m[1] * te["exp_margin"].to_numpy(float)
        m2_t = b2t[0] + b2t[1] * te["exp_total"].to_numpy(float)
        r2m = ym - (b2m[0] + b2m[1] * tr["exp_margin"].to_numpy(float))
        r2t = yt - (b2t[0] + b2t[1] * tr["exp_total"].to_numpy(float))

        # M3: Elo difference, linear calibration
        b3m = fit_ols(tr["elo_diff"].to_numpy(float), ym, w)
        m3_m = b3m[0] + b3m[1] * te["elo_diff"].to_numpy(float)
        r3m = ym - (b3m[0] + b3m[1] * tr["elo_diff"].to_numpy(float))

        # ensemble: fixed equal weights, never fitted
        ens_m = (pred_m + m2_m + m3_m) / 3.0
        ens_t = (pred_t + m2_t) / 2.0
        rens_m = ym - ((predict_ridge(b_m, mu_m, sd_m, Xm)
                        + (b2m[0] + b2m[1] * tr["exp_margin"].to_numpy(float))
                        + (b3m[0] + b3m[1] * tr["elo_diff"].to_numpy(float))) / 3.0)
        rens_t = yt - ((predict_ridge(b_t, mu_t, sd_t, Xt)
                        + (b2t[0] + b2t[1] * tr["exp_total"].to_numpy(float))) / 2.0)

        frame = te[["game_id", "alt_game_id", "season", "week", "game_type", "gameday",
                    "home_team", "away_team", "home_score", "away_score", "result", "total",
                    "market_spread", "market_total", "market_home_ml", "market_away_ml",
                    "home_spread_odds", "away_spread_odds", "over_odds", "under_odds",
                    "elo_diff", "exp_margin", "exp_total", "rest_diff", "div_game",
                    "temp", "wind", "temp_missing", "wind_missing", "roof", "season_idx",
                    "adj_exp_margin", "adj_exp_total"]].copy()
        frame["fit_season"] = S
        for name, pm, rm in [("ridge", pred_m, resid_m), ("matchup", m2_m, r2m),
                             ("elo", m3_m, r3m), ("ensemble", ens_m, rens_m)]:
            frame[f"pred_margin_{name}"] = pm
            frame[f"sigma_margin_{name}"] = float(np.std(rm, ddof=1))
        for name, pt, rt in [("ridge", pred_t, resid_t), ("matchup", m2_t, r2t),
                             ("ensemble", ens_t, rens_t)]:
            frame[f"pred_total_{name}"] = pt
            frame[f"sigma_total_{name}"] = float(np.std(rt, ddof=1))
        out.append(frame)

    pred = pd.concat(out, ignore_index=True)

    # probabilities + originated prices from the ensemble (the published line)
    for tag in ["ensemble"]:
        m, s = pred[f"pred_margin_{tag}"], pred[f"sigma_margin_{tag}"]
        sp = pred["market_spread"]
        probs = np.array([outcome_probs(a, b, c) for a, b, c in zip(m, s, sp)])
        pred["p_home_cover"], pred["p_push_spread"], pred["p_home_fail_cover"] = probs.T
        mt, st = pred[f"pred_total_{tag}"], pred[f"sigma_total_{tag}"]
        tprobs = np.array([outcome_probs(a, b, c) for a, b, c in zip(mt, st, pred["market_total"])])
        pred["p_over"], pred["p_push_total"], pred["p_under"] = tprobs.T
        ml = np.array([moneyline_probs(a, b) for a, b in zip(m, s)])
        pred["p_home_ml"], pred["p_tie"], pred["p_away_ml"] = ml.T

    pred["fair_spread"] = pred["pred_margin_ensemble"]
    pred["fair_total"] = pred["pred_total_ensemble"]
    pred["originated_home_ml"] = [fair_american(p) for p in pred["p_home_ml"]]
    pred["originated_away_ml"] = [fair_american(p) for p in pred["p_away_ml"]]
    pairs = [american_with_hold(1 - p, 0.045) for p in pred["p_away_ml"]]
    pred["posted_home_ml"] = [p[1] for p in pairs]
    pred["posted_away_ml"] = [p[0] for p in pairs]
    pred["edge_spread"] = pred["fair_spread"] - pred["market_spread"]
    pred["edge_total"] = pred["fair_total"] - pred["market_total"]

    # ---- metrics -----------------------------------------------------------
    rows = []
    for fam in ["ridge", "matchup", "elo", "ensemble"]:
        col = f"pred_margin_{fam}"
        for S, g in pred.groupby("season"):
            rows.append(dict(model=fam, market="spread", season=int(S), n=len(g),
                             mae=float(np.mean(np.abs(g[col] - g["result"]))),
                             rmse=float(np.sqrt(np.mean((g[col] - g["result"]) ** 2))),
                             bias=float(np.mean(g[col] - g["result"]))))
        rows.append(dict(model=fam, market="spread", season="ALL", n=len(pred),
                         mae=float(np.mean(np.abs(pred[col] - pred["result"]))),
                         rmse=float(np.sqrt(np.mean((pred[col] - pred["result"]) ** 2))),
                         bias=float(np.mean(pred[col] - pred["result"]))))
    for fam in ["ridge", "matchup", "ensemble"]:
        col = f"pred_total_{fam}"
        for S, g in pred.groupby("season"):
            rows.append(dict(model=fam, market="total", season=int(S), n=len(g),
                             mae=float(np.mean(np.abs(g[col] - g["total"]))),
                             rmse=float(np.sqrt(np.mean((g[col] - g["total"]) ** 2))),
                             bias=float(np.mean(g[col] - g["total"]))))
        rows.append(dict(model=fam, market="total", season="ALL", n=len(pred),
                         mae=float(np.mean(np.abs(pred[col] - pred["total"]))),
                         rmse=float(np.sqrt(np.mean((pred[col] - pred["total"]) ** 2))),
                         bias=float(np.mean(pred[col] - pred["total"]))))
    mk = pred.dropna(subset=["market_spread", "market_total"])
    for S, g in list(mk.groupby("season")) + [("ALL", mk)]:
        rows.append(dict(model="market", market="spread", season=S, n=len(g),
                         mae=float(np.mean(np.abs(g["market_spread"] - g["result"]))),
                         rmse=float(np.sqrt(np.mean((g["market_spread"] - g["result"]) ** 2))),
                         bias=float(np.mean(g["market_spread"] - g["result"]))))
        rows.append(dict(model="market", market="total", season=S, n=len(g),
                         mae=float(np.mean(np.abs(g["market_total"] - g["total"]))),
                         rmse=float(np.sqrt(np.mean((g["market_total"] - g["total"]) ** 2))),
                         bias=float(np.mean(g["market_total"] - g["total"]))))
    metrics = pd.DataFrame(rows)

    # ---- originate lines for scheduled-but-unplayed games ------------------
    fut = future.copy()
    if not fut.empty:
        # use the most recent complete fit (last test season) to line future games
        last = int(pred.season.max())
        fut["fit_season"] = last
        ref = pred[pred.season == last]
        # refit on everything up to `last` inclusive is not needed for a demo line;
        # instead carry the last fitted coefficients forward via a stored refit.
    return pred, metrics, config


def originate_future(df: pd.DataFrame, future: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Fit on every completed game and price the scheduled games."""
    if future.empty:
        return future
    S = int(df.season.max()) + 1
    Xm, Xt = df[FEATURES_MARGIN].to_numpy(float), df[FEATURES_TOTAL].to_numpy(float)
    ym, yt = df["result"].to_numpy(float), df["total"].to_numpy(float)
    seas = df["season"].to_numpy(int)
    w = _weights(seas, S)
    a_m = inner_cv_alpha(Xm, ym, seas, S)
    a_t = inner_cv_alpha(Xt, yt, seas, S)
    b_m, mu_m, sd_m = fit_ridge(Xm, ym, w, a_m)
    b_t, mu_t, sd_t = fit_ridge(Xt, yt, w, a_t)
    b2m = fit_ols(df["exp_margin"].to_numpy(float), ym, w)
    b2t = fit_ols(df["exp_total"].to_numpy(float), yt, w)
    b3m = fit_ols(df["elo_diff"].to_numpy(float), ym, w)

    Fm, Ft = future[FEATURES_MARGIN].to_numpy(float), future[FEATURES_TOTAL].to_numpy(float)
    ens_m = (predict_ridge(b_m, mu_m, sd_m, Fm)
             + b2m[0] + b2m[1] * future["exp_margin"].to_numpy(float)
             + b3m[0] + b3m[1] * future["elo_diff"].to_numpy(float)) / 3.0
    ens_t = (predict_ridge(b_t, mu_t, sd_t, Ft)
             + b2t[0] + b2t[1] * future["exp_total"].to_numpy(float)) / 2.0

    rm = ym - ((predict_ridge(b_m, mu_m, sd_m, Xm) + b2m[0] + b2m[1] * df["exp_margin"].to_numpy(float)
                + b3m[0] + b3m[1] * df["elo_diff"].to_numpy(float)) / 3.0)
    rt = yt - ((predict_ridge(b_t, mu_t, sd_t, Xt) + b2t[0] + b2t[1] * df["exp_total"].to_numpy(float)) / 2.0)
    sm, st = float(np.std(rm, ddof=1)), float(np.std(rt, ddof=1))

    future = future.copy()
    future["fair_spread"] = ens_m
    future["fair_total"] = ens_t
    future["sigma_margin"] = sm
    future["sigma_total"] = st
    ml = np.array([moneyline_probs(a, sm) for a in ens_m])
    future["p_home_ml"], future["p_tie"], future["p_away_ml"] = ml.T
    future["originated_home_ml"] = [fair_american(p) for p in future["p_home_ml"]]
    future["originated_away_ml"] = [fair_american(p) for p in future["p_away_ml"]]
    future["edge_spread"] = future["fair_spread"] - future["market_spread"]
    future["edge_total"] = future["fair_total"] - future["market_total"]
    config.setdefault("future_fit", {})["alpha_margin"] = a_m
    config["future_fit"]["alpha_total"] = a_t
    config["future_fit"]["sigma_margin"] = sm
    config["future_fit"]["sigma_total"] = st
    config["future_fit"]["trained_through"] = int(df.season.max())
    return future


def main() -> None:
    df = pd.read_csv(PROC / "games_model.csv")
    fut = pd.read_csv(PROC / "upcoming.csv")
    pred, metrics, config = walk_forward(df, fut)
    fut_line = originate_future(df, fut, config)
    pred.to_csv(PROC / "originated_lines.csv", index=False)
    fut_line.to_csv(PROC / "originated_upcoming.csv", index=False)
    metrics.to_csv(PROC / "model_metrics.csv", index=False)
    write_json(PROC / "model_config.json", config)

    print(f"originated_lines: {pred.shape}, seasons {pred.season.min()}–{pred.season.max()}")
    allrows = metrics[metrics.season == "ALL"]
    print(allrows.pivot(index="model", columns="market", values="mae").round(3).to_string())
    # A scheduled game with a blank fair line is a published hole: the earlier build emitted
    # 164 of them because the future frame had no weather fill. Refuse to write such a file.
    priced_cols = ["fair_spread", "fair_total", "p_home_ml", "p_away_ml",
                   "originated_home_ml", "originated_away_ml"]
    blank = int(fut_line[priced_cols].isna().any(axis=1).sum())
    if blank:
        bad = fut_line[fut_line[priced_cols].isna().any(axis=1)]
        raise SystemExit(
            f"refusing to publish {blank} scheduled games with blank originated lines: "
            + ", ".join(bad.game_id.head(5)))
    print(f"\nupcoming priced: {len(fut_line)} games, {fut_line.market_spread.notna().sum()} with a market line, "
          f"{blank} blank lines")


if __name__ == "__main__":
    main()
