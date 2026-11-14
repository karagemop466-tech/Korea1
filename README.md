# NFL Line Lab

An auditable NFL line-origination and strategy-research dashboard.

**Current decision: no validated betting edge and no reward award.** The engine originates lines and
tests single bets, situational signals and parlays. Authenticated executable quotes and verified
player-prop ticket prices are missing, so the evidence does not support funding a strategy.

## Explore

- **`review-queue.html`** — every proposal from all four suggestion registers merged into 14 topic
  clusters; each row keeps its source register, original id, writing session and published page, so a path
  is chosen here before any code changes (added 2026-11-13, `arena/132e7ca2-korea1`)
- **`answers.html`** — all four question registers merged: information we have, information we do not, the
  answer on record (blank when there is none) and the step that would close each gap (added 2026-11-13)
- **`competition.html`** — the leaderboard competition: entry rules, three divisions, a seven-tier reward
  ladder, the eight-gate luck-removal battery and standings ranked on gates passed, not profit
  (added 2026-11-13)
- **`repo-review.html`** — every tracked file inventoried, the official-source checks run during the
  2026-11-13 review, the row-by-row injury and score comparisons, and six irregularities (added 2026-11-13)
- `index.html` — clean landing page and searchable leaderboard
- `review.html` — **all four suggestion registers and all three question registers in one table** (76 proposals, 74 questions), clustered by topic, with one recommended first move and its limits. Nothing implemented.
- `live-verification.html` — **line-by-line re-check of the published availability data against the official pages**: injury cells, depth-chart slots and all 59 matchup sentences, each with a verdict and its source
- `decision-board.html` — suggestions with options, to review and choose before any change is made
- `open-questions.html` — what is known, what is missing, how to find it
- `availability.html` — official injury report joined to official club depth charts (starter / 2nd / 3rd / 4th string)
- `executive-summary.html` — decision and limitations
- `lines.html` — model design and research line board
- `strategies.html` — complete candidate library and competition rules
- `forward.html` — **forward test**: picks frozen before kickoff, settled only against official NFL.com finals (4 of 65 settled; no verdicts, no rewards)
- `validation.html` — eight fail-closed gates
- `correlations.html`, `props.html` — joint-dependence and prop evidence boundaries
- `referents.html` — every citation on the site, resolved against the live page it points at
- `audit.html`, `flagged.html`, `sources.html` — official comparisons, irregularities and references
- `suggestions-review.html` — dedicated interactive Path A / B / C selector across 12 staged improvements (review before implementing changes)
- `suggestions.html` — 22 proposals with cost, risk, dependencies and four decision paths
- `decision-readiness.html` — 14 pre-decision Q&As, 8 missing-info discovery blueprints and all 28 post-pin settled Week 8–9 NFL.com scores
- `decisions.html` — 12 decision questions, known answers and discovery steps (parallel session register)
- `questions.html` — what must be known before a decision, what is answered and what is blocked
- `lineup-deficiencies.html` — 39 verified Week 10 offensive & defensive 1st–4th string entries across 8 NFL clubs (`WAS`, `NYG`, `NE`, `DET`, `KC`, `ATL`, `MIN`, `GB`), NFL Operations T-90m countdown rules, and prefix-safe PBP backup diagnostics
- `lineups.html` — seven observed players plus two club depth charts; roles and impacts blank
- `injuries.html` — verified official captures, the coverage gap and the availability signal register
- `requirements.html` — requirement-by-requirement delivery register
- `DECISIONS.md` — dated decision log (owner-facing)
- `lab/` — independent historical replication annex, strict public view

The publication source is **`main` / repository root**, not `docs/`.
Live site: <https://karagemop466-tech.github.io/Korea1/>.

## Consolidation pass — 2026-11-13 (`arena/132e7ca2-korea1`)

