"""T4 — statistics used to separate skill from luck.

Nothing here is decorative: every gate in `validation.py` is computed by one of
these functions, and every function is deterministic given `SEED`.

* `bh_fdr`              Benjamini–Hochberg false-discovery control across the
                        whole strategy library (we test ~20 strategies, so this
                        matters).
* `stationary_bootstrap` Politis–Romano stationary bootstrap, resampling whole
                        (season, week) blocks because bets inside a week are not
                        independent.
* `deflated_sharpe`      Bailey & López de Prado (2014) deflated Sharpe ratio:
                        the probability the observed Sharpe survives the number
                        of trials actually run.
* `reality_check`        White (2000) bootstrap reality check on the best
                        strategy in the library.
* `required_n`           how many bets are needed to detect a given ROI — the
                        single most useful number for "is this luck?".
"""
from __future__ import annotations

import numpy as np
from scipy import stats

SEED = 20261101


def bh_fdr(pvals: np.ndarray, q: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    """Benjamini–Hochberg. Returns (reject_mask, adjusted_p)."""
    p = np.asarray(pvals, float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    adj = ranked * n / np.arange(1, n + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    out = np.empty(n)
    out[order] = adj
    return out <= q, out


def _blocks(weeks: np.ndarray) -> list[np.ndarray]:
    """Group row positions by (season, week) block."""
    uniq = {}
    for i, w in enumerate(weeks):
        uniq.setdefault(w, []).append(i)
    return [np.array(v) for v in uniq.values()]


def stationary_bootstrap(pnl: np.ndarray, weeks: np.ndarray, n_boot: int = 10000,
                         mean_block: float = 4.0, seed: int = SEED) -> np.ndarray:
    """Bootstrap the mean of `pnl`, resampling contiguous blocks of weeks."""
    rng = np.random.default_rng(seed)
    blocks = _blocks(weeks)
    if not blocks:
        return np.array([np.nan])
    k = len(blocks)
    p_geom = 1.0 / max(1.0, mean_block)
    means = np.empty(n_boot)
    for b in range(n_boot):
        draw = []
        while len(draw) < k:
            start = rng.integers(0, k)
            length = 1
            while rng.random() > p_geom and length < k:
                length += 1
            draw.extend([(start + j) % k for j in range(length)])
        idx = np.concatenate([blocks[j] for j in draw[:k]])
        means[b] = pnl[idx].mean()
    return means


def deflated_sharpe(sr: float, n_obs: int, n_trials: int, skew: float,
                    kurt: float, sr_variance_across_trials: float) -> float:
    """P(true Sharpe > 0) after accounting for `n_trials` attempts.

    sr     : observed per-bet Sharpe (mean/sd of the ledger's pnl)
    skew   : skewness of the ledger pnl
    kurt   : Pearson kurtosis of the ledger pnl (3.0 for a normal)
    sr_variance_across_trials : variance of Sharpe across the strategy library
    """
    if not np.isfinite(sr) or n_obs < 3 or n_trials < 2:
        return float("nan")
    var = max(float(sr_variance_across_trials), 1e-12)
    euler = 0.5772156649
    z1 = stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1 - 1.0 / (n_trials * np.e))
    sr0 = np.sqrt(var) * ((1 - euler) * z1 + euler * z2)
    denom = 1 - skew * sr + (kurt - 1) / 4.0 * sr ** 2
    if denom <= 0:
        return float("nan")
    return float(stats.norm.cdf((sr - sr0) * np.sqrt(n_obs - 1) / np.sqrt(denom)))


def reality_check(week_matrix: np.ndarray, n_boot: int = 5000, seed: int = SEED) -> dict:
    """White's Reality Check on a (weeks × strategies) matrix of mean pnl.

    H0: the best strategy in the library has no expected edge.
    """
    X = np.asarray(week_matrix, float)
    T, k = X.shape
    rng = np.random.default_rng(seed)
    obs = np.nanmean(X, axis=0)
    best = np.nanmax(obs)
    centred = X - obs
    stats_b = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, T, T)          # week-level resampling, whole rows
        sample = centred[idx]
        stats_b[b] = np.nanmax(np.nanmean(sample, axis=0))
    return {
        "observed_best_mean_pnl": float(best),
        "p_value": float(np.mean(stats_b >= best)),
        "n_weeks": int(T),
        "n_strategies": int(k),
    }


def required_n(roi: float, sd: float = 1.0, alpha: float = 0.05,
               power: float = 0.80, two_sided: bool = True) -> float:
    """Bets required to detect `roi` with the given power (normal approximation)."""
    if roi <= 0:
        return float("inf")
    z_a = stats.norm.ppf(1 - alpha / (2 if two_sided else 1))
    z_b = stats.norm.ppf(power)
    return float(((z_a + z_b) ** 2) * (sd ** 2) / (roi ** 2))


def t_stat_p(pnl: np.ndarray, two_sided: bool = False) -> tuple[float, float]:
    x = np.asarray(pnl, float)
    if len(x) < 3 or np.std(x, ddof=1) == 0:
        return float("nan"), float("nan")
    t = stats.ttest_1samp(x, 0.0)
    p = t.pvalue if two_sided else t.pvalue / 2.0
    if (t.statistic < 0) and not two_sided:
        p = 1.0 - p
    return float(t.statistic), float(min(1.0, max(0.0, p)))
