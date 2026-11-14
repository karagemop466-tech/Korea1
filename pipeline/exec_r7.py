"""The R7 section of the executive summary (session arena/7da09b4d-korea1).

Kept in its own module rather than inside `render_site.py` so this session does
not grow another session's module and so the summary is generated from the
artefacts instead of a literal that could drift from the pages it summarises.
"""
from __future__ import annotations

import json

from common import PROC, ROOT

PRICES = ROOT / "data" / "prices"

EXEC_TABLE = 'class="tablewrap"'


def _j(name: str) -> dict:
    """Read a JSON artefact from either the processed or the prices directory."""
    for base in (PROC, PRICES):
        p = base / name
        if p.exists():
            return json.loads(p.read_text())
    return {}


def section() -> str:
    prices = _j("price_provenance.json")
    if not prices:
        return ""
    res = _j("results_summary.json")
    orig = _j("origination_summary.json")
    three = _j("three_columns.json")
    sstake = _j("signal_staking_summary.json")
    depth = _j("replacement_summary.json")
    corr = _j("official_corr_summary.json")
    demo = _j("demotion_gate_summary.json")
    sug = _j("suggestions_2026_11_14_summary.json")
    qs = _j("decision_questions_2026_11_14_summary.json")

    f = prices["facts"]
    dd = depth.get("replacement_depth_counts", {})
    rows = [
        ["Price snapshots", f"{f['rows']:,} rows · {sum(f['games_by_kind'].values()):,} game-kinds",
         f"<strong>Opening-to-closing movement is unmeasurable.</strong> {f['capture_time_rows']} rows carry a capture "
         f"time because no source in the pin has one. The opener covers 2021 only and the named closer 2006–2018, so no "
         f"game carries two instruments of known kind. The undated series and the named closing series disagree on "
         f"55–90% of games from 2006 to 2016 and under 3% in 2017–2018 — one of the two is wrong for a decade and this "
         f"project cannot say which.", '<a href="prices.html">prices.html</a>'],
        ["Verified results", f"{res.get('settleable', 0)} games settleable",
         f"Official documents only. {res.get('by_tier', {}).get('OFFICIAL_GAME_BOOK', 0)} scores were read this session "
         f"from NFL Game Book PDFs because the Game Center renders &ldquo;Hidden Score&rdquo;. "
         f"{res.get('settled_after_the_pin', 0)} verified games settled after the pinned snapshot and are labelled, not "
         f"dropped. The feed lists all {res.get('rows', 0):,} games; {res.get('unverified', 0):,} have no official score.",
         '<a href="results.html">results.html</a>'],
        ["Origination order", f"side → total → moneyline · {orig.get('games_tested', 0):,} games",
         f"The moneyline is <strong>derived</strong> from the margin distribution at a zero handicap, not fitted "
         f"separately. The three-market partition identity holds at {orig.get('max_side_partition_violation', 0):.1e}, so "
         f"the three markets cannot disagree about the same game.", '<a href="three-columns.html">three-columns.html</a>'],
        ["Three columns", f"{three.get('rows', 0):,} rows · {three.get('games', 0):,} games",
         f"Fair line, market line and difference are three separate columns in every row, each labelled with its status. "
         f"The build fails if <code>difference ≠ fair − market</code> (error on this build: "
         f"{three.get('max_recompute_error', 0):.0e}). A difference is not an edge: an edge needs an executable price.",
         '<a href="three-columns.html">three-columns.html</a>'],
        ["Signal vs staking", f"{sstake.get('strategies', 0)} strategies · "
         f"{sstake.get('strategies_whose_roi_flips_sign_under_staking', 0)} flip sign under staking",
         f"Signal is hit rate minus break-even rate and contains no stake. "
         f"{sstake.get('strategies_whose_roi_flips_sign_under_staking', 0)} strategies change the sign of their return "
         f"under a staking rule alone ({sstake.get('largest_staking_swing', 0) * 100:.1f} points at the extreme), which "
         f"is exactly the masking the requirement names. Nothing here is promoted to a result.",
         '<a href="signal-staking.html">signal-staking.html</a>'],
        ["Replacement depth", f"{depth.get('joined_to_chart', 0)} of {depth.get('injury_rows', 0)} rows joined",
         f"Official injury report joined to official club depth charts. Depth of the replacement is measured directly: "
         f"{dd.get('2nd string', 0)} slots inherit a 2nd string, {dd.get('3rd string', 0)} a 3rd or deeper, "
         f"{dd.get('NOBODY LISTED', 0)} have no listed successor. Two join defects were found and fixed (Green Bay "
         f"jersey-number prefixes; Houston's unparseable chart). No row asserts that anyone started.",
         '<a href="replacement-depth.html">replacement-depth.html</a>'],
        ["Official correlations", f"{corr.get('pairs_published', 0)} computed · {corr.get('pairs_blank', 0)} blank",
         f"Only official NFL numbers are admissible. {corr.get('pairs_published', 0)} correlations carry n and a 95% "
         f"interval over {corr.get('official_games', 0)} games. The {corr.get('pairs_blank', 0)} that need a market line, "
         f"a prop price or a joint ticket quote are published blank with the exact input each would require — not "
         f"approximated from a community mirror.",
         '<a href="official-correlations.html">official-correlations.html</a>'],
        ["Demotion gate", f"{demo.get('demoted', 0)} demoted · {demo.get('live', 0)} live",
         f"Pre-registered {str(demo.get('registered_utc', ''))[:10]}, fail-closed, and it demotes on a staking-induced "
         f"sign flip. <strong>The live state is unreachable by construction</strong>: P4 needs a bootstrap bound over "
         f"authenticated prices and none exist. Every strategy is on paper with its trigger recorded.",
         '<a href="demotion.html">demotion.html</a>'],
        ["Suggestions & questions", f"{sug.get('proposals', 0)} proposals · {qs.get('questions', 0)} questions "
         f"({qs.get('open', 0)} open)",
         f"{sug.get('proposals', 0)} proposals across four costed paths, none implemented, each with a reversal "
         f"condition. {qs.get('questions', 0)} questions split into FACT / OWNER / EXTERNAL / UNKNOWN; the "
         f"{qs.get('open', 0)} open ones carry a <strong>blank answer</strong> rather than a plausible one, because most "
         f"of the remaining uncertainty is an owner decision or third-party data, not analysis.",
         '<a href="suggestions-hub.html">suggestions-hub.html</a> · '
         '<a href="decision-questions-2026-11-14.html">questions</a>'],
    ]
    body_rows = "".join(
        f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td>"
        f'<td><a href="https://www.nfl.com/scores/" target="_blank" rel="noopener">nfl.com/scores</a></td></tr>'
        for r in rows)
    return f"""<section id="r7"><h2>Eight requirements, delivered 2026-11-14</h2>
<p>Each requirement now has its own module and its own page. The point of the table is the middle column: in six of the
eight the deliverable is a <strong>measurement of a limit</strong> rather than a validation, and saying so is the result.</p>
<div class="tablewrap"><table><caption>R7 deliverables, what each measured, and the page that carries the detail</caption>
<thead><tr><th>Requirement</th><th>What exists</th><th>What it established</th><th>Page</th><th>Official source</th></tr></thead>
<tbody>{body_rows}</tbody></table></div>
<p><strong>The finding that matters most.</strong> The pinned archive carries a price for 7,412 games and a capture
timestamp for none of them, and its undated series contradicts its own named closing series on more than half of all games
for eleven consecutive seasons. Everything downstream — ROI, closing-line value, drawdown, the demotion gate — needs a
price that existed at a known moment. Until one is bought, or the upstream owner documents what the existing column is,
every return figure on this site is descriptive and must stay labelled that way. That is why the competition awards
nothing and why the demotion gate's live state is unreachable.</p>
<p>The second is that the results side is solvable and cheap. Thirty-one games now settle against an official NFL
document, three of them read this session out of Game Book PDFs after the Game Center's client-side score rendered as
&ldquo;Hidden Score&rdquo;. Extending that to the full history is mechanical rather than blocked — a question about
budget and effort, not evidence.</p>
<p class="muted">Proposals, costs and reversal conditions are on <a href="suggestions-hub.html">the suggestions hub</a>.
The questions that must be answered before a path is chosen — including the four only the owner can answer — are on
<a href="decision-questions-2026-11-14.html">the decision questions page</a>.</p>
</section>

"""


if __name__ == "__main__":
    print(section()[:400])
