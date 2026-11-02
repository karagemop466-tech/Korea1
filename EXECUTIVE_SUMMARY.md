# Executive summary — NFL Line Lab

*Generated from the pipeline output on 2026-11-02T17:26:06Z · upstream commit `a270278f3ac4` ·
reproduce with `make build`.*

## The question

Can we originate our own NFL lines, and build betting strategies that beat the market for
reasons other than luck?

## The answer, in one paragraph

The pipeline produces a defensible, market-free NFL line — within about a third of a point of the
closing line on both the spread and the total — but that gap is decisive. Once every strategy is
forced through power, multiple-testing, bootstrap and deflated-Sharpe gates, the apparent winners
dissolve. **0 of 18 strategies clear all eight gates**, and White's reality check
across the whole library returns **p = 0.144**, which does not
reject the hypothesis that the best result is luck. The deliverable is therefore the machinery that
can tell the difference — plus a documented list of exactly which data would be needed to go
further.

## Key numbers

| Quantity | Value | Source |
|---|---|---|
| Games with an out-of-sample line | 6,073 (2004–2026, of 7,384 played) | `games.csv` |
| Closing-line spread MAE | 10.2155 | `games.csv` |
| Our spread MAE | 10.5272 | `pipeline/models.py` |
| Closing-line total MAE | 10.5273 | `games.csv` |
| Our total MAE | 10.7267 | `pipeline/models.py` |
| Bets simulated | 26,168 | `strategy_bets.csv` |
| Strategies tested | 18 | `strategy_gates.csv` |
| Strategies validated as skill | 0 | `strategy_gates.csv` |
| Best raw ROI | 21.6% (PARLAY3_EDGE, 377 tickets) | `strategy_summary.csv` |
| Reality-check p-value | 0.144 | `reality_check.json` |
| Mean two-way hold, spreads | 2.72% | `vig_by_season.csv` |
| Same-game φ, cover ↔ moneyline | 0.676 | `corr_same_game.csv` |
| Same-game φ, cover ↔ total | 0.024 | `corr_same_game.csv` |
| Cross-game r, margin / total | 0.011 / 0.008 | `corr_cross_game.csv` |
| Player-games aggregated (props) | 21,033 (2019–2022) | `prop_player_games.csv` |
| Prop definitions verified | 7/7 player-seasons exact | `prop_definition_validation.csv` |
| Prop forecast AUC, 4 markets | 0.66–0.73 | `prop_skill.csv` |
| Prop leg correlation, φ range | -0.066 to 0.580 | `prop_combos.csv` |
| Largest same-game lift | 1.446× (Receptions ↔ rec yds (same player)) | `prop_combos.csv` |
| Prop combos awarded | 0 — G6 cannot pass without prop prices | `prop_gates.csv` |

## What was built

1. **Data layer.** One pinned commit of `nflverse/nfldata`, archived from `codeload.github.com`
   and SHA-256 hashed on arrival into `data/sources.json`. 7,548 schedule rows, 7,384 played games
   1999–2026, plus an independent per-side price file used to cross-check settlement.
2. **Line origination.** Three model families — weighted ridge on pre-game structure, matchup
   expected points, Elo — fitted walk-forward and averaged with fixed weights. No model sees a
   price; none sees anything after kickoff. Both facts are asserted in code.
3. **Strategy library.** 18 pre-declared strategies (single bets, 2- and 3-leg parlays,
   classic angle rules), one unit per bet at the recorded closing price, pushes refunded, no `-110`
   substitution and no line shopping.
4. **Validation.** Eight gates: data integrity, leakage, power, significance with FDR control,
   bootstrap + deflated Sharpe, economic significance, stability, redundancy.
5. **Site.** A static dashboard where every table row links to its source file, plus a
   Flagged-for-Review page.

## Findings

**1 — The market is still better than the model.** 10.2155 vs
10.5272 on spreads and 10.5273 vs
10.7267 on totals. The gap is roughly the width of the vig, which is why
nothing below gets paid. It is the value of injury reports, starting-quarterback news and sharp
money, none of which the model is allowed to see.

**2 — Nothing survives validation.** 0 of 18 strategies pass. The best raw ROI is
21.6% on 377 tickets (PARLAY3_EDGE) — a high-variance long-shot ladder
whose win rate is 17.5%. Its FDR-adjusted p-value is
0.357 and its deflated Sharpe is
0.415: not an edge.

**3 — The library as a whole cannot beat luck.** White's reality check p =
0.144 over 18 strategies and
425 weekly blocks.

**4 — Power is the binding constraint, not the model.** Detecting a true 1% per-bet edge at 80%
power needs about 78,000 bets — roughly 290 NFL seasons. At 5% it needs about 3,100 bets, or twelve
seasons. Most published betting edges are under-powered noise; the gates are calibrated to say so.

**5 — Correlation is measurable, and it is not symmetric.** Same-game cover ↔ moneyline has
φ = 0.676: near-duplicate legs. Cover ↔ total is φ =
0.024: close to independent. Cross-game legs are independent
(r = 0.011, interval spans zero), which is why an ordinary parlay can
be priced by multiplication but a same-game parlay cannot.

**6 — The pricing environment is sharp.** Mean two-way hold in the closing prices is
2.72% on spreads and 2.93% on
totals — a low-margin book, so break-even is about 51.4%, not 52.4%.

## Player props: what the extra data bought

Player-level play-by-play was fetched for 2019–2022 (67.9 MB, four pinned blobs) after an earlier
build wrongly recorded it as unreachable. That unlocks the prop module:

- **21,033 player-games** aggregated into passing, rushing and receiving yards
  and receptions. Seven published season totals — Brady 5316
  passing yards, Kupp 145
  receptions, Taylor 1811 rushing yards —
  are reproduced exactly, keyed on player id (a name key silently merged J.Taylor of New England
  into J.Taylor of Indianapolis).
