"""GC2 (session `arena/7cbb2e60-korea1`) — publish `gamecentre.html`.

The official game-centre / Game Book evidence page the gamebooks workflow
expects (it already calls this module when the file exists).  Everything on
the page is transcribed from documents the league itself published and that
``pipeline/fetch_official_games.py`` captured on a GitHub-hosted runner:

* one row per fixture with the **venue** the fixture's game centre prints
  (LOCATION / STADIUM) — requirement REQ-23, "transcribe the venue of every
  fixture from the official game centre";
* the Game Book's **starting lineups**, **Not Active** (game-day inactive)
  and **Did Not Play** lists, exactly as printed — requirement REQ-25, "use
  official NFL Game Books for actual starters and game-day status; do not
  infer depth rank or snaps";
* the provenance of every captured document: official URL, byte count,
  SHA-256 and capture time.

Design rules inherited from ``render_site.py``:

* every table row carries an official/primary reference (the game centre or
  schedule page on www.nfl.com; the Game Book PDF link is printed beside it);
* a value the document does not print stays blank and says why — nothing is
  inferred, no depth rank is derived, no snap count is invented;
* no table is emitted with zero rows (``tests/check_links.py`` fails an empty
  ``tbody``); an absent capture is a prose note, not a hollow table;
* before the first runner capture the page states that plainly and links the
  standing finding about the superseded REG9/REG10 evidence (F-2026-11-19-08).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT  # noqa: E402
from render_site import layout, table, flag, e, src_link, card, kpi_grid  # noqa: E402

EVIDENCE = ROOT / "data" / "evidence" / "official_games"
SCHEDULE_LIVE = "https://www.nfl.com/schedules/2026/by-week/week-10"


def _csv(name: str) -> pd.DataFrame:
    # dtype=str + keep_default_na=False: blanks stay empty strings, so no
    # table cell can ever render the literal token "nan" (verify V3).
    p = PROC / name
    return (pd.read_csv(p, dtype=str, keep_default_na=False)
            if p.exists() else pd.DataFrame())


def _slug(url: str) -> str:
    path = str(url).split("?")[0].split("#")[0].rstrip("/")
    return path.rsplit("/", 1)[-1]


def _matchup(fx) -> str:
    return f"{fx.away_as_printed} at {fx.home_as_printed}"


def render() -> dict[str, str]:
    fixtures = _csv("official_fixtures.csv")
    centres = _csv("official_gamecentres.csv")
    books = _csv("official_gamebooks.csv")
    rosters = _csv("official_gamebook_rosters.csv")
    manifest_path = EVIDENCE / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:  # pragma: no cover - corrupt capture
            manifest = {}
    fresh = bool(manifest.get("schedule_source"))   # legacy manifest = superseded capture

    cidx = {}
    if not centres.empty and "slug" in centres.columns:
        cidx = centres.set_index("slug")
    bidx = {}
    if not books.empty and "slug" in books.columns:
        bidx = books.set_index("slug")

    n_fix = 0 if fixtures.empty else len(fixtures)
    n_cent = 0 if centres.empty else len(centres)
    n_book = 0 if books.empty else len(books)
    starters = rosters[rosters.roster_block == "starter"] if not rosters.empty else pd.DataFrame()
    inactives = rosters[rosters.roster_block == "not_active"] if not rosters.empty else pd.DataFrame()
    dnp = rosters[rosters.roster_block == "did_not_play"] if not rosters.empty else pd.DataFrame()

    body = ""
    body += "<section><h2>Capture status</h2>"
    body += kpi_grid([
        card(str(n_fix), "fixtures captured", "by-week schedule rows, slug-checked", ""),
        card(str(n_cent), "game centres", "venue printed by the league", ""),
        card(str(n_book), "Game Books", "finished games only", ""),
        card(str(0 if starters.empty else len(starters)), "printed starters",
             "Game Book lineup rows", ""),
        card(str(0 if inactives.empty else len(inactives)), "Not Active rows",
             "official game-day inactives", ""),
        card(str(len(manifest.get("errors", []))), "capture errors",
             "a non-zero count fails the run", "good" if not manifest.get("errors") else "bad"),
    ])
    if manifest.get("retrieved_utc"):
        body += (f"<p class=\"small\">Capture manifest timestamp "
                 f"<code>{e(manifest['retrieved_utc'])}</code> · source "
                 f"{e(str(manifest.get('schedule_source', 'legacy manifest (superseded)')))}. "
                 f"Every document below keeps its SHA-256; the raw bytes are a workflow artifact.</p>")
    if not fresh:
        body += flag(
            "No week-selecting capture has been committed yet. The earlier REG9/REG10 "
            "capture is superseded: its URL did not select the week (both files were "
            "byte-identical Week-11 content labelled weeks 9 and 10 — see "
            "<a href=\"flagged.html\">F-2026-11-19-08</a> on the Flagged page; the "
            "superseded bytes are retained under "
            "<code>data/evidence/official_games/superseded/</code>). The repaired "
            "capture runs on the scheduled workflow and commits only when every "
            "drift check passes.")
    if n_fix == 0:
        body += (f"<p>The fixtures table appears after the first successful runner "
                 f"capture. The capture reads the league's own week-selecting page "
                 f"({src_link(SCHEDULE_LIVE, 'example: week 10 by-week schedule')}) and "
                 f"the scores page for the same week, and refuses to commit when the "
                 f"two documents disagree.</p>")
    body += "</section>"

    # ---------------------------------------------------------------- fixtures
    if n_fix:
        rows = []
        for fx in fixtures.itertuples(index=False):
            slug = _slug(fx.official_url)
            loc = stad = ""
            centre_url = fx.official_url
            if slug in cidx.index:
                loc = str(cidx.at[slug, "venue_location"]) if "venue_location" in cidx.columns else ""
                stad = str(cidx.at[slug, "venue_stadium"]) if "venue_stadium" in cidx.columns else ""
                centre_url = str(cidx.at[slug, "official_url"]) if "official_url" in cidx.columns else centre_url
            state = (str(getattr(fx, "status_as_printed", "")) or "scheduled")
            state_label = "FINAL (printed)" if state == "FINAL" else "scheduled (pregame print)"
            time = str(getattr(fx, "time_as_printed", "")) or "—"
            net = str(getattr(fx, "network_as_printed", "")) or "—"
            venue_cell = (f"{e(loc)}<br>{e(stad)}" if loc or stad
                          else "<em>blank — venue not captured</em>")
            rows.append([
                e(str(fx.week)), e(_matchup(fx)), e(fx.date_as_printed), e(time), e(net),
                e(state_label), venue_cell,
                src_link(centre_url, "game centre") + " · " +
                src_link(str(getattr(fx, "schedule_url", "")), "schedule"),
            ])
        body += "<section><h2>Fixtures and venues (REQ-23)</h2>"
        body += ("<p>Location and Stadium are transcribed from the fixture's own game-centre "
                 "Game Info block; the kickoff line and network are the schedule page's print. "
                 "Nothing is filled from any other document.</p>")
        body += table(rows, ["Week", "Fixture (as printed)", "Date (as printed)",
                             "Kickoff", "Network", "State", "Venue (game centre print)",
                             "Official sources"],
                      caption=f"{len(rows)} captured fixtures — venue as printed by the "
                              f"official game centre, one official link per row")
        body += "</section>"

    # ---------------------------------------------------------------- starters
    if not starters.empty:
        rows = []
        for r in starters.itertuples(index=False):
            rows.append([
                e(str(r.week)), e(str(r.slug)), e(str(r.team_as_printed)), e(str(r.unit)),
                e(str(r.position)), e(str(r.jersey)), e(str(r.player)),
                src_link(str(r.source_url), "game centre") + " · " +
                src_link(str(r.official_url), "Game Book PDF"),
            ])
        body += "<section><h2>Actual starters — Game Book lineups (REQ-25)</h2>"
        body += ("<p>Every row is a lineup line printed on page 1 of the official Game Book: "
                 "four printed columns (visitor offence, visitor defence, home offence, home "
                 "defence). Jersey, position and name are transcribed; no depth rank is "
                 "inferred and no snap count is used.</p>")
        body += table(rows, ["Week", "Game", "Club (printed)", "Unit", "Pos", "No.",
                             "Player (printed)", "Official sources"],
                      caption=f"{len(rows)} printed starter rows from {n_book} official "
                              f"Game Book(s)")
        body += "</section>"

    # -------------------------------------------------------------- inactives
    if not inactives.empty:
        rows = []
        for r in inactives.itertuples(index=False):
            rows.append([
                e(str(r.week)), e(str(r.slug)), e(str(r.team_as_printed)),
                e(str(r.position)), e(str(r.jersey)), e(str(r.player)),
                src_link(str(r.source_url), "game centre") + " · " +
                src_link(str(r.official_url), "Game Book PDF"),
            ])
        body += "<section><h2>Game-day status — Not Active (REQ-25)</h2>"
        body += ("<p>The Game Book's own \"Not Active\" lists. A player absent from the "
                 "weekly injury report is not treated as available; this list is the "
                 "league's game-day statement.</p>")
        body += table(rows, ["Week", "Game", "Club (printed)", "Pos", "No.",
                             "Player (printed)", "Official sources"],
                      caption=f"{len(rows)} Not Active rows transcribed from the official "
                              f"Game Book(s)")
        body += "</section>"

    if not dnp.empty:
        rows = []
        for r in dnp.itertuples(index=False):
            rows.append([
                e(str(r.week)), e(str(r.slug)), e(str(r.team_as_printed)),
                e(str(r.position)), e(str(r.jersey)), e(str(r.player)),
                src_link(str(r.source_url), "game centre") + " · " +
                src_link(str(r.official_url), "Game Book PDF"),
            ])
        body += "<section><h2>Did Not Play (printed)</h2>"
        body += table(rows, ["Week", "Game", "Club (printed)", "Pos", "No.",
                             "Player (printed)", "Official sources"],
                      caption=f"{len(rows)} Did Not Play rows transcribed from the official "
                              f"Game Book(s)")
        body += "</section>"

    # ------------------------------------------------------------- provenance
    prov_rows = []
    for sp in manifest.get("schedule_pages", []):
        prov_rows.append([
            "Schedule page (by-week)", e(str(sp.get("week", ""))),
            src_link(str(sp.get("url", "")), "official schedule"),
            e(str(sp.get("raw_bytes", ""))), e(str(sp.get("raw_sha256", ""))),
            e(str(sp.get("retrieved_utc", ""))), "—",
        ])
    for sc in manifest.get("scores_pages", []):
        prov_rows.append([
            "Scores page (cross-check)", e(str(sc.get("week", ""))),
            src_link(str(sc.get("url", "")), "official scores"),
            "—", "—", e(str(sc.get("retrieved_utc", ""))),
            e(str(sc.get("crosscheck", ""))),
        ])
    for gc in manifest.get("game_centres", []):
        prov_rows.append([
            "Game centre", e(str(_slug(str(gc.get("url", ""))))),
            src_link(str(gc.get("url", "")), "game centre"),
            e(str(gc.get("raw_bytes", ""))), e(str(gc.get("raw_sha256", ""))),
            e(str(gc.get("retrieved_utc", ""))),
            e(f"{gc.get('venue_location', '')} · {gc.get('venue_stadium', '')}"),
        ])
    for gb in manifest.get("game_books", []):
        prov_rows.append([
            "Game Book PDF", e(str(_slug(str(gb.get("game_centre_url", ""))))),
            src_link(str(gb.get("game_centre_url", "")), "game centre") + " · " +
            src_link(str(gb.get("url", "")), "Game Book PDF"),
            e(str(gb.get("raw_bytes", ""))), e(str(gb.get("raw_sha256", ""))),
            e(str(gb.get("retrieved_utc", ""))), e(str(gb.get("extraction_method", ""))),
        ])
    if prov_rows:
        body += "<section><h2>Capture provenance</h2>"
        body += ("<p>One row per captured document: the league's own URL, the byte count, "
                 "the SHA-256 of the bytes read and the capture time. A hash proves which "
                 "bytes were parsed; the raw bytes are retained as a workflow artifact.</p>")
        body += table(prov_rows, ["Document", "Week / game", "Official URL", "Bytes",
                                  "SHA-256", "Captured (UTC)", "Printed venue / method / check"],
                      caption=f"{len(prov_rows)} captured official documents with hashes")
        body += "</section>"

    body += ("<section><h2>How to read this page</h2>"
             "<p>Every cell on this page is a transcription of an official NFL document. "
             "Where a document prints nothing, the cell stays blank and says so. This page "
             "never ranks depth, never converts a jersey number into an order and never "
             "treats absence from a list as availability. Expected-vs-actual starter joins "
             "(the availability graph) are built only when both the club's own depth chart "
             "and this Game Book are captured for the same fixture.</p></section>")

    return {"gamecentre.html": layout(
        "gamecentre.html", "Official game centre & Game Books",
        "Venue per fixture from the league's game centre; starters, Not Active and "
        "Did Not Play from the official Game Book — every row with its official link "
        "and every document with its SHA-256.",
        body, wide=True)}


def main() -> int:
    pages = render()
    for name, html_text in pages.items():
        (ROOT / name).write_text(html_text, encoding="utf-8")
        print(f"  wrote {name} ({len(html_text):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
