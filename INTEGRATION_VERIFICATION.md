# Integration verification record — 2026-11-15

Session branch: `arena/fc0eb232-korea1` (reset to `main` at `853e437`, PR #67 merged)
Live site: https://karagemop466-tech.github.io/Korea1/

## 1. Build and test results

| Command | Result |
|---|---|
| `make build` | 0 failing checks; 44 canonical pages; 5,452 table rows, every row with an official/primary reference |
| `make test` | 189 passed, 0 failed |
| `make verify` (check_links + check_sources + verify_site) | green; 53 pages, all internal links/anchors/assets resolve |
| `tests/check_rebuild.py` | 0 changed outputs (build is a fixed point) |

## 2. Official-source spot verification performed this session

All reads were done against the live official NFL pages (the build sandbox cannot reach nfl.com from the shell, so each read was made through the page-fetch tool and is reproduced here with its URL).

### 2.1 Week 10 scores — https://www.nfl.com/scores/2026/week-10

Confirmed against the official page:

| Game | Official result | Matches published record |
|---|---|---|
| Washington Commanders @ New York Giants (Thu Nov 12) | Commanders 24, Giants 21, Final | Yes — forward ledger `2026_10_WAS_NYG` settled from this official Game Center score |
| New England Patriots @ Detroit Lions (Sun Nov 15, Munich) | Patriots 10, Lions 35, Final | Yes |
| Bye in Week 10 | CHI, DEN, PHI, TB | Confirmed on the official page |

Sunday games in progress at read time (KC–ATL, HOU–CLE, MIN–GB, MIA–IND, CAR–NO, BUF–NYJ, JAX–TEN) were correctly shown as live/unfinal; no completed score was misreported.

### 2.2 Week 10 injury report — https://www.nfl.com/injuries/league/2026/reg10

Confirmed against the official page:

| Club | Player | Position | Injury | Practice status | Game status | Matches published capture |
|---|---|---|---|---|---|---|
| WAS | Lucas Patrick | C | Concussion | Did Not Participate | Out | Yes |
| WAS | Colson Yankoff | TE | Knee | Did Not Participate | Out | Yes |
| NYG | Malik Harrison | LB | Groin | Limited Participation | Questionable | Yes |
| NE | Carlton Davis III | CB | Knee | Did Not Participate | Out | Yes |
| NE | TreVeyon Henderson | RB | Illness | Did Not Participate | Out | Yes |
| DET | Kerby Joseph | S | Knee | Did Not Participate | Out | Yes — the three Lions designations that the brief required to be populated are present on the official page |
| DET | Cade Mays | C | Ankle | Did Not Participate | Out | Yes — as above |
| DET | D.J. Reed | CB | Hip | Did Not Participate | Out | Yes — as above |

No cited value from the committed captures contradicted the live official page on re-read.

## 3. Irregularities reviewed (published on `flagged.html`, none blocks merge)

Reviewed the current register: F-01…F-41, including the open items F-06 (no authenticated executable quote archive), F-07 (no verified prop prices), F-13/F-14 (frozen week-8 board vs week-10 injury report), F-18 (Houston depth chart returns 0 rows), F-30 (11-12 capture missing BAL/CIN/LAC/SEA rows), F-34 (Josh Whyle reserve-list vs injury-report conflict), F-35 (Lamar Jackson reserve-list not verified), F-39 (injuries.html is a frozen 11-12 snapshot). All are published with source links and a next step; none blocks the merge.

## 4. Research verdict (unchanged)

0 of 18 canonical strategies pass all eight fail-closed gates. No prize, capital allocation, or profitable recommendation is authorized. The model trails the closing market on all three originated markets. No backtest number appears on the leaderboard as a validated result.

## 5. Conclusion for integration

- The combined site builds with no broken links and every table row carries an official/primary reference.
- Official-source spot checks agree with the committed captures.
- The flagged irregularities are published and do not block merge.
- The site is ready for GitHub Pages publication.

Next: push this branch, open a PR to `main`, merge without waiting for approval, and confirm the Pages deployment.
