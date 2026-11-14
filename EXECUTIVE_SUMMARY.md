# Executive summary — NFL Line Lab

Final integration: 2026-11-13. Research snapshot: `a270278f3ac4e937295fe6a27814b3c4a2b62645`.

## Decision

**Keep the research engine; do not fund or reward a betting strategy yet.** The repository originates
NFL lines and evaluates single-bet, situational and parlay candidates. It does not contain authenticated,
timestamped executable bookmaker quotes or verified player-prop ticket prices. **0 of 18 canonical
strategies pass all eight final gates.** No prize, capital allocation or profitable recommendation is authorized.

“Unverified” is not a finding of zero edge. It means the evidence cannot support the stronger claim.
Statistical corrections reduce false discoveries; they cannot eliminate luck or guarantee future returns.

## Decision readiness & lineup follow-up — 2026-11-12

Four review registers sit in front of the research, generated from the same data as the pages, and none
of them is an approval:

| Register | Size / status | What it establishes |
|---|---|---|
| `suggestions-review.html` | 12 staged improvements — interactive Path A / B / C selector | Side-by-side Conservative / Balanced / Full path options, trade-offs, affected gates and browser-only decision JSON export before any model or rule edit |
| `suggestions.html` | 22 proposals — 8 ready now, 6 pilot, 4 recommended before any reward, 2 rejected, 1 deferred, 1 blocked | Cost, risk, dependency and acceptance evidence for every change, plus four paths (A–D) and a change-control worksheet |
| `decision-readiness.html` | 14 pre-decision Q&As, 8 discovery protocols & 28 post-pin NFL.com scores | Separates verified knowns from missing inputs and reconciles all 28 Week 8–9 2026 games settled on NFL.com after the 2026-11-01 archive pin |
| `decisions.html` | 12 readiness questions plus a parallel 8-proposal register | Current answers, missing inputs, discovery steps and the gate each one feeds |
| `questions.html` | 40 questions — 29 answered, 2 open, 7 blocked, 2 needing an owner decision | Every answer cited; blocked rows left blank with the reason and a closure test |
| `lineup-deficiencies.html` | 39 Week 10 entries across 8 clubs / 4 matchups + NFL Operations T-90m rule | Offensive & defensive 1st–4th string tracking across `WAS@NYG`, `NE@DET`, `KC@ATL` and `MIN@GB`, club disclaimers/trade lag, and prefix-safe PBP backup diagnostics |

Two dated captures are transcribed in `injuries.html`: the 2026 week-10 WAS/NYG report (20 rows — 2 Out, 1
Questionable, 17 blank) and 2019 week 5 (11 rows), while `lineup-deficiencies.html` expands verified 2026
Week 10 depth-chart coverage to **8 of 32 clubs** (`commanders.com`, `giants.com`, `patriots.com`,
`detroitlions.com`, `chiefs.com`, `atlantafalcons.com`, `vikings.com`, `packers.com`) and documents the
mandatory T-90m Game Day Administration inactive & roof rule on `operations.nfl.com`. 8 availability signals assessed: 1 available, 4 pilot-only, 2 open, 1 blocked — **0 in
the leaderboard**, because none clears the leakage and confirmation tests and the board is pinned before week 8.

The initial official source inventory in `availability.py` holds 12 checks (9 verified,
3 verified-negative, including 2 club depth charts), and `sources_lineups.json` adds 6 further
verified club depth charts (total **8 of 32 clubs**). No player is called a confirmed game-day replacement,
no depth rank is invented for a player absent from a chart, and no availability signal enters the model.
A read-only daily Actions monitor archives the sources; collection is not verified extraction. All-club
coverage, game-day role confirmation and validated impact remain blocked.

## Update of 2026-11-12

