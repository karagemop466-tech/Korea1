# Executive summary — NFL Line Lab

Final integration: 2026-11-02. Research snapshot: `a270278f3ac4e937295fe6a27814b3c4a2b62645`.

## Decision

**Keep the research engine; do not fund or reward a betting strategy yet.** The repository originates
NFL lines and evaluates single-bet, situational and parlay candidates. It does not contain authenticated,
timestamped executable bookmaker quotes or verified player-prop ticket prices. **0 of 18 canonical
strategies pass all eight final gates.** No prize, capital allocation or profitable recommendation is authorized.

“Unverified” is not a finding of zero edge. It means the evidence cannot support the stronger claim.
Statistical corrections reduce false discoveries; they cannot eliminate luck or guarantee future returns.

## Decision readiness & lineup follow-up — 2026-11-12

The review surface stages all proposed improvements, pre-decision questions, missing-information discovery
protocols, and Week 10 offensive/defensive starter-vs-backup tracking **before** any model or gate rule is changed:
- **Suggestions for review (`suggestions-review.html` & `suggestions.html`):** compares Path A (Conservative),
  Path B (Balanced) and Path C (Full) options with an interactive browser-only path selector alongside the 22-proposal
  register (`suggestions.html`) and 8-proposal parallel register (`decisions.html`); zero model changes are auto-applied.
- **Pre-decision Q&A & missing-info discovery (`decision-readiness.html`, `decisions.html`, `questions.html`):**
  separates verified knowns from missing evidence across 14 core pre-decision questions and 8 discovery protocols,
  and reconciles all **28 post-pin Week 8 & Week 9 2026 games** verified Final on NFL.com on 2026-11-12 without
  mutating the historical backtest pin.
- **Offensive & defensive 1st–4th string lineup tracker (`lineup-deficiencies.html`, `lineups.html`, `injuries.html`):**
  verifies **39 Week 10 offensive and defensive entries across 8 NFL clubs / 4 complete matchups** (`WAS @ NYG`,
  `NE vs DET`, `KC @ ATL`, `MIN @ GB`) against `nfl.com/injuries/`, 8 official NFL club depth charts (1st through
  4th string), and the live NFL Football Operations T-90m/T-60m Game Day Administration inactive & roof rule
  (`operations.nfl.com`). Club "Unofficial" disclaimers, blank source cells and roster/trade lag (e.g. Kirk Cousins
  on MIN, Micah Parsons on GB, Lucas Patrick on WAS) remain blank/flagged rather than inferred, and walk-forward
  community-PBP backup estimates stay blank in strict public HTML tables.

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
| Dashboard | Static categorized pages, searchable tables, source links and flagged-review register | Deployment recorded separately after merge | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |

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
