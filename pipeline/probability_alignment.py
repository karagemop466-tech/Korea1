"""Check that the model's probabilities line up with the bets that were taken.

The leaderboard publishes an expected return for every strategy. That number is
computed from the model's own probability for the side and the line that was
bet. Two things have to be true before the number means anything:

  1. **Alignment.** The probability must be the one that belongs to the bet:
     the same side, and the same line the bet was actually taken at. A
     probability computed at a different line or for the other side is not a
     slower number, it is a different number.

  2. **Calibration.** The probability must mean what it says. A model that
     claims a 55% chance where the outcome happens 51% of the time produces an
     expected return that is an artefact of its own over-confidence.

This module checks both, and produces a *calibrated* probability for every
game, market and side so that the expected return can be computed against a
number that survives its own calibration test.

The calibration is walk-forward: the mapping is fitted only on games from
earlier seasons and applied to the season in hand, so no game is calibrated
with knowledge of a later result.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, SITE_DATA  # noqa: E402

LINES = PROC / "originated_lines.csv"
BETS = PROC / "strategy_bets.csv"
INT = ROOT / "data" / "integration"

RIDGE = 1.0        # L2 pull of the calibration towards the identity mapping
MIN_TRAIN = 200    # observations required before a season's mapping is fitted
EPS = 1e-4         # probability clipping for the logit transform

# market, side, model probability column, push probability column,
# the market price pair used for the de-vigged benchmark, and the outcome rule
GROUPS = [
    ("SPREAD", "home", "p_home_cover", "p_push_spread",
     ("home_spread_odds", "away_spread_odds"), "cover_home"),
    ("SPREAD", "away", "p_home_fail_cover", "p_push_spread",
     ("home_spread_odds", "away_spread_odds"), "cover_away"),
    ("TOTAL", "over", "p_over", "p_push_total",
     ("over_odds", "under_odds"), "over"),
    ("TOTAL", "under", "p_under", "p_push_total",
     ("over_odds", "under_odds"), "under"),
    ("MONEYLINE", "home", "p_home_ml", "p_tie",
     ("market_home_ml", "market_away_ml"), "win_home"),
    ("MONEYLINE", "away", "p_away_ml", "p_tie",
     ("market_home_ml", "market_away_ml"), "win_away"),
]


# ---------------------------------------------------------------------------
# probability helpers
# ---------------------------------------------------------------------------
def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, float), EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(z, float)))


def de_vig(home_odds: np.ndarray, away_odds: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The market's two-way probability, with the hold removed."""
    h = np.asarray(home_odds, float)
    a = np.asarray(away_odds, float)
    # A price of zero is a missing price, not a price; it produces no probability.
    good = (np.isfinite(h) & np.isfinite(a) & (h != 0) & (a != 0)
            & (np.abs(h) != 100) & (np.abs(a) != 100))
    hs = np.where(good, h, -110.0)
    as_ = np.where(good, a, -110.0)
    hp = np.where(hs < 0, (-hs) / (-hs + 100.0), 100.0 / (hs + 100.0))
    ap = np.where(as_ < 0, (-as_) / (-as_ + 100.0), 100.0 / (as_ + 100.0))
    tot = hp + ap
    with np.errstate(invalid="ignore", divide="ignore"):
        p_home, p_away = hp / tot, ap / tot
    return np.where(good, p_home, np.nan), np.where(good, p_away, np.nan)


def fit_logistic(X: np.ndarray, y: np.ndarray, ridge: float = RIDGE,
                 prior: tuple[float, ...] | None = None) -> np.ndarray:
    """Ridge-penalised logistic fit of `q = sigmoid(X·theta)` on the outcome.

    The penalty pulls the coefficients towards `prior`, so a model with little
    data stays close to the identity mapping rather than learning a wild
    correction from a handful of games.
    """
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    if prior is None:
        prior = tuple([0.0] * X.shape[1])
    prior = np.asarray(prior, float)
    if len(y) < MIN_TRAIN or len(np.unique(y)) < 2:
        return np.concatenate([[0.0], prior])

    # An intercept column is added here; the prior's first entry is the prior
    # intercept, which is zero.
    X = np.column_stack([np.ones(len(X)), X])
    full_prior = np.concatenate([[0.0], prior])

    def objective(theta):
        q = np.clip(_sigmoid(X @ theta), EPS, 1.0 - EPS)
        nll = -np.sum(y * np.log(q) + (1.0 - y) * np.log(1.0 - q))
        diff = theta - full_prior
        penalty = ridge * float(np.sum(diff * diff))
        resid = q - y
        grad = X.T @ resid + 2.0 * ridge * diff
        return (nll + penalty) / len(y), grad / len(y)

    res = minimize(objective, full_prior.copy(), jac=True, method="L-BFGS-B",
                   options={"maxiter": 500})
    if not np.all(np.isfinite(res.x)):
        return full_prior
    return res.x


