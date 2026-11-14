"""Render `prices.html` — the R7-01 price-snapshot store page.

Every table on this page is flat: a single header row followed by data rows, and
every row links the official NFL scores page for its own season. That is the
official source every number on the page is ultimately about — the score the
price was attached to — and it is why no row is merely a label.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r7_common import (BLANK, E, PRICES, link, num, official_col, pct, pill, read,  # noqa: E402
                       season_url, table)
from render_site import card, kpi_grid, layout  # noqa: E402
from common import ROOT, read_json  # noqa: E402

MAX_ROWS = 90


def body() -> str:
    prov = read_json(PRICES / "price_provenance.json")
    facts = prov["facts"]
    inv = read(PRICES / "price_inventory.csv")
    snap = read(PRICES / "price_snapshots.csv", low_memory=False)

    cards = kpi_grid([
        card(f"{facts['rows']:,}", "stored price rows", "game × market × side × kind"),
        card(f"{facts['games_by_kind']['UNDATED']:,}", "games · undated price",
             "kind not asserted by the source", "warn"),
        card(f"{facts['games_by_kind']['INITIAL']:,}", "games with an opener",
             "2021 only · one book · WSGT"),
        card(f"{facts['games_by_kind']['CLOSING']:,}", "games with a closing print",
             "2006–2018 · the file name states closing"),
        card(f"{facts['capture_time_rows']}", "rows with a capture time",
             "no source in the pin carries one", "warn"),
    ])

    # ---- instrument table --------------------------------------------------
    kind_source = {"games.csv": "community", "initial_lines.csv": "initial",
                   "closing_lines.csv": "closing"}
    prow = []
    for key, p in prov["sources"].items():
        prow.append([
            link(kind_source[p["file"]]),
            pill(p["claims_kind"], "ok" if p["claims_kind"] != "UNDATED" else "unverified"),
            "yes" if p["timestamp_field"] else "<strong>no</strong>",
            E(", ".join(p["documented_columns"])) if p["documented_columns"] else "<strong>none</strong>",
            E(p["note"]),
            f'<a href="{season_url(2021)}" target="_blank" rel="noopener">nfl.com/scores</a>',
        ])

    # ---- coverage ----------------------------------------------------------
    spread = inv[inv.market == "SPREAD"].copy()
    crow = []
    for r in spread.itertuples():
        crow.append([
            f'<a href="{season_url(int(r.season))}" target="_blank" rel="noopener">{int(r.season)}</a>',
            num(r.games_undated, 0, signed=False),
            num(r.games_initial, 0, signed=False),
            num(r.games_closing, 0, signed=False),
            num(r.undated_vs_closing_overlap, 0, signed=False),
            num(r.undated_vs_closing_disagreements, 0, signed=False),
            num(r.undated_vs_closing_median_abs_gap, 2),
            num(r.initial_to_closing_pairs, 0, signed=False),
            num(r.initial_to_closing_mean_move, 3),
            pill("BLANK", "unverified"),
            f'<a href="{season_url(int(r.season))}" target="_blank" rel="noopener">season scores</a>',
        ])

    # ---- store sample ------------------------------------------------------
    sample = snap[(snap.season >= 2021) & snap.market.isin(["SPREAD", "TOTAL", "MONEYLINE"])] \
        .sort_values(["season", "week", "game_id", "market", "side", "snapshot_kind"]).head(MAX_ROWS)
    srow = []
    for r in sample.itertuples():
        srow.append([
            E(r.game_id), E(r.market), E(r.side),
            (E(r.team) if str(r.team) not in ("", "nan") else
             '<span class="blank" aria-label="not applicable: a total has no team"></span>'),
            pill(r.snapshot_kind, "ok" if r.snapshot_kind != "UNDATED" else "unverified"),
            num(r.line, 1), num(r.price_american, 0),
            (E(r.book) if str(r.book) not in ("", "nan") else BLANK),
            "no" if not r.capture_time_known else E(r.captured_utc),
            link({"games_csv": "community", "initial_lines_csv": "initial",
                  "closing_lines_csv": "closing"}[r.source_key]),
            f'<a href="{season_url(int(r.season))}" target="_blank" rel="noopener">week scores</a>',
        ])

    return f"""
