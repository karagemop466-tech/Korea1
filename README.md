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
- `decisions.html` — questions, known answers, missing evidence and discovery steps
- `suggestions.html` — proposed improvements, alternatives and acceptance evidence; none approved
- `lineups.html` — dated official injury/chart evidence; unconfirmed roles and impacts blank
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

Read `COORDINATION.md` before editing. Each Arena session is pinned to its own `arena/<id>-korea1`
branch; PR, merge and deployment records are appended to `COORDINATION.md`.

Research and education only. No guaranteed returns, betting recommendations or funded prize pool.

## Injury and decision-readiness boundaries

The follow-up dated **2026-11-12** adds a seven-player WAS/NYG official injury-report sample
and selected chart rows from the two clubs (`lineups.html`). That sample is not a live all-club service;
the scheduled all-club capture is `availability.html` (see *Availability tracker* above). Published chart
order does not prove a game-time role, promotion or performance deficiency. Unknown fields stay
blank; proposed model changes remain unapproved in the suggestions queue.

`pipeline/monitor_official.py` runs daily via `official-monitor.yml` and stores official response
archives and success/failure manifests as 30-day Actions artifacts. It does not silently update
the dated site sample, historical research pin or model inputs. Local restricted-network failures
are recorded, not replaced by cached success. Run `python pipeline/monitor_official.py` to inspect
collection; normal `make build` is deterministic and does not fetch changing official pages.
