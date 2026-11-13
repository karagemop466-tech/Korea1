# DECISIONS.md — dated decision log

Owner-facing log introduced by session `arena/25460478-korea1` on 2026-11-12 (suggestion S22).
One row per decision. A decision is reversible and names the condition that would reverse it.
Nothing here overrides the evidence policy on `sources.html`: a decision cannot make an
unverified number verified.

| ID | Date (UTC) | Owner | Decision | Evidence at the time | Reversal condition |
|---|---|---|---|---|---|
| D-01 | 2026-11-12 | Agent session `arena/25460478-korea1`, acting on the brief “work on your own” | Adopt **Path A** from `suggestions.html`: publish the review surface, keep every evidence line, change no published research number. Paths **B**, **C** and **D** remain for the owner to choose. | `questions.html` (40 questions, 24 answered / 8 open / 5 blocked / 2 decisions), `suggestions.html` (22 proposals), build and verifier pass | If the owner selects B, C or D, record it as D-02 and re-run `make build`, `make test` and the verify workflow |
| D-02 | 2026-11-12 | Same | Do **not** join the live week-10 injury report to the pinned week-8/9 board. Label the board as a snapshot and publish the injury capture separately. | Official week-8 finals (NFL.com) vs board rows; `injuries.html` §5 | Reverse only after the pin is refreshed and every row is keyed to its own kickoff |
| D-03 | 2026-11-12 | Same | Do **not** label any player a *confirmed* starter, replacement or 3rd/4th-string option. Quote published chart cells with their club and date; publish the signal register with its blockers instead. | `nfl.com/teams/<club>/depth-chart` → HTTP 404; roster and `?tab=depth` alphabetical. Club charts (WAS, NYG) verified 2026-11-12 do give an order, but carry no publication time and cover 2 of 32 clubs | Reverse per club when a dated chart or official inactives confirm the role pre-kickoff, documented in S17 |
| D-04 | 2026-11-12 | Agent session `arena/d6b3fd34-korea1` | Expand verified official club depth-chart coverage from 2 clubs to **8 clubs across 4 complete Week 10 matchups** (`WAS@NYG`, `NE@DET`, `KC@ATL`, `MIN@GB` — 39 offensive & defensive 1st–4th string entries on `lineup-deficiencies.html`), verify the live `operations.nfl.com` T-90m/T-60m pregame inactive & roof rule, reconcile all **28 post-pin settled Week 8–9 Final scores** (`decision-readiness.html`), and stage Path A/B/C model improvements in `suggestions-review.html` without mutating the frozen canonical backtest pin or promoting unverified signals into the leaderboard. | `nfl.com/injuries/`, 8 club `/team/depth-chart` pages, `nfl.com/scores/2026/REG8` & `REG9`, `operations.nfl.com/.../game-and-stadium-prep` | Reverse/promote into live line adjustments only after reviewer selects Path B/C on `suggestions-review.html` and T-90m official club inactives are archived across all 32 clubs |
| D-05 | 2026-11-13 | Agent session `arena/18c4acce-korea1` (task R1) | Replace the "2 of 32 clubs" coverage wording with the automated count: **31 of 32** club charts captured on the 2026-11-13 run, **Houston blank and flagged** (F-18), and the line-level checks stated as exactly what was done: 2 club charts cell by cell (ARI, WAS: 118 cells, all match or tie) and 20 injury rows (WAS, NYG: all match). Club chart labels are recorded as a flag (F-19), not used to rank sources. No player role is inferred. | `data/availability/manifest.json` (HOU `parsed 0 rows` on the 2026-11-12 and 2026-11-13 captures); `data/governance/availability_reconciliation_2026_11_13.csv`; `data/governance/injury_reconciliation_2026_11_13.csv`; nfl.com/injuries/league/2026/reg10; azcardinals.com/team/depth-chart; commanders.com/team/depth-chart; houstontexans.com/team/depth-chart | Reopen Q30 if a Houston chart is captured with ordered rows (then update F-18), or if any club publishes a dated chart that shows a publication time for a game week |

## Not decided here

- Any reward, prize pool, entry fee or stake sizing (blocked on Q13, S11).
- Any refresh of the pinned upstream commit (Q40, S08).
- Any purchase of a price feed (Q09, S07).

Those are owner decisions with a cost. This log records only what the agent could decide without
spending money or making a claim the evidence does not support.

## Agent recommendation — 2026-11-13 (not a decision)

| ID | Date (UTC) | Owner | Recommendation | Evidence at the time | Reversal condition |
|---|---|---|---|---|---|
| REC-01 | 2026-11-13 | Agent session `arena/917fe36e-korea1` | Treat **prices and executable quotes** as the first-paid item and **availability modelling** as the first no-cost work item, both behind Path A's rule that nothing unverified is presented as verified. | `review.html` (76 proposals in 4 registers, 74 questions in 3 registers; 4 of 4 registers raise prices and it holds the most blocked questions) and `live-verification.html` (the availability layer is extracted correctly but goes stale within 29 hours) | Reverse on any recorded D-row that selects a different path |

This is a recommendation, not a decision. It is separated from the D-rows above precisely so it
cannot be read as an approval: no money has been committed, no reward is authorised, and no
published number changed.
