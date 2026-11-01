# Coordination board

This repository started with only an 8-byte `README.md`; no prior task board or parallel-session claims were present.

## Tasks

| Task | Status | Owner/session ID | File scope |
|---|---|---|---|
| NFL methodology research, evidence-backed findings, dashboard/site, and final integration | in progress | `arena/bc2ac83d-korea1` | `COORDINATION.md`, `README.md`, `.github/workflows/pages.yml`, `.nojekyll`, `assets/`, `data/`, `docs/`, root dashboard pages, `scripts/` |

## Session constraints

Arena fixes this session to branch `arena/bc2ac83d-korea1`; work remains on that branch rather than creating the requested `session-<id>/<task>` branch. Initial task claim was committed as `fb9a0ec` and pushed to this branch. First pull attempt could not find a remote branch because there was no upstream yet; rebasing on `origin/main` and setting the fixed branch upstream succeeded. No other claims existed at task start.

## Source review and verification log

- **NFL passing stats:** [NFL.com official 2025 player passing view](https://www.nfl.com/stats/player-stats/category/passing/2025/reg/all/passingyards/desc) opened; page heading and passing category/fields reviewed.
- **NFL rushing stats:** [NFL.com official 2025 player rushing view](https://www.nfl.com/stats/player-stats/category/rushing/2025/reg/all/rushingyards/desc) opened; page heading and rushing category reviewed.
- **NFL receiving stats:** [NFL.com official 2025 player receiving view](https://www.nfl.com/stats/player-stats/category/receiving/2025/reg/all/receivingreceptions/desc) opened; page heading, reception/rushing/receiving fields reviewed.
- **NFL team scoring:** [NFL.com official 2025 team scoring view](https://www.nfl.com/stats/team-stats/offense/scoring/2025/reg/all) opened; scoring category and fields reviewed.
- **Next Gen Stats:** [NFL Next Gen Stats passing page](https://nextgenstats.nfl.com/stats/passing/2025/REG/3) opened; official description and published passing metrics reviewed. [NFL Football Operations tracking overview](https://operations.nfl.com/game-operations-logistics/technology/performance-tracking-data-next-gen-stats) opened; public overview describes tracked fields but does not establish rights/access for every raw field.
- **NFL analytics competition context:** [NFL Football Operations Big Data Bowl](https://operations.nfl.com/programs-initiatives/innovation/big-data-bowl) opened across both content chunks; contest structure and public prediction leaderboard description reviewed. It is cited as competition design context, not betting-performance evidence.
- **Rules:** [2025 Official NFL Playing Rules PDF](https://media.nfl.com/content/dam/communications/Official%20Playing%20Rules/2025%20Official%20Playing%20Rules.pdf) opened; season, timing/scoring/overtime scope reviewed. This does not verify 2026 rules.
- **Calibration:** [scikit-learn probability calibration documentation](https://scikit-learn.org/stable/auto_examples/calibration/plot_calibration_curve.html) opened across chunks; reliability plots, proper scores and synthetic-example caveat reviewed.
- **Correlation:** [NIST/SEMATECH Engineering Statistics Handbook glossary](https://www.itl.nist.gov/div898/handbook/glossary.htm) opened; correlation definition/range reviewed. It supplies no NFL wager coefficient.
- **Multiplicity:** [Benjamini & Hochberg (1995), Oxford Academic](https://academic.oup.com/jrsssb/article/57/1/289/7035855) publisher landing page opened; paper title and journal/publisher record reviewed. The linked PDF is the publisher-hosted paper.
- Research findings, source limitations, and line-by-line source scope are recorded in `data/strategy-data.json`, `README.md`, `docs/executive-summary.md`, and the Sources/Flagged pages. NFL source views are explicitly labeled 2025 rather than represented as live/current data.

## Results and irregularities

- Candidate register covers straight bets, totals, player yardage/scoring props, parlays and prop combos. Each data-driven table record carries one or more source IDs resolved to direct HTTPS links. These references support data categories or methods only; they do not verify a wagering edge.
- Strategy, correlation, validation, leaderboard and reward metrics are not presented as observed results. Correlation/empirical fields remain blank where no dataset was available. Validation statuses remain untested/blocked.
- Flagged for Review page captures: (1) no odds or executable-price source; (2) no joined historical outcomes/settled bets; (3) NGS access/licensing unknown; (4) only 2025 rules checked; (5) no paired data/correlation values; (6) no funded rewards or entrants.
- Leaderboard awards are only a proposed non-cash badge/featured-placement design subject to gates; no money, winner or completed contest is claimed.
- No local data or odds were added; no real-money betting or automated picks are implemented.

## Build / deployment status

- Local/offline structural verification: `python3 scripts/verify_site.py` passed (8 root HTML pages, source links resolved structurally, all data records source-backed; external-link checking was done separately through page review).
- JavaScript syntax: `node --check assets/app.js` passed.
- JSON parsing: `python3 -m json.tool data/strategy-data.json` passed.
- Whitespace check: `git diff --check` passed at last run.
- Preview server is running on port 8000 for visual review. GitHub Pages workflow exists; publication/PR/merge status will be added after deployment is confirmed.
- Concurrent integration conflict discovered after PR #4 was opened: `origin/main` advanced to `fc069fb` by merged PR #3 from `arena/7eec67cb-korea1`. Main now has its own `COORDINATION.md`, README, root `index.md`, and `.github/workflows/pages.yml`; PR #4 is marked `dirty`/conflicting against that base. Main's board identifies T08 final integration as in progress and owned by `arena/7eec67cb-korea1`. I have not rebased or edited the other session's shared files/worktree.
- Review irregularity found in main's existing `index.md`, `EXECUTIVE_SUMMARY.md`, and `COORDINATION.md`: they include numerical year-over-year correlation ranges and skill/luck labels cited to non-official betting/analytics sites. The official NFL Next Gen Stats/stats sources reviewed for this session do not verify those correlation claims. This is now recorded as R-07 in this branch's candidate data and executive summary; the final integration owner should supersede or flag, not silently preserve as verified.
- Coordination request/comment posted on [PR #4](https://github.com/karagemop466-tech/Korea1/pull/4#issuecomment-6558564645) and [merged PR #3](https://github.com/karagemop466-tech/Korea1/pull/3#issuecomment-6558568834): final integration owner should review PR #4's source-backed dashboard/data and incorporate the non-overlapping research where useful, while preserving merged work and reconciling Pages paths/workflow and source/correlation claims. PR #4 must not be merged while dirty. This session is not authorized to take over T08 before its 60-minute no-commit timeout.
- Status: this branch's draft dashboard passed local structural/HTTP checks; GitHub Pages is already `built` from the current main root (`legacy` source), and the Actions deployment run for main commit `fc069fb` succeeded. PR #4 remains blocked pending coordination with the active integration owner; do not claim this branch's new dashboard is live/deployed.
