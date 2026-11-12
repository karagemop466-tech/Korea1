# NFL Line Lab — requirements and acceptance register

Final integration owner: `arena/ed58af62-korea1`. Updated 2026-11-02.

| ID | Requirement | Acceptance evidence | Status |
|---|---|---|---|
| R01 | Collect, organize and analyze requirements | This register; `requirements.html`; `COORDINATION.md` | Implemented |
| R02 | Originate own NFL lines | `pipeline/models.py`; margin, total and moneyline estimates; paired benchmarks | Implemented; estimates unverified |
| R03 | Research signal strategies | `pipeline/strategies.py`; complete candidate and hypothesis register | Implemented; no validated edge |
| R04 | Single bets | Spread, total, moneyline and situational candidates | Implemented; executable quotes unavailable |
| R05 | Parlays | Simultaneous-slate selection; push-aware research settlement; price stress | Implemented; not executable ticket validation |
| R06 | Player-prop combinations | Pinned community player statistics, research lines, dependence and combo calculations | Executable validation blocked by missing verified prop prices/quotes |
| R07 | Every strategy passes validation gates | Eight fail-closed gates; `strategy_gates.csv`; regression tests | Enforced; no strategy currently validated |
| R08 | Determine correlation values | Weekly-cluster research estimates; strict public blanks for unverified inputs | Partial; no invented prop correlations |
| R09 | Remove luck / build selectively skill-based strategies | Weekly bootstrap, Holm, power, provisional DSR, stability, redundancy, prospective protocol | Mitigation implemented; luck cannot be eliminated |
| R10 | Leaderboard competition with rewards | Complete leaderboard; eligibility tiers; anti-gaming rules | Implemented; rewards unawarded; no funded prize pool |
| R11 | Executive summary | `EXECUTIVE_SUMMARY.md`; `executive-summary.html` | Implemented |
| R12 | No manual user input | `make build`, `make test`, static site, no runtime API dependency | Implemented |
| R13 | Review repository against authoritative sources | `audit/REPORT.md`; code findings; official score sample; source registers | Targeted audit complete; not a full official census |
| R14 | Clean landing page and category subpages | Root dashboard and category pages; local assets; searchable/sortable tables | Implemented |
| R15 | Official-source link on every table row | Allowlist-based row checker; canonical and strict annex pages | Enforced |
| R16 | Unconfirmable values blank and flagged | Strict public metric cells blank; explicit UNVERIFIED labels; research downloads segregated | Enforced |
| R17 | Coordinate parallel work | Claims, scopes, conflict log, pinned session branch, final integration ownership | Implemented |
| R18 | PR, merge, deploy and verify live site | Final PR and Pages API/live-page record in `COORDINATION.md` | Recorded after execution, never inferred |
| R19 | Dedicated suggestions section, reviewed before changes | `suggestions.html`: 22 proposals with cost, risk, dependencies, four paths and a change-control workflow; `decisions.html` adds the parallel 8-proposal register; CSVs published | Implemented, nothing approved |
| R20 | Questions, information and answers needed before a decision | `questions.html`: 40 questions (28 answered, 2 open, 8 blocked, 2 for decision); answered rows cite a source, blocked rows are blank with a closure test; `decisions.html`: 12 readiness questions | Implemented |
| R21 | Injuries and lineup deficiencies (starters vs backups) | `injuries.html`: 12 official sources checked, two games captured exactly (2026 wk10: 20 rows; 2019 wk5: 11), eight-signal register; `lineups.html`: 7 observed players + ordered cells from 2 club charts | PARTIAL — order only: 2 of 32 clubs, no chart publication time, no confirmed game-day role |
| R22 | Dated decision log | `DECISIONS.md`, linked from the suggestions page | Implemented |
| R23 | Row-by-row official injury capture and depth join | `availability-capture.html`: 258 transcribed rows, every row linking the official report; `depth-register.html`: 61 rows across 6 clubs joined by exact name to 354 ranked depth rows, 9/9 integrity checks, 6 players reported UNRANKED rather than guessed | PARTIAL — 6 of 32 clubs, 4 charts self-labelled UNOFFICIAL, no chart timestamp |
| R24 | Information inventory: what exists, what does not, how to close it | `information-gaps.html`: 40 questions (site register) plus the 15-question inventory of this build (3 BLOCKING, 6 HIGH) with 3 HAVE / 3 PARTIAL / 6 MISSING and a named closure method per gap | Implemented |
| R25 | Choose a path before implementation | `decision-paths.html`: 22 proposals (site register) plus 13 of this build grouped into paths A evidence-first, B availability-first, C competition-first, each with cost, risk, dependencies and a recorded decision log | Implemented, nothing chosen |

## Evidence policy

- Official NFL observations: NFL.com / NFL Football Operations.
- Primary methods: original paper, publisher, author or university record.
- Operator settlement terms: the specific operator's published help/rules.
- Community data: hash-pinned research input, never described as official NFL data.
- A model estimate is not an observation. An official context link does not authenticate a community price.
- Missing observations are not filled from future data, adjacent rows or invented prices.

## Validation policy

All eight gates are necessary. Official timestamped executable quotes, complete trial history and
untouched prospective replication are required before recognition. Statistical significance alone is
not skill, and failure to reject is not proof of no skill. No monetary reward or betting recommendation
is authorized by this repository.
