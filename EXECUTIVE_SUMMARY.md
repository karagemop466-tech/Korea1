# Executive summary — K1 NFL Line Lab

**Session:** `arena-a1970463` · **Branch:** `arena/a1970463-korea1` · **Date:** 2026-11-01
**Live site:** GitHub Pages from `main` / `docs` (see `COORDINATION.md` for the deploy record)

---

## 1. What was asked for, and what exists now

| Requirement | Delivered as | Where |
|---|---|---|
| Originate my own NFL lines | Walk-forward ridge power-rating model producing a spread and a total for every game 1999–2026, benchmarked against the closing market | `analysis/model.py` · site **Originated lines** |
| Research strategies + generate useful signals | 24 fully specified, reproducible strategies (spread, total, moneyline, model-edge) with hypotheses and sources | `analysis/signals.py` · site **Strategy board** |
| Treat it as a leaderboard with rewards | Tier system (A/B/C/F/X) + disclosed 0–100 score + reward ladder | site **Validation** |
| Single bets | Every strategy priced one-unit-at-a-time on real two-sided closing quotes | site **Strategy board** |
| Parlays | Measured correlation values and pricing maths for same-game and cross-game parlays, incl. the parlay tax | `analysis/parlays.py` · site **Correlation & parlays** |
| Player-prop combos | Player-game stats rebuilt from the official NFL game feed; prop correlations, combo pricing framework, calibration | `analysis/build_players.py`, `analysis/props.py` · site **Player props** |
| Validation gates | 8 explicit gates, false-discovery-rate control, White's Reality Check, out-of-sample split, stability tests | site **Validation** |
| Determine correlation values | phi between every pair of leg types, measured on 6,880 settled games; prop correlations on 1,088 team-games | sites **Correlation** / **Props** |
| Remove luck / selectively skill-based | De-vigged-expectation z (primary), block bootstrap, FDR, Reality Check, walk-forward selection portfolio | site **Validation** |
| Executive summary | this file | repo root |
| GitHub Pages site, per-category subpages, tables, analysis | 9-page static dashboard, dependency-free, every row source-linked | `docs/` |
| Line-by-line verification, official sources, flag irregularities | 7 live official checks + 100%-row automated checks + 7 published irregularities | site **Verification** / **Flagged for review** |
| No manual input | one command: `python -m analysis.run_all` | `analysis/run_all.py` |

---

## 2. Headline result

**No strategy in this library survives all eight validation gates.** That is the finding, not a
shortfall of the exercise.

- 24 strategies · 27,330 priced bets · 2006–2026 · every bet settled at the two-sided closing quote
  stored upstream (never an assumed −110).
- Best raw ROI: **S07 "wind ≥ 15 mph unders"**, **+7.14%** per bet over 430 bets
  (95% block-bootstrap CI −1.7% … +16.7%; luck-adjusted z = +1.88; train +8.3%, test +5.8%).
  It passes 7 of 8 gates and fails the false-discovery-rate gate.
- **Benjamini–Hochberg FDR (q = 0.10): 0 of 24 strategies rejected.** **White's Reality Check:
  p = 0.970** — the best-of-24 result is indistinguishable from luck.
- Negative control behaves correctly: the deliberate long-shot moneyline arm returns **−8.9%**
  with a negative z, which is what a well-calibrated lab must produce.

**Interpretation.** The NFL closing market is efficient against signals that can be built from
public game-level data. Anything that claims otherwise at these sample sizes is either a data
artefact or a multiple-testing accident. The lab is built to say so.

---

## 3. Originated lines

| Metric | K1 model | Closing market |
|---|---|---|
| Spread MAE vs actual result | 10.646 pts | **10.243 pts** |
| Spread RMSE | 13.677 | **13.160** |
| Total MAE vs actual result | 11.266 pts | **10.620 pts** |
| Total RMSE | 14.341 | **13.412** |
| Games where K1 is closer than the close | 45.4% | — |
| Correlation with the closing spread | 0.796 | — |
| Correlation with the closing total | 0.629 | — |

