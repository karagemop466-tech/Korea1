# Strategy leaderboard — competition rules and rewards

**Status:** implemented as software; all rewards unawarded. This is a research competition, not a tipping service and not a funded promotion. No prize pool exists.

## Design

Every candidate is declared **before** it is run, with its rule, rationale and data requirement (`pipeline/strategies.py::build_library`). The library is executed in full and every result is published — including the failures. Nothing is dropped after the fact and no threshold is tuned on the backtest.

Bets are one unit each at the **recorded closing price**; `-110` is never substituted for a missing price — bets without a recorded price are dropped and counted. Settlement is cross-checked against the dataset's own per-side outcome column (`pipeline/backtest.py::validate_settlement`): 98.605% exact overall, 99.931% where the two files carry the same line.

## The eight fail-closed gates (G1–G8)

G1 provenance & executability — official timestamped quote, line, price, limits and settlement terms; no missing required field.
G2 no lookahead — prefix-stable features, season-level walk-forward fits, simultaneous parlay legs, no future weather fill.
G3 power — ≥ 100 bets, ≥ 3 seasons, ≥ 100 active weeks, planned detection of a 2% ROI at 80% power from weekly variance.
G4 significance — centered weekly-block bootstrap p-value, Holm family-wise correction across the library.
G5 selection bias — positive bootstrap lower bound and provisional deflated Sharpe > 0.95 (provisional: complete trial count unknown).
G6 economic value — ≥ 2% bet-weighted ROI and positive adverse-price stress (−5 cents per leg).
G7 stability — positive in ≥ 60% of eligible seasons and positive recent-three-season aggregate.
G8 redundancy — < 90% selection-identity overlap with every other entrant.

**No strategy may be labelled validated without all eight gates.** Source: `pipeline/validation.py`, `data/processed/strategy_gates.csv`.

## Current standing

18 canonical candidates: single bets (spread, total, moneyline model edges and situational angles), 2- and 3-leg parlays.

| Result | Count |
|---|---|
| Strategies tested | 18 |
| Passing all eight gates | 0 |
| Validated | 0 |
| Rewards awarded | 0 (unawarded) |
| Best raw ROI (research only, not validated) | +21.64% — PARLAY3_EDGE, 377 tickets, fails G5/G6 |

Full per-strategy diagnostics: `data/processed/strategy_summary.csv`, `strategy_stats.csv`, `strategy_gates.csv`, `strategy_weekly_matrix.csv`.

## Reward tiers (recognition framework — not an existing financial promotion)

| Tier | Requirement | Payout status |
|---|---|---|
| Research | Rule and complete trial history registered; no performance award | None |
| Candidate | Data, leakage and power gates pass; still paper-only | None |
| Replicated | All eight gates pass on untouched prospective observations | None |
| Disqualified | Leakage, selective reporting, fabricated quotes or undisclosed rule changes | None |
| Unawarded | No verified prize pool, sponsor, custody or payout obligation exists | None |

**Decision:** do not fund or reward any strategy until all eight gates pass on authenticated executable quotes and an untouched prospective replication. See `EXECUTIVE_SUMMARY.md` and `decisions.html` for the open questions that block this.

## Sources

- `pipeline/validation.py` — gate definitions; `pipeline/backtest.py` — settlement engine.
- White (2000), Bailey & López de Prado (2014), Politis & Romano (1994) — linked on `sources.html`.
- FanDuel push settlement rules (operator example, not universal house rules): https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push