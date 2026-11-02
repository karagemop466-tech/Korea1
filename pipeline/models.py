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

Probability mapping uses prior-season out-of-fold empirical residuals. This
retains discrete NFL scoring mass without claiming a normal approximation prices
key numbers correctly. All probabilities remain unverified model estimates.

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
from common import PROC, write_json, novig_probs  # noqa: E402

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
    """Theoretical two-way prices with multiplicative overround (not hold %).

    This is a model quote, NOT an observed or executable sportsbook price.
    American prices between -100 and +100 are invalid and are never emitted.
    """
    if not np.isfinite(p_fair) or not 0 < p_fair < 1:
        return (float("nan"), float("nan"))
    if not 0 <= hold < 1:
        raise ValueError("invalid overround")
    d_side = 1.0 / (p_fair * (1.0 + hold))
    d_other = 1.0 / ((1.0 - p_fair) * (1.0 + hold))
    if min(d_side, d_other) <= 1:
        return (float("nan"), float("nan"))
    def dec2am(d):
        return int(np.floor((d - 1) * 100)) if d >= 2 else int(np.ceil(-100 / (d - 1)))
    return dec2am(d_side), dec2am(d_other)


def empirical_probs(mean: float, residuals: np.ndarray, line: float) -> tuple[float, float, float]:
    """Prior out-of-fold errors shifted to an integer-score predictive lattice.

    Round the shifted empirical draws to the nearest point, then count the mass
    above/on/below the offered line. This retains discrete scoring mass without
    pretending continuous residuals land exactly on a push. Half-point lines
    have no push mass. This remains an unverified model estimate.
    """
    if not np.isfinite(line):
        return (float("nan"),) * 3
    errors = np.asarray(residuals, float)
    errors = errors[np.isfinite(errors)]
    if not len(errors):
        return (float("nan"),) * 3
    draws = np.rint(mean + errors)
    return (float(np.mean(draws > line)), float(np.mean(draws == line)),
            float(np.mean(draws < line)))


def prior_oof_residuals(tr: pd.DataFrame, target: str) -> np.ndarray:
    """Ensemble errors from three expanding historical folds, never test outcomes."""
    target_col = "result" if target == "margin" else "total"
    feature_cols = FEATURES_MARGIN if target == "margin" else FEATURES_TOTAL
    exp_col = "exp_margin" if target == "margin" else "exp_total"
    seasons = sorted(tr.season.unique())[-3:]
    errors = []
    for season in seasons:
        fit, valid = tr[tr.season < season], tr[tr.season == season]
        if len(fit) < 400 or len(valid) < 20:
            continue
        X, y = fit[feature_cols].to_numpy(float), fit[target_col].to_numpy(float)
        v = valid[feature_cols].to_numpy(float)
        w = _weights(fit.season.to_numpy(int), int(season))
        alpha = inner_cv_alpha(X, y, fit.season.to_numpy(int), int(season))
        beta, mu, sd = fit_ridge(X, y, w, alpha)
        b2 = fit_ols(fit[exp_col].to_numpy(float), y, w)
        p = predict_ridge(beta, mu, sd, v) + b2[0] + b2[1] * valid[exp_col].to_numpy(float)
        if target == "margin":
            b3 = fit_ols(fit.elo_diff.to_numpy(float), y, w)
            p = (2 * p + b3[0] + b3[1] * valid.elo_diff.to_numpy(float)) / 3
        else:
            p /= 2
        errors.extend(valid[target_col].to_numpy(float) - p)
    if len(errors) < 200:
        raise ValueError("insufficient out-of-fold history for predictive distribution")
    return np.asarray(errors)


