# Requirements traceability — NFL Line Lab

Every requirement in the brief, one row each, with the artefact that satisfies it and a source
link. Generated from [`requirements/requirements.csv`](requirements/requirements.csv) by
`pipeline/render_requirements.py`; the same data renders as
[`requirements.html`](https://karagemop466-tech.github.io/Korea1/requirements.html).

**Status vocabulary** — `MET`: a published artefact proves it. `PARTIAL`: the work exists but a
stated limitation applies. `FLAGGED`: blocked or unverified, published on the
[Flagged for review](https://karagemop466-tech.github.io/Korea1/flagged.html) page.
`NOT MET`: nothing was delivered and nothing was invented to cover the gap.

**42 requirements** — 38 MET · 3 PARTIAL · 0 FLAGGED · 1 NOT MET

## Coverage by area

| Area | Requirements | MET | PARTIAL | FLAGGED / NOT MET |
|---|---|---|---|---|
| Governance | 3 | 3 | 0 | 0 |
| Requirements | 2 | 2 | 0 | 0 |
| Data | 4 | 2 | 1 | 1 |
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

## The list

### Governance

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R01 | Keep a shared task board that lists every task, its status, its owner and the files it touches, and claim work before starting it. | **MET** | COORDINATION.md is the board: tasks T0-T9 and F1-F5 with status, owner and file scope; the F-claims were committed and pushed before any file in scope was touched. Two collision batches by earlier sessions and this session's own claim are recorded, not hidden. | [COORDINATION.md (task board + log)](COORDINATION.md) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/COORDINATION.md) |
| R02 | Never start a task another session has claimed; keep scopes non-overlapping; log cross-scope edits instead of silently making them. | **MET** | Every file this session edits is inside its claimed scope except one logged repair: pipeline/models.py, which carries the D-01 defect found by this session's audit (its owner finished and merged before this session began). The repair, its reason and its verification are recorded in COORDINATION.md. | [COORDINATION.md - cross-scope repairs](COORDINATION.md) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/COORDINATION.md) |
| R03 | Coordinate parallel sessions: record collisions, never discard another session's work. | **MET** | Collision notice plus a conflict-resolution table record five+two merge conflicts and how each was resolved (no branch reverted, rebased away or force-pushed). A fourth build from a parallel session is republished as a replication annex rather than deleted. | [COORDINATION.md - collision notice and merge log](COORDINATION.md) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/COORDINATION.md) |

### Requirements

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R04 | Collect a full list of requirements. | **MET** | This page. 42 requirements extracted line by line from the brief, each with an ID, a status, the evidence that satisfies it and a source link. | [REQUIREMENTS.md / requirements.html](requirements.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/REQUIREMENTS.md) |
| R05 | Organize and analyse the work against that requirement list. | **MET** | requirements.html groups the 42 requirements by area with a roll-up count per status, and every row links to the page or file that carries the evidence. Nothing is marked MET without an artefact behind it. | [requirements.html (roll-up table)](requirements.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/requirements/requirements.csv) |

### Data

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R06 | Use official, verified, trusted sources only - nothing scraped from an unverifiable feed. | **MET** | One pinned commit of nflverse/nfldata (the maintained open mirror of the NFL GSIS game tables) plus the official NFL rulebook for rules references. Seven files, each SHA-256 hashed on arrival into data/sources.json; the audit re-fetches that commit and re-hashes 7/7. | [sources.html - pinned input files with hashes](sources.html) | [source](https://github.com/nflverse/nfldata/blob/a270278f3ac4e937295fe6a27814b3c4a2b62645/data/games.csv) |
| R07 | Never infer, interpolate or back-fill a missing value. | **MET** | A missing value renders as an em dash and is listed on the flagged page. pipeline/verify_site.py check V3 fails the build if an unformatted missing value reaches a table cell, and tests/check_sources.py requires an unverified marker when a cell is blank. | [flagged.html - blank and unverified items](flagged.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/verify_site.py) |
| R40 | State how current the data is, and what changed upstream since the snapshot. | **PARTIAL** | Every number is tied to one pinned commit (2026-11-01) and the site says so in every footer. The audit measures the drift against upstream HEAD, including the twelve 2026 Week 8 games that were settled upstream after the pin. The canonical numbers are deliberately not refreshed mid-session, so the site is reproducible rather than current. | [verification.html - upstream drift](verification.html) | [source](https://github.com/nflverse/nfldata/commits/master) |
| R41 | Team-total and player-prop prices (needed for prop-combo ROI). | **NOT MET** | No reachable source carries team-total or player-prop prices. The four seasons of play-by-play now ingested (2019-2022) supply player outcomes but not prices, so nothing is proxied or estimated: the prop page publishes the framework and the measured structure only, every combo fails G6, and the gap is flagged. | [flagged.html - prices absent](flagged.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/prop_inputs.csv) |

### Line origination

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R08 | Originate our own NFL spread (not a copy of the market). | **MET** | Walk-forward ensemble of three market-blind model families. Out of sample 2004-2026, 6,073 games: spread MAE 10.527 against the closing line's 10.215. The model never sees a price and never sees a post-kickoff field. | [lines.html - accuracy table and season breakdown](lines.html) | [source](https://github.com/nflverse/nfldata/blob/a270278f3ac4e937295fe6a27814b3c4a2b62645/data/games.csv) |
| R09 | Originate our own total (over/under). | **MET** | Same ensemble, total market: MAE 10.727 against 10.527 for the close. Published per season and per game on the lines page. | [lines.html - model vs close](lines.html) | [source](https://github.com/nflverse/nfldata/blob/a270278f3ac4e937295fe6a27814b3c4a2b62645/data/games.csv) |
| R10 | Originate our own moneyline. | **MET** | Fair home/away prices are derived from the originated margin and its residual sigma (normal approximation, pushes carried explicitly). After defect D-01 was fixed this session, all 164 scheduled games carry an originated spread, total and both moneyline prices. | [lines.html - open board (our fair home/away ML)](lines.html) | [source](https://github.com/nflverse/nfldata/blob/a270278f3ac4e937295fe6a27814b3c4a2b62645/data/games.csv) |
| R11 | No look-ahead: a line for season S may use only seasons before S. | **MET** | fit_season == season for every published line; the first appearance of a franchise starts at Elo 1500; rows are strictly chronological. Asserted in code (build_datasets.py) and tested by tests/test_no_lookahead.py. | [methodology.html - leakage controls](https://github.com/karagemop466-tech/Korea1/blob/main/tests/test_no_lookahead.py) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/build_datasets.py) |

### Signals

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R12 | Research and develop strategies that generate useful signals. | **MET** | 18 strategies declared before any was run, in three families: model-edge rules, classic angle rules and parlay ladders. Research notes cover market structure, methodology and competition design. Every result is published, including the failures. | [strategies.html - full library with rules](strategies.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/strategies.py) |
| R13 | Single-bet strategies. | **MET** | 15 of the 18 strategies are single bets (7 model-edge rules, 8 angle rules), staked one unit at the recorded closing price with pushes refunded. | [strategies.html - leaderboard](strategies.html) | [source](https://github.com/nflverse/nfldata/blob/a270278f3ac4e937295fe6a27814b3c4a2b62645/data/games.csv) |
| R14 | Parlays. | **MET** | Three parlay strategies: 2-leg and 3-leg ladders built from the largest model edges, plus a cross-game combination. Correlation is measured, not assumed, before any parlay is priced. | [strategies.html - parlay rows](strategies.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/correlations.py) |
| R15 | Player-prop bet combinations. | **PARTIAL** | Framework, model, calibration and measured correlations are published for 21,033 player-games (play-by-play 2019-2022, pinned by blob SHA + SHA-256); seven prop combinations carry a verdict and a measured joint-versus-independent price gap. No prop ROI or combo award is claimed because no reachable source carries player-prop prices, so the economic gate (G6) fails for every combo. Prices are the gap, not the model, and the gap is on the flagged page. | [props.html and flagged.html - framework + 7 priced combos, no ROI](props.html) | [source](https://github.com/nflverse/nflverse-data/releases/tag/player_stats) |

### Leaderboard

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R16 | Run the project as a leaderboard competition. | **MET** | Every strategy is ranked by ROI at closing prices, with win rate, units, FDR-adjusted p and deflated Sharpe beside it. A full season-by-season record is published for each entrant. | [strategies.html - leaderboard](strategies.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/strategy_summary.csv) |
| R17 | Provide rewards for top-performing strategies. | **PARTIAL** | A four-tier reward split is defined (60% / 25% / 15% / nothing) against objective gate criteria, but no strategy qualifies for any tier that pays, so the prize pool is published as unawarded rather than paid to the luckiest result. | [strategies.html - reward tiers and prize pool](strategies.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/strategy_gates.csv) |

### Validation

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R18 | Every strategy must pass validation gates. | **MET** | Eight gates per strategy: data integrity, leakage, statistical power, significance with Benjamini-Hochberg FDR, bootstrap plus deflated Sharpe, economic significance, stability, redundancy. 0 of 18 strategies pass all eight; the gate-by-gate matrix is published for every one. | [validation.html - gate-by-gate results](validation.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/validation.py) |

### Correlation

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R19 | Determine correlation values. | **MET** | Measured from the settlement data, not imported: same-game cover vs moneyline phi = 0.676, cover vs total phi = 0.024, over vs moneyline phi = 0.008; cross-game margin r = 0.011 and total r = 0.008 with intervals spanning zero; team-total dependence published too. | [correlations.html - dependence tables](correlations.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/corr_same_game.csv) |

### Luck removal

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R20 | Remove luck from the equation rather than reading a raw ROI. | **MET** | White's reality check over the whole library (p = 0.144, 18 strategies, 425 weekly blocks), bootstrap intervals, deflated Sharpe ratio, FDR control and a power calculation (about 78,000 bets needed to detect a 1% edge at 80% power). | [validation.html - reality check and power](validation.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/reality_check.json) |
| R21 | Build strategies that are selectively skill-based, and say so when they are not. | **MET** | Every strategy carries a verdict - LUCK (8), NO EDGE (10), SKILL (0) - and a verifier refuses to publish SKILL for a strategy that failed a gate. The honest headline is that nothing cleared the bar. | [validation.html - verdicts](validation.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/strategy_gates.csv) |

### Reporting

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R22 | Executive summary outlining the important details. | **MET** | EXECUTIVE_SUMMARY.md is generated from the same tables the site uses (so it cannot drift), and executive-summary.html renders it with the KPI cards, key numbers and verification table. | [executive-summary.html](executive-summary.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/EXECUTIVE_SUMMARY.md) |

### Automation

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R23 | No manual input: the owner should not have to supply anything. | **MET** | make build fetches the pinned snapshot, builds the datasets, fits the models, settles the bets, runs the gates, measures correlations, renders the site and verifies it, with no hand-entered value. The audit re-derives every published cell (58/58) from the CSVs, which is the evidence that no number was typed in. | [verification.html - claims audit](verification.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/Makefile) |

### Sourcing

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R24 | Every table row must carry a link to an official source. | **MET** | Enforced twice: pipeline/verify_site.py V1 (every tbody row must contain a source href, failing the build otherwise) and tests/check_sources.py, which walks every table on the published pages. Both pass on the current build. | [sources.html - where each number comes from](sources.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/tests/check_sources.py) |
| R25 | If a value cannot be confirmed, leave it blank and flag it as unverified. | **MET** | Player-level cells, team-total prices, prop prices and multi-season openers are blank by design and listed on the flagged page with the reason and a source link. No placeholder or estimate is published. | [flagged.html](flagged.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/render_site.py) |
| R26 | Flag irregularities for manual review. | **MET** | The flagged page lists twelve items (retrieval failures, partial coverage, file disagreements, three 2015 games whose outcome flags contradict their score, the weather assumption, snapshot drift, and the model's blind spots), each with a source link and what would unblock it. | [flagged.html](flagged.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/data/processed/settlement_crosscheck.csv) |

### Delivery

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R27 | Publish a live GitHub Pages site for the repository. | **MET** | Pages is a branch build of main at / (verified against the Pages API). The site is live at the project URL and the build for the merged commit reports status built. | [index.html (live site)](index.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main#readme) |
| R28 | Clean landing page. | **MET** | index.html is a single-screen dashboard: headline KPIs, the one-question framing, five category cards and the current verdict, with no framework, no CDN and no external asset. | [index.html](index.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/assets/style.css) |
| R29 | Subpages organised by category. | **MET** | Thirteen root pages - dashboard, executive summary, originated lines, leaderboard, validation gates, correlations, player props, methodology, flagged for review, sources, requirements, verification and the reproducibility audit - plus a nine-page replication annex under lab/. | [index.html - category cards](requirements.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/render_site.py) |
| R30 | Clean, simple, user-friendly dashboard UI. | **MET** | One stylesheet, no JavaScript framework, tables that scroll on narrow screens, consistent navigation on every page, and a footer naming the pinned snapshot on each one. | [index.html](index.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/assets/style.css) |
| R31 | All entries and findings in simple, readable tables. | **MET** | Every page presents its findings as captioned tables: leaderboard, gates, correlations, provenance, flagged items, requirement traceability and the audit itself. Each table is captioned and each row cites its source. | [strategies.html - leaderboard tables](strategies.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/render_site.py) |
| R32 | Include the analysis and findings, not just data. | **MET** | Each page carries a written finding and the numbers that support it (the market is still better than the model; nothing survives validation; correlation is measurable and asymmetric; power is the binding constraint), plus research/ notes for the long form. | [executive-summary.html - findings](executive-summary.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/research/02-methodology.md) |

### Verification

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R33 | The site must build with no broken links. | **MET** | pipeline/verify_site.py runs six checks per page and exits non-zero on failure; tests/check_links.py resolves every internal href, anchor and asset across the root site and the annex; both pass on this build. | [verification.html](verification.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/tests/check_links.py) |
| R34 | Verify line by line, and be able to reproduce every artefact from the pinned source. | **MET** | Clean-room rebuild from the pinned archive reproduces every derived table and every rendered page byte-for-byte (the generated-timestamp footer is the only normalised field). Provenance re-hash 7/7, artefact digest 50/50, published-cell re-derivation 61/61. | [verification.html - rebuild and claims audit](verification.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/audit.py) |
| R42 | Independently replicate the headline findings. | **MET** | A second build from a different odds archive (Sportsbook Review ten-year, 2011-2021) with different code reproduces four headline findings: no strategy passes every gate, the originated line does not beat the close, apparent edge is mostly luck, and CLV rather than ROI carries the skill signal. | [lab/index.html - replication annex](lab/index.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/research/05-annex-executive-summary.md) |

### Publish

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R35 | Open a pull request from the integration branch with a summary, the sources used and the flagged irregularities. | **MET** | This session's pull request from arena/fb363967-korea1 to main carries the change summary, the source list and the irregularity list; the PR number and merge result are recorded in COORDINATION.md. | [COORDINATION.md - deploy record](COORDINATION.md) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/COORDINATION.md) |
| R36 | Merge without waiting for review, and do not merge a broken site. | **MET** | Merge is gated on the audit and the site verifiers passing, then performed without an approval wait. The deploy record names the merge commit and the Pages build status for it. | [COORDINATION.md - deploy record](COORDINATION.md) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/COORDINATION.md) |
| R37 | Confirm GitHub Pages deploys successfully after the merge. | **MET** | The Pages build for the merge commit is polled until it reports built, and the live URLs are fetched and read back to confirm the published content matches the build. | [verification.html - deploy evidence](verification.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/COORDINATION.md) |
| R38 | Publish flagged irregularities and unverified items on a clearly labelled page with source links. | **MET** | flagged.html is labelled Flagged for review, is in the main navigation, and every item carries a source link plus what would unblock it. Unverified items do not block the merge. | [flagged.html](flagged.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/pipeline/render_site.py) |

### Documentation

| # | Requirement | Status | How it is met | Evidence | Source |
|---|---|---|---|---|---|
| R39 | Document the methodology so a reader can audit the reasoning, not only the result. | **MET** | methodology.html carries the dataflow, the feature dictionary, the leakage controls, the gate definitions and the data-integrity checks; research/ carries the long-form notes. | [methodology.html](methodology.html) | [source](https://github.com/karagemop466-tech/Korea1/blob/main/research/02-methodology.md) |

## What is not satisfied

| # | Requirement | Status | Why |
|---|---|---|---|
| R15 | Player-prop bet combinations. | PARTIAL | Framework, model, calibration and measured correlations are published for 21,033 player-games (play-by-play 2019-2022, pinned by blob SHA + SHA-256); seven prop combinations carry a verdict and a measured joint-versus-independent price gap. No prop ROI or combo award is claimed because no reachable source carries player-prop prices, so the economic gate (G6) fails for every combo. Prices are the gap, not the model, and the gap is on the flagged page. |
| R17 | Provide rewards for top-performing strategies. | PARTIAL | A four-tier reward split is defined (60% / 25% / 15% / nothing) against objective gate criteria, but no strategy qualifies for any tier that pays, so the prize pool is published as unawarded rather than paid to the luckiest result. |
| R40 | State how current the data is, and what changed upstream since the snapshot. | PARTIAL | Every number is tied to one pinned commit (2026-11-01) and the site says so in every footer. The audit measures the drift against upstream HEAD, including the twelve 2026 Week 8 games that were settled upstream after the pin. The canonical numbers are deliberately not refreshed mid-session, so the site is reproducible rather than current. |
| R41 | Team-total and player-prop prices (needed for prop-combo ROI). | NOT MET | No reachable source carries team-total or player-prop prices. The four seasons of play-by-play now ingested (2019-2022) supply player outcomes but not prices, so nothing is proxied or estimated: the prop page publishes the framework and the measured structure only, every combo fails G6, and the gap is flagged. |

None of these block publication: each is disclosed on the site, with the reason and what
would unblock it, on the [Flagged for review](flagged.html) page.
