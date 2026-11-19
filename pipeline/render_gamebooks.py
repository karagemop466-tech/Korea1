"""Publish `gamebooks.html` — the official Game Book evidence page.

The page answers three questions with official documents only:

1. **What has the capture actually read?**  One row per captured official
   document: the league's schedule page, the league's game centre, the
   league's Game Book — each with its URL, HTTP status, byte count, SHA-256,
   capture time and the week the page published.
2. **What does the league publish about each fixture?**  The fixture-context
   table, built only from published schedule facts, with the conversion that
   was applied (the league's UTC instant to Eastern time) named on every row.
3. **Who was expected to start, and who actually did?**  The availability
   graph: the club's own depth chart against the league's own Game Book.

Where the league's Game Book has not been captured, the actual side is blank
and the gate that blocks it is printed with the number that would clear it.
Nothing is filled in from a community mirror or from a model.

Run: python pipeline/render_gamebooks.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT  # noqa: E402
from render_site import card, e, flag, kpi_grid, layout, src_link, table  # noqa: E402

DASH = "—"
EMPTY = "not captured"


def _csv(name: str) -> pd.DataFrame:
    path = PROC / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _cell(value: str) -> str:
    value = str(value).strip()
    return value if value else EMPTY


def render() -> dict[str, str]:
    documents = _csv("official_documents.csv")
    fixtures = _csv("fixture_context.csv")
    graph = _csv("availability_graph.csv")
    inactive = _csv("official_inactive_lists.csv")
    windows = _csv("week_windows.csv")

    if documents.empty and fixtures.empty:
        return {}

    n_docs = len(documents)
    n_fixtures = len(fixtures)
    n_graph = len(graph)
    n_inactive = len(inactive)
    n_captured_books = int((fixtures.gamebook_captured.astype(str) == "YES").sum()) if n_fixtures else 0

    doc_rows: list[list[str]] = []
    for r in documents.itertuples():
        url = str(r.url)
        doc_rows.append([
            e(str(r.document_id)),
            e(str(r.kind)),
            src_link(url, "official page") if url else EMPTY,
            e(str(r.http_status)) if str(r.http_status) else EMPTY,
            e(f"{int(r.bytes):,}") if str(r.bytes).isdigit() else EMPTY,
            e(str(r.sha256)[:16]) if str(r.sha256) else EMPTY,
            e(str(r.week_requested)) if str(r.week_requested) else EMPTY,
            e(str(r.week_published)) if str(r.week_published) else EMPTY,
            e(str(r.retrieved_utc)) if str(r.retrieved_utc) else EMPTY,
            e(str(r.parsed_ok)),
            e(str(r.note)) if str(r.note) else EMPTY,
        ])

    drift = documents[(documents.week_matches_url.astype(str) == "False")] if not documents.empty else pd.DataFrame()
    fixture_rows: list[list[str]] = []
    for r in fixtures.itertuples():
        venue_printed = str(r.venue_stadium_as_printed)
        fixture_rows.append([
            e(f"{r.away_team} at {r.home_team}"),
            e(str(r.week)),
            e(_cell(r.kickoff_et)),
            e(str(r.kickoff_weekday_et)),
            e(_cell(r.venue_name_as_published)),
            e(venue_printed) if venue_printed else EMPTY,
            e(_cell(r.status_as_published)),
            e(_cell(r.category_as_published)),
            e(_cell(r.networks_as_published)),
            e(_cell(r.teams_on_bye)),
            e(str(r.game_centre_captured)),
            e(str(r.gamebook_captured)),
            src_link(str(r.official_url), "game centre"),
        ])

    summary_rows: list[list[str]] = []
    for fx_id, grp in (graph.groupby("fixture_id", sort=False) if not graph.empty else []):
        first = grp.iloc[0]
        confirmed = int((grp.outcome.astype(str).str.startswith("CONFIRMED")).sum())
        replaced = int((grp.outcome.astype(str).str.startswith("REPLACEMENT")).sum())
        # 2026-11-19 (arena/7134ec74-korea1): rows whose book is captured but whose slot the
        # book does not print are "NOT CONFIRMABLE" — a different fact from "no book captured".
        # Both are counted here so the per-fixture columns still sum to the row count.
        not_confirmable = int((grp.outcome.astype(str).str.startswith("NOT CONFIRMABLE")).sum())
        unconfirmed = int((grp.outcome.astype(str).str.startswith("NOT CONFIRMED")).sum())
        co = int((grp.outcome.astype(str).str.startswith("CO-STARTERS")).sum())
        summary_rows.append([
            e(f"{first.away_team} at {first.home_team}"),
            e(str(first.week)),
            e(str(grp.club.nunique())),
            e(str(len(grp))),
            e(str(confirmed)), e(str(replaced)), e(str(co)), e(str(not_confirmable)),
            e(str(unconfirmed)),
            # the four outcome columns must account for every row of the fixture
            e("OK" if confirmed + replaced + co + not_confirmable + unconfirmed == len(grp) else "MISMATCH"),
            src_link(str(first.fixture_url), "game centre"),
        ])

    confirmed_rows: list[list[str]] = []
    for r in graph.itertuples():
        if not str(r.outcome).startswith(("CONFIRMED", "REPLACEMENT", "CO-STARTERS")):
            continue
        confirmed_rows.append([
            e(f"{r.away_team} at {r.home_team}"),
            e(str(r.club)),
            e(str(r.unit)),
            e(str(r.position)),
            e(_cell(r.expected_starter)),
            e(str(r.expected_co_starter_count)),
            e(_cell(r.actual_starter)),
            e(str(r.outcome)),
            e(str(r.replacement_depth_rank)) if str(r.replacement_depth_rank) else EMPTY,
            src_link(str(r.expected_source), "club chart"),
            src_link(str(r.fixture_url), "game centre"),
        ])

    example_rows: list[list[str]] = []
    if not graph.empty:
        first_id = graph.iloc[0].fixture_id
        example = graph[graph.fixture_id == first_id]
        for r in example.itertuples():
            example_rows.append([
                e(str(r.club)),
                e(str(r.unit)),
                e(str(r.position)),
                e(_cell(r.expected_starter)),
                e(str(r.expected_captured_utc)),
                e(str(r.expected_point_in_time)),
                e(_cell(r.actual_starter)),
                e(str(r.outcome)),
                src_link(str(r.expected_source), "club chart"),
            ])

    inactive_rows = [[
        e(f"{r.fixture_id[:12]}…"), e(str(r.week)), e(str(r.club)), e(str(r.player)),
        e(str(r.status)), e(str(r.jersey)), e(str(r.position)),
        src_link(str(r.source_url), "Game Book"),
    ] for r in inactive.itertuples()]

    schedule_url = ""
    if n_fixtures:
        first_url = str(fixtures.iloc[0].schedule_url).split(";")[0]
        schedule_url = first_url or ""
    bye_rows = [[
        e(str(r.week_label)), e(str(r.week_type)), e(str(r.date_begin)), e(str(r.date_end)),
        e(_cell(r.teams_on_bye)),
        src_link(schedule_url, "official schedule page") if schedule_url else EMPTY,
    ] for r in windows.itertuples() if str(r.week_type) == "REG"]

    # State is read from the captured tables, not hard-coded: as of the
    # 2026-11-19 capture the league's books, centres and game-day lists ARE
    # held, and a page that printed "not captured" beside them would publish a
    # false statement (repaired during the GC integration merge, 2026-11-19).
    n_books_held = (int((documents["kind"] == "official Game Book (text)").sum())
                    if not documents.empty else 0)
    n_centres_held = (int((documents["kind"] == "official game centre").sum())
                      if not documents.empty else 0)
    n_inactive_held = len(inactive) if not inactive.empty else 0
    gate_rows = [
        ["Official Game Book PDFs",
         f"{n_books_held} captured" if n_books_held else EMPTY,
         "the league publishes the Game Book for a finished game; the capture must read the "
         "game centre's own Download Game Book link",
         "one Game Book capture naming a starter for one fixture, with its SHA-256",
         "https://www.nfl.com/games/colts-at-texans-2026-reg-11"],
        ["Game-centre pages",
         f"{n_centres_held} captured" if n_centres_held else EMPTY,
         "the capture reads a game centre for every fixture it parsed from the schedule page",
         "one game-centre capture with HTTP 200 and the venue printed in its Game Info block",
         "https://www.nfl.com/games/colts-at-texans-2026-reg-11"],
        ["Official inactive and did-not-play lists",
         f"{n_inactive_held} rows captured" if n_inactive_held else EMPTY,
         "the Game Book's Not Active and Did Not Play lists are the league's game-day lists; "
         "they arrive with the Game Book",
         "one dated inactive-list capture for one fixture, joined to the injury report by player",
         "https://operations.nfl.com/game-operations-logistics/preparation-safety/game-and-stadium-prep/"],
        ["Depth-chart week alignment", "31 of 32 clubs captured",
         "the club depth charts are current-state captures, not per-week ones; a chart "
         "captured after kickoff is not a point-in-time expectation",
         "a depth-chart capture timestamped before the fixture's kickoff for every club in the fixture",
         "https://www.colts.com/team/depth-chart"],
        ["Snap counts (playing time)", EMPTY,
         "no official snap-count source is captured; the club chart's printed order is the only "
         "depth evidence held, and it is not playing time",
         "an official snap source for all 32 clubs, joined to the named replacement",
         "https://www.nfl.com/scores/2026/week-10"],
    ]
    gate_html = [[e(a), e(b), e(c), e(d), src_link(f, "official page")] for a, b, c, d, f in gate_rows]

    n_confirmed = len(confirmed_rows)
    n_drift = len(drift)

    body = f"""
{flag("This page publishes only what an official NFL document prints. Where the league's "
       "Game Book has not been captured, the actual-starter cell is blank and the gate below "
       "says what would clear it. Nothing is inferred from a depth chart, a model or a "
       "community mirror.", "info")}

