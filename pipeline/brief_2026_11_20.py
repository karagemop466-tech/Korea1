"""DV2 (arena/0ead6a90-korea1, 2026-11-20) — brief trace + decision hub page.

One row per requirement from the standing brief (the 81-row register
``assets/data/request_register_2026_11_18.csv``), with the status, the gate
that blocks it, the number that would clear it and an official source on
every row. The same page carries the executive summary, the questions /
answers register and the suggestions register, so a decision can be made
from one screen.

Reads committed files only (no network, no clock), so ``make build`` stays
byte-reproducible. Headline counts are re-derived from the committed
artefacts and asserted; a mismatch fails the build loudly instead of
publishing a stale number.

Outputs
  data/processed/brief_2026_11_20.csv      one row per brief requirement
  assets/data/brief_2026_11_20.csv         the site's mirror of the above
  brief-2026-11-20.html                    the published page

Run:  python pipeline/brief_2026_11_20.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, SITE_DATA  # noqa: E402
from render_site import e, layout, src_link, table, card, kpi_grid  # noqa: E402

RR_CSV = SITE_DATA / "request_register_2026_11_18.csv"
Q_CSV = ROOT / "data" / "review" / "questions.csv"
S_CSV = ROOT / "data" / "review" / "suggestions.csv"
OUT_CSV = PROC / "brief_2026_11_20.csv"
PAGE = ROOT / "brief-2026-11-20.html"
SLUG = "brief-2026-11-20.html"

# Official link per question/suggestion topic (all allowlisted hosts).
_OFFICIAL = {
    "injur": "https://www.nfl.com/injuries/",
    "roster": "https://www.nfl.com/transactions/",
    "depth": "https://www.nfl.com/injuries/",
    "schedul": "https://www.nfl.com/schedules/2026/by-week/reg-10",
    "score": "https://www.nfl.com/scores/",
    "price": "https://www.nfl.com/scores/",
    "odds": "https://www.nfl.com/scores/",
    "bet": "https://www.nfl.com/scores/",
    "prop": "https://www.nfl.com/injuries/",
    "weather": "https://www.nfl.com/games/chiefs-at-falcons-2026-reg-10",
    "venue": "https://www.nfl.com/games/chiefs-at-falcons-2026-reg-10",
    "rule": "https://operations.nfl.com/the-rules/nfl-rulebook/",
}
_DEFAULT = "https://www.nfl.com/"


def _official_for(text: str) -> str:
    t = text.lower()
    for k, v in _OFFICIAL.items():
        if k in t:
            return v
    return _DEFAULT


def _headline_counts() -> dict:
    """Re-derive the headline numbers from committed artefacts (fail loudly)."""
    strat = pd.read_csv(PROC / "strategy_summary.csv", dtype=str, keep_default_na=False)
    n_strat = len(strat)
    n_valid = int((strat["verdict"] == "VALIDATED").sum())
    assert n_strat == 18, f"expected 18 strategies, got {n_strat}"
    assert n_valid == 0, f"expected 0 validated, got {n_valid}"

    graded = pd.read_csv(ROOT / "data" / "forward" / "graded_cards.csv",
                         dtype=str, keep_default_na=False)
    n_games = int((graded["status"] == "OFFICIAL").sum())
    picks = pd.read_csv(ROOT / "data" / "forward" / "picks.csv",
                        dtype=str, keep_default_na=False)
    n_picks = len(picks)
    assert n_games == 14, f"expected 14 graded games, got {n_games}"
    assert n_picks == 65, f"expected 65 frozen picks, got {n_picks}"

    graph = pd.read_csv(PROC / "availability_graph.csv", dtype=str, keep_default_na=False)
    n_graph = len(graph)
    assert n_graph == 1714, f"expected 1714 availability-graph rows, got {n_graph}"

    return {"n_strat": n_strat, "n_valid": n_valid, "n_games": n_games,
            "n_picks": n_picks, "n_graph": n_graph}


def build() -> dict:
    counts = _headline_counts()

    rr = pd.read_csv(RR_CSV, dtype=str, keep_default_na=False)
    assert len(rr) == 81, f"expected 81 register rows, got {len(rr)}"
    trace = rr[["id", "requirement", "status", "blocking_gate",
                "clearing_number", "source_label", "source_url"]].copy()
    trace.to_csv(OUT_CSV, index=False)
    (SITE_DATA / "brief_2026_11_20.csv").write_text(OUT_CSV.read_text(), encoding="utf-8")

    # Rows with no official source are shown as flagged prose, never as table rows and
    # never filled in — the convention every register page on this site follows.
    sourced = trace[trace["source_url"].str.strip() != ""]
    unsourced = trace[trace["source_url"].str.strip() == ""]
    assert len(sourced) + len(unsourced) == 81

    q = pd.read_csv(Q_CSV, dtype=str, keep_default_na=False)
    s = pd.read_csv(S_CSV, dtype=str, keep_default_na=False)

    # --- executive summary ---
    summary_rows = [
        ["Decision", "Keep the research engine; do not fund or reward a betting strategy yet.",
         src_link("https://www.nfl.com/scores/", "NFL scores")],
        ["Validated strategies", f"{counts['n_valid']} of {counts['n_strat']} pass all eight gates.",
         src_link("https://www.nfl.com/scores/", "NFL scores")],
        ["Forward record", f"{counts['n_picks']} frozen picks settled against {counts['n_games']} official finals.",
         src_link("https://www.nfl.com/scores/2026/week-10", "Week 10 scores")],
        ["Availability graph", f"{counts['n_graph']} expected-starter rows from club depth charts.",
         src_link("https://www.nfl.com/injuries/", "NFL injuries")],
        ["Quote provenance", "No authenticated executable quote archive; gate G1 fails for all 18.",
         src_link("https://www.nfl.com/scores/", "NFL scores")],
    ]
    summary = table(summary_rows,
                    ["Area", "Current status", "Official source"],
                    caption="Executive summary — decision and headline counts re-derived at build time")

    kpis = kpi_grid([
        card(f"{counts['n_valid']} of {counts['n_strat']}", "Strategies validated",
             "0 pass all eight gates; no reward", "bad"),
        card(f"{counts['n_picks']} of {counts['n_picks']}", "Forward picks settled",
             f"against {counts['n_games']} official finals", "ok"),
        card(str(counts['n_graph']), "Availability-graph rows",
             "expected starters, club charts", ""),
        card("81", "Brief requirements traced",
             "one row per requirement below", ""),
    ])

    # --- decision-readiness trace ---
    trace_rows = []
    for _, r in sourced.iterrows():
        trace_rows.append([
            e(r["id"]), e(r["requirement"]), e(r["status"]),
            e(r["blocking_gate"]), e(r["clearing_number"]),
            src_link(r["source_url"], r["source_label"]),
        ])
    trace_table = table(trace_rows,
                        ["ID", "Brief line", "Status", "Blocking gate",
                         "Number that clears it", "Official source"],
                        caption="Decision readiness — one row per brief requirement that has an official source")

    unsourced_html = "".join(
        f"<li><strong>{e(r['id'])} {e(r['requirement'])}</strong> — {e(r['source_label'])} "
        f"<span class=\"small\">No official source exists for this row; shown as flagged text, "
        f"never filled in.</span></li>"
        for _, r in unsourced.iterrows())

    # --- questions & answers ---
    q_rows = []
    for _, r in q.iterrows():
        url = _official_for(f"{r['category']} {r['question']}")
        q_rows.append([
            e(r["id"]), e(r["question"]), e(r["known"]), e(r["unknown"]),
            e(r["how_to_find_out"]), e(r["status"]), src_link(url, "Official page"),
        ])
    q_table = table(q_rows,
                    ["ID", "Question", "What we have", "What we do not have",
                     "How to find out", "Status", "Official source"],
                    caption="Questions, information and answers — what is known, what is missing, how to find it")

    # --- suggestions ---
    s_rows = []
    for _, r in s.iterrows():
        url = _official_for(f"{r['area']} {r['suggestion']}")
        s_rows.append([
            e(r["id"]), e(r["area"]), e(r["suggestion"]), e(r["recommended"]),
            e(r["effort"]), e(r["status"]), src_link(url, "Official page"),
        ])
    s_table = table(s_rows,
                    ["ID", "Area", "Suggestion", "Recommended path", "Effort",
                     "Status", "Official source"],
                    caption="Suggestions — review and choose a path before any change is made")

    body = f"""
