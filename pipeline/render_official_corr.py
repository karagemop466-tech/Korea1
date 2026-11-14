"""Render `official-correlations.html` — R7-07."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r7_common import BLANK, E, link, num, pill, read, table, week_url  # noqa: E402
from render_site import card, kpi_grid, layout  # noqa: E402
from common import PROC, ROOT, read_json  # noqa: E402


def body() -> str:
    s = read_json(PROC / "official_corr_summary.json")
    corr = read(PROC / "official_correlations.csv")
    inp = read(PROC / "official_corr_inputs.csv")

    cards = kpi_grid([
        card(str(s["official_games"]), "games with an official score", "the only admissible inputs"),
        card(str(s["pairs_published"]), "correlations computed", "each with n and a 95% interval", "ok"),
        card(str(s["pairs_blank"]), "pairs left blank", "no official-sourced observations exist", "warn"),
        card(str(s["min_n"]), "minimum n to publish", "below this the cell stays blank"),
    ])

    rows = []
    for r in corr.itertuples():
        computed = str(r.status).startswith("COMPUTED")
        rows.append([
            E(r.pair),
            (num(r.n, 0, signed=False) if r.n else "<strong>0</strong>"),
            num(r.pearson_r, 4) if computed else pill("BLANK", "unverified"),
            (f"[{num(r.ci_lo, 3)}, {num(r.ci_hi, 3)}]" if computed else BLANK),
            num(r.p_approx, 3) if computed else BLANK,
            pill("COMPUTED", "ok") if computed else pill("NO OFFICIAL INPUTS", "unverified"),
            E(r.note),
            link("nfl_scores"),
        ])

    irow = []
    for r in inp.itertuples():
        irow.append([
            f'<a href="{E(r.page_url)}" target="_blank" rel="noopener">{E(r.game_id)}</a>',
            num(r.away_score, 0), num(r.home_score, 0), num(r.official_margin, 0),
            num(r.official_total, 0, signed=False), E(r.tier),
            f'<a href="{week_url(int(r.season), int(r.week))}" target="_blank" rel="noopener">week scores</a>',
        ])

    return f"""
<section><h2>The rule, and why it is stricter than it looks</h2>
<p>A correlation is published here only when <strong>all four</strong> of the following hold:</p>
<ol class="findings">
<li>every input number is stated by an official NFL document,</li>
<li>the number of paired observations <strong>n</strong> is printed on the same row,</li>
<li>a 95% interval accompanies the point estimate, and</li>
<li>the row names the official source those inputs came from.</li>
</ol>
<p>Anything that fails one of these is published <strong>blank with a reason</strong>. That is not a
failure of the page — it is the page's most valuable output, because a correlation computed from a
community mirror cannot be distinguished from a correlation computed from noise once it is quoted
without its provenance.</p>
{cards}
</section>

<section><h2>Every requested pair, computed or blank</h2>
<p>The six blank rows are the ones the brief asks about most directly — spread/moneyline dependence,
prop pairs and same-game parlays. None of them can be computed from official numbers, and each row states
which non-official input it would need.</p>
{table(rows, ["Relationship", "n", "Pearson r", "95% interval", "p (approx.)", "Status",
             "Why", "Official scores"],
       caption="Correlations from officially sourced numbers only; n printed on every row")}
</section>

<section><h2>The official inputs, game by game</h2>
<p>{len(inp)} games. Every margin and total below is arithmetic on the two official team scores beside it,
so a reader can recompute the correlation without trusting this module.</p>
{table(irow, ["Game", "Away", "Home", "Margin", "Total", "Evidence tier", "Official scores"],
       caption="The only admissible inputs: official scores from the verified results feed (R7-02)")}
<p><a href="data/processed/official_correlations.csv">Download the correlation table (CSV)</a> ·
<a href="data/processed/official_corr_inputs.csv">the paired inputs (CSV)</a></p>
</section>

<section><h2>Reading the three computed values honestly</h2>
<ul class="findings">
<li><strong>n = {s['official_games']} across {len(s['weeks'])} weeks.</strong> At this sample size a
correlation of 0.3 has an interval roughly ±0.35 wide. Treat every interval on this page as the result;
the point estimate is nearly uninformative.</li>
<li><strong>Margin vs total is not a betting relationship.</strong> Both are sums of the same two official
scores, so this measures how often a blowout coincides with a high-scoring game — a description of these
{len(s['weeks'])} weeks, not a stable league property.</li>
<li><strong>Every blank row needs a paid feed, not more work.</strong> Prop correlations need player-level
official statistics per game; same-game-parlay correlations need joint ticket quotes from a single book. Both
are named with their cost on <a href="decision-questions-2026-11-14.html">the decision questions page</a>.</li>
</ul>
</section>"""


def main() -> None:
    (ROOT / "official-correlations.html").write_text(
        layout("official-correlations.html", "Official-source correlations",
               "Every value computed from official NFL numbers, with n and an interval; everything else blank with a reason.",
               body(), wide=True))
    print("wrote official-correlations.html")


if __name__ == "__main__":
    main()
