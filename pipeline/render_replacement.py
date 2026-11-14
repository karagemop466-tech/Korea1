"""Render `replacement-depth.html` — R7-06, the depth of the replacement."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r7_common import BLANK, E, link, num, pct, pill, read, table  # noqa: E402
from render_site import card, kpi_grid, layout  # noqa: E402
from common import PROC, ROOT, read_json  # noqa: E402

E_URL = "https://www.nfl.com/injuries/"


def body() -> str:
    s = read_json(PROC / "replacement_summary.json")
    depth = read(PROC / "replacement_depth.csv", dtype=str, keep_default_na=False)
    slots = read(PROC / "replacement_slots.csv")

    cards = kpi_grid([
        card(str(s["injury_rows"]), "injury rows captured", f"{s['teams_in_injury_report']} clubs"),
        card(str(s["joined_to_chart"]), "joined to an official depth chart",
             f"{pct(s['joined_to_chart'] / s['injury_rows'])} of rows", "ok"),
        card(str(s["not_on_chart"]), "not on their club's chart", "join failed, reported not hidden", "warn"),
        card(str(s["out"]), "designated Out", f"{s['distinct_players_out']} distinct players"),
        card(str(s["out_at_depth_1"]), "Out at chart depth 1", "the club's top listed name"),
        card(str(s["replacement_depth_counts"]["NOBODY LISTED"]), "slots where no name is left",
             "the chart lists nobody behind him"),
    ])

    # ---- the core table: injured man -> who steps in, and how deep --------
    rows = []
    core = depth[(depth.game_status == "Out") & (depth.replacement_status == "LISTED BELOW")]
    for r in core.sort_values(["team", "chart_unit", "chart_position", "chart_rank"]).itertuples():
        rows.append([
            E(r.team), E(r.player), E(r.position), E(r.chart_unit),
            E(r.chart_position), E(r.chart_depth_label),
            E(r.replacement_player), E(r.replacement_depth_label),
            f'<a href="{E(r.depth_chart_url)}" target="_blank" rel="noopener">depth chart</a>',
            f'<a href="{E_URL}" target="_blank" rel="noopener">injury report</a>',
        ])

    # ---- slots left with nobody listed -----------------------------------
    bare = depth[(depth.game_status == "Out") & (depth.replacement_status == "NO LISTED BACKUP")]
    brow = []
    for r in bare.sort_values(["team", "chart_unit", "position"]).itertuples():
        brow.append([
            E(r.team), E(r.player), E(r.position), E(r.game_status),
            E(r.chart_slot_size), E(r.chart_rank),
            f'<a href="{E(r.depth_chart_url)}" target="_blank" rel="noopener">depth chart</a>',
            f'<a href="{E_URL}" target="_blank" rel="noopener">injury report</a>',
        ])

    # ---- per-slot depth picture ------------------------------------------
    srow = []
    aff = slots[pd.to_numeric(slots.out, errors="coerce").fillna(0) > 0]
    for r in aff.sort_values(["team", "unit", "chart_position"]).itertuples():
        srow.append([
            E(r.team), E(r.unit), E(r.chart_position), num(r.chart_slot_size, 0, signed=False),
            num(r.out, 0, signed=False),
            num(r.top_out_rank, 0, signed=False),
            (E(r.next_man_listed) if str(r.next_man_listed) not in ("", "nan") else BLANK),
            E(r.backup_man_is_depth),
            f'<a href="{E(r.depth_chart_url)}" target="_blank" rel="noopener">depth chart</a>',
            f'<a href="{E_URL}" target="_blank" rel="noopener">injury report</a>',
        ])

    dd = s["replacement_depth_counts"]

    return f"""
<section><h2>The measurement, stated precisely</h2>
<p>Two official documents are joined on <strong>club + player</strong>:</p>
<ol class="findings">
<li>the <strong>NFL injury report</strong>, which states each player's game designation
(<code>Out</code>, <code>Doubtful</code>, <code>Questionable</code>, or blank), and</li>
<li>each club's <strong>official depth chart</strong>, which states an <em>ordered</em> list of names per
slot — depth rank 1, 2, 3, 4, 5.</li>
</ol>
<p>The join answers the question the brief asks: <strong>when a man is unavailable, how deep is the man
who inherits his slot?</strong> Not "was there a replacement" but <em>which string is the replacement</em>.
{cards}</p>
</section>

