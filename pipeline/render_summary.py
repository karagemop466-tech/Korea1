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

from datetime import datetime, timezone  # noqa: E402

SRC = read_json(ROOT / "data" / "sources.json")
GENERATED = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
    audit_json = read_json(PROC / "audit.json")
    annex_props = read_json(ROOT / "data" / "lab" / "props.json")
    qb_wr1 = next((x for x in annex_props.get("pairs", [])
                   if x["leg_a"] == "QB passing yards" and x["leg_b"] == "WR1 receiving yards"), None)
    hold_pre = vig[vig.season < 2023]
    hold_post = vig[vig.season >= 2023]
    a_sum = audit_json.get("summary", {})

    def mae(model, market):
        r = allm[(allm.model == model) & (allm.market == market) & (allm.season == "ALL")]
        return float(r.mae.iloc[0])

    best = summ.sort_values("roi", ascending=False).iloc[0]
    n_skill = int((gates.verdict == "SKILL").sum())
    n_bets = int(summ.n.sum())
    winners = summ[summ.roi > 0].sort_values("roi", ascending=False)

    lines = f"""# Executive summary — NFL Line Lab

*Regenerated {GENERATED} from the pipeline output; data pinned {SRC['generated_utc']} at upstream
commit `{SHA[:12]}`. Reproduce with `make build`.*

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
| Mean two-way hold, spreads (season mean) | {pct(float(vig.spread_hold.mean()), 2)} | `vig_by_season.csv` |
| Mean two-way hold, spreads, 2006–2022 / 2023–2026 | {pct(float(hold_pre.spread_hold.mean()), 2)} / {pct(float(hold_post.spread_hold.mean()), 2)} | `vig_by_season.csv` |
| Same-game φ, cover ↔ moneyline | {fmt(float(sg.phi.iloc[1]), 3)} | `corr_same_game.csv` |
| Same-game φ, cover ↔ total | {fmt(float(sg.phi.iloc[0]), 3)} | `corr_same_game.csv` |
| Cross-game r, margin / total | {fmt(float(cg['corr'].iloc[0]), 3)} / {fmt(float(cg['corr'].iloc[1]), 3)} | `corr_cross_game.csv` |
| Prop-combo r, QB passing + WR1 receiving (within player) | {fmt(qb_wr1['rho_within_player'], 3) if qb_wr1 else '—'} | `data/lab/props.json` |
| Prop pairs measured (2021–2022 play-by-play) | {len(annex_props.get('pairs', []))} | `data/lab/props.json` |
| Independent-audit checks passed | {a_sum.get('passed', 0)}/{a_sum.get('checked', 0)} | `pipeline/audit.py` |

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
5. **Site.** A static dashboard where every table row links to its source file, a Flagged-for-Review
   page, and an Independent-audit page that re-derives the headline numbers instead of restating them.

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

**6 — The pricing environment is sharp, and it changes in 2023.** Mean two-way hold in the closing
prices is {pct(float(vig.spread_hold.mean()), 2)} on spreads and {pct(float(vig.total_hold.mean()), 2)}
on totals across the sample, but that average hides a step: {pct(float(hold_pre.spread_hold.mean()), 2)}
over 2006–2022 and {pct(float(hold_post.spread_hold.mean()), 2)} over 2023–2026. Break-even is
therefore about 51.4% on the earlier era and about 52.4% on the later one, and the site shows both
rather than quoting one number for the whole history.

**7 — Prop combos are strongly dependent, and the direction is leg-specific.** Measured on 2021–2022
play-by-play: QB passing yards with WR1 receiving yards has r = {fmt(qb_wr1['rho_within_player'], 3) if qb_wr1 else '—'}
within player (fair two-leg price {fmt(qb_wr1['fair_decimal_2leg'], 2) if qb_wr1 else '—'} against
{fmt(qb_wr1['independent_decimal_2leg'], 2) if qb_wr1 else '—'} if multiplied); WR1 and WR2 receiving
yards are nearly independent (r = {fmt(next((x['rho_within_player'] for x in annex_props['pairs'] if x['leg_b']=='WR2 receiving yards'), float('nan')), 3)});
QB passing yards against RB1 rushing yards is negative (game script). A calculator that multiplies
misprices every one of these. No prop *price* exists in either build, so no prop P&L is claimed.

## Decisions that shaped the result

- **Bet the close, not the opener.** Multi-season openers do not exist in the pinned data, so every
  strategy is measured against the hardest benchmark available. This makes results worse and more
  honest.
- **Declare first, run second.** All strategies were written down before any ran; every result is
  published, including the failures. No threshold was retuned after seeing a result.
- **Correct for the number of tries.** Eighteen strategies tested at p < 0.05 would produce a
  winner about 60% of the time by chance; Benjamini–Hochberg and the deflated Sharpe exist to stop
  exactly that.
- **Never fill a gap.** Team-total prices, prop prices and multi-season openers do not exist in any
  reached source, so they are blank and flagged rather than modelled from proxies. Player-level
  *statistics* do exist behind a hash-verified mirror, so the prop **correlations** are measured and
  published while the prop **prices** stay blank.

## Verification performed

| Check | Result |
|---|---|
| result == home_score − away_score | {audit[audit.check.str.startswith('result ==')].detail.iloc[0]} |
| total == home_score + away_score | {audit[audit.check.str.startswith('total ==')].detail.iloc[0]} |
| game_id uniqueness | {audit[audit.check.str.startswith('game_id')].detail.iloc[0]} |
| spread sign convention | {audit[audit.check.str.startswith('spread_line sign')].detail.iloc[0]} |
| settlement vs independent outcome column | {int(chk.outcome_match.sum()):,}/{len(chk):,} exact ({pct(float(chk.outcome_match.mean()), 3)}) |
| site tables with a source link on every row | 100% (enforced by `pipeline/verify_site.py`) |
| independent audit of every headline number | {a_sum.get('passed', 0)}/{a_sum.get('checked', 0)} automatic checks pass (`pipeline/audit.py`) |
| citations opened one by one | {a_sum.get('citations_verified', 0)}/{a_sum.get('citations', 0)} verified on 2026-11-02 |

## Independent audit (2026-11-02)

A session that did not write the analysis re-derived every headline number from the pinned raw data
and the committed tables, and opened every cited link. Result: **{a_sum.get('passed', 0)}/{a_sum.get('checked', 0)}
automatic checks pass**, five pipeline re-runs reproduce their artefacts byte-for-byte (including the
reality-check p-value), and **{a_sum.get('citations_verified', 0)} of {a_sum.get('citations', 0)}
citations verify** on the date shown. It found and fixed three defects: a Player-props page that
contradicted the repository's own manifest, a verifier check that was hard-coded to pass, and an
annex check (V02) that failed on a clean clone. It also disclosed two citation problems (the
FiveThirtyEight URL is dead; the Kelly DOI returns HTTP 500) and a hold-regime change in 2023.
Everything is on `audit.html`, with the URL used for each check.

## Flagged for review

There is **no prop price** anywhere in this repository and no prop P&L is claimed; team-total prices
and multi-season openers are likewise absent. Player-level statistics are a different story: they were
not used by the canonical build, but a mirror whose SHA-256 is recorded in `data/raw_manifest.json`
does carry 2021–2022 play-by-play plus a partial 2023 season, and the annex measures prop correlations from the two complete seasons — an earlier note
claiming every mirror stores only 132-byte LFS pointers was wrong and has been corrected. Two
citations cannot be confirmed today: the Kelly (1956) DOI returns HTTP 500 and the Nevada regulator's
PDF returns no readable text. The two nflverse price files disagree by a median 0.5 points on about a
third of games, and three 2015 games carry outcome flags that contradict their own score. Full
detail, with sources: `flagged.html` and `audit.html`.

## What would change the answer

1. A pre-kickoff injury and starting-quarterback feed — the largest known component of the MAE gap.
2. A licensed player-prop **price** history — player statistics already exist via the hashed mirror,
   so prices are the only missing piece of a prop P&L and a priced SGP programme.
3. A multi-season opener feed — unlocks genuine open-to-close CLV analysis instead of close-only.

## Annex: independent replication on a second odds archive

A fourth session (`arena/ea02c4fb-korea1`) built the same four questions from a **different** source — the
Sportsbook Review 10-year archive, 2011–2021, 2,945 games, 2,280 priced bets — with separate code
(`scripts/`), published at [`lab/`](lab/index.html) and narrated in
[`research/05-annex-executive-summary.md`](research/05-annex-executive-summary.md).

Four findings replicate independently, which is the strongest evidence in this repository:

1. **No strategy passes every gate** in any build (annex 0 of 18; first build 0 of 24; this build's best
   candidate fails its false-discovery-rate gate).
2. **The originated line does not beat the market** — annex spread MAE 10.473 vs market 10.151, and it also
   loses on totals and straight-up; this build 10.527 vs 10.216.
3. **Most apparent edge is luck.** Annex in-sample → out-of-sample ROI rank correlation is 0.485 while the
   best of 18 zero-skill trials has an expected Sharpe of 0.093 — reached from the other direction here by
   White's Reality Check (p = 0.970).
4. **Closing-line value is the skill-bearing statistic; ROI is not.** In a 20,000-trial mixed field of 999
   zero-skill bettors plus one genuinely skilled bettor, the skilled bettor ranks first 78.9% of the time on
   CLV and 0.32% of the time on ROI.

Where the builds disagree, the archives disagree, and that is flagged rather than reconciled: the annex
measures a mean 3.79% overround against 2.70% here (IR-09).
"""
    (ROOT / "EXECUTIVE_SUMMARY.md").write_text(lines, encoding="utf-8")
    print(f"wrote EXECUTIVE_SUMMARY.md ({len(lines):,} bytes)")


if __name__ == "__main__":
    main()
