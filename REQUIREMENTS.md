# Requirements traceability — NFL Line Lab

Every requirement in the brief, one row each, with the artefact that satisfies it and a source
link. Generated from [`requirements/requirements.csv`](requirements/requirements.csv) by
`pipeline/render_requirements.py`; the same data renders as
[`requirements.html`](https://karagemop466-tech.github.io/Korea1/requirements.html).

**Status vocabulary** — `MET`: a published artefact proves it. `PARTIAL`: the work exists but a
stated limitation applies. `FLAGGED`: blocked or unverified, published on the
[Flagged for review](https://karagemop466-tech.github.io/Korea1/flagged.html) page.
`NOT MET`: nothing was delivered and nothing was invented to cover the gap.

**46 requirements** — 40 MET · 5 PARTIAL · 0 FLAGGED · 1 NOT MET

## Coverage by area

| Area | Requirements | MET | PARTIAL | FLAGGED / NOT MET |
|---|---|---|---|---|
| Governance | 3 | 3 | 0 | 0 |
| Requirements | 2 | 2 | 0 | 0 |
| Data | 4 | 1 | 2 | 1 |
| Line origination | 4 | 4 | 0 | 0 |
| Signals | 4 | 3 | 1 | 0 |
| Leaderboard | 2 | 1 | 1 | 0 |
| Validation | 1 | 1 | 0 | 0 |
| Correlation | 1 | 1 | 0 | 0 |
| Luck removal | 2 | 2 | 0 | 0 |
| Reporting | 1 | 1 | 0 | 0 |
| Automation | 1 | 1 | 0 | 0 |
| Sourcing | 3 | 3 | 0 | 0 |
| Delivery | 6 | 6 | 0 | 0 |
| Verification | 3 | 3 | 0 | 0 |
| Publish | 4 | 4 | 0 | 0 |
| Documentation | 1 | 1 | 0 | 0 |
| Suggestions | 1 | 1 | 0 | 0 |
| Decision readiness | 1 | 1 | 0 | 0 |
| Injuries & Depth | 1 | 0 | 1 | 0 |
| Audit & Hygiene | 1 | 1 | 0 | 0 |

## The list

### Governance

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R01 | Keep a shared task board that lists every task, its status, its owner and the files it touches, and claim work before starting it. | **MET** | COORDINATION.md is the board: tasks T0-T14 and F1-F3 with status, owner and file scope; claims are committed before editing files. | [COORDINATION.md (task board + log)](COORDINATION.md) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/COORDINATION.md) |
| R02 | Never start a task another session has claimed; keep scopes non-overlapping; log cross-scope edits instead of silently making them. | **MET** | Every file edit in this session falls inside claimed T14 scope in COORDINATION.md, and all repairs across sibling modules are logged explicitly. | [COORDINATION.md - task log](COORDINATION.md) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/COORDINATION.md) |
| R03 | Coordinate parallel sessions: record collisions, never discard another session's work. | **MET** | Collision notice and merge-resolution logs preserve earlier parallel sessions' code, tests, props module and the replication annex under lab/. | [COORDINATION.md - collision notice and merge log](COORDINATION.md) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/COORDINATION.md) |

### Requirements

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R04 | Collect a full list of requirements. | **MET** | 46 requirements extracted from the brief and user follow-up, each with an ID, status, artifact proof and source link; single source in requirements/requirements.csv. | [REQUIREMENTS.md / requirements.html](requirements.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/REQUIREMENTS.md) |
| R05 | Organize and analyse the work against that requirement list. | **MET** | requirements.html and REQUIREMENTS.md both render from requirements/requirements.csv with per-area roll-ups and exact status counts. | [requirements.html (roll-up table)](requirements.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/requirements/requirements.csv) |

