# Repository line-by-line review and official-source verification register

**Session:** `arena/425336fc-korea1` (branch tip `645ef0c`, equal to `main`). **Date:** 2026-11-12.
**Policy:** every calculated table row is traced to its source; values confirmed against an official/primary source are marked verified, everything else is left blank and flagged UNVERIFIED. No value is inferred or filled in. Nothing below is a betting recommendation.

## Files reviewed

| File | Scope | Review result |
|---|---|---|
| `pipeline/fetch_data.py` | Pinned archive download (`nflverse/nfldata` commit SHA via `codeload.github.com`; hash-verified into `data/sources.json`) | Deterministic and reproducible; shell cannot reach `nfl.com` (egress allowlist), so official NFL pages are read through the page-fetch tool and cited here |
| `pipeline/build_datasets.py` | No-leak feature build; fold-safe weather fill; score arithmetic and sign-convention audits | Leakage assertions pass; `tests/test_no_lookahead.py` 4 passed; `tests/test_weather_fold.py` 3 passed |
| `pipeline/models.py` | Walk-forward ridge / matchup / Elo / ensemble; originated lines and future prices | Out-of-sample MAE behind market close (calculated research); future lines priced from completed-game medians only |
| `pipeline/strategies.py` | 18 pre-declared strategies (single, parlay, angles) | Every candidate published, no post-hoc dropping |
| `pipeline/backtest.py` | Settlement at recorded closing prices; cross-check vs per-side outcome file | 13,284/13,472 exact (98.605%); 99.931% where lines agree |
| `pipeline/validation.py` | Eight fail-closed gates, bootstrap, DSR, reality check | 0 of 18 strategies validated; rewards unawarded |
| `pipeline/correlations.py` | Measured leg, same-game and cross-game dependence | Intervals span zero where relevant; no imported values |
| `pipeline/render_site.py` / `*.html` | Strict-source dashboard at repository root | `verify_site.py`: 0 failing checks; `check_links`/`check_sources` pass |
| `tests/` | Integration, future-line, weather-fold, no-lookahead, props integrity | All green on the merged tree |
| `lab/`, `scripts/`, `analysis/` | Preserved replication annex and historical code | Not promoted to current findings; `analysis/` imports a layout the current pipeline no longer writes (flagged IR-16 in prior log) |

## Official verification performed this session (nfl.com via page-fetch tool)

| Check | Official page | Result |
|---|---|---|
| 2026 Week 8, CAR@GB (Green Bay 27, Carolina 19, total 46) | https://www.nfl.com/scores/2026/week-8 | **MATCH** vs `data/processed/games_model.csv` row `2026_08_CAR_GB` |
| 2026 Week 8, LAC@LAR (9–24), KC@DEN (24–28), NE@MIA (24–19), PHI@WAS (10–27), CHI@SEA (34–17) | https://www.nfl.com/scores/2026/week-8 | Matches published model rows where present |
| 2026 Week 9 sample (JAX 33–10 BAL; CIN 34–17 ATL; DEN 26–21 CAR; DAL 27–23 IND; NYJ 12–35 KC; DET 19–9 MIA; CLE 22–23 NO; NYG 19–11 PHI; LAR 20–13 WAS; HOU 44–22 LAC; LV 17–38 SF; GB 45–27 NE; ARI 3–17 SEA; TB 24–27 CHI; BUF 23–6 MIN) | https://www.nfl.com/scores/2026/week-9 | Official finals captured; **not** in the pinned archive (snapshot predates them) |
| 2026 Week 10 official injury report (all teams captured as available) | https://www.nfl.com/injuries/ | Used for `injuries.html`; rows verified cell-by-cell against the fetched page |

Note: Week-8 score cells were extracted as "Hidden Score" in the first chunk of the scores page; chunk 2 carried the values above. Week 9 and Week 10 are current/upcoming relative to the pinned snapshot (`2026-11-01T13:24:09Z`): the archive holds 2026 weeks 1–7 complete plus only the Thursday Week-8 game (CAR@GB, played 2026-10-29). The remainder of Week 8 and all of Weeks 9–10 are **absent from the data** — this is snapshot staleness, not an error, and is flagged below.

## Irregularities flagged for review (this session)

| ID | Severity | Finding | Links for manual review |
|---|---|---|---|
| IR-REV-01 | medium | Coordination log anecdote: "the official page reports Ravens 10–Bills 36, Final" for 12 November. The official Week 8 schedule carries no Ravens–Bills game (Week 8 MNF was CHI@SEA 34–17; Thursday was CAR@GB; Ravens@Bills does not appear on the official Week 8 page). The anecdote is unverified and should be treated as illustrative only, not as a data finding. | https://www.nfl.com/scores/2026/week-8 |
| IR-REV-02 | high (previously logged) | `nflverse/nfldata games.csv` ships **closing** lines, not openers; a true open→close movement study exists only for 2021 (`initial_lines.csv`, single book WSGT). No opening line is ever inferred. | https://github.com/nflverse/nfldata/blob/a270278f3ac4/data/games.csv |
| IR-REV-03 | high (previously logged) | Three 2015 games (`2015_06_ARI_PIT`, `2015_09_PHI_DAL`, `2015_15_KC_BAL`) have `closing_lines.csv` outcome flags contradicting `games.csv` scores; settlement uses `games.csv` (which reconciles result = home − away and total = home + away for all 7,384 played games). | https://github.com/nflverse/nfldata/blob/a270278f3ac4/data/closing_lines.csv |
| IR-REV-04 | medium | `data/raw/` is gitignored and not present in this checkout; `make build` re-fetches the pinned archive from `codeload.github.com`. A fully offline rebuild is impossible by design; the pin and hashes make the re-fetch auditable. | `Makefile`, `pipeline/fetch_data.py`, `data/sources.json` |
| IR-REV-05 | low | `README.md` and `COORDINATION.md` reference session id `arena/ed58af62-korea1` (stale from a previous integration). The current pinned branch is `arena/425336fc-korea1`. | `README.md`, `COORDINATION.md` |
| IR-REV-06 | high (open, previously logged) | No authenticated historical executable quote archive exists; strict public market values are blank; research calculations remain separately labelled. Blocks validation and rewards. | `flagged.html` (F-06) |
| IR-REV-07 | high (open, previously logged) | Verified player-prop prices and joint SGP quotes are absent; no prop ROI is claimed. | `props.html`, `flagged.html` (F-07) |

## Verification boundary

The full 7,384-game history cannot be row-by-row checked against NFL.com in one session (NFL.com offers 2010–2026 scores; pre-2010 and playoff games are unavailable there). The 39-game NFL.com sample from the earlier independent audit (`audit.html`, `data/audit/nfl_com_score_audit.csv`) plus the Week 8/9 spot checks above are the official coverage. Every other historical value remains community-sourced, hash-pinned, and flagged UNVERIFIED in public tables.

## Sources

- https://www.nfl.com/scores/2026/week-8 — official 2026 Week 8 scores
- https://www.nfl.com/scores/2026/week-9 — official 2026 Week 9 scores
- https://www.nfl.com/injuries/ — official NFL injury report
- https://www.nfl.com/scores/ — official NFL scores
- Pinned community archive: https://github.com/nflverse/nfldata/tree/a270278f3ac4e937295fe6a27814b3c4a2b62645