def fit_platt(p: np.ndarray, y: np.ndarray, ridge: float = RIDGE) -> tuple[float, float]:
    """Fit `logit(q) = a + b·logit(p)` on (p, y), pulled towards the identity."""
    p = np.asarray(p, float)
    y = np.asarray(y, float)
    keep = np.isfinite(p) & np.isfinite(y) & (p > 0) & (p < 1)
    p, y = p[keep], y[keep]
    if len(p) < MIN_TRAIN or len(np.unique(y)) < 2:
        return 0.0, 1.0
    z = _logit(p)[:, None]
    theta = fit_logistic(z, y, ridge, prior=(1.0,))
    return float(theta[0]), float(theta[1])


# ---------------------------------------------------------------------------
# the per-game selection table
# ---------------------------------------------------------------------------
def outcome_mask(df: pd.DataFrame, rule: str) -> tuple[np.ndarray, np.ndarray]:
    """(win, push) for the selected side of each game."""
    margin = (df["home_score"].astype(float) - df["away_score"].astype(float)).to_numpy()
    total = (df["home_score"].astype(float) + df["away_score"].astype(float)).to_numpy()
    line = df["market_spread"].astype(float).to_numpy()
    tline = df["market_total"].astype(float).to_numpy()
    if rule == "cover_home":
        win, push = margin > line, margin == line
    elif rule == "cover_away":
        win, push = margin < line, margin == line
    elif rule == "over":
        win, push = total > tline, total == tline
    elif rule == "under":
        win, push = total < tline, total == tline
    elif rule == "win_home":
        win, push = margin > 0, margin == 0
    else:
        win, push = margin < 0, margin == 0
    return win, push


def build_selection_table(lines: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, market, side) with the model's, the market's and the
    realised probability of the selection winning."""
    rows = []
    for market, side, pcol, pushcol, (od_a, od_b), rule in GROUPS:
        d = lines.copy()
        win, push = outcome_mask(d, rule)
        p_model = d[pcol].astype(float).to_numpy()
        p_push = d[pushcol].astype(float).to_numpy()
        pa, pb = de_vig(d[od_a].to_numpy(float), d[od_b].to_numpy(float))
        p_market = pa if side in ("home", "over") else pb
        rows.append(pd.DataFrame(dict(
            game_id=d["game_id"], season=d["season"].astype(int),
            week=d["week"].astype(int), gameday=d["gameday"],
            market=market, side=side,
            p_model=p_model, p_push=p_push,
            p_market=p_market,
            outcome_win=win.astype(float), outcome_push=push.astype(float),
            model_line=(d["market_spread"].astype(float) if market == "SPREAD"
                        else d["market_total"].astype(float) if market == "TOTAL" else np.nan),
            market_line=(d["market_spread"].astype(float) if market == "SPREAD"
                         else d["market_total"].astype(float) if market == "TOTAL" else np.nan),
            home_odds=d[od_a].astype(float), away_odds=d[od_b].astype(float),
        )))
    return pd.concat(rows, ignore_index=True)


def calibrate(sel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Walk-forward calibration of the model's win probability, per group.

    Two mappings are fitted on each season's training data:

      * the model's own probability alone, and
      * the model's probability together with the market's de-vigged probability.

    The second mapping is used wherever the market price is on record. The
    market's price is the sharpest published estimate of the true probability,
    and the model's error on longshots is far larger than its average error, so
    a calibration that can see the price corrects the favourite-longshot bias
    that a calibration on the model's probability alone cannot see.

    Nothing is fitted on the season it is applied to.
    """
    out, params = [], []
    for (market, side), g in sel.groupby(["market", "side"]):
        g = g.sort_values(["season", "week", "game_id"]).reset_index(drop=True)
        theta1 = np.array([0.0, 1.0])          # intercept, slope on the model
        theta2 = np.array([0.0, 1.0, 0.0])    # intercept, model slope, market slope
        cal = np.full(len(g), np.nan)
        p_model = g["p_model"].to_numpy(float)
        p_market = g["p_market"].to_numpy(float)
        y_all = g["outcome_win"].to_numpy(float)
        push_all = g["outcome_push"].to_numpy(float)
        for season in sorted(g["season"].unique()):
            test_idx = np.where(g["season"].to_numpy() == season)[0]
            prior_mask = (g["season"].to_numpy() < season) & (push_all == 0)
            n_train = int(prior_mask.sum())
            if n_train >= MIN_TRAIN:
                z1 = _logit(p_model[prior_mask])[:, None]
                theta1 = fit_logistic(z1, y_all[prior_mask], RIDGE, prior=(1.0,))
                has_market = np.isfinite(p_market[prior_mask]) & (p_market[prior_mask] > 0)                     & (p_market[prior_mask] < 1)
                if has_market.sum() >= MIN_TRAIN:
                    z2 = np.column_stack([_logit(p_model[prior_mask][has_market]),
                                          _logit(p_market[prior_mask][has_market])])
                    theta2 = fit_logistic(z2, y_all[prior_mask][has_market], RIDGE,
                                          prior=(1.0, 0.0))
            params.append(dict(market=market, side=side, season=int(season),
                               n_train=n_train,
                               calib_a=round(float(theta1[0]), 6),
                               calib_b=round(float(theta1[1]), 6),
                               calib_a_market=round(float(theta2[0]), 6),
                               calib_b_market=round(float(theta2[1]), 6),
                               calib_c_market=round(float(theta2[2]), 6),
                               fitted=bool(n_train >= MIN_TRAIN)))
            z = _logit(p_model[test_idx])
            pred = np.empty(len(test_idx))
            for j, idx in enumerate(test_idx):
                if np.isfinite(p_market[idx]) and 0 < p_market[idx] < 1:
                    pred[j] = _sigmoid(theta2[0] + theta2[1] * z[j]
                                       + theta2[2] * _logit(p_market[idx]))
                else:
                    pred[j] = _sigmoid(theta1[0] + theta1[1] * z[j])
            cal[test_idx] = pred
        g = g.copy()
        g["p_calibrated"] = cal
        out.append(g)
    return pd.concat(out, ignore_index=True), pd.DataFrame(params)


