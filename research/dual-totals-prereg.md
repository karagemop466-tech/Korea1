# Pre-registration — second game-total estimator and its walk-forward comparison

Registration rule (brief: "Freeze a rule before it sees data"): this file is committed to git
**before** `pipeline/dual_totals.py` exists or is run. The commit hash of this file is the
registration. Any later edit to the rule creates a new registration; the original stays in history
and the page must print the registration commit it honoured.

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

**Estimator B (new, independent of A).** A parameter-free form model:

```
prior_total(T, game g in season S) =
    mean of team T's combined scores in its own regular-season games of season S−1
    if T played no regular-season game in S−1:
        mean of T's combined scores in its most recent earlier season in the corpus (S−2, S−3, …)
        if T appears in no earlier season (expansion / missing): the league-wide
        regular-season mean combined score of season S−1
    if S−1 is absent from the corpus: the league-wide mean of the most recent earlier season

B(g) = (prior_total(home, g) + prior_total(away, g)) / 2
```

Rules that are part of the registration:

- Only regular-season games (`game_type == "REG"`) feed the priors; playoff games are excluded from
  both fitting and evaluation.
- Chronology: for a game in week *w* > 1, season-to-date values are **not** used; the prior is always
  the previous season (or earlier), so no game ever reads a game dated on or after itself.
- B has no fitted parameters, no tuning window, no shrinkage constant. It cannot be re-fit after
  seeing results without breaking this registration.
- If B cannot be computed for a game (no prior season anywhere in the corpus), the cell is left
  blank and the row is reported as `B_unavailable`; blank is never filled with an estimate.

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
