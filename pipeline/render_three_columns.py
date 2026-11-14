"""Render `three-columns.html` — R7-03 origination order and R7-04 the three published columns."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r7_common import BLANK, E, link, num, pct, pill, read, table, week_url  # noqa: E402
from render_site import card, kpi_grid, layout  # noqa: E402
from common import PROC, ROOT, read_json  # noqa: E402

MAX_ROWS = 90


def body() -> str:
    three = read_json(PROC / "three_columns.json")
    order = read(PROC / "origination_order.csv")
    cons = read_json(PROC / "origination_summary.json")
    tc = read(PROC / "three_columns.csv")
    cov = read(PROC / "three_columns_coverage.csv")

    cards = kpi_grid([
        card(str(three["games"]), "games with a fair line", f"{three['rows']:,} published rows"),
        card(str(three["rows_with_a_market_line"]), "rows with a market line",
             "the rest are fair-line only", "ok"),
        card(f"{cons['max_side_partition_violation']:.0e}", "side partition error",
             "all three markets from one distribution", "ok"),
        card(f"{cons['max_ml_partition_violation']:.0e}", "moneyline partition error", "derived, not fitted", "ok"),
        card(str(cons["games_tested"]), "games in the consistency test", "identity checked per game"),
    ])

    orow = [[
        E(r.order), E(r.market), pill(r.role, "ok" if "FITTED" in r.role else "unverified"),
        E(r.fitted), E(r.may_use), E(r.may_not_use), E(r.published_outputs),
        E(r.why_first if str(r.why_first) not in ("", "nan") else
          (r.why_second if str(r.why_second) not in ("", "nan") else r.why_third)),
        link("nfl_scores"),
    ] for r in order.itertuples()]

    defs = [[E(d["column"]), E(d["market"]), E(d["definition"]), E(d["units"]), pill(d["status"], "unverified"),
             E(d["who_computes_it"]), link("nfl_scores")] for d in three["columns"]]

    sample = tc[(tc.season >= 2025)].sort_values(["season", "week", "gameday", "game_id", "market_order"]).head(MAX_ROWS)
    srow = []
    for r in sample.itertuples():
        unit = "pp" if r.market == "MONEYLINE" else "pt"
        srow.append([
            f'<a href="{week_url(int(r.season), int(r.week))}" target="_blank" rel="noopener">{E(r.game_id)}</a>',
            pill(r.market, "unverified"),
            (num(r.fair_line, 3) if r.market != "MONEYLINE" else pct(r.fair_line, 2)),
            (num(r.market_line, 1) if r.market != "MONEYLINE" else pct(r.market_line, 2)),
            f"{num(r.difference, 3) if r.market != 'MONEYLINE' else num(r.difference * 100, 2)} {unit}",
            BLANK if not r.market_line_present else pill("market line present", "ok"),
            f'<a href="{week_url(int(r.season), int(r.week))}" target="_blank" rel="noopener">official scores</a>',
        ])

    covrows = []
    for r in cov[cov.season >= 2020].itertuples():
        covrows.append([
            E(r.season), E(r.market), E(r.games), E(r.market_line_present), pct(r.coverage_pct),
            link("community"),
            f'<a href="https://www.nfl.com/scores/{int(r.season)}" target="_blank" rel="noopener">season scores</a>',
        ])

    return f"""
<section><h2>Origination order — side, then total, then moneyline</h2>
<p>The order is not a layout preference. It fixes <strong>what is fitted, what may reuse what, and what is
derived</strong>. Originating the three markets independently produces the familiar inconsistency where a
team is a 60% cover at −2.5 and a 45% moneyline favourite.</p>
{table(orow, ["#", "Market", "Role", "Fitted?", "May use", "May not use", "Published outputs", "Why this position", "Official scores"],
       caption="The origination order, its inputs and its prohibitions")}
<p><strong>The consistency test passes at machine precision.</strong> Across {cons['games_tested']:,} games the
side partition sums to one with a worst error of {cons['max_side_partition_violation']:.1e} and the
moneyline partition with {cons['max_ml_partition_violation']:.1e}. Because both are evaluations of the same
empirical residual distribution rather than separate fits, the moneyline <em>cannot</em> disagree with the
side at handicap zero. This is internal consistency only — it says nothing about calibration against
outcomes, which needs the validation gates and an authenticated price.</p>
</section>

<section><h2>Fair line, market line, difference — three columns, never one</h2>
<p>A table that prints only one number cannot tell a reader whether the model moved or the market moved, and
a reviewer cannot check the arithmetic. Every row here is independently recomputable: the build fails if
<code>difference ≠ fair_line − market_line</code> (maximum recompute error on this build:
<strong>{three['max_recompute_error']:.0e}</strong>).</p>
{cards}
{table([[E(three['sign_convention']), link('nfl_scores')]],
       ["Sign convention", "Official scores"],
       caption="Sign convention, stated once and enforced by the build")}
{table(defs, ["Column", "Market", "Definition", "Units", "Status", "Produced by", "Official scores"],
       caption="Column definitions and the status of each value; no column is an official observation")}
<p class="flag warn"><strong>What a difference is not.</strong> {E(three['boundary'])}</p>
</section>

<section><h2>The three columns, 2025–2026</h2>
<p>{len(sample)} rows, ordered side → total → moneyline as the origination order requires. A blank difference
means the archive carries no market line for that game, which happens only outside the coverage blocks below.</p>
{table(srow, ["Game", "Market", "Fair line", "Market line", "Difference", "Market coverage", "Official scores"],
       caption="Fair / market / difference published as three separate columns, each labelled by status")}
<p><a href="data/processed/three_columns.csv">Download all {three['rows']:,} rows (CSV)</a> ·
<a href="data/processed/three_columns.json">column definitions (JSON)</a></p>
</section>

<section><h2>Market-line coverage, so a full table is not mistaken for full comparability</h2>
<p>The model has an opinion about every game it fits. The archive does not carry a price for every game. The
two are different denominators and the difference is published rather than smoothed away.</p>
{table(covrows, ["Season", "Market", "Games", "With a market line", "Coverage", "Price source", "Official scores"],
       caption="Market-line coverage by season; the model line and the market line have different denominators")}
</section>"""


def main() -> None:
    (ROOT / "three-columns.html").write_text(
        layout("three-columns.html", "Origination order & three columns",
               "Side, total, moneyline in that order — and fair / market / difference as three separate, recomputable columns.",
               body(), wide=True))
    print("wrote three-columns.html")


if __name__ == "__main__":
    main()
