# NFL Line Lab

A research dashboard for NFL line origination, betting strategies, correlations and validation, with a separate replication annex.

**Live site:** https://karagemop466-tech.github.io/Korea1/  
**Executive summary:** [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)  
**Audit and limitations:** [AUDIT_2026-11-02.md](AUDIT_2026-11-02.md) · [Flagged for review](flagged.html#audit-2026)

## Important status

This is **not a verified wagering system**. Official row-by-row verification is incomplete; the primary historical dataset is from [nflverse](https://github.com/nflverse/nfldata), an independent project. Historical weather preprocessing uses information from future rows, and the parlay simulation has not established simultaneous executable quotes. No strategy is certified as skill-based; statistical tests cannot remove luck. The open board is disabled. The published historical numbers remain provisional research artifacts, not officially verified facts.

## Explore

- [Originated lines](lines.html) and [leaderboard](strategies.html)
- [Validation gates](validation.html), [correlations](correlations.html), and [player props](props.html)
- [Sources](sources.html), [flagged findings](flagged.html), and [replication annex](lab/index.html)
- [Coordination board](COORDINATION.md)

## Reproduction and verification caveats

`pipeline/` contains the main analysis and site generator; `scripts/` builds the annex. The published snapshots are in `data/processed/` and `data/lab/`. Raw data is excluded from Git. Install `requirements.txt`, then use the `Makefile` for the primary pipeline and `scripts/run_all.sh` for the annex. **A fresh `make build` resolves the current upstream branch rather than reproducing the recorded SHA**; review the audit before relying on its output. Automated link and source-presence checks do not establish official source verification or validate every number. The independent `analysis/` tests require staged raw data.

Official references for manual review: [NFL schedule](https://www.nfl.com/schedules/) and [NFL rulebook](https://operations.nfl.com/rules-officiating/2026-nfl-rulebook). Neither is a source for historical bookmaker prices.