Four registers of suggestions and four registers of questions had been written in parallel by sessions
that could not see each other. `pipeline/session_decide.py` merges them without deleting any register:
every merged row keeps its source register, its original id, the session that wrote it and the page it is
published on, and rows are grouped into topic clusters so the same idea written twice is visible side by
side. `review-queue.html` is the decision surface; `answers.html` is the knowledge register. A second,
independently written consolidation of the same registers is `review.html`.

`pipeline/session_competition.py` publishes the competition: entry rules, the three divisions, the
seven-tier reward ladder, the eight fail-closed gates with the statistic that enforces each, the
sample-size arithmetic, and the standings. No prize pool exists; tier T5 (stake allocation) is explicitly
not funded.

`pipeline/session_review.py` inventories every tracked file and re-reads the official pages the project
captures. On 2026-11-13 the injury capture was compared row by row with the live NFL.com page (54 of 98
sampled rows identical on all four fields — no transcription error found; the rest are later page
updates), the post-pin score register was compared with the live NFL.com scores page (8 of 8 sampled
games identical), the pinned upstream commit was opened and confirmed, and the NFL Operations 90-minute
Game Day Administration Report rule was read and confirmed. Six irregularities are recorded on
`repo-review.html` and on `flagged.html`; none was repaired, because repair is a decision for the owner
and the files belong to earlier sessions.

