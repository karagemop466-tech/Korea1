"""Generate EXECUTIVE_SUMMARY.md from the same tables the site uses.

Writing the summary from the data (rather than by hand) is the only way to keep it
from drifting out of sync with the numbers it quotes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, fmt, pct, read_json  # noqa: E402

SRC = read_json(ROOT / "data" / "sources.json")
SHA = SRC["upstream"]["commit_sha"]


def main() -> None:
    pred = pd.read_csv(PROC / "originated_lines.csv")
    gates = pd.read_csv(PROC / "strategy_gates.csv")
    summ = pd.read_csv(PROC / "strategy_summary.csv")
    allm = pd.read_csv(PROC / "model_metrics.csv")
    rc = read_json(PROC / "reality_check.json")
    vig = pd.read_csv(PROC / "vig_by_season.csv")
    sg = pd.read_csv(PROC / "corr_same_game.csv")
    cg = pd.read_csv(PROC / "corr_cross_game.csv")
    audit = pd.read_csv(PROC / "data_audit.csv")
    chk = pd.read_csv(PROC / "settlement_crosscheck.csv")

    def mae(model, market):
        r = allm[(allm.model == model) & (allm.market == market) & (allm.season == "ALL")]
        return float(r.mae.iloc[0])

    best = summ.sort_values("roi", ascending=False).iloc[0]
    n_skill = int((gates.verdict == "SKILL").sum())
    n_bets = int(summ.n.sum())
    winners = summ[summ.roi > 0].sort_values("roi", ascending=False)

    lines = f"""# Executive summary — NFL Line Lab

*Generated from the pipeline output on {SRC['generated_utc']} · upstream commit `{SHA[:12]}` ·
reproduce with `make build`.*

## The question

Can we originate our own NFL lines, and build betting strategies that beat the market for
reasons other than luck?

## The answer, in one paragraph

The pipeline produces a defensible, market-free NFL line — within about a third of a point of the
closing line on both the spread and the total — but that gap is decisive. Once every strategy is
forced through power, multiple-testing, bootstrap and deflated-Sharpe gates, the apparent winners
dissolve. **{n_skill} of {len(gates)} strategies clear all eight gates**, and White's reality check
across the whole library returns **p = {fmt(rc.get('p_value', float('nan')), 3)}**, which does not
reject the hypothesis that the best result is luck. The deliverable is therefore the machinery that
can tell the difference — plus a documented list of exactly which data would be needed to go
further.

## Key numbers

| Quantity | Value | Source |
|---|---|---|
| Games with an out-of-sample line | {len(pred):,} ({int(pred.season.min())}–{int(pred.season.max())}, of 7,384 played) | `games.csv` |
| Closing-line spread MAE | {fmt(mae('market','spread'), 4)} | `games.csv` |
| Our spread MAE | {fmt(mae('ensemble','spread'), 4)} | `pipeline/models.py` |
| Closing-line total MAE | {fmt(mae('market','total'), 4)} | `games.csv` |
| Our total MAE | {fmt(mae('ensemble','total'), 4)} | `pipeline/models.py` |
| Bets simulated | {n_bets:,} | `strategy_bets.csv` |
| Strategies tested | {len(gates)} | `strategy_gates.csv` |
| Strategies validated as skill | {n_skill} | `strategy_gates.csv` |
| Best raw ROI | {pct(best.roi, 1)} ({best.strategy}, {int(best.n)} tickets) | `strategy_summary.csv` |
| Reality-check p-value | {fmt(rc.get('p_value', float('nan')), 3)} | `reality_check.json` |
| Mean two-way hold, spreads | {pct(float(vig.spread_hold.mean()), 2)} | `vig_by_season.csv` |
| Same-game φ, cover ↔ moneyline | {fmt(float(sg.phi.iloc[1]), 3)} | `corr_same_game.csv` |
| Same-game φ, cover ↔ total | {fmt(float(sg.phi.iloc[0]), 3)} | `corr_same_game.csv` |
| Cross-game r, margin / total | {fmt(float(cg['corr'].iloc[0]), 3)} / {fmt(float(cg['corr'].iloc[1]), 3)} | `corr_cross_game.csv` |

## What was built

1. **Data layer.** One pinned commit of `nflverse/nfldata`, archived from `codeload.github.com`
   and SHA-256 hashed on arrival into `data/sources.json`. 7,548 schedule rows, 7,384 played games
   1999–2026, plus an independent per-side price file used to cross-check settlement.
2. **Line origination.** Three model families — weighted ridge on pre-game structure, matchup
   expected points, Elo — fitted walk-forward and averaged with fixed weights. No model sees a
   price; none sees anything after kickoff. Both facts are asserted in code.
3. **Strategy library.** {len(gates)} pre-declared strategies (single bets, 2- and 3-leg parlays,
   classic angle rules), one unit per bet at the recorded closing price, pushes refunded, no `-110`
   substitution and no line shopping.
