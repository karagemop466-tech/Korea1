# NFL Line Lab

An auditable NFL line-origination and strategy-research dashboard.

**Current decision: no validated betting edge and no reward award.** The engine originates lines and
tests single bets, situational signals and parlays. Authenticated executable quotes and verified
player-prop ticket prices are missing, so the evidence does not support funding a strategy.

## Explore

- `index.html` — clean landing page and searchable leaderboard
- `decision-board.html` — suggestions with options, to review and choose before any change is made
- `open-questions.html` — what is known, what is missing, how to find it
- `availability.html` — official injury report joined to official club depth charts (starter / 2nd / 3rd / 4th string)
- `executive-summary.html` — decision and limitations
- `lines.html` — model design and research line board
- `strategies.html` — complete candidate library and competition rules
- `validation.html` — eight fail-closed gates
- `correlations.html`, `props.html` — joint-dependence and prop evidence boundaries
- `audit.html`, `flagged.html`, `sources.html` — official comparisons, irregularities and references
- `suggestions-review.html` — dedicated interactive Path A / B / C selector across 12 staged improvements (review before implementing changes)
- `suggestions.html` — 22 proposals with cost, risk, dependencies and four decision paths
- `decision-readiness.html` — 14 pre-decision Q&As, 8 missing-info discovery blueprints and all 28 post-pin settled Week 8–9 NFL.com scores
- `decisions.html` — 12 decision questions, known answers and discovery steps (parallel session register)
- `questions.html` — what must be known before a decision, what is answered and what is blocked
- `lineup-deficiencies.html` — 39 verified Week 10 offensive & defensive 1st–4th string entries across 8 NFL clubs (`WAS`, `NYG`, `NE`, `DET`, `KC`, `ATL`, `MIN`, `GB`), NFL Operations T-90m countdown rules, and prefix-safe PBP backup diagnostics
- `lineups.html` — seven observed players plus two club depth charts; roles and impacts blank
- `injuries.html` — verified official captures, the coverage gap and the availability signal register
- `review/index.html` — **independent repo audit, 2026-11-13**: every published claim re-derived from the
  file that backs it, every cited official page re-read, and all 22 proposals ranked on one scale
  (`review/claims.html`, `review/my-lines.html`, `review/injuries.html`, `review/suggestions.html`,
  `review/questions.html`, `review/official-sources.html`, `review/flagged.html`)
- `requirements.html` — requirement-by-requirement delivery register
- `DECISIONS.md` — dated decision log (owner-facing)
- `lab/` — independent historical replication annex, strict public view

The publication source is **`main` / repository root**, not `docs/`.
Live site: <https://karagemop466-tech.github.io/Korea1/>.

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

## Independent repo audit (`review/`)

`make audit` re-derives **every** published number from the artifact that is supposed to support it and
publishes the result on `review/`. Current result: **45 claims checked —
36 confirmed exactly, 3 flagged as drift, 1 undecidable (left
blank), 5 self-referential**.

The flags that matter, each with the file that decides it (full detail on `review/flagged.html`):

1. **The reproducibility baseline is stale.** `data/processed/audit_digests.csv` records a SHA-256 for
   every derived table and rendered page, and `pipeline/audit.py` was written to fail when a digest no
   longer matches. Re-running that comparison today fails on **34 of 50** entries, including
   `strategy_bets.csv` (recorded 26,149 rows, now 27,218) and `verification_report.csv` (13 pages, now
   33). Fixing it rewrites published numbers, so it is the owner's call.
2. **`26,149` is no longer reproducible.** The single-leg ticket count quoted in SUG-03 recomputes to
   26,188 today; the all-rows total is 27,218.
3. **The Week 10 Thursday game is settled.** WAS 24 – NYG 21 went Final on 2026-11-12 per
   <https://www.nfl.com/schedules/>, so any Week 10 line frozen before it is closed.
4. **One Week 8 game is absent from the post-pin score register.** NFL.com's Week 8 page carries 14
   finals; `post_pin_nfl_scores_2026_11_12.csv` lists 13 for Week 8. Verified against
   <https://www.nfl.com/scores/2026/REG8>; recorded as an observation, not as a dataset error.

One finding was **fixed by a parallel session while this audit was running** and is now recorded as
confirmed: the depth-chart coverage text states 31 of 32, matching `data/availability/manifest.json`.

The audit also re-read the official pages the site cites. All 28 Week 8–9 score rows, the 20 WAS/NYG
injury rows, 89 of 89 club depth-chart cells, the T-90 inactive rule, the operator parlay push rule and
both primary statistics papers still say what the site says they say
(`review/official-sources.html`, captures in `data/repo_audit/captures/`). The sandbox shell cannot
reach nfl.com, so these were read with the agent page-fetch tool and transcribed with a timestamp.

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
ordered cells of two club depth charts. This is not a live all-club service: coverage is 2 of 32 clubs,
neither chart shows a publication time, and chart order does not prove a game-time role, a promotion or
a performance deficiency. Unknown fields stay blank. The scheduled monitor only archives sources.
The separate scheduled all-club capture is `availability.html` (see *Availability tracker* above), added by
`arena/c0528572-korea1`.

Research and education only. No guaranteed returns, betting recommendations or funded prize pool.