## Reproduce

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
make build
make test
```

`make build` stages and hash-checks the pinned community archive, builds the canonical tables,
renders the root site and strict annex, and checks official/primary row references, blank unverified
metric cells, internal links, local assets and verdict logic. Normal builds do not move the pin.
An upstream refresh requires `python pipeline/fetch_data.py --refresh-pin` followed by a new audit.

The independent annex can be rebuilt with `PYTHON=.venv/bin/python make annex`.
Historical calculations remain in `data/lab/`; public annex tables do not present them as official facts.

## Independent verification (2026-11-13)

The build's own verifier proves every row *carries* an official link; it cannot prove the row
*matches* it. `make liveverify` runs three graders that read committed official extracts under
`data/live/` and compare them with what is published:

| Grader | What it checks | Result on 2026-11-13 |
|---|---|---|
| `pipeline/live_verify.py` | the published injury table, field by field, against `nfl.com/injuries/league/2026/reg10` | parser controlled against the repo's own verbatim 2026-11-12 capture: **254/254 rows, 0/1,016 cells differ**; 3 of 8 clubs clean, 1 confirmed defect, 8 unresolved |
| `pipeline/live_verify_depth.py` | every depth-chart slot as an ordered list, against four official club charts | **115/115 slots, 239 players** |
| `pipeline/lineup_claims.py` | all 59 availability sentences on `lineup-deficiencies.html`, against three official captures | **41 current, 17 stale, 0 contradicted**; 57 of 59 agree with the contemporaneous archive |

The control matters: because the parser is provably faithful on a fixed document, a difference
found against today's live page is the *source moving*, not the build misreading it. The official
page revised **57 of 326** player values in the 29 hours between the two captures — which is why
every status needs its capture time beside it.

`make reviewall` also consolidates the four suggestion registers and three question registers
(`pipeline/review_consolidated.py`) without deleting, renumbering or re-ranking anything.

## Forward test (settlement)

`forward.html` publishes the picks frozen before kickoff, settled only against an official NFL.com
final. `.github/workflows/forward-ledger.yml` removes manual input from the parts that are safe to
automate: it archives official game pages, re-runs the settlement engine and rebuilds the page. It
writes *proposed* scores to `data/forward/official_candidates.csv` and **never** to
`data/forward/official_results.csv`, which is evidence; promotion of a proposal stays a reviewed
step because the extraction rules have never been validated against real NFL.com HTML. The module
asserts that by hashing the evidence file before and after each run, and
`tests/test_forward_capture.py` fails if it ever changes.

## Availability tracker

`.github/workflows/availability.yml` runs on a schedule on a GitHub-hosted runner (the build sandbox
cannot reach nfl.com). It reads <https://www.nfl.com/injuries/> and each club's `/team/depth-chart`
page, writes `data/availability/` (with a dated copy under `history/`), rebuilds `availability.html`,
runs the site checks and commits. `make build` only reads the committed snapshot. Nothing is inferred:
empty official cells stay empty, failed pages are blank and flagged.

## Additive injury / availability pipeline (session `arena/774867ed-korea1`)

A second, independent pipeline runs alongside the availability tracker above. It reads a committed
verbatim copy of the official injury page under `data/evidence/nfl_injuries/` (the sandbox shell
cannot reach nfl.com, so the page is captured with the page-fetch tool and written to disk with its
SHA-256), stages the pinned community roster archive, and produces availability, position-group
pressure, QB depth, roster-depth history and lineup-deficiency tables under
`data/processed/injury_*.csv` / `lineup_deficiency*.csv` / `roster_depth_history.csv`. The
suggestion and open-question registers live in `research/*.md` and are validated by
`pipeline/build_review.py`, which **fails the build** on an empty required cell, a duplicate id, an
out-of-vocabulary status, or a source that is neither official/primary nor explicitly flagged. Run
them with `make injuries review`; `make build` runs them automatically. None of these tables or
registers replaces a published page — they are additive evidence and downloads.

## Citation integrity (`referents.html`)

Every published row was already checked for the *presence* of an official reference. Presence is not
proof: a URL that resolves to a 404 looks like evidence and is not. `scripts/referent_probe.py` extracts
every external URL printed on the site and resolves it on a GitHub-hosted runner (the build sandbox has
no egress to NFL or club domains), recording HTTP status, redirect target, body hash, page title and —
where a claim check is defined — whether the page actually contains the text the row attributes to it.
`scripts/score_reconcile.py` re-opens the official game page for all 28 rows of the Week 8–9 2026 score
census and re-reads each final score.

The current run resolves 455 of 475 printed URLs, with 8 redirects, 11 unresolved and one claim check
that the machine cannot perform (the FanDuel help centre is client-rendered; a manual read is recorded
instead and the reason is published). Results, including the exact URLs that do not resolve, are on
`referents.html` and cross-listed on `flagged.html` as F-21 to F-28.

```bash
# regenerate the page from the committed probe output
make referent-render
# re-probe (needs outbound network access; normally the scheduled workflow does this)
make referents
```

Nothing here repairs a citation automatically. A URL is only changed after a human has confirmed the
replacement page says the same thing.

## Evidence policy

Official NFL observations, primary method references, operator terms and community research inputs
are different evidence classes. Every public table row has an official/primary reference. Unverified
metric cells are blank and flagged. A hash proves file integrity, not that a community price was an
executable bookmaker offer. Model estimates are not official observations.

## Important repairs

The final audit fixed moving-pin builds, full-history weather fill, mismatched benchmark samples,
whole-week parlay lookahead, hard-coded/weak validation gates, iid bet-level inference, misleading
key-number pricing claims, and permissive source checking. See `audit/REPORT.md` and `flagged.html`.

## Coordination and deployment

Read `COORDINATION.md` before editing. The review surface was built by two sessions and merged:
`arena/25460478-korea1` owns the suggestion/question/injury registers, and `arena/03f66e17-korea1`
owns the readiness register, lineup-evidence page and the read-only source monitor. Both claims,
their sources, the verification runs and the PR/merge/deploy record are appended there.

## Injury and decision-readiness boundaries

The follow-up dated **2026-11-12** adds a seven-player WAS/NYG official injury-report sample and the
ordered cells of club depth charts. The scheduled tracker captured 31 of 32 charts on 2026-11-13 (Houston returned no
ordered rows); the Arizona and Washington charts were checked cell by cell that day. No chart shows a publication time, and chart order does not prove a game-time role, a promotion or
a performance deficiency. Unknown fields stay blank. The scheduled monitor only archives sources.
The separate scheduled all-club capture is `availability.html` (see *Availability tracker* above), added by
`arena/c0528572-korea1`.

Research and education only. No guaranteed returns, betting recommendations or funded prize pool.
