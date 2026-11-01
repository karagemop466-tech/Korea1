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
