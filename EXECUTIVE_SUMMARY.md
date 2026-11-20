# Executive summary — NFL Line Lab

Current status refreshed: 2026-11-15. Pinned research inputs: `a270278f3ac4e937295fe6a27814b3c4a2b62645`.

## Decision

**Keep the research engine; do not fund or reward a betting strategy yet.** The repository originates
NFL lines and evaluates single-bet, situational and parlay candidates. It does not contain authenticated,
timestamped executable bookmaker quotes or verified player-prop ticket prices. **0 of 18 canonical
strategies pass all eight final gates.** No prize, capital allocation or profitable recommendation is authorized.

“Unverified” is not a finding of zero edge. It means the evidence cannot support the stronger claim.
Statistical corrections reduce false discoveries; they cannot eliminate luck or guarantee future returns.

## Current status — 2026-11-15

This dated snapshot supersedes older status notes below. Counts come from the committed gate, forward-ledger, demotion and brief registers. Unverified items remain flagged; no missing evidence is filled in.

| Area | Current status | Decision meaning / blocker | Sources |
|---|---|---|---|
| Signal qualification | 0 of 18 pass the registered signal-gate set; 0 pass all eight validation gates. | Signal qualification is not a staking status or a profitability claim. No candidate is validated and no reward is supported. | [Competition](competition.html) · [validation gates](validation.html) · [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Staking and quote provenance | 0 LIVE · 18 PAPER · B6 BLOCKED · 18 fail quote-provenance G1. | No authenticated, timestamped executable bookmaker quote archive is recorded. Signal qualification and paper/live state are shown separately; no live stake or reward is authorized. | [Price archive](price-archive.html) · [paper/live register](assets/data/demotion_register.csv) · [NFL scores (settlement context)](https://www.nfl.com/scores/) |
| Prospective results | 65 official-settled · 0 open · 0 validated | Official outcomes are used for settlement; open tickets remain open. The available prospective record does not validate a strategy or establish a repeatable edge. | [Forward ledger](forward.html) · [NFL Week 10 scores](https://www.nfl.com/scores/2026/week-10) |
| Injury, roster and depth blockers | B1 PARTLY DONE; B7 PARTLY DONE. | Reserve-list live capture (CI) has not run; chunk 0 re-read is partial in this session; Reserve-list CI run; HOU depth chart (0 rows); 2026-11-12 coverage gap cause (unverified). Missing rows are not read as healthy; the 2026-11-12 coverage-gap cause remains unverified. | [Brief tracker](brief-2026-11-15.html) · [NFL injury report](https://www.nfl.com/injuries/league/2026/reg10) · [NFL reserve list](https://www.nfl.com/transactions/league/reserve-list/2026/11) |
| Parlay and player-prop priceability | UNVERIFIED — no executable price evidence. | Verified player-prop prices and joint parlay/SGP quotes are still missing. Structural research is not a ticket offer, and no prop ROI or actionable recommendation is established. | [Props](props.html) · [correlation rules](correlations.html) · [NFL injuries](https://www.nfl.com/injuries/) |
| F-38 competitive-display policy | Implemented in the 2026-11-15 update. | Competitive tables withhold historical backtest returns, hit rates, mean signal edge and staked-unit totals. Signal qualification is separate from PAPER/LIVE status. The two-sided mind-changer fields show move-up thresholds and stop/demotion triggers only; current historical result values are omitted. This is a display-policy change, not validation. | [Strategy leaderboard](strategies.html) · [competition standings](competition.html) · [frozen thresholds](assets/data/validation_config.json) · [demotion register](assets/data/demotion_register.csv) |


## Update - 2026-11-19 (`arena/eeba949e-korea1`): the official Game Book evidence layer

**The capture chain was dead and is now repaired.** The league's schedule page no longer
prints `/games/` anchors, so the old reader found no fixture at all: the capture had stored
two byte-identical documents and zero game centres and zero Game Books. The reader now reads
the league's own published schedule payload, and the capture uses the league's own weekly URL
form (`/schedules/<season>/by-week/reg-<week>`), which is the form the league's own game-centre
records already cite.

| What | Count | Note |
|---|---|---|
| Official documents captured | 76 | each with its URL, HTTP status, byte count and SHA-256 |
| Fixtures published from the league's schedule page | 42 | every column printed by the league |
| Availability-graph rows (expected starter) | 1714 | the club's own depth chart, with its capture time |
| Confirmed starters | 356 | needs an official Game Book |
| Co-starter positions | 240 | the club named more than one first player; none is chosen |
| Game centres captured | 42 | of the fixtures above |
| Game Books captured | 29 | of the fixtures above |
| Inactive / did-not-play rows | 412 | the league's game-day lists |

**Drift, published rather than hidden.** 2 captured schedule page(s) served a
week other than the one the capture asked for: the 2026-11-19 capture requested Weeks 9 and 10
and was served the same Week 11 document for both (identical SHA-256). The document register
publishes the requested week, the published week and the disagreement, and the fixture rows
carry both. This is recorded as an open irregularity, not corrected by assumption.

The page is [Official Game Book evidence](gamebooks.html). The expectation side of the
availability graph is complete for the fixtures read; the actual side is blank on every row
because no official Game Book has been captured yet, and each such row says so.


## Update - 2026-11-19 (`arena/35c0fd93-korea1`): the Week-11 rollover repair (W1)

**Both scheduled capture chains went red when the league flipped its pages to Week 11, and
neither published wrong data.** The availability tracker failed four consecutive runs at the
rebuild step because a comparator pinned to the 2026-11-18 official read derived its KC
omission arithmetic from the **rolling** capture (reproduced offline: one added KC row raises
`SystemExit("KC omission count is 2, expected 1")`); every dated comparator now reads the
dated `history/2026-11-18/` snapshot, guarded by source-level tests. The Game Book capture
failed twice on its own fail-loud contract because the scores-page cross-check collected the
current week's links that the league's post-flip scores pages carry beside the requested
week's fixtures (the runs' own annotations record `only schedule: []; only scores:
[13 reg-11 slugs]`); the cross-check now compares same-week slugs only, records the extras,
and keeps every same-week disagreement fatal. At repair time the rolling capture and the
dated snapshot hold the same rows: yes.

| Capture reference | Rows | KC rows | Week label |
|---|---|---|---|
| Dated snapshot `history/2026-11-18` (the pinned comparator reference) | 347 | 13 | WEEK 10 |
| Rolling top-level capture (the tracker overwrites it with the newest week) | 347 | 13 | WEEK 10 |

The research verdict is unchanged: no strategy is validated, no reward is authorized, and no
published research number moved — the repair changes which capture a dated comparison reads,
not any value.


## Update — 2026-11-19 (`arena/db0e98e2-korea1`)

- **Decision unchanged.** Still no validated strategy and no reward. Nothing in this update adds evidence for an edge.
- **Reserve list is not a complete record (F-2026-11-19-06, High, open; same pattern as F-57).** The live NFL.com November reserve page, read on 2026-11-19, matches the 2026-11-19 capture row for row (25 rows). Four rows dated 11/10 that were on the 2026-11-18 capture are gone, including Malik Willis (MIA), and four dated 11/18 were added. A row that is absent is therefore *not on the page at capture time*. It is never evidence of availability. Source: [NFL.com reserve list, November 2026](https://www.nfl.com/transactions/league/reserve-list/2026/11).
- **Repair (F-2026-11-19-07).** The rolling `latest.csv` had been overwritten, so code labelled it as the 2026-11-18 capture and one test failed on `main`. The sibling session's fix (`37816e4`) pins the comparison to the 2026-11-18 history folder; the remaining reader is pinned in this branch. Build and tests are green.
- Flags and the live read are on [Flagged for review](flagged.html) and in `data/live/spotcheck_2026_11_19/`.

## Update — 2026-11-19 (`arena/7cbb2e60-korea1`) — official capture repair

- **Decision unchanged.** Still no validated strategy and no reward; nothing here adds evidence for an edge.
- **The schedule capture did not select the week (F-2026-11-19-08, High).** The committed REG9 and REG10
  evidence files were byte-identical (raw SHA-256 `6ad52b57…`, 2,291,069 bytes each) and both contained
  Week-11 fixture cards while labelled weeks 9 and 10, because `/schedules/<season>/REG<week>` ignored the
  week for the capture client. The capture now reads the league's by-week URL, requires every fixture slug
  to print the requested week, and cross-checks the fixture set against the week's scores page before
  anything is written. Source: [NFL by-week schedule, week 10](https://www.nfl.com/schedules/2026/by-week/week-10).
- **A blank capture published as a success (F-2026-11-19-09, Medium, repaired).** The parser returned 0 rows
  on the real page shape (relative hrefs, labels nested in `sr-only` spans) and the run still exited 0 with
  `game_centres: []`. The capture now aborts with exit 2 and writes no evidence on any missing field —
  zero fixtures, week mismatch, schedule/scores disagreement, blank venue, finished fixture without a Game
  Book link, or a Game Book that does not match the fixture.
- **New page: [gamecentre.html](gamecentre.html)** — venue per fixture from the official game centre
  (REQ-23) and the Game Book's printed starters, Not Active and Did Not Play lists (REQ-25), one official
  link per row and one SHA-256 per captured document. It renders an explicit waiting state until the
  scheduled runner capture commits genuine week-selecting evidence.

## Decision readiness & lineup follow-up — 2026-11-12

Four review registers sit in front of the research, generated from the same data as the pages, and none
of them is an approval:

| Register | Size / status | What it establishes |
|---|---|---|
| `suggestions-review.html` | 12 staged improvements — interactive Path A / B / C selector | Side-by-side Conservative / Balanced / Full path options, trade-offs, affected gates and browser-only decision JSON export before any model or rule edit |
| `suggestions.html` | 22 proposals — 8 ready now, 6 pilot, 4 recommended before any reward, 2 rejected, 1 deferred, 1 blocked | Cost, risk, dependency and acceptance evidence for every change, plus four paths (A–D) and a change-control worksheet |
| `decision-readiness.html` | 14 pre-decision Q&As, 8 discovery protocols & 28 post-pin NFL.com scores | Separates verified knowns from missing inputs and reconciles all 28 Week 8–9 2026 games settled on NFL.com after the 2026-11-01 archive pin |
| `decisions.html` | 12 readiness questions plus a parallel 8-proposal register | Current answers, missing inputs, discovery steps and the gate each one feeds |
| `questions.html` | 40 questions — 29 answered, 2 open, 7 blocked, 2 needing an owner decision | Every answer cited; blocked rows left blank with the reason and a closure test |
| `lineup-deficiencies.html` | 39 Week 10 entries across 8 clubs / 4 matchups + NFL Operations T-90m rule | Offensive & defensive 1st–4th string tracking across `WAS@NYG`, `NE@DET`, `KC@ATL` and `MIN@GB`, club disclaimers/trade lag, and prefix-safe PBP backup diagnostics |

Two dated captures are transcribed in `injuries.html`: the 2026 week-10 WAS/NYG report (20 rows — 2 Out, 1
Questionable, 17 blank) and 2019 week 5 (11 rows), while `lineup-deficiencies.html` expands verified 2026
Week 10 depth-chart coverage to **8 of 32 clubs** (`commanders.com`, `giants.com`, `patriots.com`,
`detroitlions.com`, `chiefs.com`, `atlantafalcons.com`, `vikings.com`, `packers.com`) and documents the
mandatory T-90m Game Day Administration inactive & roof rule on `operations.nfl.com`. 8 availability signals assessed: 1 available, 4 pilot-only, 2 open, 1 blocked — **0 in
the leaderboard**, because none clears the leakage and confirmation tests and the board is pinned before week 8.

The initial official source inventory in `availability.py` holds 12 checks (9 verified,
3 verified-negative, including 2 club depth charts), and `sources_lineups.json` adds 6 further
verified club depth charts (total **8 of 32 clubs**). No player is called a confirmed game-day replacement,
no depth rank is invented for a player absent from a chart, and no availability signal enters the model.
A read-only daily Actions monitor archives the sources; collection is not verified extraction. All-club
coverage, game-day role confirmation and validated impact remain blocked.

## Update of 2026-11-12

| Area | Status | What changed and what it means | Official reference |
|---|---|---|---|
| Injuries and lineups | Tracking live; effect not priced | A scheduled GitHub Actions workflow reads the official NFL.com injury report and each club's depth-chart page and publishes, for offense and defense, which first-listed players are Out or Doubtful and which 2nd, 3rd or 4th-string player the club lists next (`availability.html`). It does not yet move the originated line: the point value of an absence has not been measured. | [NFL injury report](https://www.nfl.com/injuries/) |
| Suggestions | Awaiting your decision | Every proposed change is on `decision-board.html` with options, a recommendation and the evidence behind it. Nothing is implemented. Decide DB-02 (real prices) and DB-03 (forward paper ledger) first. | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Open questions | Unanswered | `open-questions.html` separates what is known from what is missing and names how to find it. Some only you can answer: sportsbooks and jurisdiction, bankroll, success threshold, refresh cadence, reward. | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Line board freshness | Stale | The open line board still starts at Week 8 (snapshot pinned 2026-11-02); the injury capture is for the current week. Refreshing is suggestion DB-04. | [NFL schedule](https://www.nfl.com/schedules/) |
| Site | Repaired | Navigation grouped by category; stylesheet now defines the classes the pages use. Review findings RV-01 to RV-11 are on `flagged.html`. | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |

## Citation integrity audit — 2026-11-13 (session `arena/84e42ecc-korea1`)

Until now every published row was checked for the *presence* of an official reference. Presence is not
proof: a citation that resolves to a 404 looks like evidence and is not. `scripts/referent_probe.py`
now extracts every external URL printed on the site and resolves it, and the result is published on
`referents.html`.

| Result | Count | What it means |
|---|---|---|
| Resolved | 455 | HTTP 200 at the printed path, and — where a text check is defined — the page contains the text the row attributes to it. |
| Redirect | 8 | HTTP 200 only after a redirect. Works today; the printed path is stale. |
| Unresolved | 11 | 4xx/5xx or an NFL Football Operations soft-404. **Do not rely on these.** |
| Claim not supported | 1 | The page loaded without the asserted text. On inspection this one is a false negative: the FanDuel help centre is client-rendered, so the machine probe only sees a loading shell. A manual read found the quoted settlement rule. |

Confirmed dead, independently by hand and by machine: the [2017 NFL injury-report policy](https://operations.nfl.com/updates/football-ops/2017-nfl-injury-report-policy/)
and player-protections pages on `operations.nfl.com` (three pages each); the NFL.com
`/teams/<club>/depth-chart` path (four pages — the working official source is the club's own
depth-chart page, verified live for Arizona); two GitHub links (the `nfl-dbt` path uses `main` but that
repository's default branch is `master`, and `data/processed/audit.json` does not exist); and the
GitHub Pages publishing-source documentation page.

Two results need a human decision rather than a code change. The **Deflated Sharpe Ratio** reference is
printed on 13 pages and neither its publisher URL nor its DOI could be read (302). The **FiveThirtyEight
Elo methodology** URL now redirects to `abcnews.com/politics`, so the K=20 values this project quotes are
no longer readable from the printed link. Neither affects a published number; both weaken a citation.

Separately, `scripts/score_reconcile.py` re-opens the official game page for all 28 rows of the Week 8–9
2026 score census and re-reads the final score. This is the only place where the project checks its own
archived outcomes against an official source, so agreement here is what makes the pin trustworthy for
scores even though it is stale for results.

**The first machine run produced no verdict for any of the 28 rows.** The official game-centre page is
client-rendered: the runner receives raw HTML with no score in it, so every row came back `UNPARSED`
rather than `MATCH` or `MISMATCH`. That is recorded as a parser limitation, not as agreement. Two rows
(`ARI 33–30 DAL` and `ATL 0–16 TB`) were opened by hand on 2026-11-13 and both agree with the official
page — including the Atlanta shutout, which is exactly the kind of value that should be re-checked rather
than assumed. The census is therefore spot-verified, not machine-verified end to end.

All of this is published on `referents.html` and cross-listed on `flagged.html` as F-21 to F-28. Nothing
was silently repaired: a citation is only changed after a human confirms the replacement says the same thing.

## Forward test — first settlement, 2026-11-13 (session `arena/8a322b62-korea1`)

The repository now publishes a **prospective** record, which is the only evidence that cannot be
contaminated by hindsight. `forward.html` prints every ticket frozen before kickoff and settles it only
against an official NFL.com final.

| Item | State | Meaning |
|---|---|---|
| Frozen before kickoff | 65 tickets across 18 strategies and 14 Week 10 games; written `2026-11-12T13:26:48Z`, received by GitHub `13:28:07Z`, 11.78 h before the first kickoff | The picks were public before the games started. The receipt time is GitHub's, not the committer's. [NFL week 10 schedule](https://www.nfl.com/schedules/2026/by-week/reg-10) |
| Settled from an official final | **65 of 65** — every Week 10 final is certified by two official documents (the [week 10 scores page](https://www.nfl.com/scores/2026/week-10) and the league's own Game Book, hash-pinned in this repository) | 0 tickets stay `OPEN`; 0 provisional, awaiting an official final; none is defaulted to a push or a void. Net +3.110 units across the settled tickets. |
| Strategies with a counted result | 14 of 18 | One ticket each is not a record. |
| Validated strategies / rewards | **0 / none** | No strategy is past its declared horizon (150 single or 60 parlay tickets over 30 weeks); verdicts are withheld from the agent by ledger amendment A1. |
| Gate F2 (official settlement) | PASS where a ticket has settled | Settlement now rests on an official page; before this pass the same 4 tickets were `PROVISIONAL`. |
| Gate F6 (quote provenance) | FAIL for all strategies | Frozen prices are community-mirror values, not authenticated bookmaker quotes. |

**What this does not mean.** 65 tickets at one game is not a sample, and a 2–2 split is
indistinguishable from chance. `forward.html` prints no p-value, no ROI and no verdict, and awards
nothing. The honest reading is that the forward clock has started and the record can now be audited;
nothing about the strategy library has been demonstrated.

**A defect repaired on the way.** The committed evidence manifest
`data/evidence/nfl_injuries/week10_2026/manifest.json` was rewritten by every build and carried
`"sha256": null` for `news_register.md`, because `pipeline/fetch_injuries.py` hashed only `files[0]`.
`tests/check_rebuild.py` does not cover `data/evidence/`, so the drift survived review and left the tree
dirty after each build. Every declared file is now hashed, a missing file raises, and
`tests/test_evidence_integrity.py` fails on a null or mismatched digest (verified by restoring the old
code: 2 tests fail). Findings F-T41-01 to F-T41-06 are on `flagged.html`.


## What was delivered

| Requirement | Delivery | Evidence status | Official / primary reference |
|---|---|---|---|
| Requirements register | `research/requirements.md` and `requirements.html` | Implemented | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |
| Own NFL lines | Walk-forward Elo, rolling matchup and ridge models; margin, total and moneyline estimates | Implemented; benchmark inputs unverified | [NFL official scores](https://www.nfl.com/scores/) |
| Signal strategies | 18 canonical candidates plus preserved historical annex | No validated edge | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Parlays | Simultaneous-slate selection, push-aware research settlement and adverse-price stress | Executable ticket quotes unavailable | [FanDuel push rules](https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push) |
| Player-prop combos | Input inventory, joint-distribution protocol and combo hypotheses | Blocked by missing verified prices and joint quotes | [NFL injury report](https://www.nfl.com/injuries/) |
| Correlations | Reproducible research estimates; strict public values blank where inputs unverified | Partial evidence | [NFL official scores](https://www.nfl.com/scores/) |
| Luck mitigation | Weekly-block bootstrap, Holm FWER, power, provisional DSR, stability and redundancy | Implemented with assumptions | [Bailey & López de Prado (2014)](https://www.pm-research.com/content/iijpormgmt/40/5/94) |
| Competition rewards | Fail-closed recognition tiers; all rewards unawarded | No funded prize pool | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Official score audit | 31 matching games in a 39-game NFL.com sample | Sample, not a census | [NFL official scores](https://www.nfl.com/scores/) |
| Dashboard | Static categorized pages, searchable tables, source links and flagged-review register | Deployment recorded separately after merge |
| Suggestions before changes (R19) | 22 proposals with cost, risk, dependencies, four paths and change control | Implemented; nothing approved |
| Questions and answers (R20) | 40 open questions plus 12 readiness questions, each with a closure test | Implemented; blocked rows blank |
| Injury / lineup deficiency (R21) | Official report captures plus 2 of 32 club depth charts | PARTIAL — order only, no confirmed roles | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |

## Addendum - 2026-11-13

A fifth pass (`arena/132e7ca2-korea1`) merged the parallel registers and re-read the official pages.

| What was added | Size | What it does |
|---|---|---|
| `review-queue.html` | 76 proposals merged from 5 registers into 14 clusters (29 awaiting a path) | The decision surface: one lead row per cluster, every source row kept with its register and original id, so a path is chosen before any code changes |
| `answers.html` | 90 questions merged from 4 registers (58 without an answer on record) | Information we have, information we do not, the answer on record and the discovery step for each |
| `competition.html` | 3 divisions, 7 reward tiers, 8 gates | Leaderboard competition rules, the reward ladder and the luck-removal battery; the highest reachable tier today is **T0** because gate G1 fails for every candidate |
| `repo-review.html` | 967 tracked files, 8 official-source checks, 6 irregularities | Line-by-line repository inventory, verification log and irregularity register |

**Official-source re-verification performed on 2026-11-13.**

| Check | Result |
|---|---|
| Pinned upstream commit | `a270278f3ac4e937295fe6a27814b3c4a2b62645` exists in `nflverse/nfldata`, titled "Automated data update" |
| Injury capture re-read against nfl.com/injuries/ | **54 of 98 rows identical** on position, injury, practice status and game status - no transcription error found. The remaining rows are later page updates, not bad copies |
| Availability completeness | **IRREGULARITY**: the live page shows 21 Out designations in the 8 clubs re-read, the whole 28-club capture shows 8 |
| Post-pin score register re-read against nfl.com/scores/2026/week-8 | **8 of 8 sampled games identical**; the one game that settled before the pin is correctly absent |
| NFL Operations 90-minute rule | Verified: the Game Day Administration Report, containing each club's inactive list and C2P helmet designations, is exchanged 90 minutes before kickoff, and the roof/wall designation is fixed at the same mark |

Two new irregularities were recorded and left for a decision: **IR-132E-01** (the scheduled
availability capture runs before the Friday game designations post, so the deficiency table
understates current unavailability) and **IR-132E-02** (`pipeline/fetch_injuries.py` writes
`"sha256": null` for the news register, so one committed file changes on every build for no data
reason). Neither was repaired here; repair is a decision for the owner, and the files belong to
earlier sessions.

**Decision unchanged:** keep the research engine, fund nothing, reward nothing. The merged
registers make the decision easier to review, not different.

## Addendum - 2026-11-14 (integration session `arena/bfcd9879-korea1`)

The eight bolded requirements were re-checked line by line against the code after
parallel sessions merged their own implementations of the same brief. What this
session added on top, verified in `make build` and `make test` (140 tests):

| Requirement | Where it stands after this session |
|---|---|
| Price-snapshot store | `price-snapshot.html` keeps the strict blank-cell store; **`price-archive.html`** now publishes the archive-populated view: 29704 snapshot rows over 7426 games - 5886 opening prices (2011-2021 archive), 11253 archive closes, 25658 pinned closes, 112 forward freezes - each row tier-labelled and flagged NOT AN AUTHENTICATED QUOTE (G1 fails) |
| Verified results feed | **`results-feed.html`**: 7548 games in three never-mixed tiers (43 official game-centre reads, 7383 pinned-archive finals, 122 scheduled with blank scores), 0 source conflicts, and 18 rows spot re-read on nfl.com this session - all agree |
| Origination order (side then total then moneyline) | Already the code order; now asserted by `tests/test_origination_order.py` (source order + output columns) |
| Fair / market / difference columns | `lines.html` publishes all three per market (spread and total in points, moneyline in price and probability points); the test pins the columns and their arithmetic |
| Signal vs staking on the leaderboard | `strategies.html` prints Units staked and Mean signal edge beside blank ROI: a lucky staking run cannot be read as signal |
| Correlation n and official-only inputs | Annex tables now publish n with every value (BF6 repair); `correlations.html` adds a provenance register for every correlation surface and one correlation computed ONLY from officially read finals with n on the row |
| Demotion gate | Published on `validation.html` from the forward scoreboard (X7/P4 implementations verified, not replaced) |
| Replacement depth | 1st-4th string tracking already published on `lineup-deficiencies.html`; verified, no gap found |

**F-29a:** the four contradictory injury rows flagged by X7 were each re-read on the
live official report (nfl.com/injuries/league/2026/reg10, 2026-11-14). JAX BJ Green II
and CIN Jalen Davis / Andrei Iosivas / Brian Parker II appear exactly as published -
faithful transcriptions of a pairing that is itself contradictory on the official page.

**Decision unchanged:** keep the research engine; fund nothing, reward nothing.

## Addendum - 2026-11-18 (session `arena/f84bc1d7-korea1`, CR1-CR3)

CS5 (the request register) was deferred as "not done" by the 2026-11-18 session log; this
session builds it. **`request-register.html`** now carries one row per standing-request item
(81 rows, REQ-01..REQ-81), each with the status (43 built, 20 partly built, 11 not built, 2 blocked on an owner decision, 2 rejected as requested, 3 process), the repository
evidence, the gate that blocks full delivery and the number or condition that would clear it.
The landing page links it as the decision-readiness table the request asked for.

CR2 re-read eight official pages live on 2026-11-18 (nfl.com week-10 injury report, November
reserve list, week-10 scores, the WAS@NYG game centre, the Texans and Ravens club depth charts,
NFL Operations game prep): 7 checks verified the published values (including the
three Lions Out designations and the Malik Willis reserve row) and 1 refuted the
request's Baltimore stale-QB claim (the live chart reads Brissett | Fagnano | Slovis). Verbatim
excerpts are committed under `data/live/request_spotcheck_2026_11_18/`.

## Addendum - 2026-11-18 (request register, session `arena/53ef9544-korea1`)

The full 2026-11-18 request is now a single decision-readiness register: one row per
request item with its status, the evidence file that supports it, the gate that blocks
it and the number that would clear it. It is published on
`request-register-2026-11-18.html` and in `data/integration/request_register_2026_11_18.csv`.

**81 request items** - 38 done, 30 partly done, 0 built on open PR #82 (not
merged to main), 9 blocked or not started, 3 rejected by design,
1 needing an owner decision. 74 rows carry an official/primary source link;
7 rows have no official source and are printed as flagged text, never filled in.

The register is the consolidated answer to the brief's central ask - the questions,
information and answers that must be resolved before a decision, plus the suggestions
that discover the missing information. It does not change any research number: the
verdict stays **0 of 18 strategies validated, no reward**, and gate G1 (executable quote
provenance) still fails for every candidate.


## Update — 2026-11-20 (`arena/79a986b7-korea1`): every frozen ticket can now be graded

The forward test held frozen picks that could not be settled, so no accuracy, no ROI, no Brier
score and no closing-line value existed for them. That is now closed for Week 10, and closed by
two official documents rather than one.

| What | Count | How it is known | Official source |
|---|---|---|---|
| Week 10 finals published | **14 of 14** | one row per fixture, each certified by two documents | [week 10 scores page](https://www.nfl.com/scores/2026/week-10) |
| Fixtures where both documents agree | **14 of 14** | the league's scores page and the league's own Game Book print the same final; a disagreement writes nothing and fails the build | [the comparison table](assets/data/week10_finals_2026_11_20.csv) |
| Frozen tickets settled against an official final | **65 of 65** | the grading engine labels a ticket `OFFICIAL` only from a recorded official final | [forward test](forward.html) |
| Tickets that finished ahead | 32 of 65 | win/loss only; **not** evidence of skill | [NFL scores](https://www.nfl.com/scores/2026/week-10) |
| Net units across settled tickets | +3.110 | research arithmetic at the frozen prices; the prices are not authenticated quotes | [competition rules](competition.html) |
| Strategies validated / rewarded | **0 of 18 / none** | sample horizons are not reached; no gate is waived | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |

**How a final is accepted.** `pipeline/finals_2026_11_20.py` reads the league's scores page and the
league's own Game Book — the same PDF bytes the scheduled capture committed, checked by SHA-256 —
and writes a row only when the club identities and both scores agree. It raises, and writes nothing,
if a fixture is missing from either document, if a club name does not match, if a score disagrees,
or if a score already in the file would be overwritten. Eleven adversarial tests pin those rules,
including a mutation test that flips one point and asserts the build refuses the row.

**What this does not mean.** 65 settled tickets at 14 games is one week. It is a starting record,
not a result: no p-value, no ROI claim and no verdict is published from it, and the win/loss line
above is arithmetic, not skill. The staking and signal columns stay separate on every surface so a
lucky run cannot be read as a good signal.

**A process defect repaired on the way.** The committed tree was not a fixed point of its own
generators: a plain `make build` on this base modified 15 tracked files, and `tests/check_rebuild.py`
was never run by the verify workflow, so the drift was invisible. One source was the reserve-list
capture workflow, which committed a snapshot but not the two derived files that read it. The verify
workflow now builds twice (self-referential counts), runs `check_rebuild.py`, and fails on any
residual `git diff`; both capture workflows do the same before they commit.

## Material audit corrections

1. **Pinned reproduction:** normal builds now read the committed SHA. Refreshing upstream requires an explicit flag.
2. **No future weather fill:** missing observations stay blank. Weather and roof fields are excluded from the default model until pre-kickoff availability is verified.
3. **Fair benchmark comparison:** each model and market metric uses identical available games for that market.
4. **No whole-week parlay hindsight:** tickets use an earliest eligible simultaneous kickoff slate. They remain research simulations, not confirmed ticket offers.
5. **Discrete predictive probabilities:** prior out-of-fold empirical errors replace the claim that a normal continuity correction correctly prices key numbers.
6. **Dependence-aware inference:** weekly returns, shared stationary-bootstrap resampling and Holm correction replace bet-level independence and an unsupported FDR claim.
7. **Fail-closed verdicts:** all eight gates, including redundancy and official quote provenance, are required. A profitable backtest is not labelled skill.
8. **Trial-count uncertainty:** the complete exploratory search history is unknown. Deflated Sharpe is provisional and cannot certify a strategy.
9. **Source policy:** community hashes are not official NFL verification. Strict public tables blank unverified observations; historical calculations remain in labelled data downloads.
10. **Settlement conflicts:** three 2015 closing-file outcome flags conflict with NFL.com Game Center scores. The score file agrees with NFL.com; the conflicting price-file flags remain flagged.

## What remains blocked

| Missing evidence | Consequence | Official context |
|---|---|---|
| Authenticated historical entry/closing quotes with timestamps and limits | No executable ROI or CLV validation | [NFL official scores](https://www.nfl.com/scores/) |
| Verified player-prop prices and joint SGP quotes | No prop-combo ROI or validated correlation | [NFL injury report](https://www.nfl.com/injuries/) |
| League-wide dated depth charts or official inactives (2 of 32 charts, neither dated) | No confirmed starter/replacement role and no availability term in any model | [NFL injury report](https://www.nfl.com/injuries/) |
| Complete trial registry and untouched prospective replication | No reward eligibility | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Full official census of historical scores and pregame fields | Research inputs remain only partially officially verified | [NFL official scores](https://www.nfl.com/scores/) |

## Reproduce and inspect

Run `make build` and `make test`. The canonical pipeline writes `data/processed/`; the independent
replication annex is preserved under `scripts/`, `data/lab/` and `lab/`. Public annex tables use the same
strict-source policy. Historical JSON/CSV calculations are explicitly unverified research data.

See `audit/REPORT.md`, `data/audit/`, `flagged.html` and `COORDINATION.md` for the audit scope,
conflicts, verification commands and final PR/deployment record. A code/data audit is not a claim that
every third-party historical observation has been individually authenticated.

**Research and education only. No guaranteed returns.**
