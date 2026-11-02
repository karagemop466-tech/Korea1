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
   build reaches the same conclusion from the other direction with White's Reality Check, p = 0.144.
4. **Closing-line value is the skill-bearing statistic; ROI is not.** In a 20,000-trial mixed field of
   999 zero-skill bettors plus one genuinely skilled bettor, the skilled bettor ranks first 78.9% of the
   time on CLV and 0.3% of the time on ROI.

Where the two builds disagree, the archives disagree, and that is flagged rather than reconciled: the
annex measures a mean 3.79% overround against {{spread_hold}} here — each is correct for its own price
archive.

**Correction (2026-11-02, session `arena/fb363967-korea1`).** An earlier revision of this section cited
"White's Reality Check (p = 0.970)" for the annex. No annex artefact contains that number: the annex
pipeline never computes a White's Reality Check (it gates on its own eight criteria plus a max-Sharpe
luck simulation), so the figure had no source and has been removed rather than restated. The verified
annex numbers are the rank correlation (0.485), the expected best Sharpe of pure luck (0.093) and the
mixed-field CLV/ROI split (0.789 / 0.003), all in `data/lab/validation.json`.
