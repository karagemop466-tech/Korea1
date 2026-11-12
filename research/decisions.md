# Pre-decision register — questions, information and answers

**Purpose:** the questions, information and answers that must be addressed before any decision (funding, rewarding, publishing a line for use, changing the site) can reasonably be made — based only on information we have and do not have. Blank = information not available; never inferred.

**How missing information is discovered:** each question lists the source to check and the action required. If a source cannot confirm a value, the cell stays blank and flagged UNVERIFIED — this register is a discovery plan, not a substitute for evidence.

## Register

| ID | Question | Information needed | Answer (from evidence we have) | Status | Official source to check | How to discover missing information |
|---|---|---|---|---|---|---|
| Q-01 | Is there any validated betting edge? | A strategy passing all eight gates G1–G8 on authenticated quotes | **No.** 0 of 18 canonical strategies pass all eight gates; rewards unawarded. | Answered (negative) | https://www.nfl.com/scores/ (results only — no quotes) | Re-run `pipeline/validation.py` after every build; no strategy may be promoted without G1–G8 |
| Q-02 | Are authenticated, timestamped executable bookmaker quotes available? | Entry/closing prices, timestamps, limits, settlement terms per bet | **No.** Community closing lines are hash-verified as files, not authenticated as executable offers; `-110` is never substituted for missing prices. | Blocked | https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push (operator example only) | Contact bookmakers; archive quotes with timestamps; no value inferred in the meantime |
| Q-03 | Are verified player-prop prices and joint SGP quotes available? | Prop opening/closing prices, settlement terms, joint ticket quotes | **No.** No retrieved source carries prop prices; no prop ROI is calculated or claimed. | Blocked | https://www.nfl.com/injuries/ (player availability context only) | Prop-price archive required; combinations remain hypotheses only |
| Q-04 | Is the data snapshot current enough for decisions? | Snapshot date vs official schedule and results | **No.** Pinned snapshot `2026-11-01T13:24:09Z` holds 2026 weeks 1–7 complete plus only Thursday's Week-8 game (CAR@GB 27–19). Week 9 is final on NFL.com but absent from the archive; Week 10 games are upcoming. | Blocked (stale) | https://www.nfl.com/scores/2026/week-8 , https://www.nfl.com/scores/2026/week-9 | Refresh the pin explicitly (`NFDATA_SHA=` / `fetch_data.py --refresh-pin`) followed by a new audit; never refresh silently |
| Q-05 | Are injuries and starter/backup deficiencies integrated into line origination? | Weekly injury report with practice/game status and depth position (starter, 2nd, 3rd, 4th string) for offense and defense | **Partially.** Official Week 10 injury report is captured on `injuries.html` (verified vs nfl.com/injuries). Depth-chart order (which backup replaces a starter) is **not** officially integrated — blank, flagged UNVERIFIED. | Partial | https://www.nfl.com/injuries/ | Capture injury report weekly; official depth charts are not published by NFL.com — flag any replacement-level claim as unverified |
| Q-06 | Can correlation values be treated as verified? | Joint outcomes at official lines, row-by-row provenance | **No.** Correlations are measured from community settlement data; strict public values are blank. Intervals span zero for cross-game dependence — no claim of independence or dependence. | Blocked | https://www.nfl.com/scores/ (results only) | Official lines and joint outcome provenance required |
| Q-07 | Can luck be removed from strategy evaluation? | Test proving skill rather than variance | **No.** Gates bound luck; no test eliminates it. Deflated Sharpe is provisional (complete trial count unknown). | Answered (negative) | White (2000), Bailey & López de Prado (2014) — primary papers | Prospective replication on untouched weeks; frozen trial registry |
| Q-08 | Is a reward/prize decision authorized? | Funded prize pool, sponsor, custody, payout obligation | **No.** Reward tiers are defined (research → candidate → replicated → disqualified → unawarded); all unawarded. No prize pool is represented as existing. | Answered (negative) | https://docs.github.com/en/pages (publication only — not a financial promotion) | Separate authorization and funding required before any reward |

## Decision rule

No decision (funding, reward, publication of a line for real-money use, or a site change affecting published numbers) may be made while any Q item above is **Blocked** or **Partial** without a recorded waiver signed by the reviewer, listing the exact item and the rationale. Answered items may still change when the underlying data is refreshed — re-check before every decision.

## Sources

- https://www.nfl.com/scores/ — official NFL scores
- https://www.nfl.com/injuries/ — official NFL injury report
- https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping — White (2000)
- https://www.pm-research.com/content/iijpormgmt/40/5/94 — Bailey & López de Prado (2014)