# Live official Week 11 injury-report read — 2026-11-20 (claim L-W11)

**Source (official):** https://www.nfl.com/injuries/ — the page header reads
"Official Latest NFL Injury Report for Players - Week 11 of the 2026 Season".

**Read method:** page-fetch of the official page on 2026-11-20 (UTC date; the fetch tool does not
record a clock time, so no time is claimed). The sandbox cannot reach nfl.com with `curl`, so the
rows were transcribed from that read. No byte-level hash of the page is available; the page has 7
chunks and only the first ~3 were read in full.

## What is in scope

| Game on page | Rows captured | Page count per club | Status |
|---|---|---|---|
| IND (Colts) vs HOU (Texans), Thu 19 Nov | 26 | IND 11, HOU 15 | **complete for both clubs** |
| PIT (Steelers) vs PHI (Eagles), Sun 22 Nov | 25 | PIT 10, PHI 15 | **complete for both clubs** |
| ARI vs KC and the rest of Week 11 | 0 | — | **not read — unverified** |

Row counts are checked against the counts printed on the page (`build_delta.py` fails loudly if
they drift).

## Files

- `w11_official_read.csv` — 51 rows, one per listed player, each with `source_url` = the official page.
- `build_delta.py` — joins the rows to the stored Week 10 capture `data/availability/injuries.csv`
  (`WEEK 10` rows, the 2026-11-18 official read) and writes the delta.
- `w11_vs_w10_delta.csv` — per-player comparison; `changed_fields` lists which of injury /
  practice / game status differ, or `unmatched`.

## Results (Week 11 official vs Week 10 stored capture)

- 51 Week 11 rows: **23 matched** to a Week 10 row, **28 unmatched**.
- Of the 23 matched: 13 unchanged; 10 changed (injury, practice or game status).
- **Unmatched is not "healthy".** The Week 10 capture lists only players on that week's report;
  a player absent from it had no designation that week. An unmatched row therefore cannot be called
  a change from "Full Participation" or from "available". It is recorded as unmatched, never filled in.

Matched changes (Week 10 → Week 11, from the stored capture and the official page):

| Team | Player | Week 10 (injury / practice / game) | Week 11 official (injury / practice / game) |
|---|---|---|---|
| IND | Jaylon Carlies | Neck / DNP / Out | — / DNP / — |
| IND | Will Mallory | Hamstring / LP / Questionable | Hamstring / DNP / Out |
| IND | Luke Rhodes | Hamstring / DNP / Out | Hamstring / LP / Questionable |
| IND | Charvarius Ward | — / FP / — | Knee / DNP / Out |
| HOU | Azeez Al-Shaair | Groin, not injury related / DNP / Out | — / DNP / — |
| HOU | Brevin Jordan | Finger, Foot / DNP / Out | Foot, Illness / DNP / Out |
| HOU | Woody Marks | — / FP / — | Concussion / DNP / Out |
| HOU | David Montgomery | Groin / FP / Questionable | — / FP / — |
| HOU | Keylan Rutledge | Neck, Shoulder / DNP / Out | — / FP / — |
| HOU | Wyatt Teller | Illness, Back / LP / Questionable | Back / FP / Questionable |

## Flagged for review (irregularities, not resolved here)

1. **Thursday game date precedes the read date.** The page lists IND–HOU under "THURSDAY, NOVEMBER 19TH".
   The read is dated 2026-11-20, so this game's designations are the pre-game report for a game that
   has already been played. Whether the official final exists was not checked in this slice.
2. **Name/URL mismatch on the official page:** "Jacob Hummel" (LB, HOU) links to
   `https://www.nfl.com/players/jake-hummel/`. Recorded as printed; not corrected.
3. **Unmatched rows (28):** most are players with no Week 10 designation (see above). Not a change.
4. **Week 10 rows with blank practice/game cells** (for example, Charvarius Ward, Week 10 FP and blank
   game status) are recorded as blank, not inferred as "Available."
5. **Stored Week 10 capture is pinned**, while the official page has rolled to Week 11. The live
   pipeline's rolling file `data/availability/injuries.csv` is still the Week 10 capture.
   This is the same rollover that the sibling W1 repair is addressing (`COORDINATION.md`, W1); it is
   not changed here.
6. **Unverified:** every row of every club outside IND, HOU, PIT, PHI for Week 11; all Week 11
   game-status values for clubs not read here.

## Not claimed

- No Week 11 "starter out" or "replacement" conclusion is drawn; the official report does not name starters.
- No model, leaderboard or strategy number changes because of this file.
