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
| R19 | Dedicated suggestions section, reviewed before changes | `suggestions-review.html` (12 staged proposals with Path A/B/C interactive selector) + `suggestions.html` (22 proposals, four paths and change-control workflow) + `decisions.html` (parallel 8-proposal register); CSVs published | Implemented, nothing approved |
| R20 | Questions, information and answers needed before a decision | `decision-readiness.html` (14 Q&As + 8 missing-info discovery blueprints) + `questions.html` (40 questions) + `decisions.html` (12 readiness questions) | Implemented |
| R21 | Injuries and lineup deficiencies (starters vs backups) | `lineup-deficiencies.html` (39 Week 10 offensive & defensive 1st–4th string entries across 8 clubs / 4 matchups + prefix-safe PBP backup diagnostics) + `injuries.html` (12 official sources checked, eight-signal register) + `lineups.html` | Expanded — 8 of 32 clubs verified; club disclaimers & roster lag flagged; no confirmed game-day snap counts |
| R22 | Dated decision log | `DECISIONS.md`, linked from the suggestions pages | Implemented |
| R23 | Post-pin Week 8–9 official score census & T-90m countdown verification | `decision-readiness.html` reconciles all 28 settled Week 8–9 NFL.com Final scores; `lineup-deficiencies.html` verifies NFL Operations T-90m/T-60m pregame inactive & roof rule | Implemented |

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
