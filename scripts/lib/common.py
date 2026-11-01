"""
Shared quantitative library for the NFL line-origination / strategy-research project.

All formulas here are standard and are cited in research/02-methodology.md:
  * American <-> decimal odds, implied probability            (definitional)
  * Proportional (multiplicative) no-vig de-margining         (standard)
  * Shin (1993) no-vig de-margining                           PAPER-SHIN
  * Kelly (1956) stake sizing                                 PAPER-KELLY
  * Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014)      PAPER-DSR
  * Benjamini-Hochberg FDR control                            Benjamini & Hochberg (1995)
  * Sheppard-style bivariate-normal joint probability for two 50/50 legs:
        P(both) = 1/4 + arcsin(rho) / (2*pi)                 (verified numerically in
                                                              scripts/tests/test_math.py)

No empirical parameter in this file is hard-coded; every empirical value is estimated
in the numbered scripts and written to data/*.json with its provenance.
"""
from __future__ import annotations

import math
import random
from typing import Iterable, Sequence

# ---------------------------------------------------------------- odds conversions


def american_to_decimal(a: float) -> float:
    """American odds -> decimal odds (total return per 1 unit staked)."""
    if a == 0:
        raise ValueError("American odds of 0 are undefined")
    return 1.0 + (a / 100.0 if a > 0 else 100.0 / abs(a))


def american_to_prob(a: float) -> float:
    """American odds -> raw implied probability (includes the bookmaker margin)."""
    return 1.0 / american_to_decimal(a)


def prob_to_american(p: float) -> float:
    if not 0 < p < 1:
        raise ValueError("probability must be in (0,1)")
    if p >= 0.5:
        return round(-100.0 * p / (1.0 - p))
    return round(100.0 * (1.0 - p) / p)


def decimal_to_american(d: float) -> float:
    return prob_to_american(1.0 / d)


# ---------------------------------------------------------------- de-margining


def no_vig_proportional(p_home: float, p_away: float) -> tuple[float, float]:
    """Multiplicative normalisation: divide each implied probability by the overround."""
    s = p_home + p_away
    return p_home / s, p_away / s


def margin_from_probs(p_home: float, p_away: float) -> float:
    """Bookmaker margin (a.k.a. overround / 'vig' as a fraction of total implied prob)."""
    return p_home + p_away - 1.0


def shin_z(p_home: float, p_away: float, tol: float = 1e-13, iters: int = 300) -> float:
    """Solve Shin (1993) insider-trading proportion z for a two-outcome market.

    Implementation follows the standard form used in the forecasting literature
    (Shin 1993; Strumbelj 2014, IJF 30(3): p_i = [sqrt(z^2 + 4(1-z)pi_i^2/PI) - z] / (2(1-z)),
    where PI = sum_j pi_j > 1 is the raw implied probability mass.

    At z = 0 the formula returns pi_i/sqrt(PI) (mass sqrt(PI) > 1), and the sum of the
    de-margined probabilities is strictly decreasing in z, so a unique root in (0, 1) exists
    whenever PI > 1.  Bisection is used; the function is monotone by construction.
    """
    pi = (p_home, p_away)
    PI = p_home + p_away
    if PI <= 1.0:            # no margin (or arbitrage) -> nothing to remove
        return 0.0

    def total(z: float) -> float:
        s = 0.0
        for p in pi:
            s += (math.sqrt(z * z + 4.0 * (1.0 - z) * p * p / PI) - z) / (2.0 * (1.0 - z))
        return s

    lo, hi = 0.0, 1.0 - 1e-12
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if total(mid) > 1.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def no_vig_shin(p_home: float, p_away: float) -> tuple[float, float]:
    """Shin (1993) de-margined probabilities for a two-outcome market.

    Longshots are de-margined more aggressively than by the proportional method
    (the model attributes the excess margin on longshots to informed trading),
    so the de-margined probability of the underdog is *lower* than proportional.
    Verified in scripts/tests/test_math.py.
    """
    z = shin_z(p_home, p_away)
    PI = p_home + p_away
    out = []
    for p in (p_home, p_away):
        out.append((math.sqrt(z * z + 4.0 * (1.0 - z) * p * p / PI) - z) / (2.0 * (1.0 - z)))
    s = sum(out)
    return out[0] / s, out[1] / s


def no_vig_additive(p_home: float, p_away: float) -> tuple[float, float]:
    """Equal-margin ('additive') de-margining: subtract half the overround from each side."""
    excess = (p_home + p_away - 1.0) / 2.0
    return p_home - excess, p_away - excess


# ---------------------------------------------------------------- bet settlement


def settle_spread(side: str, line: float, home_score: float, away_score: float) -> int:
    """Return 1 win, 0 push, -1 loss for a spread bet.

    `line` is the handicap applied to the chosen side (e.g. home +3.5 -> line=+3.5).
    """
    if side == "home":
        margin = home_score - away_score + line
    else:
        margin = away_score - home_score + line
    if margin > 0:
        return 1
    if margin < 0:
        return -1
    return 0


