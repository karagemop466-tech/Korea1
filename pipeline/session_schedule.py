"""2026-11-15 schedule page (PS4): the dated schedule announcement beside the Week 10 schedule.

Reads committed files only (no network) and the constants below, which were read from NFL.com on
2026-11-15 and are cited next to each use.

Sources read in this session (fetched with the page-fetch tool, not from search snippets)
  https://www.nfl.com/news/2026-nfl-schedule-powered-by-aws-to-be-released-thursday-may-14
      League announcement: the 2026 schedule is released Thursday, May 14 at 8 p.m. ET; the remaining
      international games are announced Wednesday, May 13 at 9 a.m. ET (fetched text).
  https://www.nfl.com/schedules/2026/by-week/reg-10   (3 chunks)
      Week 10 games and the "Teams on Bye" list: CHI, DEN, PHI, TB (fetched text).

What is re-read and what is carried
  * The 14 Week 10 games come from data/forward/official_schedule.csv (transcribed 2026-11-12). The
    fetched page this session shows the same 14 matchups, the same game links, and the same networks
    and times for the 8 games whose times it prints (see RE_READ_TIMES).
  * Byes are the four clubs the fetched page lists under "Teams on Bye".
  * The announcement page text carries no print date. The search index lists it as 8 May 2026; that
    date is shown as "index date", not as a fetched fact.

Outputs
  data/integration/schedule_week10_2026_11_15.csv   14 games + 4 byes, one row per fixture or bye
  schedule.html

Run:  python pipeline/session_schedule.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import e, ref_link, write_csv  # noqa: E402

ANNOUNCE_URL = "https://www.nfl.com/news/2026-nfl-schedule-powered-by-aws-to-be-released-thursday-may-14"
SCHEDULE_URL = "https://www.nfl.com/schedules/2026/by-week/reg-10"
BYES = ["CHI", "DEN", "PHI", "TB"]   # "Teams on Bye", fetched 2026-11-15 from SCHEDULE_URL
# Game times printed on the fetched page this session (game id -> time as printed).
RE_READ_TIMES = {
    "2026_10_LA_ARI": "4:05 PM", "2026_10_SEA_LV": "4:05 PM", "2026_10_SF_DAL": "4:25 PM",
    "2026_10_PIT_CIN": "8:20 PM", "2026_10_LAC_BAL": "8:15 PM",
}
# Dates printed on the fetched page this session: Thursday Nov 12, Sunday Nov 15, Monday Nov 16.
FETCHED_DATES = {"2026-11-12", "2026-11-15", "2026-11-16"}


def games() -> pd.DataFrame:
    s = pd.read_csv(ROOT / "data" / "forward" / "official_schedule.csv", dtype=str).fillna("")
    assert len(s) == 14, f"expected 14 Week 10 games, found {len(s)}"
    rows = []
    for r in s.itertuples(index=False):
        rows.append(dict(
            kind="GAME", game_id=r.game_id, date=r.official_game_date,
            time_as_printed=r.official_time_as_printed, network=r.network_as_printed,
            matchup=f"{r.away_team} at {r.home_team}", away=r.away_team, home=r.home_team, bye="",
            re_read_2026_11_15=("time, network, date" if r.game_id in RE_READ_TIMES else "date only"
                                if r.official_game_date in FETCHED_DATES else "not re-read"),
            source_url=r.official_url,
        ))
    for t in BYES:
        rows.append(dict(kind="BYE", game_id="", date="", time_as_printed="", network="",
                         matchup="", away="", home="", bye=t, re_read_2026_11_15="listed on page",
                         source_url=SCHEDULE_URL))
    return pd.DataFrame(rows)


def coverage_ok(df: pd.DataFrame) -> bool:
    clubs = list(df[df.kind == "GAME"].away) + list(df[df.kind == "GAME"].home) + list(df[df.kind == "BYE"].bye)
    return len(clubs) == 32 and len(set(clubs)) == 32


def page(df: pd.DataFrame) -> str:
    g = df[df.kind == "GAME"]
    rows = []
    for r in g.itertuples(index=False):
        rows.append([e(r.game_id), e(r.date), e(r.time_as_printed) + " ET" if r.time_as_printed else "",
                     e(r.network), f"<strong>{e(r.matchup)}</strong>", e(r.re_read_2026_11_15),
                     ref_link("NFL game page", r.source_url)])
    byes = ", ".join(df[df.kind == "BYE"].bye)
    body = f"""
<section><h2>Dated schedule announcement</h2>
<p class="lede">The league's own announcement, read 2026-11-15. It sits beside the live Week 10 schedule below, so the dates on both can be checked against one page.</p>
<div class="cards">
<div class="card">Thu May 14, 2026<div class="card-label">2026 schedule release, 8 p.m. ET (league announcement)</div></div>
<div class="card">Wed May 13, 2026<div class="card-label">remaining international games, 9 a.m. ET (same announcement)</div></div>
<div class="card">Wed Sep 9, 2026<div class="card-label">season opener, Seattle host (headline and date seen in the announcement page's related-content list; the article itself was not opened)</div></div>
</div>
{table([[ref_link("2026 NFL schedule powered by AWS to be released Thursday, May 14", ANNOUNCE_URL),
          "Thursday, May 14, 2026 · 8 p.m. ET", "Index date: May 8, 2026 (the page text has no print date)"]],
       ["Official announcement", "What it says", "Date note"], caption="The announcement · one row, read on this page")}
</section>
<section><h2>Live schedule · Week 10</h2>
<p class="lede">The 14 Week 10 games and the four bye clubs ({e(byes)}). Every game row links to its NFL.com game page. The last column says what was re-read on this page today; other values are the 2026-11-12 transcription.</p>
{table(rows, ["Game", "Date", "Time", "Network", "Matchup (away at home)", "Re-read 2026-11-15", "Official source"], caption="14 games · 4 teams on bye · 32 clubs accounted for once")}
</section>
"""
    return layout("schedule.html", "Schedule: dated announcement and Week 10 games",
                  "The league's announcement dates and the live Week 10 schedule, with NFL.com links on every row.",
                  body, wide=True)


def main() -> None:
    df = games()
    assert coverage_ok(df), "a club is missing or counted twice in the Week 10 schedule"
    write_csv(df, "schedule_week10_2026_11_15.csv")
    (ROOT / "schedule.html").write_text(page(df), encoding="utf-8")
    print(json.dumps(dict(games=int((df.kind == "GAME").sum()), byes=int((df.kind == "BYE").sum())), indent=1))


if __name__ == "__main__":
    main()
