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

## Not decided here

- Any reward, prize pool, entry fee or stake sizing (blocked on Q13, S11).
- Any refresh of the pinned upstream commit (Q40, S08).
- Any purchase of a price feed (Q09, S07).

Those are owner decisions with a cost. This log records only what the agent could decide without
spending money or making a claim the evidence does not support.
| D-05 | 2026-11-13 | Agent session `arena/d58198fc-korea1` | Publish the independent repo audit as an **additive** sub-site under `review/` and change **no published number, table or verdict** on the main site. The five drift findings (depth-chart coverage, stale digest baseline, 26,149 tickets, missing Week 8 score, settled Week 10 Thursday game) are published with both values on `review/flagged.html`. | `data/repo_audit/claims.csv` (44 claims: 34 confirmed, 5 drift, 1 undecidable), 11 official captures, `verify_site.py` + `verify_audit_site.py` at 0 failures | Reverse only after the owner approves a rebuild: `python pipeline/audit.py --rebuild` re-freezes `audit_digests.csv` and the narrative figures are refreshed with it |