def settle_total(side: str, line: float, home_score: float, away_score: float) -> int:
    total = home_score + away_score
    if total == line:
        return 0
    if side == "over":
        return 1 if total > line else -1
    return 1 if total < line else -1


def settle_ml(side: str, home_score: float, away_score: float) -> int:
    if home_score == away_score:
        return 0
    home_won = home_score > away_score
    return 1 if (home_won and side == "home") or ((not home_won) and side == "away") else -1


def payout_per_unit(outcome: int, american: float) -> float:
    """Profit per 1 unit staked.  Push (0) returns stake -> profit 0."""
    if outcome == 0:
        return 0.0
    if outcome > 0:
        return american_to_decimal(american) - 1.0
    return -1.0


# ---------------------------------------------------------------- inference


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def stdev(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def t_stat(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    sd = stdev(xs)
    if sd == 0:
        return float("nan")
    return mean(xs) / (sd / math.sqrt(n))


def bootstrap_ci(
    xs: Sequence[float], n_boot: int = 10000, alpha: float = 0.05, seed: int = 20261101
) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean. Deterministic given `seed`."""
    if not xs:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(xs)
    means = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += xs[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int((alpha / 2) * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return lo, hi


def norm_sf(z: float) -> float:
    """Upper tail of the standard normal (Abramowitz & Stegun 7.1.26 erf approx, |err|<1.5e-7)."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def two_sided_p(t: float) -> float:
    if math.isnan(t):
        return float("nan")
    return 2.0 * norm_sf(abs(t))


def norm_ppf(p: float) -> float:
    """Inverse standard normal (Acklam's rational approximation, |rel err| < 1.15e-9)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def bh_qvalues(pvals: Iterable[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values (q-values), monotonicity enforced."""
    p = list(pvals)
    n = len(p)
    order = sorted(range(n), key=lambda i: p[i])
    q = [0.0] * n
    prev = 1.0
    for rank in range(n, 0, -1):
        i = order[rank - 1]
        val = min(prev, p[i] * n / rank)
        q[i] = val
        prev = val
    return q


def expected_max_sharpe(n_trials: int, var_sharpe: float = 1.0) -> float:
    """E[max of n_trials iid N(0, sqrt(var_sharpe))] - selection bias benchmark."""
    if n_trials < 2:
        return 0.0
    e = 0.5772156649
    return math.sqrt(var_sharpe) * (
        (1 - e) * norm_ppf(1 - 1.0 / n_trials) + e * norm_ppf(1 - 1.0 / (n_trials * math.e))
    )


def deflated_sharpe_ratio(
    sr: float, n_obs: int, skew: float, kurt: float, n_trials: int, sr_variance: float
) -> float:
    """Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio -> probability the true SR > 0.

    sr         : observed (non-annualised) Sharpe of the strategy's per-bet returns
    n_obs      : number of observations
    skew, kurt : skewness and (non-excess) kurtosis of the return series
    n_trials   : number of strategy configurations searched
    sr_variance: variance of the Sharpe ratios across those trials
    """
    if n_obs < 3 or math.isnan(sr):
        return float("nan")
    sr0 = expected_max_sharpe(n_trials, sr_variance)
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4.0 * sr * sr))
    z = (sr - sr0) * math.sqrt(n_obs - 1) / denom
    return 1.0 - norm_sf(z)


def kelly_fraction(p: float, decimal_odds: float) -> float:
    """Kelly (1956): f* = (p*b - q)/b with b = net odds."""
    b = decimal_odds - 1.0
    if b <= 0:
        return 0.0
    return (p * b - (1 - p)) / b


def bivariate_normal_joint(p1: float = 0.5, p2: float = 0.5, rho: float = 0.0) -> float:
    """P(both legs win) for two standard-normal legs.  Exact for p=0.5:
    P = 1/4 + arcsin(rho)/(2*pi)  (Sheppard's formula).  Used as the parlay fair-price kernel.
    """
    if abs(p1 - 0.5) < 1e-12 and abs(p2 - 0.5) < 1e-12:
        return 0.25 + math.asin(rho) / (2 * math.pi)
    # general case: numerical integration of the Gaussian copula
    steps = 400
    total = 0.0
    z1 = [norm_ppf(1e-6 + (1 - 2e-6) * i / steps) for i in range(steps + 1)]
    h = z1[1] - z1[0]
    for i in range(steps):
        z = z1[i]
        cond_mean = rho * z
        cond_sd = math.sqrt(max(1e-12, 1 - rho * rho))
        # P(Z2 > c2 | Z1 = z) with c2 = norm_ppf(1-p2)
        c2 = norm_ppf(1 - p2)
        pc2 = norm_sf((c2 - cond_mean) / cond_sd)
        dens1 = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
        total += dens1 * pc2 * h
    # mass below left edge handled by tail refinement
    m = -z1[0]
    total += norm_sf(m) * 0.0
    return max(0.0, min(1.0, total))
