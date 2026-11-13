# Improvements for decision making — 2026-11-13

Session `arena/534e771f-korea1`. The register is `data/review/improvements.csv`; it is published as `improvements.html`.

The user asked for **a dedicated section where someone can review suggestions and choose the best path before implementing changes**. That section is `improvements.html`, and this is the reasoning behind it.

Three rules shaped the register:

1. **Nothing is implemented that changes a published number.** Improvements that build a new page, a new register or a new diagnostic can be built by this session; improvements that move a model, a gate or a price need your decision first.
2. **Every row names what it blocks.** An improvement that unblocks nothing is a preference, not an improvement.
3. **Every row offers options, not a fait accompli.** Where a choice is yours, the register says so.

## The observation that drove it

Ten registers covering the same ground were already on the site when this session started: **8 machine-readable** and 2 prose, written by six sessions that could not see each other. 166 individual rows. Three ideas appeared in four separate registers each:

| Idea | Filed as | Built here as |
|---|---|---|
| An all-club 1st–4th string deficiency register | S03, SR-04, SUG-06 | `gameday-deficiencies.html` — 171 rows, 26 clubs |
| One canonical surface for the questions | DB-01, S05, SR-01 | `decision-hub.html` — 16 decisions mapped to all 166 rows |
| Prospective grading of the forward ledger | DB-03, S07, SR-03 | `pipeline/forward_settle.py` — first 4 picks graded |

None of those sessions could build them alone, because each idea spans registers owned by the others. **The de-duplication itself was the blocker, and it is now done.**

## Built this session

| Id | Area | Improvement | Why it improves decision making | Status | Blocks |
|---|---|---|---|---|---|
| IMP-01 | Site structure | One decision hub that maps all 166 rows onto 16 canonical decisions and links back to every original. | A reviewer can see the whole decision surface at once and can prove nothing was dropped, instead of guessing which page is current. | Implemented this session (decision-hub.html) |  |
| IMP-02 | Availability | Print the capture time on every availability table and publish the cell-level drift between the last two reads of the same official page. | An Out designation that appeared after the capture is invisible otherwise; the drift table makes the rate of change measurable. | Implemented this session (gameday-deficiencies.html) |  |
| IMP-03 | Availability | Join every designation to the club's own 1st / 2nd / 3rd / 4th string order and flag compounded deficiencies where the next man is also Out or Doubtful. | This is the requirement the project was missing: it turns an injury list into a lineup-deficiency statement for both offence and defence. | Implemented this session (gameday-deficiencies.html) |  |
| IMP-04 | Validation | Grade every frozen pick against the official final as soon as the game is Final, and publish the running record. | It is the only mechanism in the repository that removes hindsight; without grading it produces no evidence at all. | Partly implemented this session — 1 of 14 games graded; the weekly job is proposed as IMP-12 | IMP-12 |
| IMP-08 | Navigation | Group them under one Decide heading with the hub first, and label each as an original register. | Reduces the chance that a reviewer reads one register and believes it is complete. | Implemented this session (hub + sidebar grouping) |  |

## Proposed — these are yours to decide

| Id | Area | Improvement | Options | Cost | Risk | Blocks |
|---|---|---|---|---|---|---|
| IMP-05 | Reproducibility | Repair the rewrite and add a byte-identity check to CI so a non-deterministic build fails the pipeline. | A) Repair and add a CI check. B) Repair only. C) Leave. | Small | Low. |  |
| IMP-06 | Availability | Strip the number at parse time in `pipeline/fetch_availability.py` as well as in the join. | A) Fix the parser. B) Keep compensating in the join. C) Nothing. | Small | Low, but the file is owned by another session — logged as a cross-scope request, not edited. |  |
| IMP-07 | Availability | Transcribe the image by hand with a hash and a date, or drop Houston from coverage and say so on the page. | A) Hand-transcribe weekly with a hash. B) Flag and exclude. C) Nothing. | Small | Medium — hand transcription is an inference risk; it must be dated and hash-recorded. |  |
| IMP-09 | Executive summary | Add a "what would change this decision" block naming the two or three measurements that would flip it. | A) Add the block. B) Leave. | Small | Low. |  |
| IMP-10 | Machine readability | Publish a `decisions.json` with the state of every gate and every canonical decision, so two builds can be diffed. | A) Publish the file. B) Leave. | Small | Low. |  |
| IMP-11 | Verification | Print a per-page "last verified" line naming the exact command and timestamp. | A) Add the line. B) Leave. | Small | Low — rendered from a build timestamp. |  |
| IMP-12 | Validation | A scheduled workflow that reads official finals for settled games and grades the frozen picks, then commits the result. | A) Weekly scheduled grading job. B) Grade at end of season. C) Manual. | Medium | Low, but it must never grade against an unofficial score. | IMP-04 |
| IMP-13 | Availability | Add a rule that raises a flag row whenever such a designation appears, with the string and next man attached. | A) Flag on the page. B) Flag plus a workflow annotation. C) Nothing. | Small | Low. |  |
| IMP-14 | Leaderboard | Publish two boards: an eligibility board (which strategy has passed which gate) and a labelled risk-adjusted research board. | A) Two boards. B) One board with a toggle. C) Nothing. | Medium | Medium — depends on the DH-01 evidence-display decision. |  |
| IMP-15 | Site structure | Label every archived page as superseded with a date and a link to its successor, or remove them from the served site. | A) Label in place. B) Remove from the served site. C) Nothing. | Small | Low for A; B loses audit history. |  |

## What this session deliberately did not do

- **It did not change any published number.** Every model output, gate verdict and ROI cell is byte-identical to `main` at `43a946a`. The only lines that changed in `strategies.html`, `lines.html`, `validation.html`, `correlations.html`, `props.html` and `requirements.html` are the navigation block.
- **It did not relax a gate.** Two earlier registers recorded proposals to raise volume until ROI turns positive, or to relax a gate so a strategy can be shown as a winner. Both are recorded in the hub as DH-15 option B and both are rejected: a gate lowered to produce a winner produces a winner, not evidence.
- **It did not add an availability term to any model.** The 171-row deficiency join tells you who is missing; it does not tell you what the absence is worth. Measuring that is IMP-06/DH-05 and it needs an out-of-sample test against the market first.
- **It did not invent a depth string.** 44 rows could not be matched to a club depth chart (Houston publishes its chart as an image). Those rows are blank, and blank is the honest answer.

## How to use the register

1. Open `improvements.html`. The built items are at the top so you can see what changed without asking.
2. Read the proposed items against the "Blocks" column. Anything that blocks a gate, a price or a reward comes first.
3. Record your choice. The register is a CSV; the decision is yours to log, and `COORDINATION.md` describes where.

**Research and education only. No guaranteed returns.**
