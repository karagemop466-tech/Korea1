# 04 — Leaderboard competition design

Goal: reward strategies that are **selectively skill based**, and make it structurally impossible
for a lucky season to win. The rules below are derived from the measurements in
`03-validation-gates.md`, not from convention.

## 1. The problem being solved

| Fact (measured) | Design consequence |
|---|---|
| A zero-skill 1,000-bettor field produces a **+18.7% median winner** over one 267-bet season | Never rank or pay on raw seasonal P&L |
| A bettor with a genuine 2% edge finishes **1st only 0.32%** of the time on a season-ROI board, but **1st 78.9%** of the time on a CLV board (20,000 trials) | CLV must dominate the score, and it does (`w_C = 0.5`) |
| A 2% edge needs ~**17,800 bets** to prove by win/loss alone | Score CLV and require large bet counts; use multi-season windows |
| 18 rules produced 5 "significant" results at p < 0.05 before correction | Every submitted strategy counts as a trial; apply BH-FDR and DSR to the whole field |
| Parlay cards hold **19.94%** vs straight sports pool **6.74%** (official, NV 12-month) | Parlay entries must post correlation-adjusted, not price-multiplied, returns |
| The QB/WR1 stack is genuinely correlated at ρ = 0.44 | Correlation-aware props are the one place a real edge can exist; reward measured correlation, punish "independent-leg" fantasy |

## 2. Scoring: luck-adjusted skill score (LASS)

Each strategy is scored per bet, then aggregated with shrinkage:

```
per bet i:  r_i = profit_i / stake_i                       (-1, +0.9091, or 0 for a push)
            c_i = CLV_i in points                           (0 if not measurable)

CLV component  C = mean(c_i) / sd(c_i) * sqrt(n_c)          (t-stat of closing-line value)
Return comp.   R = mean(r_i) / sd(r_i) * sqrt(n)            (per-bet Sharpe, annualised separately)
Shrinkage      λ = n / (n + n0),  n0 = 400 bets             (empirical-Bayes shrink to zero)

LASS = λ * ( 0.5*tanh(C/2) + 0.3*tanh(R/2) + 0.2*(2*DSR - 1) )
```

* `w_C = 0.5`, `w_R = 0.3`, `w_D = 0.2`. CLV dominates because it is the lowest-variance skill signal
  (§ 3 of `02-methodology.md`), and because the simulation in `03-validation-gates.md` §3.1 shows
  that a CLV-ranked board finds a real 2% edge **about 250 times more often** than an ROI-ranked one.
* `n0 = 400` is not arbitrary: it is roughly the number of bets at which the standard error of a
  per-bet Sharpe of 0.05 falls below 0.05. A strategy with fewer than ~400 bets is shrunk toward
  zero by design, so an early-season fluke cannot lead the table.
* Any strategy with **G8 failed** (DSR < 0.95) is capped at a "provisional" tier and cannot win a
  cash prize, however high its LASS.

## 3. Tiers (promotion / relegation)

| Tier | Entry requirement | Reward band |
|---|---|---|
| **Paper** | any submission; ≥ 100 bets tracked | Leaderboard only, no prize |
| **Bronze** | ≥ 300 bets, G1+G2 passed | small fixed reward |
| **Silver** | ≥ 600 bets, G1–G6 passed, ≥ 1 full season | revenue share |
| **Gold** | G1–G8 passed, ≥ 2 seasons, positive CLV in both | largest revenue share + capital allocation |
| **Watch** | flagged result (see Flagged for Review) | no reward until replicated |

## 4. Anti-gaming rules (each closes a measured loophole)

1. **Bet timestamps and line snapshots are mandatory.** Without a timestamp, CLV is unfalsifiable
   and any backtest can be reverse-engineered from the close.
2. **A strategy is its whole history.** Editing a rule after publication resets it to Paper and
   counts as a new trial in the field's multiple-testing budget.
3. **No cherry-picked subsamples.** Reporting a subset of bets requires reporting all of them plus
   the filter, and the filter counts as a trial.
4. **Parlays are scored on correlation-adjusted expected value**, computed from the entrant's own
   stated leg correlations and checked against the measured correlation table in `data/props.json`.
   A parlay that only wins because independent prices were multiplied gets no credit.
5. **Flat staking is the default.** Kelly staking is allowed but the score uses the *shrunken* unit
   series, so leverage cannot manufacture a ranking.
6. **Arbitrage and bonus abuse are excluded**, since they are not signals about the game.
7. **Minimum bet count per tier** is enforced before any prize, which is the direct application of
   the power calculation: a 100-bet sample cannot support a 5% claim at any confidence level.

## 5. Reward model (revenue share, not prizes from a pot)

| Component | Weight | Paid on |
|---|---|---|
| Realised CLV | 45% | mean CLV per bet, in points |
| Risk-adjusted return (per-bet Sharpe, shrunk) | 30% | unit-stake P&L |
| Replication | 15% | out-of-sample seasons surviving the gates |
| Correlation contribution (props/parlays) | 10% | measured joint-probability accuracy vs fair price |

Payouts are conditional on the gates, so a Gold-tier strategy is one that survived **selection-bias
correction**, not one that happened to lead in week 9.

## 6. What the leaderboard will show for this repo's own battery

Applying the rules to the 18 strategies measured here: **0 Gold, 0 Silver, 0 Bronze, 4 Watch (S01,
S11, S12, S17), 14 Paper.** That is the honest outcome, and it is the point of building the
gate set — a competition that would have awarded a prize here would be broken.

The machinery, however, is finished and reusable: point it at a live feed and the same gates,
the same DSR correction and the same correlation table apply without modification. The blocker is
data (I-05), not design.
