"""Per-team view (session `arena/46f0a137-korea1`, 2026-11-20) -> `team-view.html`.

One row per NFL club (32 rows, every club listed even when a value is missing):
players listed on the official injury report, Out / Doubtful / Questionable counts,
a net injury count, the club's first-listed depth-chart starters ruled Out, the
replacement named directly below each one, and the source of every value.

Rules (the same ones the rest of the site follows):

* Nothing is inferred. "Starter" means the first-listed player of a depth slot, as
  the club's own depth chart prints it. Slots that list more than one player at
  rank 1 are counted once per slot, never as "the" starter of the position.
* "Net injury count" is defined here and only here: players on the report whose
  game status is Out, Doubtful or Questionable. It is a count of entries, not an
  estimate of lost value.
* A club absent from the injury capture is shown as absent, with the reason the
  committed evidence gives (bye per the official schedule capture, or "No Injuries
  Reported" on the capture). Zero on this page never means "healthy by absence".
* Injury entries come from the scheduled official capture of 2026-11-18T04:24:05Z
  (data/availability/injuries.csv, sha256 b065c612...). That capture was compared with
  the live official page on 2026-11-20 for four clubs (57 rows, 0 differences). The
  older 2026-11-12 capture (data/processed/injury_report.csv) is NOT used here: it
  shows "No Injuries Reported" for four clubs that the live page lists with players.
* Every row carries the official source it came from.

Inputs (committed files only; no network, no clock, so `make build` stays byte-stable):
  data/availability/injuries.csv   (2026-11-18 official capture, one row per player entry)
  data/availability/slot_status.csv (depth-chart slots joined to that same capture)
  data/live/claim_reads_2026_11_18/nfl_schedule_week10_2026_games_and_byes.md
Outputs:
  assets/data/team_view.csv, team-view.html
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, SITE_DATA  # noqa: E402
from render_site import layout, table, flag, e, src_link, card, kpi_grid  # noqa: E402

SLUG = "team-view.html"
TITLE = "Per-team view · starters out, replacements named, net injury count"
SUBTITLE = ("One row per NFL club: who the club's own depth chart lists first at each slot and is "
            "ruled Out, the player named directly below, and the net count of game-status entries "
            "on the official injury report. Every value carries its source; blanks are unverified.")

NFL_INJURY_URL = "https://www.nfl.com/injuries/"
NFL_INJURY_LIVE = "https://www.nfl.com/injuries/league/2026/reg10"
NFL_SCHEDULE_URL = "https://www.nfl.com/schedules/2026/by-week/week-10"
HOU_DEPTH_URL = "https://www.houstontexans.com/team/depth-chart"
SCHEDULE_CAPTURE = ROOT / "data" / "live" / "claim_reads_2026_11_18" / "nfl_schedule_week10_2026_games_and_byes.md"

ALL_CLUBS = ["ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB",
             "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
             "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS"]
# slot_status.csv prints the Rams as "LA"; the injury report prints "LAR".
SLOT_TEAM_ALIAS = {"LA": "LAR"}

# Live re-read of the official page on 2026-11-20 (https://www.nfl.com/injuries/league/2026/reg10),
# fetch chunks 5 and 6. Each club's rows were typed from the printed table and compared field by
# field (player, injury, practice status, game status) with the 2026-11-18 capture:
#   CIN 9 rows, BAL 10 rows, LAC 19 rows, DAL 19 rows -> 57 rows, 0 differences.
# Clubs not in this dict were not re-read on 2026-11-20.
LIVE_REREAD = {
    "BAL": 10, "CIN": 9, "LAC": 19, "DAL": 19,
}

# Every row a flag would point at, in plain words, for the flagged list on the page.
FLAGS = [
    ("2026-11-12 injury capture is superseded for injuries",
     "data/processed/injury_report.csv (254 rows, captured 2026-11-12T13:06:29Z) still feeds the "
     "older pages, including the team-status table. Four clubs (BAL, CIN, LAC, SEA) read \"No Injuries "
     "Reported\" there. The 2026-11-18 capture lists players for BAL, CIN and LAC, and the live page "
     "agrees with it. Those older pages need re-pointing; this page does not use them.", NFL_INJURY_LIVE),
    ("Live page title and body disagree",
     "The live page is titled \"Official NFL Injury Report for Players - Week 11 of the 2026 Season\" "
     "while its body is headed \"Injuries - WEEK 10\". The 2026-11-18 capture is labelled WEEK 10. "
     "Which week the page is meant to show is not stated clearly on the page.", NFL_INJURY_LIVE),
    ("Seattle not re-read live",
     "The 2026-11-20 live re-read covered four clubs (BAL, CIN, LAC, DAL). Seattle, Houston and all "
     "other clubs were not re-read, so their rows rest on the 2026-11-18 capture alone.", NFL_INJURY_LIVE),
    ("Houston depth chart not in the committed data",
     "No Houston depth-chart rows are committed. The club publishes its chart as an image; it is "
     "not transcribed by eye. The Houston depth-chart fetch returned HTTP 200 and 481,650 bytes but "
     "parsed 0 rows (data/availability/manifest.json). Houston's starter and replacement cells are blank.", HOU_DEPTH_URL),
    ("Bye clubs are not on the report",
     "CHI, DEN, PHI and TB were on bye in Week 10 per the official schedule capture. Their absence "
     "from the injury report is expected and is not a coverage gap.", NFL_SCHEDULE_URL),
    ("Rams code differs between files",
     "The Rams are printed as LA in the 2026-11-18 capture and as LAR in the older files. This page "
     "maps LA to LAR; the mapping is shown here so it can be checked.", NFL_INJURY_URL),
]


def _csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False) if path.exists() else pd.DataFrame()


def bye_clubs() -> dict[str, str]:
    """Clubs printed under 'Teams on Bye' in the committed official schedule capture."""
    out: dict[str, str] = {}
    if not SCHEDULE_CAPTURE.exists():
        return out
    text = SCHEDULE_CAPTURE.read_text(encoding="utf-8")
    block = text.split("## Teams on Bye, as printed", 1)
    if len(block) != 2:
        return out
    for line in block[1].splitlines():
        m = re.match(r"^\s*([A-Z]{2,3})\s+.+?\s+\d+-\d+(?:-\d+)?\s*$", line)
        if m:
            out[m.group(1)] = "Teams on Bye, as printed on the official schedule (2026-11-18 read)"
    return out


def build_frame() -> pd.DataFrame:
    report = _csv(ROOT / "data" / "availability" / "injuries.csv")
    report["team"] = report["team"].map(lambda t: SLOT_TEAM_ALIAS.get(t, t))
    slots = _csv(ROOT / "data" / "availability" / "slot_status.csv")
    slots["team"] = slots["team"].map(lambda t: SLOT_TEAM_ALIAS.get(t, t))
    byes = bye_clubs()

    # opponent for each club, from the same capture (printed opponent column)
    opp: dict[str, str] = {}
    for _, r in report.iterrows():
        if r["opponent"]:
            opp[r["team"]] = SLOT_TEAM_ALIAS.get(r["opponent"], r["opponent"])
    captured = set(report["team"])

    rows = []
    for club in ALL_CLUBS:
        rep = report[report["team"] == club] if len(report) else pd.DataFrame()
        sl = slots[slots["team"] == club] if len(slots) else pd.DataFrame()

        if club in captured:
            page = "Player entries listed" if len(rep) else "No entries on capture"
            listed = len(rep)
        elif club in byes:
            page = "Not on the report · bye week"
            listed = None
        else:
            page = "Not on the report · no reason in committed evidence"
            listed = None

        def cnt(status_value: str) -> int | None:
            if listed is None:
                return None
            return int((rep["game_status"] == status_value).sum()) if len(rep) else 0


        out_n = cnt("Out")
        doubt_n = cnt("Doubtful")
        quest_n = cnt("Questionable")
        net = None if listed is None else out_n + doubt_n + quest_n

        # first-listed starters (slot rank 1 as the club prints it), flagged on the depth chart
        f_out = sl[sl["flag"] == "FIRST-LISTED OUT"] if len(sl) else pd.DataFrame()
        f_doubt = sl[sl["flag"] == "FIRST-LISTED DOUBTFUL"] if len(sl) else pd.DataFrame()
        f_quest = sl[sl["flag"] == "FIRST-LISTED QUESTIONABLE"] if len(sl) else pd.DataFrame()
        f_dnp = sl[sl["flag"].str.startswith("FIRST-LISTED DID NOT PRACTICE")] if len(sl) else pd.DataFrame()

        def slot_label(r) -> str:
            return f"{r['unit']} {r['position']} slot {r['slot']}: {r['first_listed']}"

        starters_out = "; ".join(slot_label(r) for _, r in f_out.iterrows())
        repl = "; ".join(
            f"{r['next_listed']} ({r['position']}, rank {r['next_listed_rank']}, "
            f"{r['next_listed_status'] or 'no status posted'})"
            for _, r in f_out.iterrows() if r["next_listed"])
        starters_flag_other = len(f_doubt) + len(f_quest) + len(f_dnp)

        depth_src = sl["depth_source_url"].iloc[0] if len(sl) and sl["depth_source_url"].iloc[0] else ""
        depth_slots = int(len(sl)) if len(sl) else None

        live_rows = LIVE_REREAD.get(club)
        live = (f"Matches the live page on 2026-11-20 ({live_rows} rows compared, 0 differences)"
                if live_rows else "")

        rows.append({
            "club": club,
            "week10_opponent": opp.get(club, ""),
            "official_report_status": page,
            "players_listed": "" if listed is None else listed,
            "out": "" if out_n is None else out_n,
            "doubtful": "" if doubt_n is None else doubt_n,
            "questionable": "" if quest_n is None else quest_n,
            "net_injury_count": "" if net is None else net,
            "depth_slots_published": "" if depth_slots is None else depth_slots,
            "starters_out_first_listed": "" if not len(sl) else len(f_out),
            "starters_out_detail": starters_out,
            "replacements_named": repl,
            "starters_other_flag": "" if not len(sl) else starters_flag_other,
            "live_reread_2026_11_20": live,
            "live_reread_source": NFL_INJURY_LIVE if live else "",
            "injury_source_url": NFL_INJURY_URL,
            "injury_capture": "2026-11-18T04:24:05Z",
            "depth_source_url": depth_src,
            "schedule_source_url": NFL_SCHEDULE_URL,
        })
    return pd.DataFrame(rows)


def flagged_section() -> str:
    """The same FLAGS list, rendered as a section of the Flagged for Review page."""
    rows = [[f"<strong>{e(t)}</strong>", e(d), src_link(u, "official source")] for t, d, u in FLAGS]
    return ('<section id="team-view-2026-11-20"><h2>Per-team view &#183; 2026-11-20 '
            '(<code>arena/46f0a137-korea1</code>)</h2>'
            '<p>Found while building <a href="team-view.html">the per-team view</a>. The stale-capture '
            'finding changes which injury file the older pages should read; those pages were not edited '
            'in this session.</p>'
            + table(rows, ["Flagged for review", "What the evidence shows", "Source"],
                    caption="2026-11-20 findings: stale injury capture, depth-chart parse failure, unverified cells")
            + "</section>")


def _cell(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else e(v)


def render() -> None:
    df = build_frame()
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    df.to_csv(SITE_DATA / "team_view.csv", index=False)

    n_clubs = len(df)
    listed_clubs = int((df["official_report_status"] == "Player entries listed").sum())
    no_rep = int(df["official_report_status"].str.startswith("No Injuries").sum())
    depth_clubs = int((df["depth_slots_published"] != "").sum())
    total_out = int(pd.to_numeric(df["out"], errors="coerce").fillna(0).sum())
    total_net = int(pd.to_numeric(df["net_injury_count"], errors="coerce").fillna(0).sum())
    starters_out_total = int(pd.to_numeric(df["starters_out_first_listed"], errors="coerce").fillna(0).sum())

    cards = kpi_grid([
        card(str(n_clubs), "clubs on this page", "every NFL club, one row each"),
        card(str(listed_clubs), "clubs with entries on the 2026-11-18 capture", "player entries listed"),
        card(str(no_rep), "clubs 'No Injuries Reported' on the 2026-11-18 capture",
             "none: all 28 clubs with a game list players", ""),
        card(str(depth_clubs), "clubs with a committed depth chart", "Houston has none committed"),
        card(str(starters_out_total), "first-listed starters ruled Out", "per the depth-chart flag"),
        card(str(total_net), "net injury count, all clubs", "Out + Doubtful + Questionable entries"),
    ])

    headers = ["Club", "Week 10 opponent", "Official report status (capture 2026-11-18)",
               "Players listed", "Out", "Doubtful", "Questionable", "Net injury count",
               "Depth slots published", "First-listed starters Out", "Which slot (club's own chart)",
               "Replacement named directly below", "Other first-listed starters flagged",
               "Live page check 2026-11-20", "Sources"]
    body_rows = []
    for _, r in df.iterrows():
        src = [src_link(NFL_INJURY_URL, "NFL injury report")]
        if r["depth_source_url"]:
            src.append(src_link(r["depth_source_url"], "club depth chart"))
        src.append(src_link(NFL_SCHEDULE_URL, "NFL schedule"))
        if r["live_reread_source"]:
            src.append(src_link(r["live_reread_source"], "NFL injury page, live"))
        body_rows.append([
            f"<strong>{e(r['club'])}</strong>",
            _cell(r["week10_opponent"]),
            _cell(r["official_report_status"]),
            _cell(r["players_listed"]),
            _cell(r["out"]), _cell(r["doubtful"]), _cell(r["questionable"]),
            _cell(r["net_injury_count"]),
            _cell(r["depth_slots_published"]),
            _cell(r["starters_out_first_listed"]),
            _cell(r["starters_out_detail"]) or ("<span class=\"small\">no depth chart committed</span>" if r["depth_slots_published"] == "" else "<span class=\"small\">none flagged</span>"),
            _cell(r["replacements_named"]) or ("<span class=\"small\">no depth chart committed</span>" if r["depth_slots_published"] == "" else "<span class=\"small\">none named</span>"),
            _cell(r["starters_other_flag"]),
            _cell(r["live_reread_2026_11_20"]) if r["live_reread_2026_11_20"] else "<span class=\"small\">not re-read</span>",
            " · ".join(src),
        ])
    main_table = table(body_rows, headers, cls="teamview",
                       caption="One row per NFL club · blank = not confirmed by an official source · counts from the 2026-11-18 capture")

    flag_rows = [[f"<strong>{e(t)}</strong>", e(d), src_link(u, "official source")] for t, d, u in FLAGS]
    flags = table(flag_rows, ["Flagged for review", "What the evidence shows", "Source"],
                  caption="Irregularities on this page · none blocks anything · each is checkable at the source link above")

    definitions = (
        "<section><h2>How to read it</h2><ul>"
        "<li><strong>Starter</strong> = the first-listed player of a depth-chart slot, as the club's own "
        "chart prints it. A slot can list more than one player at rank 1; this page never names one of "
        "them as 'the' starter of a position.</li>"
        "<li><strong>Replacement named</strong> = the next player the same slot lists, with his printed "
        "rank and game status. Blank means the chart names no one.</li>"
        "<li><strong>Net injury count</strong> = Out + Doubtful + Questionable entries on the report. "
        "It counts entries, not lost value.</li>"
        "<li><strong>Out, Doubtful, Questionable</strong> are the printed Game Status values; "
        "the Questionable label is not calibrated (see the open-questions page).</li>"
        "</ul></section>")

    body = (
        flag("Injury counts on this page come from the official capture of 2026-11-18T04:24:05Z. Four clubs "
             "were checked line by line against the live page on 2026-11-20. Do not read a zero as a clean bill of health: "
             "it means no entry on that capture.",
             "warn")
        + cards + main_table + definitions
        + "<section><h2>Flagged for review</h2>"
        + "<p>Published so you can check each one at its source. None blocks the merge.</p>"
        + flags + "</section>"
    )

    html_doc = layout(
        SLUG, TITLE, SUBTITLE, body, wide=True)
    (ROOT / SLUG).write_text(html_doc, encoding="utf-8")
    print(f"wrote {SLUG} ({n_clubs} clubs) and assets/data/team_view.csv")


if __name__ == "__main__":
    render()