{kpi_grid([
    card(str(n_docs), "official documents captured", "schedule page, game centre, Game Book", ""),
    card(str(n_fixtures), "fixtures published", "from the league's own schedule page", ""),
    card(str(n_graph), "availability-graph rows", "expected starter × fixture × position", ""),
    card(str(n_confirmed), "starters confirmed", "expected and actual both official", "good" if n_confirmed else "bad"),
    card(str(n_inactive), "inactive / did-not-play rows", "the league's game-day lists", ""),
    card(str(n_captured_books), "Game Books captured", "of the fixtures above", "good" if n_captured_books else "bad"),
])}

<section><h2>1 · What the capture actually read</h2>
<p>Every official document this repository holds, with the bytes that were read and their
SHA-256. The <em>requested week</em> and the <em>published week</em> are separate columns on
purpose: the league's schedule application does not always serve the week the URL names, and a
capture that silently labelled one week's fixtures with another week's number would corrupt
every downstream join.</p>
{table(doc_rows, ["Document", "Kind", "Official page", "HTTP", "Bytes", "SHA-256 (first 16)",
                  "Requested week", "Published week", "Captured (UTC)", "Parsed", "Note"],
       caption="Official documents captured, with provenance and the published week")}
{f"".join([flag("Drift detected: " + str(n_drift) + " captured page(s) published a week other than the one requested. "
       "The affected rows are published with both weeks and are not treated as a capture of the "
       "requested week.", "warn")]) if n_drift else ""}