def alignment_report(sel: pd.DataFrame, bets: pd.DataFrame) -> pd.DataFrame:
    """Per group: is the probability aligned with the bet, and is it calibrated?"""
    rows = []
    for (market, side), g in sel.groupby(["market", "side"]):
        b = bets[(bets["market"] == market) & (bets["side"] == side)]
        # --- alignment 1: the line the bet was taken at ------------------------
        if len(b) and market in ("SPREAD", "TOTAL"):
            j = b.merge(sel[(sel["market"] == market) & (sel["side"] == side)]
                        [["game_id", "model_line"]], on="game_id", how="left")
            same = float((j["line"].astype(float) == j["model_line"].astype(float)).mean())
            line_check = ("every bet was taken at the line the probability was computed at"
                          if same >= 1.0 else
                          f"{1 - same:.1%} of bets were taken at a different line")
            line_aligned = bool(same >= 1.0)
        else:
            line_check = ("the moneyline has no line; the probability is the win probability "
                          "at that price")
            line_aligned = True

        # --- alignment 2: the side the probability belongs to ------------------
        sub = g[g["outcome_push"] == 0]
        realised = float(sub["outcome_win"].mean()) if len(sub) else float("nan")
        model_mean = float(sub["p_model"].mean()) if len(sub) else float("nan")
        cal_mean = float(sub["p_calibrated"].mean()) if len(sub) else float("nan")
        market_mean = float(sub["p_market"].mean()) if len(sub) else float("nan")
        # A probability attached to the wrong side would be *negatively* related
        # to the outcome it claims to describe. A positive relation means the
        # probability belongs to this side, whatever its calibration.
        pm = sub["p_model"].to_numpy(float)
        om = sub["outcome_win"].to_numpy(float)
        ok = np.isfinite(pm)
        if ok.sum() > 2 and np.std(pm[ok]) > 0 and np.std(om[ok]) > 0:
            corr = float(np.corrcoef(pm[ok], om[ok])[0, 1])
        else:
            corr = float("nan")
        side_ok = bool(np.isfinite(corr) and corr > 0)
        side_check = (f"the model's probability moves with the outcome it describes "
                      f"(correlation {corr:+.3f})" if side_ok else
                      f"the model's probability moves against the outcome it describes "
                      f"(correlation {corr:+.3f})")

        # --- calibration -------------------------------------------------------
        def brier(p):
            p = np.asarray(p, float)
            ok = np.isfinite(p)
            if not ok.any():
                return float("nan")
            return float(np.mean((p[ok] - sub["outcome_win"].to_numpy(float)[ok]) ** 2))

        rows.append(dict(
            market=market, side=side,
            n_games=int(len(g)), n_decided_games=int(len(sub)),
            n_bets=int(len(b)),
            model_mean_probability=round(model_mean, 6),
            calibrated_mean_probability=round(cal_mean, 6),
            market_mean_probability=round(market_mean, 6),
            realised_win_rate=round(realised, 6),
            model_minus_realised=round(model_mean - realised, 6),
            calibrated_minus_realised=round(cal_mean - realised, 6),
            market_minus_realised=round(market_mean - realised, 6),
            brier_model=round(brier(sub["p_model"].to_numpy(float)), 6),
            brier_calibrated=round(brier(sub["p_calibrated"].to_numpy(float)), 6),
            probability_outcome_correlation=round(corr, 6) if np.isfinite(corr) else "",
            line_alignment=line_check, line_aligned=line_aligned,
            side_alignment=side_check, side_aligned=bool(side_ok),
            verdict=("aligned and calibrated" if line_aligned and side_ok and
                     abs(cal_mean - realised) <= abs(model_mean - realised)
                     else "aligned, side is right, probability is over-confident"
                     if line_aligned and side_ok else "not aligned"),
        ))
    return pd.DataFrame(rows)


