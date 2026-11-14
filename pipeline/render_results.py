"""Render `results.html` — the R7-02 verified results feed page."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r7_common import BLANK, E, RESULTS, link, num, read, table, week_url  # noqa: E402
from render_site import card, kpi_grid, layout  # noqa: E402
from common import ROOT, read_json  # noqa: E402

MAX_ROWS = 130
TIER_PILL = {
    "OFFICIAL_GAME_BOOK": ("ok", "Game Book PDF"),
    "OFFICIAL_GAME_CENTER": ("ok", "Game Center"),
    "OFFICIAL_SCORES_PAGE": ("ok", "Scores page"),
    "VERIFIED_PRIOR_SESSION": ("ok", "prior session"),
    "UNVERIFIED": ("unverified", "none"),
}


def body() -> str:
    summ = read_json(RESULTS / "results_summary.json")
    feed = read(RESULTS / "results_feed.csv")
    audit = read(RESULTS / "results_audit.csv")

    cards = kpi_grid([
        card(f"{summ['rows']:,}", "games listed", "nothing dropped for lack of a source"),
        card(f"{summ['settleable']:,}", "settleable", "an official score was read", "ok"),
        card(f"{summ['unverified']:,}", "settleable: no", "score blank, excluded from settlement", "warn"),
        card(f"{summ['by_tier']['OFFICIAL_GAME_BOOK']}", "from a Game Book PDF",
             "machine-readable NFL document"),
        card(f"{len(summ['seasons_verified'])}", "season(s) with a verified score",
             str(summ["seasons_verified"])),
    ])

    # ---- verified rows only, so the table is evidence and not a list --------
    ver = feed[feed.settleable == "YES"].sort_values(["season", "week", "game_id"])
    vrow = []
    for r in ver.itertuples():
        kind, label = TIER_PILL[r.tier]
        vrow.append([
            f'<a href="{E(r.page_url)}" target="_blank" rel="noopener">{E(r.game_id)}</a>',
            E(r.season), E(r.week),
            f"{E(r.away_team)} {int(r.away_score)} — {E(r.home_team)} {int(r.home_score)}",
            num(r.official_result, 0),
            num(r.official_total, 0, signed=False),
            f'<span class="pill {kind}">{E(label)}</span>',
            f'<a href="{E(r.evidence_url)}" target="_blank" rel="noopener">evidence read</a>',
            f'<a href="{week_url(int(r.season), int(r.week))}" target="_blank" rel="noopener">official scores</a>',
        ])

    # ---- the agreement audit ----------------------------------------------
    agree = audit[audit.agreement != "NOT COMPARED (no official read)"]
    arow = []
    for r in agree.itertuples():
        arow.append([
            f'<a href="{week_url(int(r.season), int(r.week))}" target="_blank" rel="noopener">{E(r.game_id)}</a>',
            num(r.away_score, 0), num(r.home_score, 0),
            num(r.archive_away, 0), num(r.archive_home, 0),
            f'<span class="pill {"ok" if r.agreement == "MATCH" else "unverified"}">{E(r.agreement)}</span>',
            f'<a href="{week_url(int(r.season), int(r.week))}" target="_blank" rel="noopener">official scores</a>',
        ])

    return f"""
<section><h2>Why a results feed is the prerequisite, not a nicety</h2>
<p>A backtest is a claim of the form "this rule, applied to these decisions, would have produced this
return". Two inputs are required and they fail independently: the <strong>price at decision time</strong>
(that is <a href="prices.html">prices.html</a>) and the <strong>settled outcome</strong> (this page).
Without an official outcome the ROI denominator is unknown, and an archive score is not an official
observation.</p>
{cards}
<p class="flag info">The feed lists every played game in the pinned archive —
<strong>including the {summ['unverified']:,} whose official score has not been read</strong>. Dropping
them would silently shrink every backtest denominator and inflate every ROI.</p>
</section>

<section><h2>The tiers, and the discovery that forced them</h2>
<p>During this session the official Game Center pages for three games were fetched directly:
<code>commanders-at-giants-2026-reg-10</code>, <code>cardinals-at-rams-2014-reg-15</code> and
<code>bengals-at-falcons-2026-reg-9</code>. All three rendered <strong>"Hidden Score"</strong> instead of
a number, because the score is injected client-side. A feed that transcribed page text would have
published "Hidden Score", and a feed that guessed would have been inventing a result.</p>
<p>The same three Game Centers link a <strong>National Football League Game Summary</strong> PDF — the
Game Book. Those PDFs are machine-readable and print the score in a quarter-by-quarter table. Every
score in the top tier below was read from that document, with the PDF URL kept as the evidence link.</p>
</section>

<section><h2>Verified results</h2>
<p>{len(ver)} games carry an official score. The <em>evidence read</em> column opens the exact document
the number came from; the <em>official scores</em> column opens the official week page for that game.</p>
{table(vrow, ["Game", "Season", "Week", "Final (away — home)", "Margin", "Total", "Evidence tier",
             "Document read", "Official scores"],
       caption="Every result this project may settle against; 31 games across 2014, 2026 week 8–10")}
<p><a href="data/results/results_feed.csv">Download the full feed (CSV, all rows)</a></p>
</section>

<section><h2>Official result vs the archive's own score</h2>
<p>An independent check, not a source of truth. {len(agree)} of the verified games could be compared with
the pinned archive; <strong>{int((audit.agreement == "ARCHIVE BLANK").sum())} could not, because the
archive has not settled them</strong>. A blank archive cell is not a disagreement, and treating it as one
was a real defect in the first run of this audit — it reported 29 false conflicts.</p>
{table(arow, ["Game", "Official away", "Official home", "Archive away", "Archive home", "Agreement",
              "Official scores"],
       caption="Agreement check; a blank archive cell is labelled, never counted as a conflict")}
</section>

<section><h2>What this unlocks, and what it still does not</h2>
<ul class="findings">
<li><strong>Unlocked:</strong> for these 31 games, margin, total, winner and push can now be settled
against an official document instead of a community transcription.</li>
<li><strong>Still blocked:</strong> a backtest over 31 games is not a backtest. The 20-year history the
model is fitted on has <em>no</em> per-game official score linked, only the archive's transcription.
Linking one official Game Book per historical game is mechanical but is 7,300+ document reads, and the
rate limit is the agent's page budget, not the data.</li>
<li><strong>Still blocked:</strong> ROI needs both a price and a result. The results side is solved for
31 games; the price side is solved for zero. Both must be solved before a return is computable at all.</li>
</ul>
<p>The concrete next step is stated as a question with a cost on
<a href="decision-questions-2026-11-14.html">the decision questions page</a> rather than acted on
unilaterally here.</p>
</section>"""


def main() -> None:
    (ROOT / "results.html").write_text(
        layout("results.html", "Verified results feed",
               "One settlement-grade outcome per game, each with the official document it was read from.",
               body(), wide=True))
    print("wrote results.html")


if __name__ == "__main__":
    main()
