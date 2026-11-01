# 03 — Validation gates and removing luck

A strategy is not "validated" because it made money. It is validated when it clears eight
pre-specified gates. The thresholds are fixed in `scripts/06_validation.py` **before** any result is
inspected, so they cannot be moved to rescue a favourite.

## 1. The gates

| Gate | Requirement | Why it exists |
|---|---|---|
| **G0** Data integrity | zero final-score disagreements on the 2021 cross-validation, closing totals within 1 point on ≥ 90% of games, ≥ 2,800 usable games | A perfect strategy on broken data is worthless |
| **G1** Sample size | n ≥ 300 graded bets and ≥ 100 out-of-sample bets | Below this, ROI is noise (see §3) |
| **G2** Significance | two-sided p < 0.05 **and** BH q < 0.10 **in the profitable direction** | Testing 18 rules guarantees a false winner at p < 0.05 |
| **G3** Out of sample | ROI > 0 on the held-out seasons (2018–2021) | The design seasons (2012–2017) cannot validate themselves |
| **G4** Robustness | ROI > 0 at −115 pricing, and ≥ 60% of seasons non-negative | An edge that dies at 5 cents of extra vig is not an edge |
| **G5** Economic edge | mean CLV > 0 where measurable, otherwise OOS ROI > 2% | Beating the close is the least noisy proof of skill |
| **G6** Risk | max drawdown ≤ 25 units, per-bet Sharpe > 0 | Positive expectancy with ruinous swings is unusable |
| **G7** Inputs available | every rule input is public pre-game data | A rule you cannot execute is not a strategy |
| **G8** Selection-bias corrected | Deflated Sharpe Ratio ≥ 0.95 | See §2.1 |

**G0 passed.** The data-integrity evidence is in `data/derived/integrity.json`.

## 2. Removing luck — three independent measurements

### 2.1 Deflated Sharpe Ratio (`PAPER-DSR`)

```
SR0 = E[max Sharpe of N zero-skill trials]
    = sqrt(var_SR) · [ (1−γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)) ],   γ = 0.5772…
DSR = Φ( (SR − SR0)·sqrt(n−1) / sqrt(1 − skew·SR + (kurt−1)/4·SR²) )
```

With N = 18 trials and the observed spread of Sharpes across the battery (variance 0.002496), the
*expected best* Sharpe of pure luck is **0.0926 per bet** (`luck.expected_best_sharpe_of_pure_luck`).
Every strategy in the battery had a selection-corrected DSR below **0.326**, and **G8 passed 0 of
18**.

### 2.2 Season overdispersion (are season-to-season swings real, or just sampling?)

```
Q = Σ_seasons (ROI_s − ROĪ)² / var_binomial(ROI_s),   var = p(1−p)·1.9091²/n_s
luck_ratio = (k−1)/Q
```

`luck_ratio ≈ 1` means the season-to-season dispersion is exactly what binomial noise would produce
on its own — i.e. **every apparent "hot season" is luck**. Values are reported per strategy in
`data/validation.json`.

### 2.3 Signal persistence (the decisive test)

Take every strategy's in-sample ROI (2012–2017) and its held-out ROI (2018–2021) and correlate them
across the battery.

* Result: **r = 0.485** across 18 strategies.
* Interpretation: there is *some* persistent structure in these families (the rules are not pure
  noise), but it is not nearly strong enough for any single strategy to clear the gate set. A
  leaderboard built on one season of this data would rank luck.

## 3. How much of a leaderboard is luck? (simulation, 2,000 × 1,000 bettors, 267 bets each)

| Field | Winner's ROI, median | Winner's ROI, 95th pct | Share of bettors profitable |
|---|---|---|---|
| **Zero skill** | **+18.66%** | **+22.68%** | 51.44% |
| True edge +2% per bet, all bettors | +20.62% | +24.62% | — |

A field of 1,000 bettors with **no edge at all** produces a winner at roughly **+19% ROI** after a
single 267-bet season. That is not a tail event; it is the median outcome. Any competition that pays
the top of a one-season leaderboard is paying a coin-flip winner.

