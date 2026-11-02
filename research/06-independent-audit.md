# 06 — Independent audit of the published build

*Session `arena/5b3f0799-korea1`, 2026-11-02. This note is the manual-review companion to
[`reproducibility.html`](../reproducibility.html) and [`data/processed/audit.json`](../data/processed/audit.json).*

> **Changed by the 2026-11-02 merge.** The page was first published as `audit.html`; a sibling session
> (T10) published its own official-source audit under that name, so this one moved to
> `reproducibility.html` and the two now sit side by side in the nav. The sibling reports and their
> findings are linked in §"Findings from the sibling audits" below — including two findings this audit
> could confirm but did not repair.*

## Mandate

The repository contains three builds of the same analysis (canonical `pipeline/`, first build
`analysis/`, replication annex `scripts/` + `lab/`). All of them verify themselves. This session's job
was to verify **them**: re-derive the numbers from the pinned raw data, open every cited link, and
record — not quietly fix — anything that did not hold up.

Nothing in the analysis method, any strategy rule, or any published result was changed. Changes are
limited to verification code, provenance, disclosure, and three defects listed below.

## What was re-derived, and how

| Check | Method | Result |
|---|---|---|
| Upstream provenance | Re-downloaded `https://codeload.github.com/nflverse/nfldata/tar.gz/a270278f3ac4…` and hashed all seven files | 7/7 SHA-256 match `data/sources.json` |
| Mirror provenance (annex) | `git clone` of the Sportsbook Review mirror; sparse clone of the play-by-play mirror | SBR `b8a577c8…`; pbp `26cf60bc…`, `f303a9d1…`, `6cf0040a…` — all match `data/raw_manifest.json` |
| Schedule integrity | 7,548 rows in `games.csv`; recompute `result` and `total` | 7,384 played, 7,384/7,384 reconcile, 0 duplicate ids |
| Settlement engine | Compare to nflverse's independent per-side `outcome` column | 13,284/13,472 exact (98.605%); 8,684/8,690 (99.931%) where lines agree |
| Line model MAE | Recompute from `originated_lines.csv` | market 10.2155 / 10.5273, model 10.5272 / 10.7267 — all four reproduce to 4 d.p. |
| Strategy P&L | Recompute every ROI from `strategy_bets.csv` | 26,168 bets, 18 strategies, 0 mismatches |
| Gates | Count strategies passing all eight | 0/18; best is 6/8; no SKILL verdict |
| White's reality check | Re-run `stats_tools.reality_check` on the weekly matrix | p = 0.1443, exact match |
| Same-game correlations | Recompute φ from `originated_lines.csv` | 0.0241 / 0.6756 / 0.0076 — exact |
| Cross-game correlation | Recompute the paired-game r | 0.0109 — exact |
| Hold | Recompute from `vig_by_season.csv` | 2.25% (2006–2022) / 4.70% (2023–2026) |
| Prop fair odds | Recompute 1/P(joint) and 1/(p·p) | 8/8 consistent |
| Full pipeline | `pipeline/validation.py` on the staged snapshot | `strategy_bets.csv`, `strategy_gates.csv`, `strategy_summary.csv`, `reality_check.json` byte-identical |
| Annex pipeline | `bash scripts/run_all.sh` | 0/18 pass, 0/0/0 podium, signal persistence 0.485; 9/9 verifier checks after the V02 fix |
| Prop layer | `scripts/05_props.py` on the staged pbp | `data/lab/props.json` reproduced exactly |
| No lookahead | `pytest tests/test_no_lookahead.py` (staging the raw snapshot in the layout that build expects) | 4/4 pass — boundary/order/same-date only, **not** preprocessing (see LEAK-01) |
| Fold-preprocessing leak (sibling finding, re-checked) | Recompute the full-sample and prior-only temperature medians from `games.csv` | 59 °F full-sample vs 60 °F prior-only for the 2004 and 2018 folds → leak confirmed; effect on MAE **not** re-estimated |
| Open board (sibling finding, re-checked) | Count non-blank forecasts in `originated_upcoming.csv` | 0/164 fair spreads and 0/164 totals — every upcoming row is blank |