| Area | Status | What changed and what it means | Official reference |
|---|---|---|---|
| Injuries and lineups | Tracking live; effect not priced | A scheduled GitHub Actions workflow reads the official NFL.com injury report and each club's depth-chart page and publishes, for offense and defense, which first-listed players are Out or Doubtful and which 2nd, 3rd or 4th-string player the club lists next (`availability.html`). It does not yet move the originated line: the point value of an absence has not been measured. | [NFL injury report](https://www.nfl.com/injuries/) |
| Suggestions | Awaiting your decision | Every proposed change is on `decision-board.html` with options, a recommendation and the evidence behind it. Nothing is implemented. Decide DB-02 (real prices) and DB-03 (forward paper ledger) first. | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Open questions | Unanswered | `open-questions.html` separates what is known from what is missing and names how to find it. Some only you can answer: sportsbooks and jurisdiction, bankroll, success threshold, refresh cadence, reward. | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Line board freshness | Stale | The open line board still starts at Week 8 (snapshot pinned 2026-11-02); the injury capture is for the current week. Refreshing is suggestion DB-04. | [NFL schedule](https://www.nfl.com/schedules/) |
| Site | Repaired | Navigation grouped by category; stylesheet now defines the classes the pages use. Review findings RV-01 to RV-11 are on `flagged.html`. | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |

## Forward test — first settlement, 2026-11-13 (session `arena/8a322b62-korea1`)

The repository now publishes a **prospective** record, which is the only evidence that cannot be
contaminated by hindsight. `forward.html` prints every ticket frozen before kickoff and settles it only
against an official NFL.com final.

| Item | State | Meaning |
|---|---|---|
| Frozen before kickoff | 65 tickets across 18 strategies and 14 Week 10 games; written `2026-11-12T13:26:48Z`, received by GitHub `13:28:07Z`, 11.78 h before the first kickoff | The picks were public before the games started. The receipt time is GitHub's, not the committer's. [NFL week 10 schedule](https://www.nfl.com/schedules/2026/by-week/reg-10) |
| Settled from an official final | **4 of 65** — WAS 24–21 NYG, read on the [Game Center](https://www.nfl.com/games/commanders-at-giants-2026-reg-10) and the [week 10 scores page](https://www.nfl.com/scores/2026/week-10) | 61 tickets stay `OPEN`; none is defaulted to a push or a void. Net -0.305 units across the settled tickets. |
| Strategies with a counted result | 4 of 18 | One ticket each is not a record. |
| Validated strategies / rewards | **0 / none** | No strategy is past its declared horizon (150 single or 60 parlay tickets over 30 weeks); verdicts are withheld from the agent by ledger amendment A1. |
| Gate F2 (official settlement) | PASS where a ticket has settled | Settlement now rests on an official page; before this pass the same 4 tickets were `PROVISIONAL`. |
| Gate F6 (quote provenance) | FAIL for all strategies | Frozen prices are community-mirror values, not authenticated bookmaker quotes. |

**What this does not mean.** 4 tickets at one game is not a sample, and a 2–2 split is
indistinguishable from chance. `forward.html` prints no p-value, no ROI and no verdict, and awards
nothing. The honest reading is that the forward clock has started and the record can now be audited;
nothing about the strategy library has been demonstrated.

**A defect repaired on the way.** The committed evidence manifest
`data/evidence/nfl_injuries/week10_2026/manifest.json` was rewritten by every build and carried
`"sha256": null` for `news_register.md`, because `pipeline/fetch_injuries.py` hashed only `files[0]`.
`tests/check_rebuild.py` does not cover `data/evidence/`, so the drift survived review and left the tree
dirty after each build. Every declared file is now hashed, a missing file raises, and
`tests/test_evidence_integrity.py` fails on a null or mismatched digest (verified by restoring the old
code: 2 tests fail). Findings F-T41-01 to F-T41-06 are on `flagged.html`.

## Update of 2026-11-13 — one hub, first measured notions, first prospective result

Six sessions each wrote their own suggestion and question register. The site arrived at **8
machine-readable registers plus 2 prose registers covering the same ground**, and a
reviewer could not tell which to read or whether anything had been dropped. This session consolidated them
without deleting any of them:

| Deliverable | What it is | Why it matters |
|---|---|---|
| `decision-hub.html` | **16 canonical decisions** (DH-01–DH-16) replacing six overlapping registers, mapped to all **166 source rows** across 8 registers | One place to choose a path. `build_hub.py` fails the build if any register row is unmapped, mapped twice, or mapped to a row that does not exist |
| `improvements.html` | 15 improvements: 4 built this session, 1 partly built, 10 proposed with the owner question each one needs | The dedicated section for reviewing suggestions before implementing changes |
| `gameday-deficiencies.html` | **171 rows across 26 clubs**: 40 first-string Out, 22 second-to-fourth string Out, 10 doubtful, 86 questionable, 3 compounded | The 1st–4th string deficiency register now covers all 26 reporting clubs, offense and defense, never just four matchups |
| Capture drift | **381 differing cells** between two reads of the same official page 90 minutes apart | Measures how fast the injury input moves; it is why a designation without T-90m inactives is not a confirmation |
| Forward ledger | First prospective result: **2W 2L 0P, net -0.3050 units** on 4 picks; 61 still open | The only mechanism in the repository that removes hindsight. Nothing in it is awarded |
| 2026-11-13 verification pass | **19 claims checked** against official pages: 11 clean, 8 revealing 8 irregularities (IR-01–IR-08) | Recorded in `research/verification-2026-11-13.md` and on `flagged.html`, each with its official link |
| Determinism repair | `fetch_injuries.py` now hashes every committed file and writes the manifest only on change | A clean build is byte-identical again; the manifest no longer carries a null digest |

Three of these came from ideas six separate sessions had already filed and none could build alone: an
all-club deficiency register (S03/SR-04/SUG-06), a single canonical question surface (DB-01/S05/SR-01),
and prospective grading of the forward ledger (DB-03/S07/SR-03).

**What to decide first:** DH-02 (price provenance) and DH-04 (data freshness). Both are cheap to answer
and both block the money question. Do not relax a validation gate to produce a winner — that produces a
winner, not evidence (DH-15).

## What was delivered

| Requirement | Delivery | Evidence status | Official / primary reference |
|---|---|---|---|
| Requirements register | `research/requirements.md` and `requirements.html` | Implemented | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |
| Own NFL lines | Walk-forward Elo, rolling matchup and ridge models; margin, total and moneyline estimates | Implemented; benchmark inputs unverified | [NFL official scores](https://www.nfl.com/scores/) |
| Signal strategies | 18 canonical candidates plus preserved historical annex | No validated edge | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Parlays | Simultaneous-slate selection, push-aware research settlement and adverse-price stress | Executable ticket quotes unavailable | [FanDuel push rules](https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push) |
| Player-prop combos | Input inventory, joint-distribution protocol and combo hypotheses | Blocked by missing verified prices and joint quotes | [NFL injury report](https://www.nfl.com/injuries/) |
| Correlations | Reproducible research estimates; strict public values blank where inputs unverified | Partial evidence | [NFL official scores](https://www.nfl.com/scores/) |
| Luck mitigation | Weekly-block bootstrap, Holm FWER, power, provisional DSR, stability and redundancy | Implemented with assumptions | [Bailey & López de Prado (2014)](https://www.pm-research.com/content/iijpormgmt/40/5/94) |
| Competition rewards | Fail-closed recognition tiers; all rewards unawarded | No funded prize pool | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Official score audit | 31 matching games in a 39-game NFL.com sample | Sample, not a census | [NFL official scores](https://www.nfl.com/scores/) |
| Dashboard | Static categorized pages, searchable tables, source links and flagged-review register | Deployment recorded separately after merge |
| Suggestions before changes (R19) | 22 proposals with cost, risk, dependencies, four paths and change control | Implemented; nothing approved |
| Questions and answers (R20) | 40 open questions plus 12 readiness questions, each with a closure test | Implemented; blocked rows blank |
| Injury / lineup deficiency (R21) | Official report captures plus 2 of 32 club depth charts | PARTIAL — order only, no confirmed roles | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |

## Material audit corrections

1. **Pinned reproduction:** normal builds now read the committed SHA. Refreshing upstream requires an explicit flag.
2. **No future weather fill:** missing observations stay blank. Weather and roof fields are excluded from the default model until pre-kickoff availability is verified.
3. **Fair benchmark comparison:** each model and market metric uses identical available games for that market.
4. **No whole-week parlay hindsight:** tickets use an earliest eligible simultaneous kickoff slate. They remain research simulations, not confirmed ticket offers.
5. **Discrete predictive probabilities:** prior out-of-fold empirical errors replace the claim that a normal continuity correction correctly prices key numbers.
6. **Dependence-aware inference:** weekly returns, shared stationary-bootstrap resampling and Holm correction replace bet-level independence and an unsupported FDR claim.
7. **Fail-closed verdicts:** all eight gates, including redundancy and official quote provenance, are required. A profitable backtest is not labelled skill.
8. **Trial-count uncertainty:** the complete exploratory search history is unknown. Deflated Sharpe is provisional and cannot certify a strategy.
9. **Source policy:** community hashes are not official NFL verification. Strict public tables blank unverified observations; historical calculations remain in labelled data downloads.
10. **Settlement conflicts:** three 2015 closing-file outcome flags conflict with NFL.com Game Center scores. The score file agrees with NFL.com; the conflicting price-file flags remain flagged.

## What remains blocked

| Missing evidence | Consequence | Official context |
|---|---|---|
| Authenticated historical entry/closing quotes with timestamps and limits | No executable ROI or CLV validation | [NFL official scores](https://www.nfl.com/scores/) |
| Verified player-prop prices and joint SGP quotes | No prop-combo ROI or validated correlation | [NFL injury report](https://www.nfl.com/injuries/) |
| League-wide dated depth charts or official inactives (2 of 32 charts, neither dated) | No confirmed starter/replacement role and no availability term in any model | [NFL injury report](https://www.nfl.com/injuries/) |
| Complete trial registry and untouched prospective replication | No reward eligibility | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Full official census of historical scores and pregame fields | Research inputs remain only partially officially verified | [NFL official scores](https://www.nfl.com/scores/) |

## Reproduce and inspect

Run `make build` and `make test`. The canonical pipeline writes `data/processed/`; the independent
replication annex is preserved under `scripts/`, `data/lab/` and `lab/`. Public annex tables use the same
strict-source policy. Historical JSON/CSV calculations are explicitly unverified research data.

See `audit/REPORT.md`, `data/audit/`, `flagged.html` and `COORDINATION.md` for the audit scope,
conflicts, verification commands and final PR/deployment record. A code/data audit is not a claim that
every third-party historical observation has been individually authenticated.

**Research and education only. No guaranteed returns.**
