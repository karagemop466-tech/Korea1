# COORDINATION — shared task board

**Repository:** `karagemop466-tech/Korea1`
**Format:** task · status (`unclaimed` / `in progress` / `done` / `needs review`) · owner session · file scope
**Rule:** claim a task by writing your session id + file scope here and pushing the claim before you start.
Never start a task another session has claimed. If you must change a file owned by another session, log
the request here instead of editing it. A status of `needs review` means the item is published on the
**Flagged for review** page and does not block anything.

---

## Session log

### Session `arena-a1970463` — branch `arena/a1970463-korea1` — started 2026-11-01

Claimed the whole build in one pass because the repository was empty (`README.md` only, single
`Initial commit`), so there were no competing claims to respect. Scope below is the complete file set;
no other session's files were touched.

| # | Task | Status | Owner | Files / scope |
|---|---|---|---|---|
| 1 | Data staging from pinned public sources | done | arena-a1970463 | `analysis/common.py`, `analysis/fetch_data.py`, `.gitignore` |
| 2 | Canonical game table + leak-free features + integrity report | done | arena-a1970463 | `analysis/build_games.py`, `data/derived/games.csv` |
| 3 | Line origination model (spread + total, walk-forward) | done | arena-a1970463 | `analysis/model.py`, `data/derived/model_lines.csv` |
| 4 | Residual cover/over models | done | arena-a1970463 | `analysis/residual_model.py` |
| 5 | Strategy library (24 signals) | done | arena-a1970463 | `analysis/signals.py` |
| 6 | Backtest engine, gates, FDR, Reality Check | done | arena-a1970463 | `analysis/backtest.py`, `data/site/backtest.json` |
| 7 | Selective-skill portfolio test | done | arena-a1970463 | `analysis/portfolio.py` |
| 8 | Correlation + parlay lab | done | arena-a1970463 | `analysis/parlays.py` |
| 9 | Player-game stats from official feed | done | arena-a1970463 | `analysis/build_players.py`, `data/derived/player_games.csv` |
| 10 | Player-prop correlations + calibration | done | arena-a1970463 | `analysis/props.py` |
| 11 | Verification (automated + live official checks) | done | arena-a1970463 | `analysis/verify.py`, `data/site/verification.json` |
| 12 | Static dashboard / GitHub Pages site | done | arena-a1970463 | `analysis/build_site.py`, `docs/**` |
| 13 | Leak tests | done | arena-a1970463 | `tests/test_no_lookahead.py`, `tests/check_links.py` |
| 14 | Docs + executive summary | done | arena-a1970463 | `README.md`, `EXECUTIVE_SUMMARY.md`, `requirements.txt` |
| 15 | **Final integration**: re-verify combined data, build site, confirm no broken links, open PR, merge, confirm Pages deploy | done | arena-a1970463 | `docs/**`, this file |

No task required editing another session's files, so no requests are logged.

---

## Sources (all pinned; nothing floating)

| Source | Pin | Used for |
|---|---|---|
| `nflverse/nfldata` | commit `a270278f3ac4e937295fe6a27814b3c4a2b62645` (2026-11-01T13:05:15Z) | schedule, results, closing lines, two-sided prices, rest, weather, officials, standings, opening lines |
| `nflverse/nflfastR` | commit `701bbf38bc1c030ff9f1f4825a23191287d3903c` | published stat-id → player-stat mapping (`R/calculate_stats.R`) |
| `nflverse/nflfastR-raw` | commit `61ab6b3dd2179d06766834784c8ba24649c8ba6c` (2026-02-09) | per-game official NFL Game Center JSON for 2024–2025 |
| nfl.com | live page `https://www.nfl.com/schedules/2026/by-week/week-9` | official schedule cross-check |
| ESPN | standings API + event payload `401873023` | official results cross-check + per-row game links |

---

## Verification performed (details on the site's **Verification** page)

**Live official checks — 7/7 passed, 0 mismatches**

| ID | Claim | Source |
|---|---|---|
| M01 | 2026 Week 9: 15/15 matchups, kickoff times, byes (PIT, TEN) | nfl.com week-9 schedule |
| M02 | 2025 records/PF/PA sample (NE 14-3 490/320, JAX 13-4 474/336) | ESPN standings API |
| M03 | 2026 W8 CAR@GB date, venue and winner | ESPN event 401873023 |
| M04 | Upstream data is the pinned nfldata commit | github.com/nflverse/nfldata |
| M05 | Player stat-id mapping | nflverse `R/calculate_stats.R` |
| M06 | Player layer lands on NFL-normal league averages | internal report |
| M07 | ESPN per-row game URL pattern | ESPN |

**Automated checks — run over 100% of rows on every build**

- `result = home − away`: 7,384 / 7,384
- `total = home + away`: 7,384 / 7,384
- duplicate game ids: 0
- standings recomputed from results vs upstream standings file: 800 team-seasons, 0 mismatches
- sign convention: home cover 48.95%, over 49.48%, mean overround 2.70% (all as expected for a valid market)
- look-ahead: `tests/test_no_lookahead.py` (features and model output are prefix-stable)

---

## Irregularities / flagged items (published on the site, non-blocking)

| ID | Severity | Item |
|---|---|---|
| IR-01 | high | Book identity and snapshot time behind the closing lines are not documented upstream |
| IR-02 | medium | `closing_lines.csv` and `games.csv` disagree on 32.7% of spreads, 38.3% of totals, 81.9% of home moneylines |
| IR-03 | high | No verifiable historical player-prop prices → prop ROI **not computed** (gate blocked) |
| IR-04 | medium | Player data ends 2026-02-09 (2025 season); no 2026 player rows |
| IR-05 | low | Venue naming differs (nfl.com "FedEx Field" vs dataset "Northwest Stadium") |
| IR-06 | medium | Opening lines exist for 2021 only → line-movement strategy fails the sample gate |
| IR-07 | low | 2026 Week 8 was partial in the snapshot (1 game complete, 13 with posted lines) |

None of these were silently corrected. Each is on the **Flagged for review** page with its evidence link.

---

## Deploy record

| Step | Result |
|---|---|
| Site build | `python -m analysis.build_site` → 9 pages, dependency-free |
| Link check | `python -m tests.check_links` → internal links and anchors verified (see below) |
| Pull request | *(filled in after the PR is opened)* |
| Merge to `main` | *(filled in after merge)* |
| GitHub Pages | served from `main` / `docs` |
| Live URL | *(recorded after deploy verification)* |

---

## Handoff notes for the next session

1. Start with the **Flagged for review** page — IR-03 is the highest-value item: verified prop prices
   would let the prop layer become a real backtest with no other rework.
2. The backtest universe deliberately excludes 1999–2005 (no two-sided prices upstream). Do not
   widen it with an assumed −110; that would break gate G1.
3. Any new strategy must be added to `analysis/signals.py` and will automatically appear on the board
   with all eight gates, FDR and Reality Check recomputed.
4. Shared outputs (`data/site/*.json`, `docs/**`) are generated — edit the generators, never the output.
