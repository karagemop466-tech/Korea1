# NFL Line Lab

An auditable NFL line-origination and strategy-research dashboard.

**Current decision: no validated betting edge and no reward award.** The engine originates lines and
tests single bets, situational signals and parlays. Authenticated executable quotes and verified
player-prop ticket prices are missing, so the evidence does not support funding a strategy.

## Explore

- `index.html` — clean landing page and searchable leaderboard
- `executive-summary.html` — decision, current build and limitations
- `lines.html` — model design and research line board (current week)
- `injuries.html` — official injury report joined to club depth charts (Week 10, 2026 pilot)
- `strategies.html` — complete candidate library and competition rules
- `validation.html` — eight fail-closed gates
- `correlations.html`, `props.html` — joint-dependence and prop evidence boundaries
- `suggestions.html` — proposals, three decision paths and a decision log (review before implementing)
- `questions.html` — what is known, what is missing and how to find out
- `audit.html`, `flagged.html`, `sources.html` — official comparisons, irregularities and references
- `requirements.html` — requirement-by-requirement delivery register
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

`make build` stages and hash-checks the pinned community archive, builds the canonical tables, joins the
official injury snapshot to the club depth charts, renders the root site and strict annex, and checks
official/primary row references, blank unverified metric cells, internal links, local assets and verdict
logic. Normal builds do not move the pin. An upstream refresh requires
`python pipeline/fetch_data.py --refresh-pin` followed by a new audit.

The independent annex can be rebuilt with `PYTHON=.venv/bin/python make annex`.
Historical calculations remain in `data/lab/`; public annex tables do not present them as official facts.

## Evidence policy

Official NFL observations, primary method references, operator terms, club publications and community
research inputs are different evidence classes. Every public table row has an official/primary reference.
Unverified metric cells are blank and flagged. A hash proves file integrity, not that a community price
was an executable bookmaker offer. Model estimates are not official observations.

The injury register adds one more distinction: a **club-published depth chart** is an official club
publication, but New England, Detroit and Kansas City label theirs **unofficial**. The register therefore
calls a player a starter only as a *projection from that chart*, reports players missing from the chart as
`UNRANKED` instead of guessing a role, and marks the 26 clubs it does not cover as not covered rather than
injury-free. The pilot covers three of the Week 10 games and six of the 32 clubs, and game designations can change until kickoff, so the capture time is printed on the page.

## Current build (2026-11-12)

The pinned snapshot was refreshed from `a270278f` (2026-11-02) to `9654533e` and every artefact was
rebuilt. The line board now starts at Week 10 (2026-11-12) instead of listing played games, and the model
inputs include results through Week 9. Settled tickets moved 27,218 → 27,344, spread error 10.523 → 10.522
against the market's 10.214, total error 10.762 → 10.768 against 10.529, and the White reality-check
p-value moved 0.186 → 0.463 (research only). **No verdict changed: 0 of 18 candidates pass all eight gates
and no reward is awarded.** The model still loses to the market on both markets.

## Important repairs

Moving-pin builds, full-history weather fill, mismatched benchmark samples, whole-week parlay lookahead,
hard-coded/weak validation gates, iid bet-level inference, misleading key-number pricing claims and
permissive source checking were repaired in earlier sessions. This session repaired a stale pin that
published played games as upcoming, an unwired executive-summary addendum carrying pre-refresh figures,
and a README that named the previous session. See `audit/REPORT.md` and `flagged.html` (F-01 … F-21).

## Coordination and deployment

Read `COORDINATION.md` before editing. This Arena session is `arena/3e57f750-korea1`; its claim, task
scope, verification record and final PR/merge/deployment record are appended there.

Research and education only. No guaranteed returns, betting recommendations or funded prize pool.