The automated subset runs in `pipeline/audit.py` and is wired into `make build` before
`pipeline/verify_site.py`, so a build whose numbers no longer recompute cannot be published.

## Citation audit (links opened on 2026-11-02)

| Citation | Link | Status |
|---|---|---|
| nflverse `nfldata` @ `a270278f3ac4` | <https://github.com/nflverse/nfldata/commit/a270278f3ac4e937295fe6a27814b3c4a2b62645> | verified (hashes) |
| 2026 NFL Rulebook (Rule 16 = Overtime; 2026 changes 6-1-3, 6-1-5, 6-1-6, 19-2) | <https://operations.nfl.com/rules-officiating/2026-nfl-rulebook> | verified |
| Bailey & López de Prado (2014), DSR | <https://doi.org/10.3905/jpm.2014.40.5.094> | verified (JPM 40(5) 94–107) |
| Gray & Gray (1997) | <https://ideas.repec.org/a/bla/jfinan/v52y1997i4p1725-37.html> | verified (JF 52(4) 1725–1737) |
| Levitt (2004) | <https://www.nber.org/papers/w9422> | verified (EJ 114(495) 223–246) |
| Shin (1993) | <https://doi.org/10.2307/2234240> | verified (EJ 103(420) 1141) |
| Benjamini & Hochberg (1995) | <https://doi.org/10.1111/j.2517-6161.1995.tb02031.x> | verified (JRSS-B 57(1) 289) |
| Kelly (1956) | <https://doi.org/10.1002/j.1538-7305.1956.tb03809.x> | **unverified** — doi.org returns HTTP 500 |
| FiveThirtyEight NFL Elo method | <https://web.archive.org/web/20250116054745/https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/> | **archived** — live URL redirects to ABC News; archive confirms K=20, MoV formula, ⅓ regression toward **1505** (project uses 1500) |
| Nevada Gaming Control Board, Nov 2025 | <https://www.gaming.nv.gov/siteassets/content/about/gaming-revenue/november-2025-monthly-revenue-report.pdf> | **unverified today** — 48-page PDF returns no readable text from the regulator or the Wayback Machine |
| SBR 10-year archive (mirror) | <https://github.com/flancast90/sportsbookreview-scraper/blob/main/data/nfl_archive_10Y.json> | verified (SHA-256) |
| Play-by-play mirror | <https://github.com/clausherther/nfl-dbt/tree/main/data_prep/data_files_load/pbp> | verified (SHA-256, 3 files) |
| nflverse club/division reference | <https://github.com/nflverse/nflverse-pbp/blob/master/teams_colors_logos.csv> | verified (32/32 clubs, SHA-256) |

## Defects found, fixed, and disclosed

