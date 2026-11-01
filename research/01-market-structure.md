# 01 — Market structure: what you actually pay, verified

Everything in this file is either (a) read from an official source, or (b) computed by a script in
this repository from the archive named. Nothing is a rule of thumb from memory.

## 1. The measured cost of a bet (computed, 2011–2021)

From 2,941 archived closing moneylines (`scripts/04_correlations.py`):

| Quantity | Value | Meaning |
|---|---|---|
| Mean overround | **3.79%** | implied home + implied away − 1, averaged over every game |
| Median overround | 3.78% | |
| 10th percentile | 3.06% | the cheapest games in the sample |
| 90th percentile | 4.55% | |
| Break-even win rate at −110 | **52.38%** | 110 / 210 |

A flat bettor who wins exactly half their spread bets loses **4.55%** of stake per bet at −110. That
is the baseline every strategy in this project must clear, and it is the number the "no strategy
passed" result has to be read against.

**Source:** `SBR-10Y` (third-party archive), recomputed in `scripts/04_correlations.py`;
output in `data/correlations.json` → `market_margin`.

## 2. The official cost of a bet (regulator data)

The Nevada Gaming Control Board publishes actual win percentages per betting product. Statewide,
all nonrestricted locations, **November 2025 monthly revenue report**:

| Product | Win % (month) | Win % (12 months) |
|---|---|---|
| Sports Pool (all sports, straight bets) | 8.02% | **6.74%** |
| Sports — Football | 9.19% | **6.14%** |
| Sports — Mobile | 7.17% | 6.41% |
| **Sports Parlay Cards** | 45.14% | **19.94%** |

**Source:** `NVGCB-NOV2025` — https://www.gaming.nv.gov/siteassets/content/about/gaming-revenue/november-2025-monthly-revenue-report.pdf
(Statewide — All Nonrestricted Locations table, fetched 2026-11-01).

Three things follow, and they are the backbone of this project:

1. **Straight betting holds ~6–7%** over a year in the most mature regulated market in the world —
   close to the 3.8% *price* margin plus parlay and teaser mix. Any strategy claiming a steady 10%
   ROI on straight bets is claiming to beat the sharpest market in the sport by a factor of two.
2. **Parlay cards hold ~20%**, roughly three times the straight-bet hold. Combining legs is not a
   path to higher expected value; it is a path to a higher house edge, unless the combination is
   priced on *correlated* legs the book has mis-modelled.
3. The monthly win percentages swing violently (parlay cards were 45.14% in November 2025 alone).
   **Monthly hold is dominated by luck.** That is the same statistical fact that governs any
   leaderboard, and it is why the competition design in `04-competition.md` scores on
   risk-adjusted, closing-line-based measures rather than on raw profit.

## 3. Is the NFL market beatable?

The prior is set by the literature, not by hope:

* Gray & Gray (1997) found probit-based NFL betting strategies that were significant in-sample and
  only partly confirmed out-of-sample, and concluded that NFL inefficiencies **dissipate over time**
  (`PAPER-GRAY`).
* Levitt (2004) shows bookmakers in the NFL take positions rather than purely balancing the book,
  which is *why* closing lines carry information a naive model does not (`PAPER-LEVITT`).

This project's own evidence points the same way:

* A full walk-forward model (Elo + pace) is **worse** than the closing line, not better:
  spread MAE **10.47** vs market **10.15**; straight-up accuracy **66.4%** vs **67.3%**.
* Of 18 pre-specified strategies, **none** cleared the full validation gate set
  (`data/validation.json`), and several failed in the *negative* direction, i.e. they lose more
  than the vig.

## 4. Where the favourite-longshot bias actually shows up (measured)

No-vig implied probability vs realised win rate, by closing moneyline bucket, 2011–2021
(`data/correlations.json` → `market_margin.price_bucket_calibration`):

| Closing price bucket | n | mean no-vig implied | realised win rate | gap |
|---|---|---|---|---|
| shorter than −400 | 484 | 82.78% | 83.26% | +0.49 pts |
| −400 to −250 | 716 | 73.02% | 75.84% | +2.82 pts |
| −250 to −150 | 1,023 | 63.46% | 60.12% | −3.34 pts |
| −150 to −110 | 686 | 54.85% | 53.50% | −1.35 pts |
| −110 to +110 | 312 | 48.14% | 48.40% | +0.26 pts |
| +110 to +150 | 687 | 42.50% | 45.71% | +3.21 pts |
| +150 to +250 | 1,053 | 33.76% | 34.76% | +1.00 pts |
| +250 to +400 | 605 | 24.24% | **21.16%** | **−3.08 pts** |
| longer than +400 | 316 | 15.13% | **13.92%** | **−1.21 pts** |

Read it carefully:

* At the **extreme longshot end** the market overprices the underdog — the classic
  favourite-longshot bias, and the only place in this table where a systematic gap of ~3 points
  appears in a consistent direction.
* The two positive gaps inside the mid-range (+110 to +150, and −400 to −250) are **not** a
  discovered edge: they are two buckets out of nine, no correction for multiple comparisons, and
  the strategies that bet those buckets (S13, S14) still lost money after the vig
  (−8.9% and −8.0% ROI respectively). That is exactly the trap the gates exist to catch.

## 5. What this means for the project

1. The only credible skill measurement is **beating the closing line**, not beating the season's
   P&L (see `02-methodology.md` §4).
2. Parlays must be justified by **measured correlation**, and the prize is the mispricing of
   correlated legs — not the multiplication of prices (`03-validation-gates.md`, `data/props.json`).
3. Any leaderboard that ranks on raw season profit will be won by luck: in a 1,000-bettor field
   with **zero** skill, the winner's median ROI over a 267-bet season is **+18.7%**
   (`data/validation.json` → `luck.leaderboard_simulation_zero_skill`). Any competition design that
   ignores this is a lottery with extra steps (`04-competition.md`).
