# Signal research — originating NFL lines without market inputs

**Status:** research only. No signal here is validated, no edge is claimed, and no calculation is a betting recommendation. All estimates are produced by `pipeline/models.py` from the pinned community archive (`data/sources.json`, upstream `nflverse/nfldata@a270278f3ac4...`); none is an official NFL observation.

## Principle

Every originated line is **market-free**: the models never see a closing line, price or moneyline as an input. Market prices are carried alongside purely as the benchmark to beat (see `data/processed/model_metrics.csv`, calculated research only — community source, not officially verified).

Three deliberately different families are fitted **walk-forward**: for test season S only seasons < S are used, so every published prediction is genuinely out-of-sample.

| Family | Basis | Fitted structure |
|---|---|---|
| M1 ridge | Elo, rolling matchup points, rest, weather, venue | Weighted ridge; alpha chosen by inner time-series CV inside each training window |
| M2 matchup | Matchup expected-points identity `off(team) + def(opponent) − league_avg` | Single scale + intercept pair per training window |
| M3 elo | Elo difference only | Linear calibration on training window |
| Ensemble | Equal fixed average of M1/M2/M3 | **Never fitted** — cannot be tuned to the backtest |

Probability mapping uses prior-season out-of-fold empirical residuals (discrete NFL scoring mass; ties and pushes retained). This is a modelling choice, not a claim that key numbers are priced correctly.

## Features used (pre-game only)

Source: `data/processed/feature_dict.csv`. No outcome or market field ever enters a feature list (asserted by `assert_no_leakage()` and `tests/test_no_lookahead.py`). Team state is updated **after** each game row is emitted, in strict chronological order.

Used in the default margin model: `elo_diff`, `exp_margin`, `rest_diff`, `div_game`, `neutral`, `is_playoff`, `week`.
Used in the default total model: `exp_total`, `season_idx`, `week`, `is_playoff`, `div_game`.

Excluded from the default model until pre-kickoff availability is verified: `temp`, `wind` (missing stays blank — never imputed from history), `roof_dome`, `roof_open` (availability timestamp not verified), `adj_exp_margin`, `adj_exp_total` (opponent-adjusted ratings; cold-start coverage incomplete — retained as research fields).

Missing weather/roof is an open evidence gap, not a missing value to be filled: see `data/processed/leakage_checks.csv` and `flagged.html`.

## Researched signal families

### 1. Model-edge signals (single bets)
`SP_EDGE_1_0 / 2_0 / 3_0` — bet the side where `|originated spread − closing spread| ≥ threshold` points.
`TOT_EDGE_2_0 / 3_5` — same for the game total.
`ML_EDGE_5 / ML_EDGE_10` — moneyline side where model win probability exceeds the de-vigged closing probability by ≥ 5 / 10 percentage points.

Hypothesis: discrepancies between a market-free line and the close are positive expected value **only if** the model is better calibrated than the available price. Being different from the market is not, by itself, an edge.

### 2. Situational angles (single bets)
`HOME_DOG_ATS` — every home underdog takes the points. `ROAD_FAV_ATS` — its mirror (same games, opposite side; the two ROIs must sum to approximately minus the vig — an internal arithmetic check on settlement).
`WIND_UNDER` — recorded kickoff wind ≥ 15 mph → under. `COLD_UNDER` — recorded kickoff temperature ≤ 32°F → under. Both require the observation to be present (missing = no bet).
`DIV_UNDER` — divisional matchups → under. `REST_ADV_ATS` — back the team with ≥ 7 more days of rest. `FADE_BLOWOUT_ATS` — bet against any team that won its previous game by ≥ 21 points. `BUY_LOW_ATS` — back any team that lost its previous game by ≥ 17 points.

All are classic, publicly known, deliberately naive hypotheses; none is validated.

### 3. Parlays
`PARLAY2_EDGE / PARLAY3_EDGE / PARLAY2_ML` — one ticket per week from the **earliest eligible simultaneous kickoff slate**: the two (or three) largest absolute edges, distinct games. Whole-week selection with later-game information is prohibited (repaired lookahead defect — see `flagged.html`). Pricing is the product of the legs' real closing decimal prices, push = "ties reduce". This is a research simulation, not an executable ticket quote; actual SGP prices and timestamps are unavailable.

### 4. Player-prop combinations (research module)
Built from hash-pinned community play-by-play (2019–2022, `data/sources_pbp.json`) — QB/WR/RB/TE passing/rushing/receiving/receptions lines, dependence at the 50/50 split (e.g. QB↔own WR1 φ = 0.152, receptions↔receiving yards φ = 0.580), calibration slope 0.14–0.23. **No prop prices exist in any reachable source**, so no prop ROI is calculated or claimed. See `props.html` and `research/04-competition.md`.

## Measured correlation values (settlement data, not imported)

Source: `data/processed/corr_*.csv` (7,384 played games; priced subset from 2006). Measured from our own settlement data; blank in the strict public view because the underlying market lines are community observations, not officially verified.

| Relationship | Estimate | 95% interval | Sample | Strict-public status |
|---|---|---|---|---|
| Home cover ↔ home moneyline win (same game) | φ 0.676 | [0.657, 0.694] | 5,900 | UNVERIFIED — near-duplicate legs |
| Home cover ↔ game over (same game) | φ 0.024 | [−0.001, 0.050] | 5,830 | UNVERIFIED |
| Game over ↔ home moneyline win | φ 0.008 | [−0.019, 0.034] | 5,971 | UNVERIFIED |
| Margin vs total (continuous) | r 0.023 | [−0.004, 0.045] | 6,073 | UNVERIFIED |
| Home points vs away points | r −0.039 | [−0.062, −0.014] | 6,073 | UNVERIFIED |
| Margin vs closing spread | r 0.433 | [0.413, 0.450] | 6,073 | UNVERIFIED (market-efficiency diagnostic) |
| Total vs closing total | r 0.314 | [0.294, 0.337] | 6,073 | UNVERIFIED (market-efficiency diagnostic) |
| Cross-game margins (within-slate pairs) | r 0.0006 | [−0.008, 0.011] | 41,502 pairs / 452 slates | Interval spans zero — no claim of dependence |
| Cross-game totals (within-slate pairs) | r 0.0044 | [−0.005, 0.014] | 41,502 pairs / 452 slates | Interval spans zero — no claim of dependence |

## Luck removal — what the gates do and do not do

Statistical gates reduce false discoveries; they **cannot remove luck**. The competition uses weekly-block returns, Holm family-wise correction, provisional deflated Sharpe, power analysis, adverse-price stress, season-stability and redundancy checks (G1–G8, `pipeline/validation.py`). A strategy must pass **all eight** before any recognition; 0 of 18 canonical strategies currently pass (`data/processed/strategy_gates.csv`). Rewards remain unawarded.

**How to discover missing signal information:** walk-forward refits on every held-out season, out-of-sample calibration slope, prospective paper-trading on untouched weeks, and a frozen trial registry so the multiple-testing denominator is known. None of these exists for the current library; each is listed on `decisions.html`.

## Sources

- Pipeline and calculated tables: `pipeline/models.py`, `pipeline/strategies.py`, `pipeline/validation.py`, `data/processed/*.csv` (community archive; calculated research estimates).
- Method references: White (2000) reality check; Bailey & López de Prado (2014) deflated Sharpe; Politis & Romano (1994) bootstrap. Linked on `sources.html`.
- Official NFL context: https://www.nfl.com/scores/ — official results used only for the sampled score audit (`data/audit/nfl_com_score_audit.csv`), not as a source of the modelled lines.