### Data

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R06 | Use official, verified, trusted sources only - nothing scraped from an unverifiable feed. | **PARTIAL** | Official NFL.com scores (59/59 MATCH across 2026 W8-W9 + sample seasons), Week 10 injuries, and 27/28 Week 10 official club depth charts are verified; historical odds/lines still rely on a pinned community mirror (nflverse/nfldata@9654533e) lacking authenticated sportsbook timestamps. | [sources.html and audit.html](sources.html) | [source](https://www.nfl.com/scores/) |
| R07 | Never infer, interpolate or back-fill a missing value. | **MET** | Missing or unverified values (including HOU's image-only depth chart and unauthenticated quotes) render blank and are listed on flagged.html; verify_site.py V1b/V3 fail on unformatted missing values. | [flagged.html - blank and unverified items](flagged.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/verify_site.py) |
| R40 | State how current the data is, and what changed upstream since the snapshot. | **PARTIAL** | Pinned upstream snapshot refreshed to 2026-11-12 commit 9654533e with 59/59 NFL.com score matches across Weeks 8-9 and historical samples; Week 10 scheduled QB mismatches are flagged and audit_drift tracks upstream HEAD. | [audit.html and verification.html](audit.html) | [source](https://github.com/nflverse/nfldata/commits/master) |
| R41 | Team-total and player-prop prices (needed for prop-combo ROI). | **NOT MET** | No reachable source provides historical team-total or player-prop prices; 2019-2022 PBP logs support joint correlation pricing only, so every prop combo fails G6. | [flagged.html - prices absent](flagged.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/prop_inputs.csv) |

### Line origination

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R08 | Originate our own NFL spread (not a copy of the market). | **MET** | Walk-forward ensemble of three market-blind model families. Out of sample 2004-2026, 6,101 games: spread MAE 10.522 vs 10.214 for closing line. Zero market or post-kickoff inputs used. | [lines.html - accuracy table and season breakdown](lines.html) | [source](https://github.com/nflverse/nfldata/blob/9654533e5a0958726afcc076860f2c828ea0bf61/data/games.csv) |
| R09 | Originate our own total (over/under). | **MET** | Same walk-forward ensemble for totals: out-of-sample MAE 10.768 vs 10.529 for closing line across 6,101 games (2004-2026). | [lines.html - model vs close](lines.html) | [source](https://github.com/nflverse/nfldata/blob/9654533e5a0958726afcc076860f2c828ea0bf61/data/games.csv) |
| R10 | Originate our own moneyline. | **MET** | Fair home/away moneylines derived from originated margin and prior out-of-fold empirical residual lattice (retaining discrete NFL scoring mass and pushes). All 136 scheduled 2026 games carry originated spread, total and moneylines. | [lines.html - open board](lines.html) | [source](https://github.com/nflverse/nfldata/blob/9654533e5a0958726afcc076860f2c828ea0bf61/data/games.csv) |
| R11 | No look-ahead: a line for season S may use only seasons before S. | **MET** | fit_season == season for every test prediction; first franchise game starts at Elo 1500; rows strictly chronological. Verified by build_datasets.py and tests/test_no_lookahead.py. | [methodology.html - leakage controls](https://github.com/karagemop466-tech/Korea1/blob/main/tests/test_no_lookahead.py) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/build_datasets.py) |

### Signals

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R12 | Research and develop strategies that generate useful signals. | **MET** | 18 strategies pre-declared across model-edge rules, situational angles and parlay ladders; full results published transparently including losing strategies. | [strategies.html - full library with rules](strategies.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/strategies.py) |
| R13 | Single-bet strategies. | **MET** | 15 of 18 canonical strategies are single bets (7 model-edge, 8 angle rules) settled in simulation at community closing prices with pushes refunded. | [strategies.html - leaderboard](strategies.html) | [source](https://github.com/nflverse/nfldata/blob/9654533e5a0958726afcc076860f2c828ea0bf61/data/games.csv) |
| R14 | Parlays. | **MET** | Three parlay ladders using simultaneous kickoff slates and measured correlation rather than week-wide hindsight; ticket pricing remains simulated without authenticated bookmaker parlay quotes. | [strategies.html - parlay rows](strategies.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/correlations.py) |
| R15 | Player-prop bet combinations. | **PARTIAL** | Framework, model, calibration and measured correlations are published for 21,033 player-games (2019-2022 PBP blobs, SHA-256 pinned); 7 prop combinations publish measured joint vs independent probability gaps. No prop ROI is claimed because player-prop prices are absent. | [props.html and flagged.html](props.html) | [source](https://www.nfl.com/injuries/) |

### Leaderboard

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R16 | Run the project as a leaderboard competition. | **MET** | All 18 strategies ranked side by side with W-L-P, Holm adjusted p-value, provisional DSR and gate verdicts; strict public cells blank unverified community ROI. | [strategies.html - leaderboard](strategies.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/strategy_summary.csv) |
| R17 | Provide rewards for top-performing strategies. | **PARTIAL** | Four-tier reward structure defined against eight objective gates, but 0/18 strategies pass and no funded prize pool exists; prize pool published as unawarded. | [strategies.html - reward tiers and prize pool](strategies.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/strategy_gates.csv) |

### Validation

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R18 | Every strategy must pass validation gates. | **MET** | Eight fail-closed gates per strategy: data integrity, leakage, statistical power, Holm FWER significance, stationary-bootstrap + provisional DSR, economic significance (quote provenance), stability and redundancy. 0/18 pass. | [validation.html - gate-by-gate results](validation.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/validation.py) |

### Correlation

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R19 | Determine correlation values. | **MET** | Measured from settled data and 2019-2022 PBP logs: same-game cover vs ML phi, cross-game slate intervals, team-total variance split, and prop pair gaps; strict public tables keep unverified market values in research downloads. | [correlations.html - dependence tables](correlations.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/corr_same_game.csv) |

### Luck removal

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R20 | Remove luck from the equation rather than reading a raw ROI. | **MET** | White's reality check across 18 strategies over 476 weekly blocks (p = 0.463, 3,000 stationary-bootstrap draws), Holm FWER control, provisional DSR with explicit trial-count bound (>= 60), and power calculation. | [validation.html - reality check and power](validation.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/reality_check.json) |
| R21 | Build strategies that are selectively skill-based, and say so when they are not. | **MET** | Fail-closed verdicts label every entrant UNVERIFIED (18/18) and 0 SKILL; verifier blocks publishing any SKILL label if a gate fails. | [validation.html - verdicts](validation.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/strategy_gates.csv) |

### Reporting

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R22 | Executive summary outlining the important details. | **MET** | EXECUTIVE_SUMMARY.md and executive-summary.html are both rendered directly from pipeline CSV outputs so headline verdicts and counts cannot drift. | [executive-summary.html](executive-summary.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/EXECUTIVE_SUMMARY.md) |

### Automation

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R23 | No manual input: the owner should not have to supply anything. | **MET** | make build runs pinned fetch checks, dataset build, models, backtest, validation, correlations, props, injuries/depth, summary/requirements and site verification deterministically. | [verification.html - claims audit](verification.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/Makefile) |

### Sourcing

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R24 | Every table row must carry a link to an official source. | **MET** | Enforced automatically by verify_site.py V1 (allowlisted official/primary/document URLs on every tbody row) and tests/check_sources.py across all published pages including verification.html. | [sources.html - where each number comes from](sources.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/tests/check_sources.py) |
| R25 | If a value cannot be confirmed, leave it blank and flag it as unverified. | **MET** | Unauthenticated market ROI/win-rates, prop prices, team-total lines, HOU image-only depth strings and unlisted reserves render blank and are listed on flagged.html. | [flagged.html](flagged.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/render_site.py) |
| R26 | Flag irregularities for manual review. | **MET** | flagged.html logs every retrieval failure, HOU image-only depth chart, 5 stale nfldata Week 10 QBs, 3 2015 closing-file outcome conflicts, weather exclusions and prior code/doc repairs with source links. | [flagged.html](flagged.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/settlement_crosscheck.csv) |

### Delivery

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R27 | Publish a live GitHub Pages site for the repository. | **MET** | GitHub Pages builds from main / and is live; post-merge status and fetched live URLs are recorded in COORDINATION.md. | [index.html (live site)](index.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/README.md) |
| R28 | Clean landing page. | **MET** | index.html provides a clean dashboard with headline KPIs, decision status, Week 10 injury/depth highlights, pre-decision Q&A/suggestions links and category cards. | [index.html](index.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/assets/style.css) |
| R29 | Subpages organised by category. | **MET** | 16 root pages (dashboard, exec summary, lines, injuries & depth, leaderboard, validation, correlations, props, Q&A & gaps, suggestions, methodology, requirements, flagged, sources, audit, verification) plus 9-page lab/ annex. | [index.html - navigation](requirements.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/render_site.py) |
| R30 | Clean, simple, user-friendly dashboard UI. | **MET** | Completed missing CSS rules for hero, status dots, filters, blank indicators, skip-links and responsive wrapped navigation with zero external CDNs or JS frameworks. | [index.html](index.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/assets/style.css) |
| R31 | All entries and findings in simple, readable tables. | **MET** | Every page presents captioned, searchable/sortable HTML tables with explicit units, status pills and per-row source links. | [strategies.html - leaderboard tables](strategies.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/render_site.py) |
| R32 | Include the analysis and findings, not just data. | **MET** | Each page explains the decision takeaway, statistical caveats and operational meaning alongside the tables and research/ notes. | [executive-summary.html - findings](executive-summary.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/research/02-methodology.md) |

### Verification

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R33 | The site must build with no broken links. | **MET** | pipeline/verify_site.py V1-V6 and tests/check_links.py check every internal href, anchor and asset across all 16 root pages and 9 annex pages. | [verification.html](verification.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/tests/check_links.py) |
| R34 | Verify line by line, and be able to reproduce every artefact from the pinned source. | **MET** | pipeline/audit.py runs provenance re-hash (7/7), derived digests, clean-room rebuild including injuries.py, drift check and re-aligned strict HTML-to-CSV claim verification. | [verification.html - rebuild and claims audit](verification.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/audit.py) |
| R42 | Independently replicate the headline findings. | **MET** | Independent 2011-2021 Sportsbook Review annex under lab/ reproduces all four headline findings with zero verified profitable strategies. | [lab/index.html - replication annex](lab/index.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/research/05-annex-executive-summary.md) |

### Publish

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R35 | Open a pull request from the integration branch with a summary, the sources used and the flagged irregularities. | **MET** | PR from current active branch arena/f115e6a2-korea1 to main records all changed deliverables, verified 2026-11-12 sources and flagged gaps. | [COORDINATION.md - deploy record](COORDINATION.md) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/COORDINATION.md) |
| R36 | Merge without waiting for review, and do not merge a broken site. | **MET** | Merge gated on CI verify (make build, make test, check_rebuild.py) and audit passing cleanly, then merged without approval wait. | [COORDINATION.md - deploy record](COORDINATION.md) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/COORDINATION.md) |
| R37 | Confirm GitHub Pages deploys successfully after the merge. | **MET** | Pages API polled until built for the merge commit and live rendered pages fetched to confirm deployment. | [verification.html - deploy evidence](verification.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/COORDINATION.md) |
| R38 | Publish flagged irregularities and unverified items on a clearly labelled page with source links. | **MET** | flagged.html is in primary navigation and lists every unverified input, retrieval failure, stale QB mismatch and conflict with source links. | [flagged.html](flagged.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/render_site.py) |

### Documentation

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R39 | Document the methodology so a reader can audit the reasoning, not only the result. | **MET** | methodology.html documents dataflow, corrected feature dictionary (temp_missing/wind_missing aligned), leakage controls and eight validation gates. | [methodology.html](methodology.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/research/02-methodology.md) |

### Suggestions

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R43 | Provide a dedicated improvement-suggestions section with options and trade-offs for review before changes are made. | **MET** | suggestions.html presents concrete Option A/B/C paths across data egress, injury modeling, features, strategy governance, UI and hygiene, each marked Proposed - awaiting selection. | [suggestions.html](suggestions.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/render_site.py) |

### Decision readiness

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R44 | List clear pre-decision questions, known vs. unknown inventory, grounded answers and missing-information discovery plans. | **MET** | questions.html inventories Known vs. Unknown data, answers 14 decision-blocking questions honestly, and provides concrete legal discovery steps for every missing input. | [questions.html](questions.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/render_site.py) |

### Injuries & Depth

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R45 | Track injuries and 1st-4th string backup depth deficiencies across both Offense and Defense. | **PARTIAL** | injuries.html and pipeline/injuries.py verify 2026 Week 10 NFL.com injuries/IR and 27/28 club Offense/Defense 1st-4th string depth charts (HOU image-only blank; 5 stale nfldata QBs flagged), plus strictly no-lookahead historical QB/PBP absence research; historical weekly inactive & depth archives remain missing. | [injuries.html](injuries.html) | [source](https://www.nfl.com/injuries/) |

### Audit & Hygiene

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R46 | Resolve repo code/CSS/verifier/audit contradictions found during line-by-line review. | **MET** | Repaired missing CSS classes in assets/style.css, updated pipeline/audit.py claims to match strict site tables, fixed FEATURE_DICT and models.py docstrings, fixed prop_inputs.csv in correlations.py, added verification.html to check_sources.py, and removed orphaned weather_fill.json. | [flagged.html and verification.html](verification.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/audit.py) |

## What is not satisfied

| # | Requirement | Status | Why |
|---|---|---|---|
| R06 | Use official, verified, trusted sources only - nothing scraped from an unverifiable feed. | PARTIAL | Official NFL.com scores (59/59 MATCH across 2026 W8-W9 + sample seasons), Week 10 injuries, and 27/28 Week 10 official club depth charts are verified; historical odds/lines still rely on a pinned community mirror (nflverse/nfldata@9654533e) lacking authenticated sportsbook timestamps. |
| R15 | Player-prop bet combinations. | PARTIAL | Framework, model, calibration and measured correlations are published for 21,033 player-games (2019-2022 PBP blobs, SHA-256 pinned); 7 prop combinations publish measured joint vs independent probability gaps. No prop ROI is claimed because player-prop prices are absent. |
| R17 | Provide rewards for top-performing strategies. | PARTIAL | Four-tier reward structure defined against eight objective gates, but 0/18 strategies pass and no funded prize pool exists; prize pool published as unawarded. |
| R40 | State how current the data is, and what changed upstream since the snapshot. | PARTIAL | Pinned upstream snapshot refreshed to 2026-11-12 commit 9654533e with 59/59 NFL.com score matches across Weeks 8-9 and historical samples; Week 10 scheduled QB mismatches are flagged and audit_drift tracks upstream HEAD. |
| R41 | Team-total and player-prop prices (needed for prop-combo ROI). | NOT MET | No reachable source provides historical team-total or player-prop prices; 2019-2022 PBP logs support joint correlation pricing only, so every prop combo fails G6. |
| R45 | Track injuries and 1st-4th string backup depth deficiencies across both Offense and Defense. | PARTIAL | injuries.html and pipeline/injuries.py verify 2026 Week 10 NFL.com injuries/IR and 27/28 club Offense/Defense 1st-4th string depth charts (HOU image-only blank; 5 stale nfldata QBs flagged), plus strictly no-lookahead historical QB/PBP absence research; historical weekly inactive & depth archives remain missing. |

None of these block publication: each is disclosed on the site, with the reason and what
would unblock it, on the [Flagged for review](flagged.html) page.