def build_bet_expectations(sel: pd.DataFrame, bets: pd.DataFrame) -> pd.DataFrame:
    """Per bet: the model's probability, the calibrated probability, the market's
    benchmark, and the expected return each of them implies."""
    key = sel.set_index(["game_id", "market", "side"])
    rows = []
    for bet_index, r in enumerate(bets.to_dict("records")):
        market, side = r["market"], r["side"]
        if market == "PARLAY":
            legs = [k.split(":") for k in str(r.get("selection_keys", "")).split(";") if k]
            p_model = p_cal = p_mkt = 1.0
            ok = bool(legs)
            for lg, mkt, sd in legs:
                k = (lg, mkt, sd)
                if k not in key.index:
                    ok = False
                    break
                row = key.loc[k]
                p_model *= float(row["p_model"])
                p_cal *= float(row["p_calibrated"])
                p_mkt *= float(row["p_market"])
            if not ok:
                continue
            price_units = str(r.get("price_units", "")).lower()
            dec = float(r["price"]) if price_units == "decimal" else float("nan")
        else:
            k = (r["game_id"], market, side)
            if k not in key.index:
                continue
            row = key.loc[k]
            p_model = float(row["p_model"])
            p_cal = float(row["p_calibrated"])
            p_mkt = float(row["p_market"])
            try:
                price = float(r["price"])
                dec = (1.0 + 100.0 / (-price) if price < 0 else 1.0 + price / 100.0) \
                    if price != 0 else float("nan")
            except (TypeError, ValueError, ZeroDivisionError):
                dec = float("nan")
        if not np.isfinite(dec):
            continue
        rows.append(dict(
            bet_index=bet_index,
            strategy=r["strategy"], game_id=r["game_id"], season=r["season"], week=r["week"],
            market=market, side=side, line=r["line"], price=r["price"],
            p_model=round(p_model, 6), p_calibrated=round(p_cal, 6),
            p_market=round(p_mkt, 6),
            edge_model=round(p_model - p_mkt, 6), edge_calibrated=round(p_cal - p_mkt, 6),
            expected_pnl_model=round(p_model * (dec - 1.0) - (1.0 - p_model), 6),
            expected_pnl_calibrated=round(p_cal * (dec - 1.0) - (1.0 - p_cal), 6),
            expected_pnl_market=round(p_mkt * (dec - 1.0) - (1.0 - p_mkt), 6),
            realised_pnl=r["pnl"], outcome=r["outcome"],
        ))
    return pd.DataFrame(rows)


def main() -> None:
    lines = pd.read_csv(LINES, low_memory=False)
    bets = pd.read_csv(BETS, low_memory=False)
    sel = build_selection_table(lines)
    sel, params = calibrate(sel)
    report = alignment_report(sel, bets)
    expectations = build_bet_expectations(sel, bets)

    params.to_csv(PROC / "probability_calibration.csv", index=False)
    report.to_csv(INT / "probability_alignment.csv", index=False)
    expectations.to_csv(PROC / "bet_expectations.csv", index=False)
    for f, src in (("probability_alignment.csv", INT / "probability_alignment.csv"),
                   ("bet_expectations.csv", PROC / "bet_expectations.csv"),
                   ("probability_calibration.csv", PROC / "probability_calibration.csv")):
        (SITE_DATA / f).write_bytes(src.read_bytes())

    print(report.to_string(index=False))
    print(f"\n  bet_expectations.csv {len(expectations):,} bets")


if __name__ == "__main__":
    main()