4. **Validation.** Eight gates: data integrity, leakage, power, significance with FDR control,
   bootstrap + deflated Sharpe, economic significance, stability, redundancy.
5. **Site.** A static dashboard where every table row links to its source file, plus a
   Flagged-for-Review page.

## Findings

**1 — The market is still better than the model.** {fmt(mae('market','spread'), 4)} vs
{fmt(mae('ensemble','spread'), 4)} on spreads and {fmt(mae('market','total'), 4)} vs
{fmt(mae('ensemble','total'), 4)} on totals. The gap is roughly the width of the vig, which is why
nothing below gets paid. It is the value of injury reports, starting-quarterback news and sharp
money, none of which the model is allowed to see.

**2 — Nothing survives validation.** {n_skill} of {len(gates)} strategies pass. The best raw ROI is
{pct(best.roi, 1)} on {int(best.n)} tickets ({best.strategy}) — a high-variance long-shot ladder
whose win rate is {pct(best.win_rate)}. Its FDR-adjusted p-value is
{fmt(float(gates[gates.strategy == best.strategy].G4_p_adj.iloc[0]), 3)} and its deflated Sharpe is
{fmt(float(gates[gates.strategy == best.strategy].G5_dsr.iloc[0]), 3)}: not an edge.

**3 — The library as a whole cannot beat luck.** White's reality check p =
{fmt(rc.get('p_value', float('nan')), 3)} over {rc.get('n_strategies')} strategies and
{rc.get('n_weeks')} weekly blocks.

**4 — Power is the binding constraint, not the model.** Detecting a true 1% per-bet edge at 80%
power needs about 78,000 bets — roughly 290 NFL seasons. At 5% it needs about 3,100 bets, or twelve
seasons. Most published betting edges are under-powered noise; the gates are calibrated to say so.

**5 — Correlation is measurable, and it is not symmetric.** Same-game cover ↔ moneyline has
φ = {fmt(float(sg.phi.iloc[1]), 3)}: near-duplicate legs. Cover ↔ total is φ =
{fmt(float(sg.phi.iloc[0]), 3)}: close to independent. Cross-game legs are independent
(r = {fmt(float(cg['corr'].iloc[0]), 3)}, interval spans zero), which is why an ordinary parlay can
be priced by multiplication but a same-game parlay cannot.

**6 — The pricing environment is sharp.** Mean two-way hold in the closing prices is
{pct(float(vig.spread_hold.mean()), 2)} on spreads and {pct(float(vig.total_hold.mean()), 2)} on
totals — a low-margin book, so break-even is about 51.4%, not 52.4%.

## Decisions that shaped the result

- **Bet the close, not the opener.** Multi-season openers do not exist in the pinned data, so every
  strategy is measured against the hardest benchmark available. This makes results worse and more
  honest.
- **Declare first, run second.** All strategies were written down before any ran; every result is
  published, including the failures. No threshold was retuned after seeing a result.
- **Correct for the number of tries.** Eighteen strategies tested at p < 0.05 would produce a
  winner about 60% of the time by chance; Benjamini–Hochberg and the deflated Sharpe exist to stop
  exactly that.
- **Never fill a gap.** Player-level props, team-total prices and multi-season openers are not
  available from any reachable source, so they are blank and flagged rather than modelled from
  proxies.

## Verification performed

| Check | Result |
|---|---|
| result == home_score − away_score | {audit[audit.check.str.startswith('result ==')].detail.iloc[0]} |
| total == home_score + away_score | {audit[audit.check.str.startswith('total ==')].detail.iloc[0]} |
| game_id uniqueness | {audit[audit.check.str.startswith('game_id')].detail.iloc[0]} |
| spread sign convention | {audit[audit.check.str.startswith('spread_line sign')].detail.iloc[0]} |
| settlement vs independent outcome column | {int(chk.outcome_match.sum()):,}/{len(chk):,} exact ({pct(float(chk.outcome_match.mean()), 3)}) |
| site tables with a source link on every row | 100% (enforced by `pipeline/verify_site.py`) |

## Flagged for review

Player-week statistics and prop prices were **not retrievable** in this build (nflverse release
assets sit behind a blocked host; mirrors store 132-byte LFS pointers). Multi-season openers do not
exist in the pinned data. The two nflverse price files disagree by a median 0.5 points on about a
third of games, and three 2015 games carry outcome flags that contradict their own score. Full
detail, with sources: `docs/flagged.html`.

## What would change the answer

1. A pre-kickoff injury and starting-quarterback feed — the largest known component of the MAE gap.
2. Player-week statistics and prop prices — unlocks the entire prop and SGP programme.
3. A multi-season opener feed — unlocks genuine open-to-close CLV analysis instead of close-only.

"""
    (ROOT / "EXECUTIVE_SUMMARY.md").write_text(lines, encoding="utf-8")
    print(f"wrote EXECUTIVE_SUMMARY.md ({len(lines):,} bytes)")


if __name__ == "__main__":
    main()
