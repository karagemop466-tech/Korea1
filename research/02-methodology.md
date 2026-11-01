# 02 — Methodology: originating lines, de-margining, CLV, correlation

Every formula below is implemented in `scripts/lib/common.py` and numerically checked by
`scripts/tests/test_math.py` (Monte-Carlo where a closed form is claimed). If a check fails, the
build stops.

## 1. Originating our own line (`scripts/02_line_model.py`)

Three components, all **walk-forward**: a game's line is produced only from information that
existed before kickoff.

### 1.1 Elo with margin-of-victory adjustment

Structure and constants follow the published FiveThirtyEight NFL specification (`FTE-ELO`):

```
expected_home = 1 / (1 + 10^(-(elo_home + HFA - elo_away)/400))
mov_multiplier = ln(|margin| + 1) * 2.2 / (0.001 * elo_diff + 2.2)
delta  = K * mov_multiplier * (result - expected_home)      K = 20
HFA    = 48 Elo points
between seasons: elo <- 1500 + (elo - 1500) * (1 - 1/3)
```

The rating pair stored for a game is the pair **before** that game is played, so using it as a
feature cannot leak the result.

### 1.2 Elo → spread: the coefficient is estimated, not assumed

`model_margin = a + b * elo_diff`, where `a` and `b` are estimated by OLS **on prior seasons only**
(expanding window). Estimated values:

| Season used for | a (intercept) | b (points per Elo point) | games in fit |
|---|---|---|---|
| 2012 predictions | 0.818 | 0.0499 | 266 |
| 2015 predictions | 0.756 | 0.0434 | 1,063 |
| 2019 predictions | 0.732 | 0.0390 | 2,127 |
| 2021 predictions | 0.150 | 0.0396 | 2,661 |

`b ≈ 0.04` means **25 Elo points ≈ 1 point of spread**. That is a *result* of this dataset, not a
constant copied from anywhere.

### 1.3 Totals: pace model

Per team: exponentially weighted points scored and allowed, **half-life 6 games**, computed only
from prior games. Expected points for each side = (own scored + opponent allowed)/2; the total is
the sum, then recalibrated by an expanding OLS on realised totals (same no-look-ahead rule).

### 1.4 Moneyline

`P(home wins) = Φ(model_margin / σ)` with `σ` estimated from the walk-forward margin residuals
(expanding). American odds are then produced with the model's own margin removed (a fair line) —
never presented as a sportsbook price.

### 1.5 Honest scoring of the model

Out of sample, 2012–2021 (`data/lines.json` → `summary`):

| Metric | Our model | Closing market | Verdict |
|---|---|---|---|
| Spread MAE (points) | 10.473 | **10.151** | market wins |
| Straight-up accuracy | 66.41% | **67.27%** | market wins |
| Total MAE (points) | 10.861 | **10.604** | market wins |
| Mean absolute disagreement with the close | 2.652 pts | — | our line is close but noisier |

**Conclusion, stated plainly: this model does not beat the closing line.** It is a legitimate
line-origination engine (it produces a spread, total and moneyline for every game, and its
probabilities are reasonably calibrated — see the calibration table in `data/lines.json`), but it is
*not* an edge. Strategies that bet its disagreements lose; that is measured in `S01`, `S02`, `S10`,
`S15`, `S17`.

## 2. Removing the vig (`no_vig_proportional`, `no_vig_shin`)

* **Proportional (multiplicative):** `p_i / Σp`. Standard, transparent, and used for every
  "fair probability" figure unless stated otherwise.
* **Shin (1993)** (`PAPER-SHIN`), two-outcome form:

```
p_i = [ sqrt(z^2 + 4(1-z)·π_i^2 / Π) − z ] / (2(1−z)),   Π = Σπ_j > 1
z solves Σ p_i = 1
```

Shin attributes excess margin on longshots to informed trading, so the de-margined **underdog
probability is lower than the proportional one** and the favourite's is higher. Verified
numerically: `-400/+330` → proportional dog 22.52%, Shin dog 21.63%.

> A first version of this implementation omitted the `Π` normalisation and produced a nonsense
> 11.8% dog probability. The unit test caught it, the fix was verified line by line, and the
> original test expectation — which asserted the *opposite* direction — was corrected too. This is
> recorded because a silently wrong de-vig would have corrupted every CLV figure downstream.

## 3. Parlay mathematics

For two **correlated** 50/50 legs with correlation ρ, the joint probability is the bivariate normal
orthant probability, which has a closed form:

