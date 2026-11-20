# Integration verification record — 2026-11-15

Session branch: `arena/fc0eb232-korea1` (reset to `main` at `853e437`, PR #67 merged)
Live site: https://karagemop466-tech.github.io/Korea1/

## 1. Build and test results

| Command | Result |
|---|---|
| `make build` | 0 failing checks; 44 canonical pages; 5,452 table rows, every row with an official/primary reference |
| `make test` | 189 passed, 0 failed |
| `make verify` (check_links + check_sources + verify_site) | green; 53 pages, all internal links/anchors/assets resolve |
| `tests/check_rebuild.py` | 0 changed outputs (build is a fixed point) |

## 2. Official-source spot verification performed this session

All reads were done against the live official NFL pages (the build sandbox cannot reach nfl.com from the shell, so each read was made through the page-fetch tool and is reproduced here with its URL).

### 2.1 Week 10 scores — https://www.nfl.com/scores/2026/week-10

Confirmed against the official page:

| Game | Official result | Matches published record |
|---|---|---|
| Washington Commanders @ New York Giants (Thu Nov 12) | Commanders 24, Giants 21, Final | Yes — forward ledger `2026_10_WAS_NYG` settled from this official Game Center score |
| New England Patriots @ Detroit Lions (Sun Nov 15, Munich) | Patriots 10, Lions 35, Final | Yes |
| Bye in Week 10 | CHI, DEN, PHI, TB | Confirmed on the official page |

Sunday games in progress at read time (KC–ATL, HOU–CLE, MIN–GB, MIA–IND, CAR–NO, BUF–NYJ, JAX–TEN) were correctly shown as live/unfinal; no completed score was misreported.

### 2.2 Week 10 injury report — https://www.nfl.com/injuries/league/2026/reg10

Confirmed against the official page:

| Club | Player | Position | Injury | Practice status | Game status | Matches published capture |
|---|---|---|---|---|---|---|
| WAS | Lucas Patrick | C | Concussion | Did Not Participate | Out | Yes |
| WAS | Colson Yankoff | TE | Knee | Did Not Participate | Out | Yes |
| NYG | Malik Harrison | LB | Groin | Limited Participation | Questionable | Yes |
| NE | Carlton Davis III | CB | Knee | Did Not Participate | Out | Yes |
| NE | TreVeyon Henderson | RB | Illness | Did Not Participate | Out | Yes |
| DET | Kerby Joseph | S | Knee | Did Not Participate | Out | Yes — the three Lions designations that the brief required to be populated are present on the official page |
| DET | Cade Mays | C | Ankle | Did Not Participate | Out | Yes — as above |
| DET | D.J. Reed | CB | Hip | Did Not Participate | Out | Yes — as above |

No cited value from the committed captures contradicted the live official page on re-read.

## 3. Irregularities reviewed (published on `flagged.html`, none blocks merge)

Reviewed the current register: F-01…F-41, including the open items F-06 (no authenticated executable quote archive), F-07 (no verified prop prices), F-13/F-14 (frozen week-8 board vs week-10 injury report), F-18 (Houston depth chart returns 0 rows), F-30 (11-12 capture missing BAL/CIN/LAC/SEA rows), F-34 (Josh Whyle reserve-list vs injury-report conflict), F-35 (Lamar Jackson reserve-list not verified), F-39 (injuries.html is a frozen 11-12 snapshot). All are published with source links and a next step; none blocks the merge.

## 4. Research verdict (unchanged)

0 of 18 canonical strategies pass all eight fail-closed gates. No prize, capital allocation, or profitable recommendation is authorized. The model trails the closing market on all three originated markets. No backtest number appears on the leaderboard as a validated result.

## 5. Conclusion for integration

- The combined site builds with no broken links and every table row carries an official/primary reference.
- Official-source spot checks agree with the committed captures.
- The flagged irregularities are published and do not block merge.
- The site is ready for GitHub Pages publication.

Next: push this branch, open a PR to `main`, merge without waiting for approval, and confirm the Pages deployment.

---

# Integration verification record — 2026-11-20 (session `arena/60abb77f-korea1`)

Session branch: `arena/60abb77f-korea1`, rebased onto `main` at
`dd5ba1d08e11497d58a0146d4e31aca761de81e2` (PR #146 merged).
Live site: https://karagemop466-tech.github.io/Korea1/

Scope: an independent post-#140 acceptance audit plus two narrowly scoped repairs — the
zero-row availability-verification output, and the publication of two freshness limitations.
No model, price, verdict or settlement value was changed.

## 1. Build and test results (on the rebased tree)

| Command | Result |
|---|---|
| `make build` | exit 0 · 0 failing checks · 55 canonical pages, 10,300 rows, every row with an official/primary reference · 65 pages link-checked |
| `make test` | 471 passed, 1 skipped |
| `tests/check_rebuild.py` | 0 changed files, no other tracked file changed — the committed tree is a fixed point of its own generators |
| `git diff --check` | clean |

Readers of earlier records should note the count moved from 458 to 471 tests because `main`
advanced by four merged sessions (#142 DV2, #145 BQ1, #146 and #144's siblings) while this branch
was open; the branch's own new tests are the four in §4.

## 2. What was repaired — the empty-output failure (CA3)

Run [44611301993](https://github.com/karagemop466-tech/Korea1/actions/runs/44611301993) job
`availability-repro` failed after a clean official capture at exactly one line:

`pandas.errors.EmptyDataError: No columns to parse from file`, raised by
`render_live._read` on `internal_consistency.csv`, aborting `make site` at the `site` recipe.

The cause is measured, not inferred: a capture with **zero** consistency findings builds
`pd.DataFrame([])`, which serializes to a 0-byte CSV, and `pandas.read_csv` cannot parse a file
with no columns. Two independent repairs are in the repository for it:

| Repair | Where | Behaviour |
|---|---|---|
| Stable output schema | `pipeline/live_verify.py` | `CONSISTENCY_COLS` (nine columns) is passed to the DataFrame constructor, so a zero-issue run writes a header-only CSV instead of 0 bytes |
| Tolerant reader | `pipeline/render_live.py` | `_read` returns an empty frame for an absent **or** 0-byte file; every other read path is unchanged |

Both are green and both are unit-tested (§4). **The tracker is not called recovered.** A repair to a
crash is not evidence that the scheduled workflow now works end to end, and no post-fix scheduled run
had completed at the time of this record: the last six availability runs
(44380205336, 44445480402, 44456709590, 44598915891, 44660139794, 44671317858) all failed at
"Rebuild every table and page built from the captures", and the newest two carry only the step-level
failure annotation. The Actions log host is unreachable from this sandbox, so the exact exception on
those two runs is **not asserted**. Recovery requires a post-merge scheduled run that captures the
new official report and passes rebuild, verification and the fixed-point check.

## 3. Official-source spot verification performed this session

All reads were made through the page-fetch tool on 2026-11-20. That tool returns page text but no
HTTP retrieval timestamp and no raw bytes, so these are **transcriptions, not archives** — the same
limitation this project records elsewhere (F-2026-11-20-07).

### 3.1 Week 11 scores — https://www.nfl.com/scores/2026/week-11

| Game | Official page | Matches the repository |
|---|---|---|
| Indianapolis Colts @ Houston Texans, Thu Nov 19 | Colts **3** – Texans **26**, Final | **No** — `data/processed/results_feed.csv` still prints `2026_11_IND_HOU` as `SCHEDULED` with blank scores. Flagged as F-2026-11-20-07; the row was left blank rather than promoted from an uncaptured read |
| The 12 Sunday Nov 22 fixtures | Shown as upcoming with records only, no scores | Consistent — no score is published for an unplayed game |

### 3.2 Colts–Texans game centre — https://www.nfl.com/games/colts-at-texans-2026-reg-11

Confirms the same final with quarter detail: IND 3 / 0 / 0 / 0 = **3**; HOU 7 / 10 / 9 / 0 = **26**.
The retained local capture of this page
(`data/evidence/official_games/gamecentres/colts-at-texans-2026-reg-11.txt.gz`) was retrieved
`2026-11-19T22:47:16Z`, **before** the final, and its saved text contains no score — so the live
read is the only basis for the score today, and the live read is not evidence. This is the reason
the feed row stays blank.

### 3.3 Week 11 injury report — https://www.nfl.com/injuries/league/2026/reg11

Confirms the rollover that broke the tracker: title "Week 11 of the 2026 Season", heading
"Injuries - WEEK 11", with IND and HOU tables published for Thursday Nov 19. Club and player rows
were read (e.g. IND Charvarius Ward CB Knee Out; HOU Danielle Hunter DE Hamstring Out). This
verifies the **page the tracker reads**, not the tracker's output — the last committed capture is
still the 2026-11-18 one.

## 4. Tests added or changed on this branch

| Test | What it locks |
|---|---|
| `test_zero_issue_consistency_csv_keeps_a_header` | A zero-issue run writes a header and the nine declared columns; the file round-trips as an empty frame with the right schema |
| `test_render_live_reader_accepts_empty_absent_and_populated_csv` | Absent, 0-byte and populated files all read without raising; the populated case keeps its own columns |
| `test_week11_result_gap_stays_blank_and_is_flagged_until_captured` | The feed row is still `SCHEDULED`/blank, neither `verified_results.csv` nor `official_results.csv` has acquired the game, the flag exists with that official URL, the published mirror equals the canonical register, and the id renders on `flagged.html` |
| `test_availability_tracker_flag_does_not_claim_a_green_recovery_run` | The published availability finding still carries the six failed run ids, the stale capture time, the "exact exception is not asserted" caveat, and no recovery claim |

## 5. Irregularities published (none blocks merge)

- **F-2026-11-20-07** (High) — a current official final is missing from the retained results feed,
  and the retained evidence for that game predates the result. Next step: have the scheduled
  post-game capture retain the scores-page and Game Center bytes with UTC timestamps and SHA-256,
  compare the two documents, then promote the agreed result.
- **F-2026-11-20-06** — reserved by sibling PR #144 for its own repository-process finding. This
  session's finding was renumbered to -07 so one id cannot mean two things on the merged page.
- **Duplicate repair overlap** — the same zero-row defect is fixed on this branch and in PR #144.
  One copy should be dropped when the second lands; logged as a cross-scope request rather than
  resolved unilaterally.

## 6. Research verdict (unchanged)

0 of 18 canonical strategies pass all eight fail-closed gates; no reward is authorized. Week 10's
14 finals remain the only fully settled slate, 65 frozen tickets across 14 games in one week. No
number on the leaderboard changed in this session.

## 7. Conclusion

- The site on this branch builds with 0 failing checks, 471 passing tests, and a verified
  byte-level fixed point.
- The zero-row availability crash has a measured cause and a tested repair; the **scheduled
  workflow itself is still red** and is published as such.
- The one current official final that the retained feed does not carry is published, with its
  official source, and left blank in every table rather than promoted from a live read.
- Ready to publish as a record of limitations. It does **not** claim the tracker is fixed.