| ID | Defect | Resolution |
|---|---|---|
| IR-14 | The Player props page claimed no player data was retrievable and that all mirrors hold 132-byte LFS pointers. `data/raw_manifest.json` records a 17 MB-per-season mirror, and the annex already used it. | Page now publishes the eight measured prop-combo correlations, sourced to the hashed mirror, and keeps the true "no prop prices" flag. The false sentence was removed from the page and from `prop_inputs.csv`. |
| IR-15 | `pipeline/verify_site.py` had a check hard-coded to `True` ("prop page publishes no unverified value"). | Replaced with a check that every published prop row matches `data/lab/props.json` and links to the hashed mirror. |
| IR-16 | Annex check V02 failed on a clean checkout (reference file only in git-ignored `data/raw/`). | Reference committed at `data/lab/reference/` with a SHA-256 sidecar; verifier checks the hash, ingest fetches it from the GitHub contents API. Re-run: 9/9. |
| IR-17 | FiveThirtyEight URL is dead. | Archived URL cited; 1505-vs-1500 disclosed; flagged as F-06 on the annex review page. |
| IR-18 | Kelly DOI and the Nevada PDF cannot be re-verified. | Flagged as F-04/F-07; neither underlies a computed number. |
| IR-19 | Single "break-even 51.4%" headline hid a hold regime change in 2023 (2.25% → 4.70%). | Both eras shown, with break-even ≈51.4% / ≈52.4%. |
| IR-20 | White's reality check is order-sensitive under its fixed seed (0.1443 library order vs 0.1367 alphabetical). | Documented in the audit; the audit pins library order so the published p is exactly reproducible. Both fail to reject. |
| IR-21 | **Leak (sibling finding).** Missing weather is imputed with a full-sample median *before* the walk-forward split, so earlier folds see later seasons (`build_datasets.py` ~303–318, split in `models.py` ~149–180). | **Disclosed, not fixed.** Re-checked here (LEAK-01); effect on the reported MAE not re-estimated and no number changed. The fix — a per-fold imputer — changes results and needs a methods decision, not a verification one. |
| IR-22 | **Empty, stale board (sibling finding).** All 164 upcoming rows carry a blank line (future weather is all-missing, so the imputer yields NaN), and the pinned snapshot predates completion of 2026 week 8, so games NFL.com lists as Final are still marked upcoming. | **Flagged, not back-filled.** Re-checked here (LINE-01). Nothing was guessed or filled; the Lines page states its as-of time. |

## What remains unverifiable from inside this repository

- **Individual odds rows.** Prices come from a single upstream archive; they are checked structurally
  and cross-validated on 2021 (final scores 263/263, closing totals within 1 pt on 97.1%), not row by
  row against a second feed.
- **Prop and team-total prices.** None exist in any reached source, so no P&L is claimed for those
  markets. Player statistics exist; prices do not.
- **Live markets.** The archives stop before the current season; the open board is blank and stale (IR-22).
- **The fold leak.** Confirmed and disclosed; its effect on the published MAE has not been measured here.
- **The raw snapshot in CI.** `data/raw/` is git-ignored (23 MB, re-fetchable). Provenance checks
  report "not staged" in CI rather than pretending to pass; they pass in full on a machine that has
  run `make data`.

## How to reproduce this audit

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pandas numpy scipy pytest
make data                     # fetch the pinned archive and verify hashes (needs network)
python pipeline/audit.py      # 20 automatic checks + 13 citations -> data/processed/audit.json
python pipeline/validation.py  # optional: re-run the whole strategy/validation stage
python pipeline/render_site.py && python pipeline/verify_site.py
```

## Findings from the sibling audits

Three sessions audited this repository on 2026-11-02 without seeing each other's conclusions. They are
published separately because they asked different questions, and this note does not restate their
evidence as its own:

| Report | Session | Question | What it adds |
|---|---|---|---|
| [`audit.html`](../audit.html) | `arena/1642ee06-korea1` | Do the scores match an *official* source, and how many rows rest on a community mirror? | 39 NFL.com game pages read: 31 match, 0 mismatch, 8 blank (season not final in the snapshot). Of 523 root-page rows, 516 link only to nflverse; historical prices have no official NFL source (IR-T10-01/-02). |
| [`notes/no-lookahead-2026-11-02.md`](../notes/no-lookahead-2026-11-02.md) | `arena/8eb93b26-korea1` | Does any step look ahead, and is the board live? | Fold-preprocessing leak (IR-21) and empty/stale board (IR-22); also checks and rejects a same-date team-state leak. |

Two consequences for how this audit should be read:

1. `tests/test_no_lookahead.py` passing 4/4 is **not** a clean bill of health. It checks split boundaries,
   ordering and same-date state; it never inspects preprocessing. The leak survived it, which is exactly
   why the sibling's finding matters and why it is disclosed here rather than argued away.
2. Reproducibility is not accuracy. This audit shows the published numbers are the ones the committed
   code and data produce; it does not show that the inputs are official or that the method is unbiased.
   Both limits are now stated on the reproducibility page itself.
