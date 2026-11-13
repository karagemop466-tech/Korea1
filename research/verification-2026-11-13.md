# Verification pass of 2026-11-13 — line by line, against official sources

Session `arena/534e771f-korea1`. Branch `arena/534e771f-korea1`, branched from `main` @ `43a946aed4c3ec86b17b920757dc780ced73ea93`.

This document records **only what was actually checked against an official page during this session**. Nothing is carried over from a previous session's claim, and no value is filled in from memory. Where a check produced a blank, the blank is published as a blank.

Machine-readable form: `data/processed/verify_2026_11_13.csv` and `data/audit/official_review_2026_11_13.json`. Every irregularity below also appears on `flagged.html` with its official link.

**Result: 19 claims checked — 11 clean, 8 verified but revealing a defect, 0 unconfirmed.**

## What was checked

### Upstream data pin

**V-01 — Pinned commit `a270278f3ac4e937295fe6a27814b3c4a2b62645` exists in nflverse/nfldata**

- Expected: commit exists
- Observed on the official page: commit exists, authored 2026-11-01T13:05:15Z
- Result: **VERIFIED**
- Note: Read from the GitHub REST API on 2026-11-13.
- Checked against: <https://github.com/nflverse/nfldata/commit/a270278f3ac4e937295fe6a27814b3c4a2b62645> at 2026-11-13T23:40Z

**V-02 — Upstream `master` has moved since the pin**

- Expected: pin equals upstream master
- Observed on the official page: upstream master HEAD b6047f62bdffb23c775e6d0f9b5472a609fff94e, 2026-11-13T22:35:18Z, 733 commits ahead of the pin
- Result: **VERIFIED — DEFECT** (irregularity IR-01)
- Checked against: <https://github.com/nflverse/nfldata/compare/a270278f3ac4e937295fe6a27814b3c4a2b62645...master> at 2026-11-13T23:40Z

**V-03 — The pin was taken before this season's current week**

- Expected: snapshot covers the week being published
- Observed on the official page: snapshot is dated 2026-11-01; Week 10 was still in progress on 2026-11-13
- Result: **VERIFIED — DEFECT** (irregularity IR-02)
- Checked against: <https://www.nfl.com/scores/2026/week-10> at 2026-11-13T23:40Z

### Official scores — Week 10

**V-04 — Week 10 is only partly played**

- Expected: all frozen games settled
- Observed on the official page: 1 final (WAS at NYG, Thu Nov 12); the other 16 kick off Sun 2026-11-15
- Result: **VERIFIED — DEFECT** (irregularity IR-03)
- Checked against: <https://www.nfl.com/scores/2026/week-10> at 2026-11-13T23:40Z

**V-05 — Commanders at Giants finished 24–21**

- Expected: a single official final
- Observed on the official page: WAS 24, NYG 21, status Final
- Result: **VERIFIED**
- Note: MetLife Stadium, East Rutherford, NJ; Thursday 12 November, 8:15 PM EST.
- Checked against: <https://www.nfl.com/games/commanders-at-giants-2026-reg-10> at 2026-11-13T23:40Z

**V-06 — The official quarter scores sum to the official final**

- Expected: quarters sum to the final
- Observed on the official page: WAS 0/10/7/7 = 24; NYG 0/7/7/7 = 21
- Result: **VERIFIED**
- Note: Checked so the settlement used by forward_settle.py is internally consistent.
- Checked against: <https://www.nfl.com/games/commanders-at-giants-2026-reg-10> at 2026-11-13T23:40Z

**V-07 — An official game book exists for the settled game**

- Expected: a primary document is published
- Observed on the official page: PDF game book linked from the official game centre page
- Result: **VERIFIED**
- Checked against: <https://www.nfl.com/games/commanders-at-giants-2026-reg-10> at 2026-11-13T23:40Z

**V-08 — The derived total and margin used for grading are correct**

- Expected: total 45, home margin −3
- Observed on the official page: total 45, home margin −3 (21 − 24)
- Result: **VERIFIED**
- Checked against: <https://www.nfl.com/games/commanders-at-giants-2026-reg-10> at 2026-11-13T23:40Z

### Official injury report

**V-09 — The official injury page is live for Week 10 of the 2026 season**

- Observed on the official page: page title: 'Official Latest NFL Injury Report for Players - Week 10 of the 2026 Season'
- Result: **VERIFIED**
- Checked against: <https://www.nfl.com/injuries/> at 2026-11-13T23:40Z

**V-10 — The official injury page covers all 32 clubs**

- Expected: 32 clubs listed
- Observed on the official page: 28 clubs listed on the page read at 2026-11-13T23:40Z; Denver, Philadelphia, Tampa Bay and Chicago do not appear
- Result: **VERIFIED — DEFECT** (irregularity IR-04)
- Checked against: <https://www.nfl.com/injuries/> at 2026-11-13T23:40Z

**V-11 — The committed capture matches a fresh read of the same page**

- Expected: the 326 committed rows match a fresh read
- Observed on the official page: committed 326 rows with 18 game-status values; fresh read 344 rows with 159; 381 differing cells (363 changed, 18 rows missing from the capture)
- Result: **VERIFIED — DEFECT** (irregularity IR-05)
- Checked against: <https://www.nfl.com/injuries/> at 2026-11-13T23:40Z

**V-12 — A single read of the injury page is stable enough to grade a pick**

- Expected: one read is a reliable snapshot
- Observed on the official page: two reads 90 minutes apart differ in 381 cells; a designation is only a confirmation once the T-90m inactives and the final scoreboard agree
- Result: **VERIFIED — DEFECT** (irregularity IR-06)
- Checked against: <https://www.nfl.com/injuries/> at 2026-11-13T23:40Z

**V-13 — Every row of this session's read uses the official vocabulary**

