"""Shared utilities for the K1 NFL Line Lab.

All paths are relative to the repository root. Raw data lives in data/raw
(git-ignored); every table that ships to the site is regenerated from raw
by `python -m analysis.run_all`.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"
SITE = ROOT / "data" / "site"
DOCS = ROOT / "docs"

for _p in (RAW, DERIVED, SITE, DOCS):
    _p.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Pinned upstream sources. Every number on the site traces back to these.
# ---------------------------------------------------------------------------
SOURCES = {
    "nfldata": {
        "repo": "nflverse/nfldata",
        "commit": "a270278f3ac4e937295fe6a27814b3c4a2b62645",
        "commit_date": "2026-11-01T13:05:15Z",
        "tarball": "https://codeload.github.com/nflverse/nfldata/tar.gz/a270278f3ac4e937295fe6a27814b3c4a2b62645",
        "blob": "https://github.com/nflverse/nfldata/blob/a270278f3ac4e937295fe6a27814b3c4a2b62645/data/",
        "license_note": "Upstream README credits nflverse contributors; data files are public GitHub-hosted CSVs.",
    },
    "nflfastR": {
        "repo": "nflverse/nflfastR",
        "commit": "701bbf38bc1c030ff9f1f4825a23191287d3903c",
        "tarball": "https://codeload.github.com/nflverse/nflfastR/tar.gz/701bbf38bc1c030ff9f1f4825a23191287d3903c",
        "blob": "https://github.com/nflverse/nflfastR/blob/701bbf38bc1c030ff9f1f4825a23191287d3903c/R/calculate_stats.R",
        "note": "Reference implementation used for the NFL stat-id -> player stat mapping (calculate_stats.R).",
    },
    "nflfastR-raw": {
        "repo": "nflverse/nflfastR-raw",
        "commit": "61ab6b3dd2179d06766834784c8ba24649c8ba6c",
        "commit_date": "2026-02-09T03:36:14Z",
        "blob": "https://github.com/nflverse/nflfastR-raw/tree/61ab6b3dd2179d06766834784c8ba24649c8ba6c/raw",
        "note": "Per-game NFL Game Center JSON (official league stat feed), scraped by nflverse.",
    },
    "nfl_com_schedule": "https://www.nfl.com/schedules/",
    "nfl_com_standings": "https://www.nfl.com/standings/",
    "espn_standings": "https://www.espn.com/nfl/standings/_/season/{season}",
    "espn_api_standings": "https://site.api.espn.com/apis/v2/sports/football/nfl/standings?season={season}",
    "espn_api_core_events": "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{season}/types/2/weeks/{week}/events?limit=100",
    "espn_api_event": "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{event}",
    "espn_games": "https://www.espn.com/nfl/game/_/gameId/{espn_id}",
    "pfr": "https://www.pro-football-reference.com/",
}

SESSION_ID = "arena-a1970463"

# ---------------------------------------------------------------------------
# Odds helpers (American odds throughout).
# ---------------------------------------------------------------------------
def american_to_decimal(o):
    """Convert American odds to decimal. Accepts scalars or numpy arrays."""
    o = np.asarray(o, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        dec = 1.0 + np.where(o > 0, o / 100.0, 100.0 / np.abs(o))
    return dec if dec.ndim else float(dec)


def american_to_prob(o: float) -> float:
    """Implied (vigged) probability from American odds."""
    o = float(o)
    return 100.0 / (o + 100.0) if o > 0 else abs(o) / (abs(o) + 100.0)


def pnl_per_unit(odds: float, won: float) -> float:
    """Profit on a 1-unit stake. `won` in {1 win, 0 loss, 0.5 push->0 pnl}."""
    if won is None or (isinstance(won, float) and math.isnan(won)):
        return np.nan
    o = float(odds)
    if won == 0.5:  # push
        return 0.0
    if won == 1:
        return o / 100.0 if o > 0 else 100.0 / abs(o)
    return -1.0


def nv_american_to_prob(o: float) -> float:
    """No-vig probability for a two-way market priced at o_a / o_b."""
    raise NotImplementedError


def devig_two_way(o_a, o_b):
    """No-vig probabilities. Accepts scalars or arrays (vectorised)."""
    oa = np.asarray(o_a, dtype=float)
    ob = np.asarray(o_b, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        pa = np.where(oa > 0, 100.0 / (oa + 100.0), np.abs(oa) / (np.abs(oa) + 100.0))
        pb = np.where(ob > 0, 100.0 / (ob + 100.0), np.abs(ob) / (np.abs(ob) + 100.0))
    s = pa + pb
    return pa / s, pb / s


def assign_grade_bucket(x: float, edges=(0, 1, 2, 3, 5, 7, 10)) -> str:
    for i, e in enumerate(edges):
        if x < e:
            return f"<{e}"
    return f">={edges[-1]}"


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------
def write_json(name: str, obj) -> Path:
    p = SITE / name
    with open(p, "w") as f:
        json.dump(obj, f, indent=1, default=str)
    return p


def read_json(name: str):
    with open(SITE / name) as f:
        return json.load(f)


def write_csv(df: pd.DataFrame, name: str, derived: bool = True) -> Path:
    p = (DERIVED if derived else RAW) / name
    df.to_csv(p, index=False)
    return p


# ---------------------------------------------------------------------------
# Statistics: bootstrap, permutation, FDR, White reality check
# ---------------------------------------------------------------------------
def block_bootstrap_ci(
    values: np.ndarray,
    blocks: np.ndarray | None = None,
    n_boot: int = 4000,
    seed: int = 7,
    alpha: float = 0.05,
) -> dict:
    """Bootstrap CI for the mean of per-bet returns.

    If `blocks` is given the resampling is a *block* bootstrap (blocks are
    resampled with replacement), which respects within-block dependence
    (e.g. all bets inside one week / one season).
    """
    rng = np.random.default_rng(seed)
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    n = len(v)
    if n < 5:
        return {"mean": float(np.mean(v)) if n else float("nan"), "lo": float("nan"),
                "hi": float("nan"), "se": float("nan"), "n": n, "p_boot": float("nan")}
    if blocks is None:
        idx = rng.integers(0, n, size=(n_boot, n))
        means = v[idx].mean(axis=1)
    else:
        b = np.asarray(blocks)
        uniq = pd.unique(b)
        groups = {u: v[b == u] for u in uniq}
        means = np.empty(n_boot)
        for i in range(n_boot):
            pick = rng.choice(uniq, size=len(uniq), replace=True)
            means[i] = np.concatenate([groups[u] for u in pick]).mean()
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    se = float(np.std(means, ddof=1))
    return {
        "mean": float(v.mean()),
        "lo": float(lo),
        "hi": float(hi),
        "se": se,
        "n": n,
        "p_boot": float((means <= 0).mean()),
    }


def bootstrap_skill_prob(values: np.ndarray, se_hint: float | None = None, n_boot: int = 3000,
                         seed: int = 11) -> float:
    """P(true mean return > 0) from a normal approximation with the empirical SE.

    Reported as an explicit 'probability this is skill, not luck' figure. It is
    a model-based quantity (normality of the sampling distribution of the mean),
    not a p-value; the gate uses the p-value and FDR instead.
    """
    v = np.asarray(values, float)
    v = v[~np.isnan(v)]
    if len(v) < 10:
        return float("nan")
    se = se_hint if se_hint else v.std(ddof=1) / math.sqrt(len(v))
    if se <= 0:
        return float("nan")
    z = v.mean() / se
    return float(0.5 * (1 + math.erf(z / math.sqrt(2))))


def bh_fdr(pvals: dict, q: float = 0.10) -> dict:
    """Benjamini-Hochberg step-up. Returns per-hypothesis reject flags."""
    items = sorted([(k, v) for k, v in pvals.items() if v is not None and not math.isnan(v)],
                   key=lambda z: z[1])
    m = len(items)
    if m == 0:
        return {}
    out = {k: {"p": v, "reject": False, "rank": None} for k, v in items}
    kmax = 0
    for i, (k, v) in enumerate(items, start=1):
        out[k]["rank"] = i
        if v <= q * i / m:
            kmax = i
    for i, (k, v) in enumerate(items, start=1):
        out[k]["reject"] = i <= kmax
    return out


def reality_check(matrix: np.ndarray, n_boot: int = 2000, seed: int = 3) -> dict:
    """White (2000) Reality Check via stationary bootstrap on the *max* mean.

    `matrix` rows are observations (bets), columns are strategies. Missing
    entries must be NaN. Tests H0: the best strategy's expected return is <= 0,
    after accounting for having searched over all columns.
    """
    rng = np.random.default_rng(seed)
    X = np.asarray(matrix, float)
    T, K = X.shape
    means = np.nanmean(X, axis=0)
    best = int(np.nanargmax(means))
    # centre each column at its own mean under the null
    Xc = X - np.nanmean(X, axis=0)
    Xc = np.nan_to_num(Xc)
    max_boot = np.empty(n_boot)
    for i in range(n_boot):
        # stationary bootstrap index (Politis-Romano), mean block length ~ 3
        idx = np.empty(T, dtype=int)
        t = rng.integers(0, T)
        p = 1 / 3
        for j in range(T):
            if rng.random() < p:
                t = rng.integers(0, T)
            else:
                t = (t + 1) % T
            idx[j] = t
        max_boot[i] = np.max(Xc[idx].mean(axis=0))
    observed = means[best]
    p_value = float((max_boot >= observed).mean())
    return {
        "best_strategy_idx": best,
        "best_mean": float(observed),
        "p_value": p_value,
        "n_strategies": int(K),
        "n_obs": int(T),
        "note": "White's Reality Check, stationary bootstrap (mean block 3), 2000 replications.",
    }


def cluster_ols_newey_west(y: np.ndarray, x: np.ndarray, lags: int = 4) -> dict:
    """Simple OLS with Newey-West standard errors (used for calibration slopes)."""
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    n = len(y)
    X = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    XtX_inv = np.linalg.inv(X.T @ X)
    S = (X * resid[:, None]).T @ (X * resid[:, None])
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = (X[L:] * resid[L:, None]).T @ (X[:-L] * resid[:-L, None])
        S += w * (G + G.T)
    cov = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.diag(cov))
    return {"intercept": float(beta[0]), "slope": float(beta[1]),
            "se_intercept": float(se[0]), "se_slope": float(se[1]),
            "t_slope": float(beta[1] / se[1]) if se[1] > 0 else float("nan"), "n": n}


def two_sided_z_p(z: float) -> float:
    return float(2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))))


@dataclass
class BetResult:
    strategy: str
    game_id: str
    season: int
    week: int
    market: str
    side: str
    price: float
    won: float  # 1 win, 0 loss, 0.5 push
    pnl: float
    model_edge: float = float("nan")