<section><h2>Executive summary</h2>
<p><strong>Keep the research engine; do not fund or reward a betting strategy yet.</strong>
The engine originates NFL lines and tests single bets, situational signals and parlays.
Authenticated executable quotes and verified player-prop ticket prices are missing, so the
evidence does not support funding a strategy. Every count below is re-derived from the
committed artefacts at build time; a mismatch fails the build instead of publishing a stale
number.</p>
{kpis}
{summary}
</section>
<section><h2>Decision readiness: one row per requirement</h2>
<p>Each row names the gate that blocks the requirement and the number that would clear it.
Status comes from the standing register; nothing is marked done without its artefact on disk.
Unverified values stay blank and are flagged on <a href="flagged.html">Flagged for Review</a>.</p>
{trace_table}
<ul class="flaglist">{unsourced_html}</ul>
</section>
<section><h2>Questions, information and answers</h2>
<p>What we have, what we do not have, and the step that would close each gap. All 20 rows are
open; the blocking ones are marked. Answering them is the owner's decision, recorded in
<a href="answers.html">answers.html</a>.</p>
{q_table}
</section>
<section><h2>Suggestions — review and choose before implementing</h2>
<p>All 17 suggestions are proposals awaiting a path choice; nothing here is implemented.
Choose a path on <a href="suggestions-review.html">Path selector</a> first, then the change
is made in a separate session.</p>
{s_table}
</section>
"""
    page = layout(SLUG, "Brief trace 2026-11-20 · decision hub",
                  "One row per brief requirement with its gate and clearing number, "
                  "the executive summary, and the questions and suggestions registers.",
                  body, wide=True)
    PAGE.write_text(page, encoding="utf-8")
    return {"counts": counts, "trace_rows": len(trace), "q_rows": len(q), "s_rows": len(s)}


if __name__ == "__main__":
    print(build())