```
P(both legs) = 1/4 + arcsin(ρ) / (2π)
```

Verified against a 400,000-draw Monte Carlo for ρ ∈ {−0.6, −0.2, 0, 0.25, 0.62}
(`scripts/tests/test_math.py`, max deviation observed 0.002).

Consequences (`data/correlations.json` → `parlay_pricing_kernel`):

| ρ | P(both) | fair 2-leg decimal | if priced independently (4.00) |
|---|---|---|---|
| 0.0 | 25.00% | 4.000 | correct |
| 0.2 | 28.21% | 3.546 | book overpays 12.7% |
| 0.4 | 31.55% | 3.170 | book overpays 26.2% |
| 0.6 | 35.24% | 2.838 | book overpays 41.0% |
| 0.8 | 39.76% | 2.515 | book overpays 59.1% |

*"Book overpays"* means: if a book priced those two legs independently it would be paying 4.00 on a
combination that is really worth 3.55 at ρ = 0.2 — the book loses. This is exactly why sportsbooks
restrict or reprice same-game parlays, and why the only parlay edge available to a bettor is in
legs whose correlation the book has priced **below** the true correlation.

### 3.1 Measured correlations (play-by-play, 2021–2022, 1,086 team-games)

Reported two ways, because they answer different questions:

* `rho_raw` — across all player-games. The number a pricing model needs on average.
* `rho_within_player` — after removing each player's own season mean. Pure game-to-game
  co-movement.

| Leg pair | raw ρ | within-player ρ | empirical P(both > median) | if independent | gap |
|---|---|---|---|---|---|
| QB passing yards × WR1 receiving yards | 0.568 | **0.441** | 35.64% | 25.51% | **+39.7%** |
| QB passing yards × QB passing TDs | 0.506 | 0.426 | 45.67% | 39.67% | +15.1% |
| WR1 receiving yards × WR2 receiving yards | 0.142 | 0.035 | 27.62% | 25.28% | +9.3% |
| WR1 receptions × WR2 receptions | 0.374 | 0.182 | 44.94% | 39.42% | +14.0% |
| QB passing yards × RB1 rushing yards | −0.158 | −0.135 | 24.49% | 26.16% | −6.4% |
| RB1 rushing yards × team points | 0.327 | 0.333 | 32.04% | 26.54% | +20.7% |
| QB passing yards × team points | 0.393 | 0.307 | 33.33% | 26.30% | +26.7% |
| QB passing yards × opposing QB passing yards | 0.124 | 0.112 | 28.55% | 25.93% | +10.1% |

Two findings worth keeping:

1. **The QB/WR1 stack is the single most mispriced combination available**: ρ = 0.44. The copula at
   ρ = 0.44 gives a 32.26% joint (fair price 3.10) and the direct empirical joint at the median split
   gives 35.64% (fair price 2.81) against 25.51% (price 3.92) if the legs were independent. The two
   estimates differ slightly because the medians are not exactly 50/50; both say the same thing —
   an independent price overpays by roughly a third.
2. **WR1 and WR2 are mildly positive, not negative.** The intuitive story ("they compete for the
   same targets, so they must be negatively correlated") is wrong in this data: within-player
   ρ = +0.035 for yards and **+0.18 for receptions**. Game environment (pace, attempts) dominates
   target competition. Anyone pricing a WR1+WR2 "hedge" as negatively correlated is pricing it
   backwards.

The same table also validates the copula: predicted joint vs empirical joint differs by at most
**0.034** across the pairs (`copula_abs_error` in `data/props.json`), so the closed form is safe to
use for pricing where a leg pair has no direct empirical estimate.

## 4. Proving skill: closing line value

Beating the close is the standard evidence of skill (`PAPER-LEVITT`), because the close is the
market's most informed price. For a bet placed at the opening line:

```
spread, home side : CLV = open − close
spread, away side : CLV = close − open
total,  over      : CLV = close − open
total,  under     : CLV = open − close
```

Positive CLV means the number you took was better than the number the market settled on. It is a
**lower-variance** skill measure than win/loss, because it is measured on every bet rather than on
the ~50% of bets that happen to win. It is gate **G5**.

## 5. What is *not* modelled (and is therefore not claimed)

* Injuries, weather, travel, officiating crews and roster moves — no licence-clean feed for them
  was reachable. The model is deliberately limited to results-derived features.
* Player-prop *prices* (only correlations are measured — see I-04).
* Live/in-play markets.