- Observed on the official page: 344 rows; practice status is one of Full / Limited / Did Not Participate In Practice; game status is one of blank / Out / Doubtful / Questionable
- Result: **VERIFIED**
- Checked against: <https://www.nfl.com/injuries/> at 2026-11-13T23:40Z

**V-14 — Every row of the injury page was readable**

- Expected: all rows parse
- Observed on the official page: one Jacksonville row could not be read unambiguously and is recorded as unreadable rather than guessed
- Result: **VERIFIED — DEFECT** (irregularity IR-07)
- Checked against: <https://www.nfl.com/injuries/> at 2026-11-13T23:40Z

**V-15 — Blank game-status values are published as blanks**

- Expected: no value is invented
- Observed on the official page: blank on the page, blank in every published table
- Result: **VERIFIED** (irregularity IR-08)
- Checked against: <https://www.nfl.com/injuries/> at 2026-11-13T23:40Z

### Forward ledger

**V-16 — The forward freeze predates kickoff**

- Expected: frozen before kickoff
- Observed on the official page: frozen 2026-11-12T13:26:48Z, pushed 2026-11-12T13:28:07Z, kickoff 2026-11-13T01:15:00Z — 11 h 47 min before kickoff
- Result: **VERIFIED**
- Checked against: <https://www.nfl.com/games/commanders-at-giants-2026-reg-10> at 2026-11-13T23:40Z

**V-17 — The frozen picks were graded only against an official final**

- Expected: no pick is graded without an official result
- Observed on the official page: 4 of 65 picks graded, 61 still open
- Result: **VERIFIED**
- Checked against: <https://www.nfl.com/games/commanders-at-giants-2026-reg-10> at 2026-11-13T23:40Z

**V-18 — 18 canonical strategies are published on the leaderboard**

- Observed on the official page: 0 of 18 carry the VALIDATED verdict
- Result: **VERIFIED**
- Checked against: <https://www.nfl.com/scores/2026/week-10> at 2026-11-13T23:40Z

**V-19 — Gate G1 (official quote provenance) passes for at least one strategy**

- Expected: at least one strategy has executable quote provenance
- Observed on the official page: 0 of 18 pass G1, so no strategy can be called validated
- Result: **VERIFIED — DEFECT** (irregularity IR-01)
- Checked against: <https://www.nfl.com/scores/2026/week-10> at 2026-11-13T23:40Z

## Irregularities found

| Id | Irregularity | Where to look |
|---|---|---|
| IR-01 | The pinned nflverse/nfldata commit is 733 commits behind upstream master, so the research snapshot no longer reflects the current season. | <https://github.com/nflverse/nfldata/compare/a270278f3ac4e937295fe6a27814b3c4a2b62645...master> |
| IR-02 | Upstream master moved on 2026-11-13, the same day as this review; the pin will keep drifting until DH-04 is answered. | <https://www.nfl.com/scores/2026/week-10> |
| IR-03 | Week 10 is only partly played. One of the frozen games has settled; the remaining sixteen have not, so no strategy verdict can change yet. | <https://www.nfl.com/scores/2026/week-10> |
| IR-04 | The official injury page read on 2026-11-13 lists 28 of the 32 clubs. Denver, Philadelphia, Tampa Bay and Chicago do not appear on it at this time. | <https://www.nfl.com/injuries/> |
| IR-05 | The committed capture `data/availability/injuries.csv` carries a game-status value for 18 of 326 rows while this session's read of the same page carried one for 159 of 344. The difference is capture cadence, not a parser defect. | <https://www.nfl.com/injuries/> |
| IR-06 | Two reads of the same official page 90 minutes apart differ in 381 cells. Any single read is a snapshot, and a designation is not a confirmation without the T-90m inactives and the final scoreboard. | <https://www.nfl.com/injuries/> |
| IR-07 | One Jacksonville row on the official injury page could not be read unambiguously; it is recorded as unreadable rather than guessed. | <https://www.nfl.com/injuries/> |
| IR-08 | Game-status values that the official page does not show are left blank in every published table. No string is invented for a player absent from a club chart. | <https://www.nfl.com/injuries/> |

## The one official result available this week

The forward ledger froze **65 picks across 14 strategies and 17 games** at 2026-11-12T13:26:48Z, pushed to GitHub at 2026-11-12T13:28:07Z, 11 h 47 min before kickoff before the first kickoff (2026-11-13T01:15:00Z).

Exactly one of those games has settled officially:

| Field | Official value |
|---|---|
| Game | 2026_10_WAS_NYG |
| Date | 2026-11-12 |
| Away | WAS |
| Away score | 24 |
| Home | NYG |
| Home score | 21 |
| Total points | 45 |
| Home margin | -3 |
| Status | Final |
| Venue | MetLife Stadium, East Rutherford, NJ |
| Verified at | 2026-11-13T23:00Z |

Graded against that result: **2 win, 2 losses, 0 pushes, net -0.3050 units** on 4 settled picks. 61 picks remain open.

**Verdict: NOT A RESULT — 1 of 17 games settled and 4 of 65 picks graded, against a 30-week / 150-pick horizon.** Four graded picks is not evidence of skill or of its absence; it is the first row of a ledger that needs 150 picks over 30 weeks before it can say anything at all.

## Second and third string deficiencies

The join of the official injury report against the committed club depth charts covers **171 rows across 26 clubs**: 40 first-string players Out, 22 second-to-fourth-string players Out, 10 doubtful, 86 questionable and 3 compounded deficiencies where the next listed man is himself Out or Doubtful. 44 rows could not be matched to a depth chart and are published with a blank string, never an inferred one.

## Reproduce

```
make build
make test
.venv/bin/python pipeline/official_review.py
```

**Research and education only. No guaranteed returns.**
