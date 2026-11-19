# Pre-registration — second game-total estimator and its walk-forward comparison

Registration rule (brief: "Freeze a rule before it sees data"): this file is committed to git
**before** `pipeline/dual_totals.py` exists or is run. The commit hash of this file is the
registration. Any later edit to the rule creates a new registration; the original stays in history
and the page must print the registration commit it honoured.

**Revision history.** v1 (`3e14638`, 2026-11-19) defined B as previous-season form only. v2 (this
text) widens the prior to the team's most recent regular-season games up to the game itself,
because a pure previous-season model would ignore everything the team has already shown in the
current season and make the comparison uninformative. v2 was amended **before any evaluation code
existed and before any error number was computed** — no result was seen between v1 and v2. v1 stays
in git history at `3e14638`; the page prints the commit of the text it honoured.

- Registered by: session `arena/a0e376ae-korea1`
- Registered on: 2026-11-19 (UTC)
- Brief items served: REQ-62 / RR-62 — "Publish every model total twice until one wins. Keep both
  estimators visible with the gap column, and only collapse to one after a walk-forward
  comparison."
- What this is not: not a strategy, not a leaderboard entry, not a validation-gate change, not a
  reward-relevant claim. It is a model-publication rule.

## 1. The two estimators

**Estimator A (published, unchanged).** `pred_total_ensemble` from `data/processed/originated_lines.csv`
— the equal-weight ensemble of the ridge, matchup and Elo total estimators already published as
`fair_total` on `lines.html`. Nothing about A is retrained, reweighted or reselected by this
registration.

**Estimator B (new, independent of A).** A parameter-free form model — the mean combined score of
the team's most recent games:

```
prior_games(T, game g in season S week w) =
    team T's regular-season games in the corpus with (season < S), or
    (season == S and week < w), most recent season/week first

prior_total(T, g) =
    mean of T's combined scores in the up-to-5 most recent games of prior_games(T, g)
    if prior_games(T, g) is empty: the league-wide regular-season mean combined score
        of the most recent season in the corpus before S

B(g) = (prior_total(home, g) + prior_total(away, g)) / 2
```

Rules that are part of the registration:

- Only regular-season games (`game_type == "REG"`) feed the priors; playoff games are excluded from
  both fitting and evaluation.
- Chronology: the window is 5 games, taken from seasons strictly before S or from weeks strictly
  before w inside S — a game never reads itself, its own week or any later game.
- The window size (5), the averaging (equal weight, home and away priors averaged) and the fallback
  are fixed constants. B has no fitted parameters and cannot be re-fit after seeing results without
  breaking this registration.
- If B cannot be computed for a game (no prior game anywhere in the corpus and no prior season
  mean), the cell is left blank and the row is reported as `B_unavailable`; blank is never filled
  with an estimate.

## 2. Sample window

- Seasons **2004–2026** (the seasons for which estimator A is published), regular season only.
- A row is evaluated only when it has: an A estimate, a B estimate, and a final combined score
  (`total` non-blank) in `data/processed/games_model.csv` joined on `game_id`.
- The 2026 season is partial (games played through the capture date); its rows are evaluated on the
  games that have finals and the row prints the partial `n`.

## 3. Metrics and gates (verdict rule)

Per season *s* and pooled overall:

- `n`, `MAE_A`, `MAE_B`, `RMSE_A`, `RMSE_B`, `bias_A`, `bias_B` in points.
- `d_i = |outcome_i − B_i| − |outcome_i − A_i|` per game; `ΔMAE = mean(d_i)`; a **paired 95%
  confidence interval** for `mean(d_i)` from the t distribution (two-sided, n−1 degrees of freedom).
- Season verdict:
  - `B wins season s` iff the CI upper bound < 0;
  - `A wins season s` iff the CI lower bound > 0;
  - otherwise `no separation`.
- **Primary gate = the pooled overall CI.** Per-season verdicts are descriptive: with ~23 seasons
  the multiplicity of per-season tests is not used to declare an overall winner.
- Overall verdict:
  - `A wins` iff pooled CI lower bound > 0;
  - `B wins` iff pooled CI upper bound < 0;
  - otherwise `inconclusive — both estimators remain published`.
- **Collapse rule** (the brief's "only collapse to one after a walk-forward comparison"): collapsing
  to a single published total requires the overall verdict above to name a winner **and** that
  winner to also win at least two-thirds of the evaluated seasons. If either condition fails, both
  estimators and the gap column stay published. This session does not collapse anything regardless;
  the comparison is published and the collapse stays an owner decision recorded in `DECISIONS.md`.

## 4. Evidence tiers (what the numbers are made of)

- Outcomes come from the pinned community archive (`data/raw/games.csv`, nflverse pin recorded in
  `data/sources.json`). Every published row prints the tier mix:
  - `OFFICIAL_READ` — the game's final also appears in the officially read set
    (`data/results/verified_results.csv` official tier or `data/audit/nfl_com_score_audit.csv`);
  - `PINNED_COMMUNITY` — community final only, settlement unverified.
- Every row prints the official season standings link (`https://www.nfl.com/standings/league/<season>/REG`,
  verified live 2026-11-19) for manual review.
- The overall verdict prints as **PROVISIONAL** while any evaluated row is `PINNED_COMMUNITY` and
  the officially read subset does not cover the evaluated rows. Official reads can only move the
  tier counts; they cannot change estimator definitions in this registration.

## 5. What would change our mind (two-sided)

- **Against keeping both:** B wins the pooled gate with the two-thirds season supermajority — then
  an owner decision may collapse the published total to the winner (still recorded in
  `DECISIONS.md`, still not a leaderboard action).
- **Against B entirely:** if any chronology violation is found in test (a B value that reads a game
  dated on or after its own), B's rows are withdrawn, the failure is published on the Flagged for
  Review page, and this registration is marked broken rather than silently re-fit.
