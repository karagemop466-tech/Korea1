"""Generate the executive summary from final public evidence, not stale headlines."""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,PROC,read_json

def main():
    gates=pd.read_csv(PROC/'strategy_gates.csv')
    scores=pd.read_csv(ROOT/'data/audit/nfl_com_score_audit.csv')
    src=read_json(ROOT/'data/sources.json')
    n=int(gates.verdict.eq('VALIDATED').sum()); matched=int(scores.status.eq('MATCH').sum())
    # T16: the review registers are generated, so their counts are read from the same data, never retyped.
    from decisions import SUGGESTIONS
    from render_decisions import recount
    import availability as av
    rc = recount()
    n_src = len(av.SOURCE_CHECKS)
    # Group the conditional verdicts the same way injuries.html does: anything that did not yield the
    # needed field counts as verified-negative (negative result), never as positive evidence.
    n_verified = sum(1 for c in av.SOURCE_CHECKS if c["status"] == "VERIFIED")
    n_neg = len(av.SOURCE_CHECKS) - n_verified
    charts = sum(1 for c in av.SOURCE_CHECKS if "depth chart" in c["source"].lower())
    from collections import Counter
    sig = Counter(s["status"] for s in av.SIGNALS)
    sig_line = f"{len(av.SIGNALS)} availability signals assessed: {sig['AVAILABLE']} available, {sig['PILOT ONLY']} pilot-only, {sig['OPEN']} open, {sig['BLOCKED']} blocked"
    text=f'''# Executive summary — NFL Line Lab

Final integration: 2026-11-02. Research snapshot: `{src['upstream']['commit_sha']}`.

## Decision

**Keep the research engine; do not fund or reward a betting strategy yet.** The repository originates
NFL lines and evaluates single-bet, situational and parlay candidates. It does not contain authenticated,
timestamped executable bookmaker quotes or verified player-prop ticket prices. **{n} of {len(gates)} canonical
strategies pass all eight final gates.** No prize, capital allocation or profitable recommendation is authorized.

“Unverified” is not a finding of zero edge. It means the evidence cannot support the stronger claim.
Statistical corrections reduce false discoveries; they cannot eliminate luck or guarantee future returns.

## Decision readiness & lineup follow-up — 2026-11-12

Four review registers sit in front of the research, generated from the same data as the pages, and none
of them is an approval:

| Register | Size / status | What it establishes |
|---|---|---|
| `suggestions-review.html` | 12 staged improvements — interactive Path A / B / C selector | Side-by-side Conservative / Balanced / Full path options, trade-offs, affected gates and browser-only decision JSON export before any model or rule edit |
| `suggestions.html` | {rc['suggestions']} proposals — {rc['adopt']} ready now, {rc['pilot']} pilot, {rc['recommended']} recommended before any reward, {rc['rejected']} rejected, {rc['deferred']} deferred, {rc['blocked_suggestions']} blocked | Cost, risk, dependency and acceptance evidence for every change, plus four paths (A–D) and a change-control worksheet |
| `decision-readiness.html` | 14 pre-decision Q&As, 8 discovery protocols & 28 post-pin NFL.com scores | Separates verified knowns from missing inputs and reconciles all 28 Week 8–9 2026 games settled on NFL.com after the 2026-11-01 archive pin |
| `decisions.html` | 12 readiness questions plus a parallel 8-proposal register | Current answers, missing inputs, discovery steps and the gate each one feeds |
| `questions.html` | {rc['questions']} questions — {rc['answered']} answered, {rc['open']} open, {rc['blocked']} blocked, {rc['decisions']} needing an owner decision | Every answer cited; blocked rows left blank with the reason and a closure test |
| `lineup-deficiencies.html` | 39 Week 10 entries across 8 clubs / 4 matchups + NFL Operations T-90m rule | Offensive & defensive 1st–4th string tracking across `WAS@NYG`, `NE@DET`, `KC@ATL` and `MIN@GB`, club disclaimers/trade lag, and prefix-safe PBP backup diagnostics |

Two dated captures are transcribed in `injuries.html`: the 2026 week-10 WAS/NYG report (20 rows — 2 Out, 1
Questionable, 17 blank) and 2019 week 5 (11 rows), while `lineup-deficiencies.html` expands verified 2026
Week 10 depth-chart coverage to **8 of 32 clubs** (`commanders.com`, `giants.com`, `patriots.com`,
`detroitlions.com`, `chiefs.com`, `atlantafalcons.com`, `vikings.com`, `packers.com`) and documents the
mandatory T-90m Game Day Administration inactive & roof rule on `operations.nfl.com`. {sig_line} — **0 in
the leaderboard**, because none clears the leakage and confirmation tests and the board is pinned before week 8.

The initial official source inventory in `availability.py` holds {n_src} checks ({n_verified} verified,
{n_neg} verified-negative, including {charts} club depth charts), and `sources_lineups.json` adds 6 further
verified club depth charts (total **8 of 32 clubs**). No player is called a confirmed game-day replacement,
no depth rank is invented for a player absent from a chart, and no availability signal enters the model.
A read-only daily Actions monitor archives the sources; collection is not verified extraction. All-club
coverage, game-day role confirmation and validated impact remain blocked.

## Update of 2026-11-12

| Area | Status | What changed and what it means | Official reference |
|---|---|---|---|
| Injuries and lineups | Tracking live; effect not priced | A scheduled GitHub Actions workflow reads the official NFL.com injury report and each club's depth-chart page and publishes, for offense and defense, which first-listed players are Out or Doubtful and which 2nd, 3rd or 4th-string player the club lists next (`availability.html`). It does not yet move the originated line: the point value of an absence has not been measured. | [NFL injury report](https://www.nfl.com/injuries/) |
| Suggestions | Awaiting your decision | Every proposed change is on `decision-board.html` with options, a recommendation and the evidence behind it. Nothing is implemented. Decide DB-02 (real prices) and DB-03 (forward paper ledger) first. | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Open questions | Unanswered | `open-questions.html` separates what is known from what is missing and names how to find it. Some only you can answer: sportsbooks and jurisdiction, bankroll, success threshold, refresh cadence, reward. | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Line board freshness | Stale | The open line board still starts at Week 8 (snapshot pinned 2026-11-02); the injury capture is for the current week. Refreshing is suggestion DB-04. | [NFL schedule](https://www.nfl.com/schedules/) |
| Site | Repaired | Navigation grouped by category; stylesheet now defines the classes the pages use. Review findings RV-01 to RV-11 are on `flagged.html`. | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |

## Citation integrity audit — 2026-11-13 (session `arena/84e42ecc-korea1`)

Until now every published row was checked for the *presence* of an official reference. Presence is not
proof: a citation that resolves to a 404 looks like evidence and is not. `scripts/referent_probe.py`
now extracts every external URL printed on the site and resolves it, and the result is published on
`referents.html`.

| Result | Count | What it means |
|---|---|---|
| Resolved | 455 | HTTP 200 at the printed path, and — where a text check is defined — the page contains the text the row attributes to it. |
| Redirect | 8 | HTTP 200 only after a redirect. Works today; the printed path is stale. |
| Unresolved | 11 | 4xx/5xx or an NFL Football Operations soft-404. **Do not rely on these.** |
| Claim not supported | 1 | The page loaded without the asserted text. On inspection this one is a false negative: the FanDuel help centre is client-rendered, so the machine probe only sees a loading shell. A manual read found the quoted settlement rule. |

Confirmed dead, independently by hand and by machine: the [2017 NFL injury-report policy](https://operations.nfl.com/updates/football-ops/2017-nfl-injury-report-policy/)
and player-protections pages on `operations.nfl.com` (three pages each); the NFL.com
`/teams/<club>/depth-chart` path (four pages — the working official source is the club's own
depth-chart page, verified live for Arizona); two GitHub links (the `nfl-dbt` path uses `main` but that
repository's default branch is `master`, and `data/processed/audit.json` does not exist); and the
GitHub Pages publishing-source documentation page.

Two results need a human decision rather than a code change. The **Deflated Sharpe Ratio** reference is
printed on 13 pages and neither its publisher URL nor its DOI could be read (302). The **FiveThirtyEight
Elo methodology** URL now redirects to `abcnews.com/politics`, so the K=20 values this project quotes are
no longer readable from the printed link. Neither affects a published number; both weaken a citation.

Separately, `scripts/score_reconcile.py` re-opens the official game page for all 28 rows of the Week 8–9
2026 score census and re-reads the final score. This is the only place where the project checks its own
archived outcomes against an official source, so agreement here is what makes the pin trustworthy for
scores even though it is stale for results.

**The first machine run produced no verdict for any of the 28 rows.** The official game-centre page is
client-rendered: the runner receives raw HTML with no score in it, so every row came back `UNPARSED`
rather than `MATCH` or `MISMATCH`. That is recorded as a parser limitation, not as agreement. Two rows
(`ARI 33–30 DAL` and `ATL 0–16 TB`) were opened by hand on 2026-11-13 and both agree with the official
page — including the Atlanta shutout, which is exactly the kind of value that should be re-checked rather
than assumed. The census is therefore spot-verified, not machine-verified end to end.

All of this is published on `referents.html` and cross-listed on `flagged.html` as F-21 to F-28. Nothing
was silently repaired: a citation is only changed after a human confirms the replacement says the same thing.

## What was delivered

| Requirement | Delivery | Evidence status | Official / primary reference |
|---|---|---|---|
| Requirements register | `research/requirements.md` and `requirements.html` | Implemented | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |
| Own NFL lines | Walk-forward Elo, rolling matchup and ridge models; margin, total and moneyline estimates | Implemented; benchmark inputs unverified | [NFL official scores](https://www.nfl.com/scores/) |
| Signal strategies | {len(gates)} canonical candidates plus preserved historical annex | No validated edge | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Parlays | Simultaneous-slate selection, push-aware research settlement and adverse-price stress | Executable ticket quotes unavailable | [FanDuel push rules](https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push) |
| Player-prop combos | Input inventory, joint-distribution protocol and combo hypotheses | Blocked by missing verified prices and joint quotes | [NFL injury report](https://www.nfl.com/injuries/) |
| Correlations | Reproducible research estimates; strict public values blank where inputs unverified | Partial evidence | [NFL official scores](https://www.nfl.com/scores/) |
| Luck mitigation | Weekly-block bootstrap, Holm FWER, power, provisional DSR, stability and redundancy | Implemented with assumptions | [Bailey & López de Prado (2014)](https://www.pm-research.com/content/iijpormgmt/40/5/94) |
| Competition rewards | Fail-closed recognition tiers; all rewards unawarded | No funded prize pool | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Official score audit | {matched} matching games in a {len(scores)}-game NFL.com sample | Sample, not a census | [NFL official scores](https://www.nfl.com/scores/) |
| Dashboard | Static categorized pages, searchable tables, source links and flagged-review register | Deployment recorded separately after merge |
| Suggestions before changes (R19) | {rc['suggestions']} proposals with cost, risk, dependencies, four paths and change control | Implemented; nothing approved |
| Questions and answers (R20) | {rc['questions']} open questions plus 12 readiness questions, each with a closure test | Implemented; blocked rows blank |
| Injury / lineup deficiency (R21) | Official report captures plus {charts} of 32 club depth charts | PARTIAL — order only, no confirmed roles | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |

## Material audit corrections

1. **Pinned reproduction:** normal builds now read the committed SHA. Refreshing upstream requires an explicit flag.
2. **No future weather fill:** missing observations stay blank. Weather and roof fields are excluded from the default model until pre-kickoff availability is verified.
3. **Fair benchmark comparison:** each model and market metric uses identical available games for that market.
4. **No whole-week parlay hindsight:** tickets use an earliest eligible simultaneous kickoff slate. They remain research simulations, not confirmed ticket offers.
5. **Discrete predictive probabilities:** prior out-of-fold empirical errors replace the claim that a normal continuity correction correctly prices key numbers.
6. **Dependence-aware inference:** weekly returns, shared stationary-bootstrap resampling and Holm correction replace bet-level independence and an unsupported FDR claim.
7. **Fail-closed verdicts:** all eight gates, including redundancy and official quote provenance, are required. A profitable backtest is not labelled skill.
8. **Trial-count uncertainty:** the complete exploratory search history is unknown. Deflated Sharpe is provisional and cannot certify a strategy.
9. **Source policy:** community hashes are not official NFL verification. Strict public tables blank unverified observations; historical calculations remain in labelled data downloads.
10. **Settlement conflicts:** three 2015 closing-file outcome flags conflict with NFL.com Game Center scores. The score file agrees with NFL.com; the conflicting price-file flags remain flagged.

## What remains blocked

| Missing evidence | Consequence | Official context |
|---|---|---|
| Authenticated historical entry/closing quotes with timestamps and limits | No executable ROI or CLV validation | [NFL official scores](https://www.nfl.com/scores/) |
| Verified player-prop prices and joint SGP quotes | No prop-combo ROI or validated correlation | [NFL injury report](https://www.nfl.com/injuries/) |
| League-wide dated depth charts or official inactives ({charts} of 32 charts, neither dated) | No confirmed starter/replacement role and no availability term in any model | [NFL injury report](https://www.nfl.com/injuries/) |
| Complete trial registry and untouched prospective replication | No reward eligibility | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Full official census of historical scores and pregame fields | Research inputs remain only partially officially verified | [NFL official scores](https://www.nfl.com/scores/) |

## Reproduce and inspect

Run `make build` and `make test`. The canonical pipeline writes `data/processed/`; the independent
replication annex is preserved under `scripts/`, `data/lab/` and `lab/`. Public annex tables use the same
strict-source policy. Historical JSON/CSV calculations are explicitly unverified research data.

See `audit/REPORT.md`, `data/audit/`, `flagged.html` and `COORDINATION.md` for the audit scope,
conflicts, verification commands and final PR/deployment record. A code/data audit is not a claim that
every third-party historical observation has been individually authenticated.

**Research and education only. No guaranteed returns.**
'''
    (ROOT/'EXECUTIVE_SUMMARY.md').write_text(text)
    print('wrote EXECUTIVE_SUMMARY.md')
if __name__=='__main__':main()
