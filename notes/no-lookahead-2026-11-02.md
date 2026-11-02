# Targeted temporal and current-line audit — 2026-11-02

**Status:** read-only audit completed; code/site fixes are requested from the integration owner.  
**Scope:** `pipeline/build_datasets.py` and `pipeline/models.py`, evaluated against the committed artifacts and the pinned input. No model, data table, or site page was edited in this task.  
**Important source caveat:** the model's game/market dataset is an nflverse community-maintained GitHub snapshot, not an official NFL feed. The official NFL links below independently confirm the specific current-week example only; they do not certify the entire historical dataset or any betting prices.

## Executive findings

### 1. Historical walk-forward preprocessing uses a full-sample weather median

The pipeline currently creates `wind_med` and `temp_med` from *all* played games, then fills missing weather in the full played-game frame before the walk-forward split. The variables holding those medians are not used; instead each frame fills from its own median. The model then splits those already-imputed rows into training and test seasons. Thus the weather imputer is not fitted within each training fold and uses information from later seasons when preparing earlier folds.

- Build/imputation: [`pipeline/build_datasets.py` lines 303–318](https://github.com/karagemop466-tech/Korea1/blob/3453d41/pipeline/build_datasets.py#L303-L318).
- Walk-forward split and feature extraction: [`pipeline/models.py` lines 149–180](https://github.com/karagemop466-tech/Korea1/blob/3453d41/pipeline/models.py#L149-L180).
- Pinned input: [`nflverse/nfldata games.csv`](https://github.com/nflverse/nfldata/blob/a270278f3ac4e937295fe6a27814b3c4a2b62645/data/games.csv); recorded hash and snapshot metadata are in [`data/sources.json`](https://github.com/karagemop466-tech/Korea1/blob/3453d41/data/sources.json).

Recomputed from the pinned file (SHA-256 `ba34f3619067eb4459eb257f629d7f29adce74cba824e1708e7bbb9ef3246e6a`): 7,384 played rows; temperature and wind each have 5,251 recorded values and 2,133 missing values. The all-seasons medians are 59°F and 8 mph. A prior-only split median differs for temperature in two test seasons:

| Walk-forward test season | Prior seasons' temperature median | Full-sample median used by build | Missing temperature values in prior training rows | Missing temperature values in test season |
|---:|---:|---:|---:|---:|
| 2004 | 60°F | 59°F | 280 | 58 |
| 2018 | 60°F | 59°F | 1,240 | 70 |

Across the other test seasons in this snapshot, the prior-only and full-sample medians match (wind is 8 mph in every prior-only split). The leakage is therefore demonstrated, but its effect on the reported MAE/ROI has **not** been re-estimated here; no claim is made about the size or direction of any performance change.

**Requested correction:** fit each imputer using only that walk-forward fold's training rows, apply it to that fold's test rows, and use the most recent completed-game training values for future inference. Add a regression test that fails if any fold's preprocessing uses later seasons.

### 2. All current upcoming originated lines are blank due to missing weather

The pinned snapshot contains 164 unplayed schedule rows. All 164 have missing `temp` and `wind`. The build loops over the future frame separately and fills each column with that same future frame's median; when all values are missing, the median is NaN, so the values remain NaN. `originate_future()` then passes those NaNs into the ridge predictor and carries the NaNs into the ensemble line and moneyline probabilities.

Observed in the committed `data/processed/originated_upcoming.csv`:

| Output | Nonblank rows | Total rows |
|---|---:|---:|
| Fair spread | 0 | 164 |
| Fair total | 0 | 164 |
| Home/away moneyline probabilities | 0 / 0 | 164 |
| Originated home/away moneyline | 0 / 0 | 164 |

The pipeline function was also smoke-tested **in memory only** after replacing missing future weather with the completed-game medians; all 164 spread/total/probability outputs became finite. That is a diagnostic of NaN propagation, **not** a validated prediction or a published line. No replacement values have been written to the repository.

Relevant code: [`pipeline/build_datasets.py` lines 303–318](https://github.com/karagemop466-tech/Korea1/blob/3453d41/pipeline/build_datasets.py#L303-L318) and [`pipeline/models.py` lines 297–342](https://github.com/karagemop466-tech/Korea1/blob/3453d41/pipeline/models.py#L297-L342).

**Requested correction:** use only documented pregame values or a training-fold imputer; otherwise leave each line blank and explicitly mark it unavailable/unverified. Add a verifier that rejects a published “open board” when the originated prices are all missing. Do not populate future weather with guesses.

### 3. The published open board is stale against the official current schedule

The committed snapshot was generated at `2026-11-01T13:24:09Z`, before the Sunday Week 8 games were completed. On the audit date, the derived upcoming table still lists 12 games dated **2026-11-01** with no result as future games. The live [`Originated lines`](https://karagemop466-tech.github.io/Korea1/lines.html) page is built from those artifacts.

This stale status was checked against the official NFL [2026 Week 8 schedule](https://www.nfl.com/schedules/2026/by-week/week-8) and the official [Ravens at Bills Game Center](https://www.nfl.com/games/ravens-at-bills-2026-reg-8), which reports **Final**, Baltimore 10–Buffalo 36, Week 8, November 1. The pinned input's `2026_08_BAL_BUF` row is still in `upcoming.csv` with blank result and score. The official page also shows the Bears at Seahawks game is scheduled for Monday, November 2; that one is not counted among the 12 Sunday games.

This is a freshness mismatch, not evidence that nflverse is an official source. The immutable snapshot remains useful for reproducible historical analysis, but it must not be presented as a current open board after the games have started/finished.

**Requested correction:** refresh the current schedule/results from a verified source before presenting a live board, or label the page clearly with its “as of” timestamp and suppress expired games. Reconcile every current-week row against official NFL game-center pages before marking it verified. Do not change historical results from the schedule page without preserving provenance and hashes.

### 4. Same-date team-state updates were checked; no cross-game leak was found

The builder emits features and updates per-team Elo/offence/defence state after each played row. I checked the pinned 7,384 played rows: 711 season/date groups have more than one game, and **zero teams appear in two games on the same season/date**. The league scoring average is cached at each season's start, and opponent-adjusted coefficients are held constant within a season/week. Therefore sequentially updating one game's teams on a date cannot change another distinct same-date matchup's team-state features in this data. I found no evidence of a same-date state leak from that mechanism; the confirmed preprocessing issue is the full-sample imputation above.

## Reproduction performed

1. Downloaded the archive for the exact SHA in `data/sources.json` from the pinned [`codeload` archive](https://codeload.github.com/nflverse/nfldata/tar.gz/a270278f3ac4e937295fe6a27814b3c4a2b62645), extracted only `data/games.csv` to the git-ignored `data/raw/`, and confirmed its SHA-256 equals the recorded value.
2. Installed the declared Python dependencies in ignored `.venv/` and ran `.venv/bin/python -m pipeline.verify_site`: **0 failing checks** for the currently committed static site. This site-level check did not catch the missing future forecasts or stale schedule status.
3. Used pandas to count missing weather and split medians from the pinned CSV and to count nonmissing predictions in `data/processed/originated_upcoming.csv`.
4. Compared the specific current-week game/status to the official NFL schedule and game-center links above.
5. Inspected `pipeline/build_datasets.py` and `pipeline/models.py` at the source lines linked above. No source file or derived artifact was modified by this audit.
6. Ran `python3 tests/check_links.py`, `python3 tests/check_sources.py`, and `pytest -q tests/test_no_lookahead.py`; all passed (20 pages, 11 pages / 606 table rows, and 4 tests respectively). The test fixture reads `data/raw/nfldata/data/games.csv`, so an ignored symlink to the already hash-verified `data/raw/games.csv` was created for the test run; no tracked file changed.

## Integration request / disposition

This is additive to the official-source review merged in PRs [#13](https://github.com/karagemop466-tech/Korea1/pull/13) and [#14](https://github.com/karagemop466-tech/Korea1/pull/14): that review flags stale Week 8 data and confirms sampled official scores, while this targeted audit checks the fold-level preprocessing and the actual future predictions. The merge changed the audit/flagged presentation but did not modify `pipeline/build_datasets.py`, `pipeline/models.py`, or the 164-row forecast artifact.

These findings touch the completed T1/T2 model-data scope and the generated `lines.html` page. This audit session did **not** edit those files. The current T12 task is complete as a targeted audit; the fold-safe imputer, finite-line guard, freshness handling, and visible Flagged-for-Review notices are requested from the active integration owners. Until fixed and re-run, the live open board should be treated as **stale and unavailable**, not as current originated NFL lines.
