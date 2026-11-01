# Coordination board

| Task | Status | Owner | File scope |
|---|---|---|---|
| Research, verification, site integration and publication | needs review | arena/6452271e-korea1 | COORDINATION.md, README.md, site files and GitHub Pages configuration |

2026-11-01: Repository initially contains only README.md; acting as integration session. Session branch is fixed by the platform. Other sessions should avoid the claimed scope and record requests here.

## Integration log
- 2026-11-01: Inspected repository (README only); no historical entries or data to reconcile. Reviewed the NFL's [2026 schedule release](https://media.nfl.com/content/dam/communications/football-communications/2026/news/05%2014%2026%20-%20Schedule%20Release.pdf), [player health page](https://operations.nfl.com/inside-football-ops/players-legends/player-health-safety), [NIST discussion of overfitting and cross-validation](https://www.nist.gov/system/files/documents/2021/07/19/ir_7346_appendix_e.pdf), and [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages). The schedule fact was checked against the NFL release; source links on proposals are context, not validation of performance. Checked each table row for a source link and distinguished designs from verified facts.
- Irregularities: no archived official prices, outcomes, prop data, fitted models, empirical correlations, competition funding or validation results. These are published on Flagged for Review, with unknown numeric values blank. External URLs were checked via source retrieval, not a live automated link crawl. Luck cannot be eliminated.
- Built static HTML and ran `python3 scripts/check.py` successfully; this checks internal links, stylesheet references and external source presence, not availability of all external sites. GitHub Pages already configured to publish main/root.
