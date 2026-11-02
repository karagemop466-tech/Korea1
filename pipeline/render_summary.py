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


# Appended verbatim at the end of the generated summary. It is written by the annex session
# (`arena/ea02c4fb-korea1`) and must survive regeneration — a naive rewrite of this file silently
# deleted it once, which is exactly the kind of cross-session loss the task board exists to prevent.
ANNEX_SECTION = """## Annex: independent replication on a second odds archive

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


# The independent-audit section belongs to session `arena/1642ee06-korea1` (it ships `audit.html` and
# `data/audit/`). Their session appended it by hand to this generated file; embedding it here is the
# same fix applied for the annex below, so a regeneration cannot delete another session's work.
AUDIT_SECTION = """## Independent official-source audit (2026-11-02, session `arena/1642ee06-korea1`)

Full detail: [`audit.html`](audit.html) · data in [`data/audit/`](data/audit/) · scripts `scripts/audit_*.py`.

- **Scores.** 39 games read on NFL.com (2014, 2015, 2016, 2022 and 2026 week pages, plus the three 2015 games
  whose nflverse outcome flag contradicts the score): **31 match the pinned data, 0 mismatch**, 8 are 2026
  week-8 games that NFL.com lists as Final and the pinned snapshot predates (left blank, flagged).
  This is a sample, not a census; games before 2010 (2,913) and playoff games (309) were not checked.
- **Inputs.** All 7 pinned nfldata files re-downloaded from the pinned commit: SHA-256 and byte count match.
  Rebuilding every table from them reproduces the published files byte for byte; `tests/test_no_lookahead.py` 4/4.
- **Official sources.** Of 523 table rows on the ten root pages, 3 link to nfl.com and 516 link only to
  nflverse (a community project). Historical closing lines, totals and prices have **no official NFL source**
  and the upstream data dictionary does not name the sportsbook. These are flagged (IR-T10-01, -02), not blanked.