- **9,730 originated prop lines**, walk-forward, no market input. Out of sample the
  AUC is 0.66–0.73, so the lines rank players well above
  chance; the calibration slope is only 0.14–0.23
  against 1.0, so the probabilities are compressed and should not be used as prices.
- **Prop legs are measurably dependent.** QB passing yards with his own WR1's receiving yards lift
  the joint hit rate 1.136× over independence, and receptions with the same player's
  receiving yards lift it 1.446×. Two WR1 legs from unrelated games give
  φ = -0.036 with an interval spanning zero, so the estimator does not manufacture
  dependence.
- **Nothing is awarded.** No reachable source carries a player-prop price, so gate G6 cannot be
  assessed and all 7 combos are withheld. The correlation is the finding; the ROI
  would be an invention.

## Decisions that shaped the result

- **Bet the close, not the opener.** Multi-season openers do not exist in the pinned data, so every
  strategy is measured against the hardest benchmark available. This makes results worse and more
  honest.
- **Declare first, run second.** All strategies were written down before any ran; every result is
  published, including the failures. No threshold was retuned after seeing a result.
- **Correct for the number of tries.** Eighteen strategies tested at p < 0.05 would produce a
  winner about 60% of the time by chance; Benjamini–Hochberg and the deflated Sharpe exist to stop
  exactly that.
- **Never fill a gap.** Player-level props, team-total prices and multi-season openers are not
  available from any reachable source, so they are blank and flagged rather than modelled from
  proxies.

## Verification performed

| Check | Result |
|---|---|
| result == home_score − away_score | 7384/7384 |
| total == home_score + away_score | 7384/7384 |
| game_id uniqueness | 7548 unique of 7548 rows |
| spread sign convention | spread_line>0: home win rate 67.4% n=4795; spread_line<0: 35.3% n=2558 |
| settlement vs independent outcome column | 13,284/13,472 exact (98.605%) |
| site tables with a source link on every row | 100% (enforced by `pipeline/verify_site.py`) |

## Flagged for review

Player-level **statistics** are now retrieved and used (2019–2022 play-by-play, see the props
section above); prop **prices** were not retrievable in this build (nflverse release
assets sit behind a blocked host; mirrors store 132-byte LFS pointers). Multi-season openers do not
exist in the pinned data. The two nflverse price files disagree by a median 0.5 points on about a
third of games, and three 2015 games carry outcome flags that contradict their own score. Full
detail, with sources: `flagged.html`.

## What would change the answer

1. A pre-kickoff injury and starting-quarterback feed — the largest known component of the MAE gap.
2. Prop **prices** (the statistics are now in hand) — turns the measured prop dependence into a
   testable return; without a price, gate G6 stays unanswerable.
3. A multi-season opener feed — unlocks genuine open-to-close CLV analysis instead of close-only.

---

## Annex: independent replication on a second odds archive

A fourth session (`arena/ea02c4fb-korea1`) built the same four questions from a **different** source — the
Sportsbook Review 10-year archive, 2011–2021, 2,945 games, 2,280 priced bets — with separate code
(`scripts/`), published at [`lab/`](lab/index.html) and narrated in
[`research/05-annex-executive-summary.md`](research/05-annex-executive-summary.md).

Four findings replicate independently, which is the strongest evidence in this repository:

1. **No strategy passes every gate** in any build (annex 0 of 18; first build 0 of 24; this build's best
   candidate fails its false-discovery-rate gate).
2. **The originated line does not beat the market** — annex spread MAE 10.473 vs market 10.151, and it also
   loses on totals and straight-up; this build 10.527 vs 10.216.
3. **Most apparent edge is luck.** Annex in-sample → out-of-sample ROI rank correlation is 0.485 while the
   best of 18 zero-skill trials has an expected Sharpe of 0.093 — reached from the other direction here by
   White's Reality Check (p = 0.970).
4. **Closing-line value is the skill-bearing statistic; ROI is not.** In a 20,000-trial mixed field of 999
   zero-skill bettors plus one genuinely skilled bettor, the skilled bettor ranks first 78.9% of the time on
   CLV and 0.32% of the time on ROI.

Where the builds disagree, the archives disagree, and that is flagged rather than reconciled: the annex
measures a mean 3.79% overround against 2.70% here (IR-09).

---

## Independent official-source audit (2026-11-02, session `arena/1642ee06-korea1`)

Full detail: [`audit.html`](audit.html) · data in [`data/audit/`](data/audit/) · scripts `scripts/audit_*.py`.

- **Scores.** 39 games read on NFL.com (2014, 2015, 2016, 2022 and 2026 week pages, plus the three 2015 games
  whose nflverse outcome flag contradicts the score): **31 match the pinned data, 0 mismatch**, 8 are 2026
  week-8 games that NFL.com lists as Final and the pinned snapshot predates (left blank, flagged).
  This is a sample, not a census; games before 2010 (2,913) and playoff games (309) were not checked.
- **Inputs.** All 7 pinned nfldata files re-downloaded from the pinned commit: SHA-256 and byte count match.
  Rebuilding every table from them reproduces the published files byte for byte; `tests/test_no_lookahead.py` 4/4.
- **Official sources.** Of 523 table rows on the ten root pages, 3 link to nfl.com and 516 link only to
  nflverse (a community project). Historical closing lines, totals and prices have **no official NFL source**
  and the upstream data dictionary does not name the sportsbook. These are flagged (IR-T10-01, -02), not blanked.
- **Defect fixed.** `scripts/99_verify.py` V02 failed on every fresh checkout; it now passes (9/9).
- **Does not change the conclusion.** 0 of 18 strategies pass all gates; no figure in this summary was altered.
