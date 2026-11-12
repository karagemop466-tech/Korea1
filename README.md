# NFL Line Lab

An auditable NFL line-origination and strategy-research dashboard.

**Current decision: no validated betting edge and no reward award.** The engine originates lines and
tests single bets, situational signals and parlays. Authenticated executable quotes and verified
player-prop ticket prices are missing, so the evidence does not support funding a strategy.

## Explore

- `index.html` — clean landing page, Week 10 status banner and searchable leaderboard
- `decision-board.html` — parallel decision-board register covering DB-01 through DB-07
- `open-questions.html` — parallel open-questions register with GitHub issue closure templates
- `availability.html` — scheduled all-club official injury report joined to official club depth charts (starter / 2nd / 3rd / 4th string)
- `executive-summary.html` — decision and limitations
- `lines.html` — model design and research line board (136 scheduled 2026 games)
- `injuries.html` — Week 10 2026 official injuries & Offense/Defense 1st–4th string club depth deficiencies, 5 stale `nfldata` QB catches, historical QB/PBP absence research, and preserved 2019 pilot & availability register
- `lineups.html` — seven observed players plus two club depth charts; unconfirmed roles and impacts blank
- `strategies.html` — complete candidate library (18 strategies) and competition rules
- `validation.html` — eight fail-closed validation gates
- `correlations.html`, `props.html` — joint-dependence and prop evidence boundaries (2019–2022 PBP logs)
- `questions.html` — Known vs. Unknown inventory, 14 grounded Q&As, missing-data discovery plan, and preserved 40-question register
- `decisions.html` — 12 decision-readiness questions, parallel proposal register, and discovery steps
- `suggestions.html` — concrete Option A/B/C improvement tracks (`Proposed — awaiting selection`) plus 20-proposal register and decision worksheet
- `audit.html`, `flagged.html`, `sources.html`, `verification.html` — 59/59 NFL.com score comparisons, 28 club depth URLs, irregularities, pinned hashes and reproducibility
- `requirements.html` — 46-requirement traceability matrix rendered directly from `requirements/requirements.csv`
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
make audit
.venv/bin/python tests/check_rebuild.py
```

`make build` stages and hash-checks the pinned community archive, builds the canonical tables,
runs Week 10 injury/depth and historical absence pipelines (`pipeline/injuries.py`), renders all
18 root pages and the 9-page strict annex, and checks official/primary row references, blank
unverified metric cells, internal links, local assets and verdict logic. Normal builds do not move the pin.
An upstream refresh requires `python pipeline/fetch_data.py --refresh-pin` followed by a new audit.

The independent annex can be rebuilt with `make annex`.
Historical calculations remain in `data/lab/`; public annex tables do not present them as official facts.

## Availability tracker

`.github/workflows/availability.yml` runs on a schedule on a GitHub-hosted runner (the build sandbox
cannot reach nfl.com). It reads <https://www.nfl.com/injuries/> and each club's `/team/depth-chart`
page, writes `data/availability/` (with a dated copy under `history/`), rebuilds `availability.html`,
runs the site checks and commits. `make build` only reads the committed snapshot. Nothing is inferred:
empty official cells stay empty, failed pages are blank and flagged.

## Evidence policy

Official NFL/club observations, primary method references, operator terms and community research inputs
are different evidence classes. Every public table row has an official/primary reference. Unverified
metric cells and image-only club depth strings (`HOU`) remain blank and flagged. A hash proves file integrity,
not that a community price was an executable bookmaker offer. Model estimates are not official observations.

## Important repairs

Prior integration (`arena/ed58af62-korea1`) fixed moving-pin builds, full-history weather fill, mismatched
benchmark samples, whole-week parlay lookahead, weak validation gates, and permissive source checking.
Follow-up work (`arena/f115e6a2-korea1`) refreshed `nfldata` to `9654533e` (59/59 NFL.com score matches),
added 28-club Week 10 injuries/depth + Q&A + Option A/B/C suggestions, removed orphaned `weather_fill.json`,
repaired missing CSS classes, fixed `audit.py` claim checks and `FEATURE_DICT` / `models.py` / `prop_inputs.csv`
contradictions, unified `requirements/requirements.csv` across MD/HTML, added `verification.html` to
`tests/check_sources.py`, and merged `origin/main` readiness/monitor registers (`decisions.html`, `lineups.html`,
`DECISIONS.md`, `official-monitor.yml`, `tests/test_{decisions,review_registers}.py`).
See `audit/REPORT.md` and `flagged.html`.

## Coordination and deployment

Read `COORDINATION.md` before editing. Previously merged sessions (`arena/25460478-korea1`,
`arena/03f66e17-korea1`, `arena/c0528572-korea1`) added `decisions.html`, `lineups.html`, `availability.html`,
`decision-board.html`, `open-questions.html`, `DECISIONS.md`, `research/decision-register.json`, and the
`official-monitor.yml` / `availability.yml` scheduled collectors. Current active integration branch:
`arena/f115e6a2-korea1`.

## Injury and decision-readiness boundaries

Two complementary Week 10 availability tracks exist cleanly side by side:
`injuries.html` (`pipeline/injuries.py`, 27/28 Week 10 club HTML depth charts, 5 stale `nfldata` QBs caught,
`HOU` blank image-only) plus `availability.html` (`pipeline/fetch_availability.py` / `depth_status.py`
scheduled GitHub Actions collector) and `lineups.html` (seven WAS/NYG observations + two club depth charts).
All unverified cells stay blank; no availability adjustment enters automated lines or betting signals.

Research and education only. No guaranteed returns, betting recommendations or funded prize pool.
