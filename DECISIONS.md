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

## Not decided here

- Any reward, prize pool, entry fee or stake sizing (blocked on Q13, S11).
- Any refresh of the pinned upstream commit (Q40, S08).
- Any purchase of a price feed (Q09, S07).

Those are owner decisions with a cost. This log records only what the agent could decide without
spending money or making a claim the evidence does not support.
