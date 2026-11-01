# Flagged for Review

## Irregularities and Unverified Items

The following items require manual review after site deployment. All values left blank where official sources could not confirm.

### 1. Approximate Correlation Values
- **Issue**: Public play-by-play research values (~0.55-0.65 for EPA, ~0.50-0.60 for Success Rate, etc.) cannot be recomputed from bundled game logs
- **Affected Strategies**: PP-001, PP-002, PP-003, PP-004, PP-005
- **Source Reference**: [Regression Analysis](https://nflanalytic.com/betting-regression.html)
- **Status**: Unverified - values are approximate from public research, not recomputed from official game logs
- **Review Required**: Confirm if approximate values meet validation gate VG-002 (≥ 0.45 YoY correlation)

### 2. Prop Pattern Correlation Methodology
- **Issue**: Spike identification for target share correlation requires gamebook CSV import and analysis
- **Affected Strategy**: PP-007
- **Source Reference**: [Player Prop Sources](https://surehandstransportation.com/2026/04/27/the-best-historical-data-sources-for-nfl-player-props/)
- **Status**: Unverified - methodology requires manual CSV processing from official NFL gamebooks
- **Review Required**: Validate spike identification process against official gamebook data

### 3. CPOE Replication Limitation
- **Issue**: Completion Percentage Over Expectation (CPOE) uses proprietary formula; public version correlates r²=0.88 but is not one-to-one
- **Affected Strategy**: PP-005
- **Source Reference**: [Advanced Metrics](https://www.covers.com/nfl/key-advanced-metrics-betting-tips)
- **Status**: Unverified - proprietary formula prevents exact replication
- **Review Required**: Determine if public version correlation (r²=0.88) meets validation gate VG-002 threshold

### 4. Table Row Verification Status
- **Issue**: All strategy table rows currently marked as [Pending Verification] and [Unverified]
- **Affected Strategies**: SB-001 through SB-005, PR-001 through PR-003, PP-001 through PP-007
- **Source Reference**: All official sources listed in [index.md](/index.md)
- **Status**: Unverified - line-by-line verification pending completion
- **Review Required**: Complete verification against official NFL.com, Next Gen Stats, Pro Football Reference sources

### 5. Validation Gate Compliance
- **Issue**: Validation gates VG-001 through VG-005 currently marked as [Pending Verification]
- **Source Reference**: [NFL Betting Systems](https://nflbettingsystems.com/)
- **Status**: Unverified - backtesting and out-of-sample testing results pending
- **Review Required**: Confirm 3-season backtesting (200+ games) and out-of-sample testing completion

---

## Official Source Links for Review
- [NFL Next Gen Stats](https://nextgenstats.nfl.com/stats/passing/2025/REG/3)
- [NFL Official Gamebooks](https://surehandstransportation.com/2026/04/27/the-best-historical-data-sources-for-nfl-player-props/)
- [Pro Football Reference](https://www.pro-football-reference.com/)
- [NFL.com Official](https://rg.org/guides/football/betting-lines)
- [NFL Betting Systems](https://nflbettingsystems.com/)
- [Regression Analysis](https://nflanalytic.com/betting-regression.html)
- [Popular NFL Strategies](https://www.mybookie.ag/sports-betting-guide/popular-nfl-strategies-theories/)
- [Advanced Metrics](https://www.covers.com/nfl/key-advanced-metrics-betting-tips)
- [NFL Stats for Betting](https://bestbetfornfl.com/articles/nfl-stats-betting-analysis/)
- [NFL Scores & Data](https://www.kaggle.com/tobycrabtree/nfl-scores-and-betting-data/home)

---

## Coordination Note
- **Session ID**: arena/7eec67cb-korea1
- **Branch**: arena/7eec67cb-korea1
- **Task**: T07 - Flagged for Review page creation
- **Status**: Done (integration session)
- **Last Update**: 2026-11-01
- **Next Action**: Final integration, PR creation, merge, and GitHub Pages deployment

---

## Footer
*Flagged for Review - Manual review required after site deployment | Repository: karagemop466-tech/Korea1 | Branch: arena/7eec67cb-korea1*