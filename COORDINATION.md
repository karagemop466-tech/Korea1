# COORDINATION.md — Shared Task Board

**Repo:** `karagemop466-tech/Korea1`
**Live site:** https://karagemop466-tech.github.io/Korea1/
**Pages source (pre-existing, verified 2026-11-01):** branch `main`, path `/`, build type `legacy`
**Project:** NFL line origination, signal research, parlay/prop correlation, validation gates, leaderboard competition.

> Read this file before starting work. Claim a task, write your session ID and file scope here,
> commit and push the claim immediately, and never start a task another session has claimed.
> `needs review` items are already published on the *Flagged for Review* page and block nothing.

---

## 1. Session registry

| Session ID | Branch | Window (UTC) | Role | Tasks |
|---|---|---|---|---|
| `S-ARENA-EA02C4FB` | `arena/ea02c4fb-korea1` | 2026-11-01 13:19 → open | Sole active session + final integration | T01–T12 |

**Branch naming note (deviation, logged):** the workspace platform pins this session to the fixed
branch `arena/ea02c4fb-korea1`; the `session-<id>/<task>` branch convention therefore cannot be used
for per-task branches (creating other branches is disallowed for this session). The non-overlap
requirement is instead enforced by **disjoint file scopes per task** below. Recorded here rather than
silently ignored.

**Concurrency note (transparency):** task owners other than `TBD` are the same session. No other
session had claimed anything at first claim time (`2026-11-01T13:20Z`), and the repository contained
a single 8-byte `README.md` and one commit (`d8d7d81`) at that moment, so there was no work to
duplicate. The board is still maintained in the required multi-session format so a later session can
verify what was touched, re-verify it, or take over a task.

---

## 2. Task board

Status legend: `unclaimed` · `in progress` · `done` · `needs review`

| ID | Task | File scope (exclusive) | Owner | Status | Verif. state |
|---|---|---|---|---|---|
| T01 | Repo audit + provenance register | `README.md`, `research/00-repo-audit.md` | S-ARENA-EA02C4FB | done | verified |
| T02 | Market structure, hold/vig, rules research | `research/01-market-structure.md` | S-ARENA-EA02C4FB | in progress | partly unverified |
| T03 | Data pipeline + integrity gates (G0) | `scripts/00_ingest.py`, `scripts/lib/*`, `data/raw_manifest.json` | S-ARENA-EA02C4FB | in progress | verified |
| T04 | Line origination model (spread/total/ML) | `scripts/02_line_model.py`, `data/lines.json` | S-ARENA-EA02C4FB | unclaimed→claimed | pending |
| T05 | Single-bet strategy battery + backtests | `scripts/03_strategies.py`, `data/strategies.json` | S-ARENA-EA02C4FB | unclaimed→claimed | pending |
| T06 | Parlay correlation engine | `scripts/04_correlations.py`, `data/correlations.json` | S-ARENA-EA02C4FB | unclaimed→claimed | pending |
| T07 | Player-prop combo correlations | `scripts/05_props.py`, `data/props.json` | S-ARENA-EA02C4FB | unclaimed→claimed | pending |
| T08 | Validation gates + luck removal | `scripts/06_validation.py`, `data/validation.json`, `research/03-validation-gates.md` | S-ARENA-EA02C4FB | unclaimed→claimed | pending |
| T09 | Leaderboard / competition design | `research/04-competition.md`, `data/leaderboard.json` | S-ARENA-EA02C4FB | unclaimed→claimed | pending |
| T10 | Executive summary | `EXECUTIVE_SUMMARY.md` | S-ARENA-EA02C4FB | unclaimed→claimed | pending |
| T11 | Site build (dashboard + subpages) | `docs/**` (all generated), `scripts/07_build_site.py` | S-ARENA-EA02C4FB | in progress | pending |
| T12 | Integration, link check, PR, merge, Pages | `data/site/*`, `COORDINATION.md`, PR | S-ARENA-EA02C4FB | unclaimed→claimed | pending |

Reserved by T12 only: `data/site/*` (the shared table payloads consumed by the site) and the PR.

---

## 3. Claim log

| UTC | Session | Action |
|---|---|---|
| 2026-11-01T13:20Z | S-ARENA-EA02C4FB | Board created. T01/T02/T03/T11 claimed. Repo audit executed. |
| 2026-11-01T13:2xZ | S-ARENA-EA02C4FB | T04–T10, T12 claimed (no competing claims present). |

---

## 4. Source register (authoritative for every table row on the site)