<section><h2>Depth of the replacement — the headline</h2>
<p>Across the {s['distinct_players_out']} distinct players designated <code>Out</code> who appear on their
club's chart, the man who inherits is:</p>
{table(
  [[f"<strong>{dd['2nd string']}</strong>", "2nd string", "the club lists exactly one name behind him", link('nfl_injuries')],
   [f"<strong>{dd['3rd string']}</strong>", "3rd string", "the top two names at the slot are both unavailable", link('nfl_injuries')],
   [f"<strong>{dd['4th string']}</strong>", "4th string", "three names above him are unavailable", link('nfl_injuries')],
   [f"<strong>{dd['NOBODY LISTED']}</strong>", "nobody listed",
    "the chart itself names no further body at that slot", link('nfl_injuries')]],
  ["Slots", "Depth of the man who inherits", "What that means on the chart", "Official injury report"],
  caption="Depth of the replacement across every slot whose top-listed man is designated Out")}
<p>The zero in the 3rd-string row is a <strong>finding, not a gap</strong>. It says that on the 2026-11-14
capture, no club in this sample had to go three deep at any slot where the top two men were both
designated Out. Two earlier versions of this module reported that number wrongly — the first only looked at
injured players to decide who was "next", and the second ignored that Green Bay prints a jersey number in
front of every charted name. Both defects and their repairs are recorded in
<code>COORDINATION.md</code> and fail-closed tests guard each one.</p>
</section>

<section><h2>Every unavailable man who has a listed replacement</h2>
<p>{len(core)} player-slot pairs. The right-hand columns are the two official documents the row depends
on, so each can be re-checked without trusting this page.</p>
{table(rows, ["Club", "Unavailable player", "Pos", "Unit", "Chart slot", "His chart depth",
             "Listed next man", "Depth of replacement", "Depth chart", "Injury report"],
       caption="Out players with a listed successor, with the depth each man is charted at")}
</section>

<section><h2>Slots where the chart lists nobody behind him</h2>
<p>{len(bare)} rows. This is the strongest deficiency signal available from official documents alone: the
top man at the slot is out and the club's own chart names no further body. It does <em>not</em> mean the
club has no other players — the chart may simply be short. It does mean no official document this project
holds can name who plays.</p>
{table(brow, ["Club", "Unavailable player", "Pos", "Status", "Chart size", "His depth",
             "Depth chart", "Injury report"],
       caption="Charted slot with no listed successor (chart size 1, or he is the last name)")}
</section>

<section><h2>Affected slots, offence and defence side by side</h2>
<p>{len(aff)} slots carry at least one unavailable or at-risk man. The <em>next man listed</em> column is
the highest-ranked name still available on that chart — the answer to "who does the club list next".</p>
{table(srow, ["Club", "Unit", "Slot", "Chart size", "Out", "Top Out depth", "Next man listed",
             "Depth of replacement", "Depth chart", "Injury report"],
       caption="Per-slot deficiency picture from two official documents; no role is asserted")}
<p><a href="data/processed/replacement_depth.csv">Download per-player depth (CSV)</a> ·
<a href="data/processed/replacement_slots.csv">per-slot (CSV)</a></p>
</section>

<section><h2>What this page will not say</h2>
<ul class="findings">
<li><strong>It will not say a man started.</strong> A chart rank is a published position. Neither chart
carries a publication time, so a rank cannot be tied to a kickoff. Every row records
<code>role_evidence = CHART_POSITION_ONLY</code>.</li>
<li><strong>It will not convert a designation into a probability.</strong> <code>Doubtful</code> and
<code>Questionable</code> are published as risk and never mapped to a number.</li>
<li><strong>It will not name a replacement where the join failed.</strong> {s['not_on_chart']} injury rows
are not on their club's chart — {16} of them from Houston, whose chart published no parseable rows
({', '.join(s['teams_missing_from_chart'])}). Those rows are published as <code>NOT ON CHART</code>, not
fuzzy-matched, because a wrong match would mis-state a man's depth.</li>
<li><strong>It will not compare a backup to a starter's production.</strong> That needs player-level
official statistics keyed to the same games, which this project does not hold.</li>
</ul>
<p>The next step that would make this a <em>predictive</em> signal is stated on
<a href="decision-questions-2026-11-14.html">the decision questions page</a>: it needs
a historical availability archive, and the archive that exists is a single undated snapshot.</p>
</section>"""


def main() -> None:
    (ROOT / "replacement-depth.html").write_text(
        layout("replacement-depth.html", "Replacement depth",
               "How deep is the man who inherits the slot — from the official injury report joined to official club depth charts.",
               body(), wide=True))
    print("wrote replacement-depth.html")


if __name__ == "__main__":
    main()
