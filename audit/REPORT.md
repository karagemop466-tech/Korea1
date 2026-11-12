# Final integration audit — 2026-11-02

Session: `arena/ed58af62-korea1`.

## Scope and method

This was a targeted line-by-line review of the active canonical pipeline, shared helpers, strategy
settlement, validation, correlation code, site renderer, source checkers, workflows and build commands,
plus a claim/provenance review of the preserved sibling and replication implementations. It was not a
claim to authenticate every historical third-party observation. Historical implementations remain in
the repository; their public annex now uses the same strict-source display policy.

Reviewed canonical files: `pipeline/common.py`, `fetch_data.py`, `build_datasets.py`, `models.py`,
`strategies.py`, `backtest.py`, `validation.py`, `stats_tools.py`, `correlations.py`, `render_site.py`,
`render_summary.py`, `render_audit.py`, `verify_site.py`; `assets/app.js`, `assets/style.css`;
`tests/check_links.py`, `tests/check_sources.py`, `tests/test_no_lookahead.py`; `Makefile`,
`requirements.txt`, `.github/workflows/verify.yml`, `.github/workflows/pages.yml`.
Reviewed annex entry points and verification: `scripts/run_all.sh`, `scripts/00_ingest.py`,
`scripts/02_line_model.py`–`08_leaderboard.py`, `scripts/98_linkcheck.py`, `scripts/99_verify.py`,
`scripts/lib/common.py`, `scripts/lib/data.py`, `scripts/tests/test_math.py`, and the preserved
`analysis/` feature/model path exercised by its regression tests.

## Material findings and disposition

| ID | Finding | Disposition |
|---|---|---|
| F-01 | Normal fetch resolved moving upstream master despite a published pin | Default reads committed SHA; explicit `--refresh-pin` required; staged hashes checked |
| F-02 | Missing weather filled using full-history median | No observed-field fill; weather/roof excluded from default features |
| F-03 | Model and market MAE used different samples | Per-market paired samples and paired gap |
| F-04 | Whole-week parlay selection used later-game information | Earliest eligible simultaneous kickoff slate; still research-only |
| F-05 | Leakage gate hard-coded; fixed bet count called power; final verdict omitted redundancy | Executed checks, weekly power, all eight gates in verdict |
| F-06 | Bet-level iid inference and unaligned reality-check weeks | Weekly centered stationary bootstrap; Holm; common calendar with no-bet zeros |
| F-07 | DSR treated limited library count as complete search history | Provisional DSR, documented lower bound, no validation without complete registry |
| F-08 | Normal continuity correction claimed to price key numbers correctly | Prior out-of-fold empirical errors on integer-score lattice; calibration still unverified |
| F-09 | Theoretical overround formula distorted prices | Correct multiplicative decimal overround; invalid American prices rejected |
| F-10 | Road-favourite comment contradicted selection | Sign convention documented and selection-side regression test |
| F-11 | Source checker accepted any external URL as official | Host allowlist and row-level official/primary reference enforcement |
| F-12 | Community market values displayed as verified findings | Strict public values blank; historical calculations segregated and labelled |
| F-13 | Prop prices and joint SGP quotes unavailable | No prop ROI or invented correlation; framework and missing-input register |
| F-14 | Three 2015 closing-file outcome flags conflict with scores | NFL.com Game Center re-read; score file agrees; price-file flags remain flagged |
| F-15 | Annex fresh-checkout reference check previously failed | Existing API-based repair retained; annex checks re-run |
| F-16 | Build messages/workflow referenced wrong publication directory | Root publication path and dependency install corrected |

## Official / primary review

The official score sample contains 39 rows: 31 present dataset scores match NFL.com, zero mismatch,
and eight pinned week-8 2026 scores are blank while NFL.com shows Final. The sample is not a census.
Direct row links are in `data/audit/nfl_com_score_audit.csv` and `audit.html`.

Primary method references were read through the Econometric Society (White 2000), Portfolio Management
Research (Bailey/López de Prado 2014), Taylor & Francis records (Politis/Romano 1994; Hansen 2005),
and Tel Aviv University's Benjamini/Hochberg record. FanDuel's own push-settlement help page was read;
it is an operator example, not universal house rules. NFL rulebook, schedule and injury pages were read.
GitHub Pages documentation was read. Failed regulator PDF fetches were not used as verified numeric evidence.

## Remaining limitations

No authenticated historical executable quote archive; community player statistics and research prop lines are integrated, but no verified prop-price/SGP archive; incomplete
trial history; partial official score coverage; no verified pregame availability timestamps for historical
weather/roof; no untouched prospective replication. These block validation and rewards, not publication
of a transparent research dashboard.

## Verification record

Commands: `make build`, `make test`, `make audit`, `tests/check_rebuild.py`, `scripts/99_verify.py`,
`scripts/98_linkcheck.py`, `scripts/tests/test_math.py`, and the preserved `tests/test_no_lookahead.py`.
Machine-readable canonical results: `data/processed/verification_report.csv`, `verification_data.csv`,
and `audit_*.csv`.

## 2026-11-12 follow-up (`T14`, session `arena/f115e6a2-korea1`)

- Refreshed `nflverse/nfldata` pin to `9654533e5a0958726afcc076860f2c828ea0bf61`; verified all 29 settled
  Week 8–9 games against NFL.com (`59/59 MATCH`, 0 blanks/mismatches in `data/audit/nfl_com_score_audit.csv`).
- Audited Week 10 2026 official NFL.com injuries/IR/trades and 27/28 official club HTML depth charts
  (`houstontexans.com/team/depth-chart` flagged `UNVERIFIED_IMAGE_ONLY`, depth cells strictly blank), catching
  5 stale `nfldata` Week 10 QB fields (`MIN`, `MIA`, `ARI`, `SEA`, `BAL`).
- Added `pipeline/injuries.py` & `injuries.html` covering 2026 Week 10 O/D 1st–4th string cascades plus
  no-lookahead 2006–2026 QB-continuity and 2019–2022 PBP starter-absence diagnostics (research estimate only).
- Added `questions.html` (Known vs. Unknown, 14 pre-decision Q&As, Missing-Data Discovery Plan) and
  `suggestions.html` (Option A/B/C improvement tracks strictly labelled `Proposed — awaiting selection`).
- Fixed repo hygiene & code/audit irregularities: removed orphaned `data/processed/weather_fill.json`,
  completed missing CSS rules in `assets/style.css`, unified 46-row `requirements/requirements.csv` across
  `REQUIREMENTS.md` and `requirements.html`, repaired `FEATURE_DICT`/`models.py` docstrings and
  `correlations.py` `prop_inputs.csv`, expanded `tests/check_sources.py` to include `verification.html`,
  and re-aligned `pipeline/audit.py` clean-room rebuild and claim checks after merging
  `origin/main` (`f7b17eb`, PRs #22/#23/#25/#26/#27/#28/#29/#31: `decisions.html`, `lineups.html`,
  `availability.html`, `decision-board.html`, `open-questions.html`, `DECISIONS.md`,
  `official-monitor.yml`, `availability.yml`, 21 root + 9 annex pages, `57` pytest tests passing).