<section><h2>What this store is</h2>
<p>One row per <strong>game × market × side × snapshot kind</strong>. Every row names the file that
recorded it. A snapshot kind is written down only when that file asserts it; when a file carries no
timestamp and no dictionary entry, the row is marked <code>UNDATED</code> rather than being called an
open or a close.</p>
{cards}
</section>

<section><h2>The three source instruments, and what each one actually claims</h2>
<p>The decision-relevant column is <strong>timestamp field</strong>. No source in the pinned archive
carries a capture time, and the pinned data dictionary documents none of the price columns. A number
without a time cannot be an opening number or a closing number; it is just a number.</p>
{table(prow, ["Source file", "Kind it claims", "Timestamp field", "Documented columns in the pin",
             "What it provides", "Official scores"],
       caption="Every instrument in the store, with the kind its own file asserts — nothing upgraded")}
<p class="small">Dictionary check performed by reading {link('dictionary')} at the pinned commit: the
games section stops at stadium and referee fields and never defines <code>spread_line</code>,
<code>total_line</code>, the moneylines or any price column.</p>
</section>

<section><h2>Coverage and disagreement, season by season (side market)</h2>
<p><strong>Disagreements</strong> counts games where the undated file and the file named
<em>closing</em> state a different handicap for the same game and side. It is an observation about the
archive, not line movement: an undated series has no position on a clock, so the only defensible
reading is that at most one of the two can be right and this project cannot say which.</p>
<p>The result is blunt. From 2006 to 2016 the two series disagree on <strong>more than half of all
games</strong>; from 2017 they agree almost exactly. Two files that are supposed to describe the same
market do not. <strong>Opening-to-closing movement cannot be measured anywhere in this pin</strong>,
because no game carries two instruments of known, different kind.</p>
{table(crow, ["Season", "Undated", "Initial", "Closing", "Overlap", "Disagreements", "Median gap",
              "Open→close pairs", "Mean move", "Movement", "Official scores"],
       caption="Only the UNDATED and CLOSING series ever coexist; no open→close pair exists in any season")}
<p class="small">Movement is blank in every season by construction, not by omission. For 2021 an opener
exists (272 games) but no closing print does; for 2006–2018 a closing print exists but the second series
is undated. The two never meet on the same game.</p>
</section>

<section><h2>Sample of the store</h2>
<p>{len(sample)} of {facts['rows']:,} rows, newest seasons first. A blank cell is a value the source did
not state.</p>
{table(srow, ["Game", "Market", "Side", "Team", "Snapshot kind", "Line", "Price", "Book",
             "Capture time", "Source", "Official scores"],
       caption="Price-snapshot store — undated rows are labelled, never inferred")}
<p><a href="data/prices/price_snapshots.csv">Download the full store (CSV)</a> ·
<a href="data/prices/price_inventory.csv">coverage and disagreement (CSV)</a> ·
<a href="data/prices/price_provenance.json">provenance register (JSON)</a></p>
</section>

<section><h2>What would close the gap</h2>
<ol class="findings">
<li><strong>A timestamped price feed.</strong> One authenticated open and one authenticated close per
market, with the book and the limit. This is the only route to a computable closing-line value, and it
is a paid item — an owner decision, not an agent one.</li>
<li><strong>A second named instrument for 2006–2016.</strong> A file whose own name and dictionary entry
state a different snapshot kind would make the movement column non-blank for those seasons.</li>
<li><strong>A dictionary entry for the existing price columns.</strong> Even without a timestamp, an
upstream statement of what <code>spread_line</code> is would let the store assert a kind instead of
<code>UNDATED</code>.</li>
</ol>
<p>Until then the store does the only thing it can honestly do: it records each number with the file
that produced it, and refuses to name a time nobody published.</p>
</section>"""


def main() -> None:
    (ROOT / "prices.html").write_text(
        layout("prices.html", "Price snapshots",
               "Opening and closing numbers for every market we originate — recorded per source, never inferred.",
               body(), wide=True))
    print("wrote prices.html")


if __name__ == "__main__":
    main()
