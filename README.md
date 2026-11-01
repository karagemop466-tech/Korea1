# NFL Line Lab

A source-linked research blueprint for originating NFL probabilities and evaluating candidate strategies for straight bets, game/player props, parlays and prop combos. The landing page and category subpages form a small, static, mobile-friendly dashboard.

## Executive summary

- **Current status: research blueprint only.** The starting checkout contained only this README. No odds/price feed, historical prop lines, joined play-level dataset, bet ledger, model forecasts or competition entries were supplied. As a result, no probability edge, fair line, ROI, CLV, top-performing strategy or numerical NFL bet correlation can be truthfully reported.
- **No strategy has passed validation.** Candidates are explicitly hypotheses, not picks or claims of profitability. Probability and correlation fields that cannot be confirmed remain blank and are flagged.
- **Recommended signal development:** opponent-adjusted, shrinkage-regularized team scoring/margin distributions; total distributions that model pace and scoring; player-prop models that forecast opportunity before per-opportunity efficiency; and joint same-game simulations for combo pricing. NFL official stats and Next Gen Stats are cited only as candidate inputs, not proof that these signals beat prices.
- **Separating signal from luck:** require timestamped pregame forecasts; chronological, leakage-safe and untouched holdouts; baseline comparisons; probability calibration (reliability diagrams, Brier score and log loss); multiplicity safeguards; exact price/settlement accounting; uncertainty; and prospective shadow tracking. These tests reduce false confidence; they do not remove randomness or guarantee profit.
- **Parlays:** never treat independence as established by default. Estimate exact joint events out of sample, display coefficient definitions, sample size and uncertainty, and abstain where joint evidence is sparse. All correlation values are blank because there are no paired observations in the repository.
- **Leaderboard proposal:** rank first by held-out probability scoring; present closing-line value and net yield only as secondary diagnostics with uncertainty. Gate-qualified top strategies may receive proposed non-cash category badges and featured placement; no entrants currently qualify, and no cash reward, prize pool or funding is established.
- **Publication:** a GitHub Pages workflow and dashboard are included. The pages contain strategy, validation, correlation, sources and “Flagged for Review” registers. A static dashboard does not ingest live odds or generate operational picks.

## Site map

- [Overview / executive summary](index.html)
- [Straight-bet candidates](singles.html)
- [Player props and prop combos](props.html)
- [Parlay methods](parlays.html)
- [Correlation register](correlations.html)
- [Validation gates and leaderboard proposal](validation.html)
- [Flagged for Review](flagged.html)
- [Source register](sources.html)
- [Detailed research brief](docs/executive-summary.md)
- [Shared coordination board](COORDINATION.md)

## Verification and limitations

The cited pages are recorded with publisher, scope and review date in [the source register](sources.html). NFL stat examples link to the official 2025 NFL views reviewed on 2026-11-01; they establish those public statistical categories, not a 2026 observation, a complete model dataset, or a betting edge. The official rule PDF is the 2025 edition and must not be silently carried forward to another season. The NFL tracking overview does not grant access rights to all raw fields. Methodology pages explain statistical concepts but contain no NFL betting-performance results.

“Official-source verification” here means the linked source itself was opened and its relevant content reviewed. It does **not** imply every listed candidate hypothesis was validated against outcome data. The flagged page records each material gap and its source.

## Build and local verification

```sh
python3 scripts/verify_site.py
python3 -m http.server 8000 --bind 0.0.0.0
```

The workflow deploys the static site when changes reach `main`, provided GitHub Pages is enabled for the repository and the GitHub Actions Pages permissions are available. No betting transactions, operator integrations, odds scraping, or automatic selection of bets are implemented.
