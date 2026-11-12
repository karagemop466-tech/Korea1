# NFL Line Lab — requirements and acceptance register

Final integration owner: `arena/3e57f750-korea1`. Updated 2026-11-12.

> **Note (2026-11-12).** This register, `requirements.html` and the earlier `requirements/requirements.csv`
> are three copies of the same register with different wording. The HTML page is authoritative for the
> published status; keeping three copies is flagged as irregularity F-21 rather than silently reconciled.

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
| R19 | Track injuries and lineup deficiencies | `pipeline/injuries.py`; official Week 10 report joined to 6 club depth charts; `injuries.html` | Pilot: 6 of 32 clubs; 26 flagged, never assumed healthy |
| R20 | Review suggestions before implementing | `research/suggestions.csv`; `suggestions.html`; decision log D01-D03 | Implemented; no suggestion accepted |
| R21 | Questions, information and answers register | `research/decision_questions.csv`; `research/information_inventory.csv`; `questions.html` | Implemented; 3 questions block a funded decision |

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
