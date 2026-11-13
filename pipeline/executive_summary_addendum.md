---

## Annex: independent replication on a second odds archive

A second build in this repository (`arena/ea02c4fb-korea1`, published at [`lab/`](lab/index.html))
answered the same four questions from a **different** source — the Sportsbook Review 10-year archive,
2011–2021, 2,945 games, 2,280 priced bets — with separate code (`scripts/`) and its own verifiers.
Its long form is [`research/05-annex-executive-summary.md`](research/05-annex-executive-summary.md).

Four findings replicate independently, which is the strongest evidence in this repository:

1. **No strategy passes every gate** in any build (annex 0 of 18; the earlier retained build 0 of 24;
   this build 0 of 18, and its best candidate fails the false-discovery-rate gate).
2. **The originated line does not beat the market** — annex spread MAE 10.473 against 10.151 for the
   close, and it loses on totals (10.861 vs 10.604) and straight-up (66.4% vs 67.3%) as well; this
   build is 10.527 against 10.216.
3. **Most apparent edge is luck.** The annex's in-sample → out-of-sample ROI rank correlation is 0.485
   while the expected best Sharpe of 18 zero-skill trials is 0.093 (`data/lab/validation.json`); this
   build reaches the same conclusion from the other direction with White's Reality Check, p = 0.186 (0.144 before the fold-safe weather fill, which moved 19 tickets and no verdict).
4. **Closing-line value is the skill-bearing statistic; ROI is not.** In a 20,000-trial mixed field of
   999 zero-skill bettors plus one genuinely skilled bettor, the skilled bettor ranks first 78.9% of the
   time on CLV and 0.3% of the time on ROI.

Where the two builds disagree, the archives disagree, and that is flagged rather than reconciled: the
annex measures a mean 3.79% overround against 2.70% here (the mean, across the 5,403 priced games in
`data/processed/games_model.csv`, of both sides’ implied probability minus 1; median 2.42%) — each
figure is correct for its own price archive.

## Independent repo audit — 2026-11-13 (session `arena/d58198fc-korea1`)

A second, self-contained audit re-derived every published number from the artifact that is supposed to
support it, re-read every official page the site cites, and ranked all 22 proposals on one scale. It edits
no published page; its output is the `review/` sub-site.

| Result | Count | What it means |
|---|---|---|
| Claims re-derived | 45 | one row per published number, each with its evidence file |
| Confirmed exactly | 36 | recomputed value = published value |
| Flagged (drift) | 3 | published text and repository artifact disagree; both values shown |
| Undecidable | 1 | left blank, never estimated |
| Official pages re-read | 11 of 12 | page-fetch captures in `data/repo_audit/captures/` |

**The flags.** (1) The repository's own reproducibility baseline (`data/processed/audit_digests.csv`)
fails on **34 of 50** recorded digests, including `strategy_bets.csv` (26,149 recorded rows,
27,218 now) and `verification_report.csv` (13 pages, now 33). (2) The `26,149` single-leg ticket figure
recomputes to 26,188 today, with 27,218 graded rows in total. (3) WAS 24 – NYG 21 went final on
2026-11-12, so the Week 10 Thursday game is settled. (4) NFL.com's Week 8 page carries 14 finals while the
post-pin score register lists 13 for Week 8; recorded as an observation. One earlier finding — the
depth-chart coverage text — was corrected by a parallel session while this audit ran and now reads 31 of 32.

**What the official re-read confirmed.** All 28 Week 8–9 score rows, all 20 WAS/NYG injury-report rows,
89 of 89 ordered club depth-chart cells, the T-90 inactive-list rule on `operations.nfl.com`, the operator
parlay push rule, and both primary statistics references (White 2000; Bailey & López de Prado 2014) still
say exactly what the site says they say. **Zero official pages were contradicted.**

**One number that changes the plan.** A half-point starter effect needs about **2,479 team-games** — more
than four full seasons — before a test could distinguish it from noise at 80% power, and a 0.20 leg
correlation needs about 6.1 seasons of paired observations. That is the quantitative reason the injury
signal is not priced and the leaderboard stays empty; it is not caution for its own sake.

**Read it at** `review/index.html` (overview), `review/claims.html` (line-by-line claim check),
`review/suggestions.html` (ranked decision matrix and a six-step recommended sequence),
`review/injuries.html`, `review/questions.html`, `review/official-sources.html`,
`review/flagged.html` (the flags plus every stale digest, for your review after the site is live).
Reproduce with `make audit`. Nothing flagged here blocks publication.
