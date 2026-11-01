# Executive summary: NFL line research and selective-skill framework

**Audit date:** 2026-11-01  
**Project state:** evidence-backed design and dashboard; empirical modeling is blocked.

## Decision summary

The repository began with a one-line README and no NFL data, market prices, prediction records or previous work. We can design testable hypotheses and a serious validation protocol, but cannot honestly report a generated NFL line, a positive edge, a skill-based winner or a measured correlation. Accordingly, this project does not publish picks or invent numeric findings. Candidate numerical outputs remain blank, and all strategies are explicitly untested.

## Proposed signal families

1. **Straight bets — spread/moneyline:** predict a distribution of team scoring margin from opponent-adjusted and shrunk team offense/defense inputs; compare forecast probabilities with an exact, time-stamped price. Candidate official data categories are linked from the [NFL team scoring](https://www.nfl.com/stats/team-stats/offense/scoring/2025/reg/all), [passing](https://www.nfl.com/stats/player-stats/category/passing/2025/reg/all/passingyards/desc), and [rushing](https://www.nfl.com/stats/player-stats/category/rushing/2025/reg/all/rushingyards/desc) views.
2. **Game and team totals:** model a conditional scoring distribution, including pace/opportunities and current-season rules, rather than relying on a single-point projection. Verify the [NFL rules for the applicable season](https://media.nfl.com/content/dam/communications/Official%20Playing%20Rules/2025%20Official%20Playing%20Rules.pdf); the source currently reviewed is specifically the 2025 rulebook.
3. **Player props:** forecast opportunity/volume before conditional yards or scoring efficiency. Official [NFL passing](https://www.nfl.com/stats/player-stats/category/passing/2025/reg/all/passingyards/desc), [rushing](https://www.nfl.com/stats/player-stats/category/rushing/2025/reg/all/rushingyards/desc), [receiving](https://www.nfl.com/stats/player-stats/category/receiving/2025/reg/all/receivingreceptions/desc) and [Next Gen Stats passing](https://nextgenstats.nfl.com/stats/passing/2025/REG/3) pages establish that these measures are published; they do not prove a prop signal or settle its market definition.
4. **Parlays and player-prop combos:** use a joint outcome model conditioned on shared game state. Estimate marginal and joint results on held-out games; do not multiply probabilities by default. Report a coefficient and uncertainty only when derived from aligned, exact-leg outcome data. [NIST's correlation glossary](https://www.itl.nist.gov/div898/handbook/glossary.htm) defines Pearson correlation; no NFL-specific correlation value is available here.

These are hypotheses for testing, not endorsed bets. Tracking-derived features are candidates only: the [NFL Next Gen Stats overview](https://operations.nfl.com/game-operations-logistics/technology/performance-tracking-data-next-gen-stats) does not itself establish a public raw-data endpoint, license or commercial reuse permission.

## Validation gates: luck cannot be removed, but false confidence can be reduced

A strategy should remain ineligible until it has passed all applicable gates:

- document sources, timestamps, field definitions and data rights; retain missing values instead of silently filling them;
- generate genuinely pregame forecasts and use date-ordered, game-aware splits, with all preprocessing learned inside training data and a never-tuned final holdout;
- assess reliability and probability quality on held-out data (reliability diagrams, Brier score and log loss), with a baseline, sample count and uncertainty; see the [scikit-learn calibration reference](https://scikit-learn.org/stable/auto_examples/calibration/plot_calibration_curve.html);
- register experiments and account for multiple candidate strategies to limit winner's-curse/false-discovery risk ([Benjamini & Hochberg, 1995](https://academic.oup.com/jrsssb/article/57/1/289/7035855));
- audit exact offered prices, both sides where applicable, line movement, settlement rules, pushes/voids, stakes, limits and costs before computing any yield or line value;
- validate combo joint probability and dependence out of sample; publish coefficient, exact event definitions, sample and interval; and
- preserve forecasts in prospective shadow mode before leaderboard qualification.

The [NFL Big Data Bowl](https://operations.nfl.com/programs-initiatives/innovation/big-data-bowl) is a real NFL analytics competition and describes evaluation of prediction submissions. It is useful context for leaderboard design, but its contest results are not NFL betting edge evidence. Numeric sample-size or significance thresholds have not been fabricated; they require a pre-registered power and risk policy.

## Leaderboard and rewards

Proposed primary rank: proper probability score on pre-registered, eligible out-of-sample predictions (Brier score first; log loss alongside it). Show sample size, uncertainty and version history. Closing-line value and net yield are secondary descriptive metrics, never substitutes for calibrated forecasts and locked validation. No entrants, complete closing prices, bet outcomes or reward funding are in the repository; there is no verified winner or existing prize pool. The dashboard proposes non-cash category badges and featured placement for only gate-qualified top strategies. It makes no cash-award commitment; a simulated/non-cash phase is safer than paying unvalidated strategies.

## Explicitly blank / flagged

- **Fair lines, odds, edge, ROI and CLV:** no executable or historical sportsbook prices.
- **Model accuracy, calibration and leaderboard ranking:** no forecasts or settled competition records.
- **Correlation values:** no paired leg outcomes or aligned forecast errors. A blank is not zero and does not indicate independence.
- **NGS raw-data accessibility/commercial rights:** not established by the overview page.
- **Current 2026 NFL rule details:** only the official 2025 rulebook was checked for this brief.

The dashboard's [Flagged for Review](../flagged.html) page publishes each irregularity with a source link and remediation action. The [source register](../sources.html) records source scope and what it does—and does not—support.
