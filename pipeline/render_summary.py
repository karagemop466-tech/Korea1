"""Generate the executive summary from final public evidence, not stale headlines."""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, PROC, read_json


def main():
    gates = pd.read_csv(PROC / "strategy_gates.csv")
    scores = pd.read_csv(ROOT / "data/audit/nfl_com_score_audit.csv")
    rc = read_json(PROC / "reality_check.json")
    inj_sum = pd.read_csv(PROC / "injury_deficiency_summary.csv")
    qb_w10 = pd.read_csv(PROC / "injury_qb_audit_w10.csv")
    src = read_json(ROOT / "data/sources.json")

    n = int(gates.verdict.eq("VALIDATED").sum())
    matched = int(scores.status.eq("MATCH").sum())
    stale_qbs = int(qb_w10.status.str.contains("STALE", na=False).sum())
    verified_clubs = int(inj_sum[inj_sum.unit == "Offense"].depth_coverage.eq("VERIFIED").sum())

    text = f'''# Executive summary — NFL Line Lab

Snapshot date: {src['generated_utc'][:10]}. Research snapshot: `{src['upstream']['commit_sha']}`.

## Decision

**Keep the research engine; do not fund or reward a betting strategy yet.** The repository originates
NFL lines, audits 2026 Week 10 injury and Offense/Defense depth-chart deficiencies, and evaluates
single-bet, situational and parlay candidates. It still lacks authenticated, timestamped executable
bookmaker quotes, verified player-prop ticket prices, and historical timestamped pregame inactive/depth
archives. **{n} of {len(gates)} canonical strategies pass all eight final gates** (White reality-check
*p* = {rc['p_value']:.3f} over {rc['n_weeks']} weekly blocks). No prize, capital allocation or profitable
betting recommendation is authorized.

“Unverified” is not a finding of zero edge. It means the evidence cannot support the stronger claim.
Statistical corrections reduce false discoveries; they cannot eliminate luck or guarantee future returns.

## Decision readiness follow-up — 2026-11-12

The dedicated `decisions.html` register supplies twelve questions with current answers, missing inputs,
discovery steps and acceptance gates. `suggestions.html` compares eight proposed paths and alternatives;
none is approved. `lineups.html` contains seven selected official Week 10 injury-report observations
and quoted cells from two club depth charts, retrieved 2026-11-12. Unknown injury/status fields,
confirmed starter/replacement roles, replacement depth ranks and point impacts stay blank.
This is not league-wide or live tracking. A daily read-only Actions monitor archives three official
source pages without promoting collection into verified extraction or changing model inputs.
All-club coverage, game-day role confirmation and validated player-impact signals remain blocked.

## What was delivered

| Requirement | Delivery | Evidence status | Official / primary reference |
|---|---|---|---|
| Requirements register | `REQUIREMENTS.md` and `requirements.html` (46 requirements from `requirements/requirements.csv`) | Implemented | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |
| Own NFL lines | Walk-forward Elo, rolling matchup and ridge models; margin, total and discrete empirical ML estimates | Implemented; benchmark inputs unverified | [NFL official scores](https://www.nfl.com/scores/) |
| Injuries & O/D depth | `injuries.html` & `pipeline/injuries.py`: 2026 Wk 10 NFL.com injuries/IR + {verified_clubs}/28 club depth charts; {stale_qbs} stale nfldata QBs flagged | Current week tracked; historical archive missing | [NFL injury report](https://www.nfl.com/injuries/) |
| Pre-decision Q&A & Gaps | `questions.html`: Known vs. Unknown inventory, 14 decision Q&A entries and missing-data discovery plan | Implemented | [NFL official scores](https://www.nfl.com/scores/) |
| Suggestions (Review) | `suggestions.html`: Option A/B/C proposals with pros, cons and prerequisites (`Proposed — awaiting selection`) | Awaiting review before implementation | [Bailey & López de Prado (2014)](https://www.pm-research.com/content/iijpormgmt/40/5/94) |
| Signal strategies | {len(gates)} canonical candidates plus preserved historical annex | No validated edge | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Parlays | Simultaneous-slate selection, push-aware research settlement and adverse-price stress | Executable ticket quotes unavailable | [FanDuel push rules](https://support.fanduel.com/s/article/What-happens-if-my-FanDuel-parlay-is-a-push) |
| Player-prop combos | 2019–2022 PBP framework (21,033 player-games), calibration and 7 joint-pricing gaps | Blocked by missing prop prices (fails G6) | [NFL injury report](https://www.nfl.com/injuries/) |
| Correlations | Reproducible research estimates; strict public values blank where inputs unverified | Partial evidence | [NFL official scores](https://www.nfl.com/scores/) |
| Luck mitigation | Weekly stationary bootstrap, Holm FWER, power, provisional DSR, stability and redundancy | Implemented with assumptions | [Bailey & López de Prado (2014)](https://www.pm-research.com/content/iijpormgmt/40/5/94) |
| Official score audit | {matched}/{len(scores)} matching games across 2026 Weeks 8–9 (29/29) and historical NFL.com samples | Verified sample | [NFL official scores](https://www.nfl.com/scores/) |
| Dashboard & Hygiene | 21 categorized pages (`18` + `availability.html`, `decision-board.html`, `open-questions.html`), grouped sidebar layout, strict source checks and repaired audit claims | Ready for verification | [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages) |

## Material audit & T14 findings

1. **Refreshed official 2026 snapshot:** Re-pinned `nfldata` to `{src['upstream']['commit_sha'][:12]}` and verified all 29 Week 8–9 games against NFL.com (`59/59` total audited scores match; `0` blank or mismatched).
2. **Stale Week 10 QBs exposed in `nfldata`:** {stale_qbs} of 28 Week 10 team-QB fields (`MIN`, `MIA`, `ARI`, `SEA`, `BAL`) conflict with official NFL.com IR/starter reports and club depth charts.
3. **Offense & Defense 1st–4th string tracking:** `injuries.html` maps confirmed Out/IR cascades (`BAL` down to trade acquisition Brissett past QB3; `GB` RB1/2/3 injury cascade to RB3/4; `NE` LG1 Out + LG2 DNP and RB1 DNP + RB2 Out; `LAC` traded LB1 slot blank + Derwin James IR; `SF` LCB1/RCB1/NB1 thin secondary; `TEN`/`PIT`/`CLE` zero-backup slots) while leaving `HOU` image-only depth strings strictly blank.
4. **Historical QB & PBP absence evidence:** Across 2006–2026 `games.csv`, games with a prior-game QB change (`18.7%`) suffer `+0.678` MAE penalty vs market (`+1.036` when home QB changes), proving market-blind team Elo misses starter absences; PBP 2019–2022 shows similar drops when RB1/WR1 or 2+ top-3 defenders record zero events.
5. **No-lookahead & strict-source discipline retained:** Weather/roof fields remain excluded from default models; unverified market metrics stay blank; `temp_missing`/`wind_missing` documentation, `models.py` docstring, `prop_inputs.csv`, `assets/style.css`, and `pipeline/audit.py` strict-claim checks were repaired.

## What remains blocked

| Missing evidence | Consequence | Official context |
|---|---|---|
| Authenticated historical entry/closing quotes with timestamps and limits | No executable ROI or CLV validation | [NFL official scores](https://www.nfl.com/scores/) |
| Verified player-prop prices and joint SGP quotes | No prop-combo ROI or validated correlation | [NFL injury report](https://www.nfl.com/injuries/) |
| Historical timestamped weekly NFL inactive reports & 1st–4th string depth archive | Cannot fold pregame backup adjustments cleanly into walk-forward backtests | [NFL injury report](https://www.nfl.com/injuries/) |
| Complete trial registry and untouched prospective replication | No reward eligibility | [White (2000)](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping) |
| Houston Texans HTML/machine-readable depth chart (`houstontexans.com` image-only) | HOU depth slots remain blank (`UNVERIFIED`) | [NFL injury report](https://www.nfl.com/injuries/) |

## Reproduce and inspect

Run `make build`, `make test`, and `make audit`. See `questions.html`, `suggestions.html`, `injuries.html`, `flagged.html`, `audit/REPORT.md`, and `COORDINATION.md`.

**Research and education only. No guaranteed returns.**
'''
    (ROOT / "EXECUTIVE_SUMMARY.md").write_text(text, encoding="utf-8")
    print("wrote EXECUTIVE_SUMMARY.md")


if __name__ == "__main__":
    main()