### 3.1 The decisive experiment: does a real edge even show up on a P&L leaderboard?

Simulation: **one** genuinely skilled bettor (2% ROI edge, +0.50 points of closing-line value per
bet) against **999** zero-skill bettors, 267 bets each, 3,000 trials. CLV dispersion uses the
**measured** pooled sd of per-bet CLV in this project (2.0 points).

| Board ranked by | Skilled bettor finishes 1st | Skilled bettor in top 1% |
|---|---|---|
| Season ROI | **0.32%** | **2.21%** |
| Mean CLV | **78.86%** | **95.37%** |

A real 2% edge is essentially **invisible** on a season-P&L leaderboard — it finishes first 0.32% of
the time, which is barely above the 0.1% chance rate in a 1,000-person field. The *same* bettor is
found by a CLV-ranked board 78.9% of the time. (Method: 20,000 trials, CLT normal approximation to
the exact binomial; the approximation is validated against brute force in
`luck.exact_winner_check`, median winner 14.40% exact vs 14.29% approximate.) **This is the whole argument for the scoring system in
`04-competition.md`**, and it is measured, not asserted.

## 4. How long would it take to *prove* an edge? (power arithmetic)

Bets required to distinguish a per-bet ROI from zero at 95% confidence with 80% power, at −110
payoffs (`data/validation.json` → `luck.detection_power`):

| True edge per bet | Bets needed | Seasons at 267 bets |
|---|---|---|
| 1% | 71,275 | **266.9** |
| 2% | 17,796 | **66.6** |
| 5% | 2,833 | 10.6 |
| 10% | 699 | 2.6 |

This is the single most important number in the project. A 2% edge — a *very* good professional
result — needs ~67 NFL seasons of straight bets to prove by win/loss alone. Therefore:

1. Validation cannot rely on P&L. It must rely on **CLV** and on **many bets per season** (props and
   parlays provide volume that sides cannot).
2. The competition must score **risk-adjusted, correlation-adjusted, CLV-weighted** performance
   with shrinkage, not raw profit (see `04-competition.md`).
3. Anyone selling a 5%+ straight-bet edge off one season of results is selling luck.

## 5. Result of the battery

18 pre-specified strategies, 2012–2021, 2,945 games (`data/validation.json`):

| Gate | Strategies passing |
|---|---|
| G1 sample size | 16 / 18 |
| G2 significance (BH-corrected, profitable direction) | 0 / 18 |
| G3 out of sample | 2 / 18 |
| G4 robustness at −115 | 1 / 18 |
| G5 economic edge / CLV | 4 / 18 |
| G6 risk | 2 / 18 |
| G7 inputs available | 18 / 18 |
| G8 selection-bias corrected | **0 / 18** |

**No strategy passed all eight gates.** Two are worth naming because they came closest and are the
only ones on the Flagged-for-Review list as "watch, do not fund":

* **S12 — Over the lowest-decile totals (opening line):** n = 226, ROI **+5.79%**, OOS +6.10%,
  survives −115 (+3.69%), but n is below the 300-bet floor, p = 0.349, and DSR = 0.33. It fails G1,
  G2 and G8 — i.e. it is the kind of result that a p-value hunt would promote and that a second
  season would probably erase.
* **S11 — Under the highest-decile totals:** n = 301, ROI +0.91%, OOS +3.28%, CLV **+0.79 pts**
  (the largest CLV in the battery), but p = 0.868 and it does not survive −115 (−1.16%).

And one result is significant in the **wrong direction**, which is itself a finding:

* **S01 / S17 — model edge vs the closing line:** ROI −10.9% and −9.7%, p < 0.001, q < 0.01. The
  model's disagreements with the market are *anti-informative*: the market is right and the model
  is wrong, consistently enough to be statistically detectable. Fading the model would have been
  profitable, but that inversion is an ex-post idea and is therefore logged as a **new trial**
  needing its own out-of-sample test — not published as a strategy (see Flagged for Review, F-03).
