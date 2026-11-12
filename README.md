# NFL Line Lab

An auditable NFL line-origination and strategy-research dashboard.

**Current decision: no validated betting edge and no reward award.** The engine originates lines and
tests single bets, situational signals and parlays. Authenticated executable quotes and verified
player-prop ticket prices are missing, so the evidence does not support funding a strategy.

## Explore

- `index.html` — clean landing page and searchable leaderboard
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

Research and education only. No guaranteed returns, betting recommendations or funded prize pool.