The model is a legitimate originator (spread error is within ~0.4 points of the market's) but it
is **not** an edge: regressing cover outcomes on the model-vs-market disagreement gives an
out-of-sample slope of **−0.0011** (train −0.0092), i.e. no exploitable information. Out-of-sample
log-loss 0.69298 vs 0.69315 for a coin flip — real, but worthless at −110.

Week 8 (13 unplayed games) and Week 9 (15 games) boards are published with my line, the market
line, the edge and links to the official nfl.com and ESPN pages for each game.

---

## 4. Correlation values (measured, not assumed)

Settled games with two-sided prices (n = 6,880):

| Pair | phi | Reading |
|---|---|---|
| Home ATS × Home ML | **+0.672** | one bet, not two — never stack these as independent risk |
| Home ATS × Away ML | −0.672 | mirror image |
| Home ATS × Over | **+0.014** | effectively independent |
| Over × Home ML | +0.0006 | independent |

Player props (2024–2025, 1,088 team-games, lines at each player's trailing mean):

| Pair | phi |
|---|---|
| QB pass yards × WR1 receiving yards | **+0.249** |
| QB pass yards × team total over | **+0.226** |
| WR1 receiving yards × team total over | +0.145 |
| RB rush yards × team total over | +0.118 |
| QB pass yards × RB rush yards | −0.028 |

**Parlay economics.** Because games are independent, cross-game parlays get no correlation discount:
measured mean EV is **−7.9%** for 2 legs, **−14.4%** for 3 and **−15.4%** for 4. Same-game legs are
where correlation actually lives, and books price that correlation explicitly — which is why the
same-game table is presented as a measure of dependence, never as free money.

---

## 5. Player-prop layer: what is real and what is missing

- Player-game stats were rebuilt from the official NFL Game Center feed (570 game files, 11,202
  player-game rows) using nflverse's published stat-id mapping. Validation: league averages of
  **229.5 passing yards, 118.6 rushing yards, 21.0 receptions, 2.43 offensive TDs per team-game** —
  all inside the published NFL ranges.
- The prop model's intervals were tested out of sample. The naive four-game SD is overconfident
  (80% intervals cover only ~66%). Refitting dispersion walk-forward (`var = a·mean + b·mean²` on
  the previous season only) restores coverage to **79.1% / 75.2% / 79.9%** for QB / RB / WR.
- **Prop ROI is not claimed.** No verifiable historical prop prices are reachable from this
  environment; that gate is *blocked*, published as such, and logged as IR-03.

---

## 6. Luck-removal methodology (why the conclusion is credible)

1. **De-vigged expectation.** Each bet's own two-way price implies a fair win probability; observed
   wins are compared with the sum of those probabilities (Poisson-binomial z). This is immune to
   "it just picked favourites" — the failure mode of naive ROI ranking.
2. **Block bootstrap on weeks.** Confidence intervals respect within-week dependence.
3. **Multiplicity control.** Benjamini–Hochberg across all 24 strategies plus a stationary-bootstrap
   White Reality Check on the maximum.
4. **Out-of-sample split.** Fitted on 2006–2015, scored on 2016–2026, with retention measured.
5. **Stability.** Season hit rate, profit concentration, worst leave-one-season-out ROI, split-half.
6. **Walk-forward selection portfolio.** Each season funds only strategies credentialled on prior
   seasons. Result: **−3.3%** selected vs **−1.9%** betting everything, 5/18 positive seasons —
   selection added noise. Published rather than hidden.

---

## 7. Verification and irregularities

- **7/7 live official cross-checks passed, 0 mismatches** (nfl.com Week 9 schedule 15/15 games and
  byes; ESPN standings sample; ESPN event payload for 2026 W8 CAR@GB; pinned upstream commits;
  nflverse stat mapping; ESPN URL pattern for per-row links).
- **100% of rows** pass automated checks: `result = home − away` (7,384/7,384),
  `total = home + away` (7,384/7,384), zero duplicate ids, and standings recomputed from results
  match the upstream standings file for **800 team-seasons with 0 mismatches**.
- **7 irregularities published** (not silently fixed): unspecified book behind the closing lines
  (IR-01), two upstream line files disagreeing on 33% of spreads (IR-02), no verifiable prop prices
  (IR-03), player data ending in Feb 2026 (IR-04), venue naming mismatch (IR-05), opening lines for
  one season only (IR-06), partial Week 8 snapshot (IR-07).

Every published row links to an official page (ESPN game page / nfl.com schedule) or to the pinned
upstream file. Nothing on the site is typed by hand; every number regenerates.

---

## 8. What I would build next (in priority order)

1. **Prop prices.** The prop layer is the only place with measured structure and no market to test
   against. A verified prop-line history unlocks an actual backtest; the correlation and calibration
   work is already done and does not need redoing.
2. **Injury and lineup data.** The single largest missing input; the model's residual variance is
   dominated by information it cannot see.
3. **Full opening-line history.** Line movement is the most credible practitioner signal and is
   testable only for one season in these sources (IR-06).
4. **A better allocator.** The walk-forward selector failed; a shrinkage/Bayesian allocator that
   shrinks each strategy toward zero edge is the natural next test, using the published baseline
   (all-strategies −1.9%) as the bar.

---

## 9. Reproduce

```bash
git clone https://github.com/karagemop466-tech/Korea1 && cd Korea1
pip install -r requirements.txt
python -m analysis.run_all     # ~4 min: fetch → build → model → backtest → verify → site
pytest -q tests                # look-ahead / leak tests
```

Raw data is git-ignored and re-staged from pinned commits on every run, so a fresh clone reproduces
identical numbers. Site output is committed under `docs/` and served by GitHub Pages.

---

# Appendix — parallel draft merged from `origin/main` (not used, kept for provenance)

Authored by session `arena/7eec67cb-korea1`. Its framework headings (validation gates, "luck removal",
leaderboard) are the same problem statement this branch solves with measured numbers, but **every
coefficient and threshold below is a third-party claim that this pipeline does not use**: the YoY
correlation ranges (EPA 0.55–0.65, ATS% −0.05, …) are not reproducible from the bundled data and are
flagged on the site as unverified. The measured replacements are in the tables above. Retained verbatim so
the provenance of those numbers is auditable.

# Executive Summary: NFL Line Origination & Strategy Leaderboard

## Project Overview
This project collects, organizes, and analyzes NFL betting lines to originate proprietary signals. The framework operates as a leaderboard competition rewarding top-performing strategies across single bets, parlays, and player prop bet combos. All strategies pass validation gates, correlation analysis removes luck, and skill-based signals are isolated.

## Core Components

### 1. Strategy Categories
- **Single Bet Strategies**: Point spread, moneyline, totals (over/under)
- **Parlay Strategies**: Correlated outcomes, game script alignment, risk/reward optimization
- **Player Prop Bet Combos**: Individual performance metrics, target share correlations, air yards analysis

### 2. Validation Gates
- **Statistical Significance**: Minimum 3-season backtesting (200+ qualifying games) [3](https://nflbettingsystems.com/)
- **Correlation Threshold**: Skill-based metrics ≥ 0.45 YoY correlation [2](https://nflanalytic.com/betting-regression.html)
- **Out-of-Sample Testing**: Build on in-sample seasons, test on unseen data [3](https://nflbettingsystems.com/)
- **Closing Line Value (CLV)**: Consistent beating of closing line, not just opening [3](https://nflbettingsystems.com/)
- **Multiple Hypothesis Correction**: Significance threshold adjustment for filter testing [3](https://nflbettingsystems.com/)

### 3. Skill-Based Signal Isolation (Luck Removal)
**Stable Statistics (Skill-Driven) with YoY Correlation:**
- EPA per Play: ~0.55-0.65 [2](https://nflanalytic.com/betting-regression.html)
- Success Rate: ~0.50-0.60 [2](https://nflanalytic.com/betting-regression.html)
- Yards per Play: ~0.45-0.55 [2](https://nflanalytic.com/betting-regression.html)
- Pass Block Win Rate: ~0.50+ [2](https://nflanalytic.com/betting-regression.html)
- Completion % Over Expected: ~0.45-0.55 [2](https://nflanalytic.com/betting-regression.html)

**Luck-Driven Metrics (Low Correlation - Filter Out):**
- Team Cover Rate (ATS%): -0.05 YoY correlation [2](https://nflanalytic.com/betting-regression.html)
- Wins: 0.32 YoY correlation [2](https://nflanalytic.com/betting-regression.html)
- Point Differential: 0.40 YoY correlation [2](https://nflanalytic.com/betting-regression.html)
- Turnovers: ~0.20 correlation [2](https://nflanalytic.com/betting-regression.html)

### 4. Official Data Sources
- **NFL Next Gen Stats**: Player tracking, air yards, completion % over expectation [1](https://nextgenstats.nfl.com/stats/passing/2025/REG/3) [4](https://ar5iv.labs.arxiv.org/html/1906.03339) [5](https://www.covers.com/nfl/key-advanced-metrics-betting-tips)
- **NFL Official Gamebooks**: Raw play-by-play data, formation diagrams, pressure moments [2](https://surehandstransportation.com/2026/04/27/the-best-historical-data-sources-for-nfl-player-props/)
- **Pro Football Reference**: Historical game logs, seasonal stats [1](https://rg.org/guides/football/betting-lines) [3](https://nflbettingsystems.com/) [4](https://www.kaggle.com/tobycrabtree/nfl-scores-and-betting-data/home)
- **NFL.com Official**: Betting lines, odds, market movement [1](https://rg.org/guides/football/betting-lines) [4](https://www.kaggle.com/tobycrabtree/nfl-scores-and-betting-data/home)

### 5. Leaderboard Competition Framework
- **Reward Structure**: Top-performing strategies receive recognition based on CLV and validation gate compliance
- **Performance Metrics**: Closing line beat rate, correlation strength, skill-signal isolation purity
- **Category Separation**: Single bets, parlays, and player props compete in distinct leaderboards
- **Continuous Validation**: Real-time monitoring against official sources [1](https://rg.org/guides/football/betting-lines)

### 6. Correlation Analysis Methodology
- **Game Script Correlation**: Underdog + Under (slower pace, fewer points) [5](https://www.mybookie.ag/sports-betting-guide/popular-nfl-strategies-theories/)
- **Favorite + Over**: Blowout potential increases scoring volume [5](https://www.mybookie.ag/sports-betting-guide/popular-nfl-strategies-theories/)
- **Air Yards vs Production**: Volume metric indicator, regression to career average [5](https://www.covers.com/nfl/key-advanced-metrics-betting-tips)
- **Target Share Correlation**: Spike identification for prop patterns [2](https://surehandstransportation.com/2026/04/27/the-best-historical-data-sources-for-nfl-player-props/)

### 7. Verification Protocol
- Line-by-line verification from official sources only
- Blank values for unconfirmed data with "unverified" flags
- Source links provided for every table row
- No inferences or hallucinations
- Manual review links included for all findings

## Implementation Status
- **Repository**: karagemop466-tech/Korea1 (branch: arena/7eec67cb-korea1)
- **Coordination**: COORDINATION.md established with task board [Integration Session]
- **Site Creation**: GitHub Pages dashboard with categorized subpages
- **Verification**: Official NFL.com, Next Gen Stats, Pro Football Reference sources [1](https://rg.org/guides/football/betting-lines) [2](https://nflanalytic.com/betting-regression.html) [3](https://nflbettingsystems.com/) [4](https://www.kaggle.com/tobycrabtree/nfl-scores-and-betting-data/home) [5](https://www.mybookie.ag/sports-betting-guide/popular-nfl-strategies-theories/)

## Flagged Irregularities (For Review)
- **Approximate Correlation Values**: Public play-by-play research values (~0.55-0.65 for EPA) cannot be recomputed from bundled game logs [2](https://nflanalytic.com/betting-regression.html)
- **Prop Pattern Correlation**: Spike identification methodology requires gamebook CSV import [2](https://surehandstransportation.com/2026/04/27/the-best-historical-data-sources-for-nfl-player-props/)
- **CPOE Replication**: Proprietary formula prevents exact replication; public version correlates r^2=0.88 [5](https://www.covers.com/nfl/key-advanced-metrics-betting-tips)

## Next Steps
1. Populate category-specific subpages with strategy tables
2. Complete line-by-line verification with official source links
3. Build GitHub Pages dashboard UI
4. Final integration, PR creation, and deployment
5. Publish Flagged for Review page with irregularities

---

## Annex: independent replication on a second odds archive

A second session (`arena/ea02c4fb-korea1`) built the same four questions from a **different** data source —
the Sportsbook Review 10-year archive, 2011–2021, 2,945 games, 2,280 priced bets — with entirely separate
code (`scripts/`). It is published at [`lab/`](lab/index.html) and summarised in
[`research/05-annex-executive-summary.md`](research/05-annex-executive-summary.md).

Four findings replicate independently, which is the strongest evidence in this repository:

1. **No strategy passes every gate** in either build (annex: 0 of 18; here: 0 of 24).
2. **The originated line does not beat the market** (annex spread MAE 10.473 vs market 10.151; the annex
   model also loses on totals and straight-up).
3. **Most apparent edge is luck.** Annex in-sample → out-of-sample ROI rank correlation is 0.485, while the
   best of 18 zero-skill trials has an expected Sharpe of 0.093 — the same conclusion the Reality Check
   reaches here from the other direction.
4. **Closing-line value is the skill-bearing statistic, ROI is not.** In a 20,000-trial mixed field of 999
   zero-skill bettors plus one genuinely skilled bettor, the skilled bettor ranks first 78.9% of the time on
   CLV but only 0.32% of the time on ROI.

Where the two builds disagree, it is because the archives disagree, and that is flagged rather than
reconciled: the annex measures a mean 3.79% overround against 2.70% here (IR-09 in `COORDINATION.md`).

---
**Sources:**
[1](https://rg.org/guides/football/betting-lines) Navigating NFL Betting Lines: Tips and Insights for Smart Bets - Sports Betting Guide - RG (2026-06-28)
[2](https://nflanalytic.com/betting-regression.html) Regression Analysis for NFL Betting (2026-09-05)
[3](https://nflbettingsystems.com/) NFL Betting Systems: Data-Backed Strategies That Actually Work (2026) (2026-06-17)
[4](https://www.kaggle.com/tobycrabtree/nfl-scores-and-betting-data/home) NFL scores and betting data (2023-02-14)
[5](https://www.mybookie.ag/sports-betting-guide/popular-nfl-strategies-theories/) Popular NFL Betting Strategies: How to Find Value, Beat the Lines, and Win Consistently (2026-10-05)
[6](https://nextgenstats.nfl.com/stats/passing/2025/REG/3) Passing Stats - NFL Next Gen Stats (2026)
[7](https://surehandstransportation.com/2026/04/27/the-best-historical-data-sources-for-nfl-player-props/) The Best Historical Data Sources for NFL Player Props (2026-04-27)
[8](https://bestbetfornfl.com/articles/nfl-stats-betting-analysis/) NFL Stats for Betting: Advanced Metrics That Predict Outcomes (2026-09-04)
[9](https://ar5iv.labs.arxiv.org/html/1906.03339) next-gen-scraPy: Extracting NFL Tracking Data from Images (2024-03-02)
[10](https://www.covers.com/nfl/key-advanced-metrics-betting-tips) NFL Advanced Metrics and Stats: DVOA, EPA, CPOE, aDOT & More (2026-08-31)