Machine-readable copy: `data/sources.json`. Every site row carries a `source_id` that resolves there.

| Source ID | Publisher | What it is used for | URL | Trust tier |
|---|---|---|---|---|
| `NFL-RULES` | NFL Football Operations (official) | Playing rules, scoring values, OT, timing | https://operations.nfl.com/the-rules/nfl-rulebook/ | Official (league) |
| `NFL-STATS` | NFL.com (official) | League/team/player statistics cross-checks | https://www.nfl.com/stats/ | Official (league) |
| `NFL-INJURY` | NFL Football Operations (official) | Injury report policy / practice status | https://operations.nfl.com/ | Official (league) |
| `NFL-GAMBLING` | NFL (official) | League gambling policy | https://www.nfl.com/ | Official (league) |
| `NFLVERSE-DATA` | nflverse (open data project) | Play-by-play, schedules, player-week stats (derived from official NFL gamebooks) | https://github.com/nflverse/nflverse-data | Verified third party |
| `SBR-10Y` | Sportsbook Review archive mirror (flancast90/sportsbookreview-scraper) | Open/close spread, total, moneyline 2011–2021 | https://github.com/flancast90/sportsbookreview-scraper | Third party (odds aggregator) |
| `NVGCB` | Nevada Gaming Control Board (gov) | Sports-pool hold %, verified house edge | https://gaming.nv.gov/ | Official (regulator) |
| `NJDGE` | New Jersey Division of Gaming Enforcement (gov) | Sports-wagering gross revenue/hold | https://www.nj.gov/oag/ge/ | Official (regulator) |
| `PAPER-DSR` | Bailey & López de Prado (2014), *Journal of Portfolio Management* | Deflated Sharpe Ratio | https://doi.org/10.3905/jpm.2014.40.5.094 | Peer-reviewed |
| `PAPER-PBO` | Bailey, Borwein, López de Prado, Zhu (2017), *Journal of Computational Finance* | Probability of backtest overfitting (CSCV) | https://doi.org/10.21314/JCF.2016.322 | Peer-reviewed |
| `PAPER-KELLY` | Kelly (1956), *Bell System Technical Journal* | Bankroll growth criterion | https://doi.org/10.1002/j.1538-7305.1956.tb03809.x | Peer-reviewed |
| `PAPER-SHIN` | Shin (1993), *Economic Journal* | Insider-trading/odds-normalisation model | https://doi.org/10.2307/2234340 | Peer-reviewed |
| `PAPER-GRAY` | Gray & Gray (1997), *Journal of Finance* | NFL market efficiency test | https://doi.org/10.1111/j.1540-6261.1997.tb02742.x | Peer-reviewed |
| `PAPER-LEVITT` | Levitt (2004), *Economic Journal* | Why bookmakers set lines as they do | https://doi.org/10.1111/j.1468-0297.2004.00235.x | Peer-reviewed |

Tier rules: **Official** values may be published as fact. **Peer-reviewed** formulas may be applied.
**Third party** data is published only together with its provenance and a verification status column.

---

## 5. Irregularities log (mirrored on the site's *Flagged for Review* page)

| # | Irregularity | Detail | Disposition |
|---|---|---|---|
| I-01 | Repo was empty | Only `README.md` (8 bytes, no trailing newline), 1 commit, no licence, no CI, no `.gitignore` | Logged; licence left absent deliberately (cannot invent a licence on the owner's behalf) — flagged |
| I-02 | No odds source is "official" | No sportsbook publishes a machine-readable historical odds archive under an open licence; the NFL does not publish betting lines | Odds marked *Third party*; every odds-derived row carries the archive + a `verified` column |
| I-03 | SBR archive coverage gap | Archive holds 2,956 games, 2011–2021 only; 2022+ must be sourced elsewhere | Coverage stated on every page; 2026 lines therefore marked `model-originated` not `market` |
| I-04 | Prop-line history absent | No public, licence-clean archive of historical player-prop *lines* was reachable from this sandbox | Prop *correlations* computed from play-by-play (real); prop *lines/prices* left blank and flagged `unverified` |

---

## 6. Handoff / takeover rules

A claim older than 60 minutes with no commit made against its scope may be taken over by any session.
Record the takeover in §3 with the previous owner's last commit SHA. Resolve conflicts by keeping both
sides' work and re-verifying, never by reverting another session's files.

---

## 7. Integration & release log

| UTC | Step | Result |
|---|---|---|
| — | pending | filled in by T12 |