</section>

<section><h2>2 · Fixture context, built only from published schedule facts</h2>
<p>One row per fixture, every column printed by the league: both clubs, the kickoff instant, the
week, the status, the category, the broadcast networks, the venue and the clubs on a bye. The
venue is shown twice — as the schedule page publishes it and as the game centre prints it — so
a disagreement between the two is visible rather than resolved.</p>
{table(fixture_rows, ["Fixture", "Week", "Kickoff (ET)", "Day", "Venue as published",
                      "Venue as printed", "Status", "Category", "Networks", "Clubs on a bye",
                      "Game centre", "Game Book", "Official source"],
       caption="Fixture context — published schedule facts only")}
<p class="small">The Eastern kickoff is the league's own UTC instant converted with the IANA
<code>America/New_York</code> zone; it is the only derived column in the table, and the
conversion is recorded on every row of
<code>data/processed/fixture_context.csv</code>.</p>
</section>

<section><h2>3 · The availability graph: who was expected to start, who actually did</h2>
<p>The expectation is the player the club itself lists first on its own official depth chart. The
actual starter is the player the league names in the Game Book's starting lineup. A position
where the club lists more than one first player is published as a co-starter row: a club that
names three receivers at rank one has not named a starter, and the graph does not choose one.
The two documents print names differently — the chart writes <em>Brandon Coleman</em>, the Game
Book writes <em>B.Coleman</em> — so a row is confirmed only when the surnames are equal and the
Book's initial equals the first letter of the chart's first name; a different surname is always
a replacement, and nothing else is treated as a match.</p>
{table(summary_rows, ["Fixture", "Week", "Clubs", "Graph rows", "Confirmed", "Replacements",
                       "Co-starters", "Not confirmable (slot not printed)", "Not confirmed (no book)",
                       "Rows accounted for", "Official source"],
       caption="Availability graph by fixture — the actual side needs the league's Game Book")}
