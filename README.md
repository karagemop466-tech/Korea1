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
- `decisions.html` — 12 decision questions, known answers and discovery steps (parallel session register)
- `suggestions.html` — 22 proposals with cost, risk, dependencies and four decision paths
- `questions.html` — what must be known before a decision, what is answered and what is blocked
- `lineups.html` — seven observed players plus two club depth charts; roles and impacts blank
- `injuries.html` — verified official captures, the coverage gap and the availability signal register
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