# ---------------------------------------------------------------------------
# walk-forward
# ---------------------------------------------------------------------------
def walk_forward(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
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
        # Use historical out-of-fold errors, not optimistic in-sample residuals.
        oof_m, oof_t = prior_oof_residuals(tr, "margin"), prior_oof_residuals(tr, "total")
        config.setdefault("predictive_errors", {})[str(S)] = {
            "method": "expanding three-season out-of-fold ensemble residuals",
            "n_margin": len(oof_m), "n_total": len(oof_t)}

        frame = te[["game_id", "alt_game_id", "season", "week", "game_type", "gameday",
                    "home_team", "away_team", "gametime", "home_score", "away_score", "result", "total",
                    "market_spread", "market_total", "market_home_ml", "market_away_ml",
                    "home_spread_odds", "away_spread_odds", "over_odds", "under_odds",
                    "elo_diff", "exp_margin", "exp_total", "rest_diff", "div_game",
                    "temp", "wind", "temp_missing", "wind_missing", "roof", "season_idx",
                    "adj_exp_margin", "adj_exp_total"]].copy()
        frame["fit_season"] = S
        for name, pm, rm in [("ridge", pred_m, resid_m), ("matchup", m2_m, r2m),
                             ("elo", m3_m, r3m), ("ensemble", ens_m, rens_m)]:
            frame[f"pred_margin_{name}"] = pm
            frame[f"sigma_margin_{name}"] = float(np.std(oof_m if name == "ensemble" else rm, ddof=1))
        for name, pt, rt in [("ridge", pred_t, resid_t), ("matchup", m2_t, r2t),
                             ("ensemble", ens_t, rens_t)]:
            frame[f"pred_total_{name}"] = pt
            frame[f"sigma_total_{name}"] = float(np.std(oof_t if name == "ensemble" else rt, ddof=1))
        out.append(frame)

    pred = pd.concat(out, ignore_index=True)

    # probabilities + originated prices from the ensemble (the published line)
    for tag in ["ensemble"]:
        m, s = pred[f"pred_margin_{tag}"], pred[f"sigma_margin_{tag}"]
        sp = pred["market_spread"]
        oof_by_season = {int(S): prior_oof_residuals(df[df.season < S], "margin")
                         for S in pred.season.unique()}
        probs = np.array([empirical_probs(a, oof_by_season[int(S)], c)
                          for a, c, S in zip(m, sp, pred.season)])
        pred["p_home_cover"], pred["p_push_spread"], pred["p_home_fail_cover"] = probs.T
        mt, st = pred[f"pred_total_{tag}"], pred[f"sigma_total_{tag}"]
        oof_t_by_season = {int(S): prior_oof_residuals(df[df.season < S], "total")
                           for S in pred.season.unique()}
        tprobs = np.array([empirical_probs(a, oof_t_by_season[int(S)], c)
                           for a, c, S in zip(mt, pred["market_total"], pred.season)])
        pred["p_over"], pred["p_push_total"], pred["p_under"] = tprobs.T
        ml = np.array([empirical_probs(a, oof_by_season[int(S)], 0.0)
                       for a, S in zip(m, pred.season)])
        # empirical_probs returns >, ==, < in that order: home win, tie, away win.
        pred["p_home_ml"], pred["p_tie"], pred["p_away_ml"] = ml.T

    pred["fair_spread"] = pred["pred_margin_ensemble"]
    pred["fair_total"] = pred["pred_total_ensemble"]
    pred["originated_home_ml"] = [fair_american(p) for p in pred["p_home_ml"] / (pred["p_home_ml"] + pred["p_away_ml"])]
    pred["originated_away_ml"] = [fair_american(p) for p in pred["p_away_ml"] / (pred["p_home_ml"] + pred["p_away_ml"])]
    pairs = [american_with_hold(h / (h + a), 0.045) for h, a in zip(pred["p_home_ml"], pred["p_away_ml"])]
    pred["posted_home_ml"] = [p[1] for p in pairs]
    pred["posted_away_ml"] = [p[0] for p in pairs]
    pred["edge_spread"] = pred["fair_spread"] - pred["market_spread"]
    pred["edge_total"] = pred["fair_total"] - pred["market_total"]

    # ---- metrics: each model compared with market on identical available rows ----
    rows = []
    for market, target, families in [
        ("spread", "result", ["ridge", "matchup", "elo", "ensemble"]),
        ("total", "total", ["ridge", "matchup", "ensemble"]),
    ]:
        line_col = "market_spread" if market == "spread" else "market_total"
        available = pred[pred[line_col].notna()].copy()
        for fam in families + ["market"]:
            col = line_col if fam == "market" else f"pred_{'margin' if market == 'spread' else 'total'}_{fam}"
            for S, g in list(available.groupby("season")) + [("ALL", available)]:
                err, market_err = g[col] - g[target], g[line_col] - g[target]
                rows.append(dict(model=fam, market=market, season=S, n=len(g),
                                 mae=float(err.abs().mean()), rmse=float(np.sqrt(np.mean(err ** 2))),
                                 bias=float(err.mean()), paired_n=len(g),
                                 market_mae=float(market_err.abs().mean()),
                                 mae_gap=float(err.abs().mean() - market_err.abs().mean())))
    ml = pred.dropna(subset=["market_home_ml", "market_away_ml"]).copy()
    for fam in ["ensemble", "market"]:
        if ml.empty:
            rows.append(dict(model=fam, market="moneyline", season="ALL", n=0,
                             brier=float("nan"), log_loss=float("nan"), paired_n=0))
            continue
        if fam == "market":
            hp, ap = zip(*[novig_probs(h, a) for h, a in zip(ml.market_home_ml, ml.market_away_ml)])
            hp = np.asarray(hp)
        else:
            hp = ml.p_home_ml / (ml.p_home_ml + ml.p_away_ml)
        y = np.where(ml.result > 0, 1.0, np.where(ml.result < 0, 0.0, 0.5))
        for S, idx in list(ml.groupby("season").groups.items()) + [("ALL", ml.index)]:
            p, yy = np.asarray(hp)[ml.index.get_indexer(idx)], np.asarray(y)[ml.index.get_indexer(idx)]
            rows.append(dict(model=fam, market="moneyline", season=S, n=len(idx),
                             brier=float(np.mean((p - yy) ** 2)),
                             log_loss=float(-np.mean(yy * np.log(np.clip(p, 1e-9, 1)) +
                                                     (1-yy) * np.log(np.clip(1-p, 1e-9, 1)))),
                             paired_n=len(idx)))
    metrics = pd.DataFrame(rows)

    # Future lines are fitted separately by originate_future().
    return pred, metrics, config


def originate_future(df: pd.DataFrame, future: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Fit on every completed game and price the scheduled games."""
    if future.empty:
        return future
    # Future games can belong to the current partially completed season.
    S = int(future.season.max())
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
    oof_m, oof_t = prior_oof_residuals(df, "margin"), prior_oof_residuals(df, "total")
    sm, st = float(np.std(oof_m, ddof=1)), float(np.std(oof_t, ddof=1))

    future = future.copy()
    future["fair_spread"] = ens_m
    future["fair_total"] = ens_t
    future["sigma_margin"] = sm
    future["sigma_total"] = st
    ml = np.array([empirical_probs(a, oof_m, 0.0) for a in ens_m])
    future["p_home_ml"], future["p_tie"], future["p_away_ml"] = ml.T
    future["originated_home_ml"] = [fair_american(h / (h+a)) for h, a in zip(future.p_home_ml, future.p_away_ml)]
    future["originated_away_ml"] = [fair_american(a / (h+a)) for h, a in zip(future.p_home_ml, future.p_away_ml)]
    sp = np.array([empirical_probs(m, oof_m, line) for m, line in zip(ens_m, future.market_spread)])
    future["p_home_cover"], future["p_push_spread"], future["p_home_fail_cover"] = sp.T
    tp = np.array([empirical_probs(m, oof_t, line) for m, line in zip(ens_t, future.market_total)])
    future["p_over"], future["p_push_total"], future["p_under"] = tp.T
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
    pred, metrics, config = walk_forward(df)
    fut_line = originate_future(df, fut, config)
    pred.to_csv(PROC / "originated_lines.csv", index=False)
    fut_line.to_csv(PROC / "originated_upcoming.csv", index=False)
    metrics.to_csv(PROC / "model_metrics.csv", index=False)
    write_json(PROC / "model_config.json", config)

    print(f"originated_lines: {pred.shape}, seasons {pred.season.min()}–{pred.season.max()}")
    allrows = metrics[metrics.season == "ALL"]
    print(allrows.pivot(index="model", columns="market", values="mae").round(3).to_string())
    print(f"\nupcoming priced: {len(fut_line)} games, {fut_line.market_spread.notna().sum()} with a market line")


if __name__ == "__main__":
    main()