- **Defect fixed.** `scripts/99_verify.py` V02 failed on every fresh checkout; it now passes (9/9).
- **Does not change the conclusion.** 0 of 18 strategies pass all gates; no figure in this summary was altered.
"""


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
    prop_gates = pd.read_csv(PROC / "prop_gates.csv")
    prop_combo = pd.read_csv(PROC / "prop_combos.csv")
    prop_skill = pd.read_csv(PROC / "prop_skill.csv")
    prop_defs = pd.read_csv(PROC / "prop_definition_validation.csv")
    prop_rep = read_json(PROC / "prop_report.json")
    corr_col = "combo" if "combo" in prop_combo else "pair"
    big = prop_combo.sort_values("gap", ascending=False).iloc[0]
    qbwr = prop_combo[prop_combo[corr_col].str.startswith("QB pass yds ↔ own WR1")].iloc[0]
    ctrl = prop_combo[prop_combo[corr_col].str.contains("control")].iloc[0]

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
| Player-games aggregated (props) | {prop_rep['player_games']:,} (2019–2022) | `prop_player_games.csv` |
| Prop definitions verified | {prop_rep['definition_checks_passed']}/{prop_rep['definition_checks']} player-seasons exact | `prop_definition_validation.csv` |
| Prop forecast AUC, 4 markets | {min(prop_skill.auc):.2f}–{max(prop_skill.auc):.2f} | `prop_skill.csv` |
| Prop leg correlation, φ range | {prop_combo.phi.min():.3f} to {prop_combo.phi.max():.3f} | `prop_combos.csv` |
| Largest same-game lift | {big['lift']:.3f}× ({big[corr_col]}) | `prop_combos.csv` |
| Prop combos awarded | 0 — G6 cannot pass without prop prices | `prop_gates.csv` |

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

## Player props: what the extra data bought

Player-level play-by-play was fetched for 2019–2022 (67.9 MB, four pinned blobs) after an earlier
build wrongly recorded it as unreachable. That unlocks the prop module:

- **{prop_rep['player_games']:,} player-games** aggregated into passing, rushing and receiving yards
  and receptions. Seven published season totals — Brady {prop_defs[prop_defs.player=='T.Brady'].published.iloc[0]:.0f}
  passing yards, Kupp {prop_defs[(prop_defs.player=='C.Kupp')&(prop_defs.stat=='rec')].published.iloc[0]:.0f}
  receptions, Taylor {prop_defs[prop_defs.player=='J.Taylor'].published.iloc[0]:.0f} rushing yards —
  are reproduced exactly, keyed on player id (a name key silently merged J.Taylor of New England
  into J.Taylor of Indianapolis).
- **{prop_rep['lines']:,} originated prop lines**, walk-forward, no market input. Out of sample the
  AUC is {min(prop_skill.auc):.2f}–{max(prop_skill.auc):.2f}, so the lines rank players well above
  chance; the calibration slope is only {min(prop_skill.slope):.2f}–{max(prop_skill.slope):.2f}
  against 1.0, so the probabilities are compressed and should not be used as prices.
- **Prop legs are measurably dependent.** QB passing yards with his own WR1's receiving yards lift
  the joint hit rate {qbwr['lift']:.3f}× over independence, and receptions with the same player's
  receiving yards lift it {big['lift']:.3f}×. Two WR1 legs from unrelated games give
  φ = {ctrl['phi']:.3f} with an interval spanning zero, so the estimator does not manufacture
  dependence.
- **Nothing is awarded.** No reachable source carries a player-prop price, so gate G6 cannot be
  assessed and all {len(prop_gates)} combos are withheld. The correlation is the finding; the ROI
  would be an invention.

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

Player-level **statistics** are now retrieved and used (2019–2022 play-by-play, see the props
section above); prop **prices** were not retrievable in this build (nflverse release
assets sit behind a blocked host; mirrors store 132-byte LFS pointers). Multi-season openers do not
exist in the pinned data. The two nflverse price files disagree by a median 0.5 points on about a
third of games, and three 2015 games carry outcome flags that contradict their own score. Full
detail, with sources: `flagged.html`.

## What would change the answer

1. A pre-kickoff injury and starting-quarterback feed — the largest known component of the MAE gap.
2. Prop **prices** (the statistics are now in hand) — turns the measured prop dependence into a
   testable return; without a price, gate G6 stays unanswerable.
3. A multi-season opener feed — unlocks genuine open-to-close CLV analysis instead of close-only.

"""
    lines = (
        lines.rstrip() + "\n\n---\n\n" + ANNEX_SECTION.strip()
        + "\n\n---\n\n" + AUDIT_SECTION.strip() + "\n"
    )

    # Generated addendum (annex + corrections). It is appended to `lines` BEFORE the safety net
    # below, so the net sees the section as known and cannot duplicate it, and a rebuild cannot
    # delete it either. F3/D-04, session arena/fb363967-korea1.
    addendum = ROOT / "pipeline" / "executive_summary_addendum.md"
    if addendum.exists():
        lines = lines.rstrip() + "\n\n" + addendum.read_text(encoding="utf-8").strip() + "\n"

    # Safety net: keep any `---`-separated section that some other session appended by hand and that
    # this generator does not know about. Without this, regenerating the summary silently deletes
    # cross-session work (it has already happened twice).
    dest = ROOT / "EXECUTIVE_SUMMARY.md"
    if dest.exists():
        known = lines
        for block in dest.read_text(encoding="utf-8").split("\n---\n\n## ")[1:]:
            header = "## " + block.split("\n", 1)[0].strip()
            if header not in known:
                lines = lines.rstrip() + "\n\n---\n\n" + header + "\n" + block.split("\n", 1)[1]
                print(f"preserved external section: {header}")
    dest.write_text(lines, encoding="utf-8")
    print(f"wrote EXECUTIVE_SUMMARY.md ({len(lines):,} bytes)")


if __name__ == "__main__":
    main()