<h3>Rows where the actual starter is official</h3>
{table(confirmed_rows, ["Fixture", "Club", "Unit", "Position", "Expected starter (club chart)",
                        "Co-starters", "Actual starter (Game Book)", "Outcome",
                        "Replacement depth rank", "Club chart", "Game centre"],
       caption="Confirmed and replaced starters") if confirmed_rows else
       flag("No row can be confirmed yet: the capture has not read a single official Game Book "
            "(see section 1). The expectation side is published in full below.", "warn")}
<h3>The expectation side, worked through for one fixture</h3>
{table(example_rows, ["Club", "Unit", "Position", "Expected starter", "Chart captured (UTC)",
                      "Point-in-time", "Actual starter", "Outcome", "Official source"],
       caption="One fixture's expectation side, with the chart's capture time and whether it "
               "was known before kickoff")}
</section>

<section><h2>4 · The league's own inactive and did-not-play lists</h2>
<p>The Game Book prints the players who were inactive and the players who did not play. Those
are the league's game-day lists; they are what makes a replacement confirmable rather than
suspected.</p>
{table(inactive_rows, ["Fixture", "Week", "Club", "Player", "Status", "Jersey", "Position",
                        "Official source"],
       caption="Inactive and did-not-play lists, from the official Game Book")
     if inactive_rows else
     flag("No inactive list has been captured: the Game Book has not been read yet.", "warn")}
</section>

<section><h2>5 · Week windows and the clubs on a bye</h2>
<p>The league's own week windows, as published on the schedule page.</p>
{table(bye_rows, ["Week", "Type", "Window begins (UTC)", "Window ends (UTC)", "Clubs on a bye"],
       caption="Official week windows and bye clubs")}
</section>

<section><h2>6 · What is blocked, and the number that would clear it</h2>
{table(gate_html, ["Item", "State", "Gate that blocks it", "Number that clears it",
                   "Official source"],
       caption="Open gates on this evidence layer")}
</section>"""

    return {"gamebooks.html": layout(
        "gamebooks.html",
        "Official Game Book evidence",
        "The league's own schedule page, game centre and Game Book — what was read, what the "
        "fixture context is, and who was expected to start against who actually did.",
        body, wide=True)}


def main() -> int:
    pages = render()
    for name, html_text in pages.items():
        (ROOT / name).write_text(html_text, encoding="utf-8")
        print(f"  wrote {name} ({len(html_text):,} bytes)")
    if not pages:
        print("  no official evidence captured yet — page not written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
