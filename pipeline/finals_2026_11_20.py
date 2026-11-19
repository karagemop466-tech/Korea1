"""Week 10 official finals: two independent official documents must agree before a row is written.

WHY THIS MODULE EXISTS
----------------------
The forward test held 65 picks frozen before kickoff and only **one** of them
(`2026_10_WAS_NYG`) could be settled, because `data/forward/official_results.csv` held no other
Week 10 final. Every other pick sat at `OPEN`, so no accuracy, no Brier score, no ROI and no
closing-line value could be computed for them. "A verified results feed so backtests and ROI can be
computed at all" was blocked on exactly this file.

This module closes that gap for Week 10 without inventing anything, and without trusting a single
read. For every Week 10 fixture it requires **two independent official documents** to print the
same final, then appends one row per fixture to `data/forward/official_results.csv`:

1. **The league's own scores page** — <https://www.nfl.com/scores/2026/week-10>. The printed
   section heading (e.g. "Thursday Night Football, November 12th") and the two printed scores are
   transcribed below *verbatim*, read with the page-reading tool on `READ_UTC`. The page states each
   fixture's status in the league's own word ("Final").
2. **The league's own Game Book PDF**, already captured and hash-pinned in this repository at
   `data/evidence/official_games/gamebooks/<slug>-2026-reg-10.p1.txt.gz`. The Game Book prints a
   quarter-by-quarter line whose `Total` column is the final score. The bytes are the ones the
   scheduled capture committed; nothing is re-typed from the Game Book.

If the two documents disagree about any score, or a fixture is missing from either, this module
**raises and writes nothing** (exit 2). A partial cage is worse than none: a silently dropped
fixture would look like an unfinished game.

WHAT IS NOT CLAIMED
-------------------
* No score is inferred, interpolated or copied from a community mirror.
* `official_url` is the game's own NFL.com page (the same form the file already uses); it is **not**
  claimed to have been re-read for each of the 13 new rows — the scores page and the Game Book are
  the two documents actually read, and both are recorded in `method` and `source_page`.
* A kickoff time is written only from an official source that prints one. The Week 10 schedule page
  (<https://www.nfl.com/schedules/2026/by-week/week-10>) was re-read on `READ_UTC` and prints a
  dated section heading and a network for every fixture, but **not a clock time** on the rendered
  page read here. The clock times already committed in `data/forward/official_schedule.csv` were
  transcribed on 2026-11-12 from `/schedules/2026/by-week/reg-10`, and that URL is the exact
  defect flagged as F-2026-11-19-08 (the `REG<n>` form does not select the week). They are therefore
  *carried over and labelled as such*, never re-asserted as a fresh read: the `method` column says
  which page each time came from. A settlement gate that needs a kickoff sees a time with a stated
  provenance, so the pre-kickoff test can be applied to these picks instead of being skipped.

Run:  python pipeline/finals_2026_11_20.py
Out:  data/forward/official_results.csv   (13 rows appended; idempotent — a row already present
                                           with the same score is left untouched)
      data/forward/week10_finals_2026_11_20.csv  (the two-document comparison, one row per fixture)
"""
from __future__ import annotations

import csv
import gzip
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FWD = ROOT / "data" / "forward"
BOOKS = ROOT / "data" / "evidence" / "official_games" / "gamebooks"
SCHEDULE = ROOT / "data" / "forward" / "official_schedule.csv"

SCORES_URL = "https://www.nfl.com/scores/2026/week-10"
READ_UTC = "2026-11-20"
READ_BY = "arena/79a986b7-korea1"

# ---------------------------------------------------------------------------------------------
# Document 1 — the league's scores page, transcribed verbatim on READ_UTC.
#
# (printed section heading, printed away club, away score, printed home club, home score).
# The order below is the page's own order: Thursday, the Munich international game, then the
# Sunday 1:00 block, the 4:00 block, Sunday night, then Monday night.
# ---------------------------------------------------------------------------------------------
SCORES_PAGE = [
    ("Thursday Night Football, November 12th", "WAS", 24, "NYG", 21),
    ("Sunday, November 15th, International Game", "NE", 10, "DET", 35),
    ("Sunday, November 15th", "KC", 35, "ATL", 13),
    ("Sunday, November 15th", "HOU", 24, "CLE", 27),
    ("Sunday, November 15th", "MIN", 30, "GB", 10),
    ("Sunday, November 15th", "MIA", 22, "IND", 24),
    ("Sunday, November 15th", "CAR", 20, "NO", 17),
    ("Sunday, November 15th", "BUF", 31, "NYJ", 12),
    ("Sunday, November 15th", "JAX", 40, "TEN", 23),
    ("Sunday, November 15th", "LA", 34, "ARI", 6),
    ("Sunday, November 15th", "SEA", 21, "LV", 13),
    ("Sunday, November 15th", "SF", 46, "DAL", 40),
    ("Sunday Night Football, November 15th", "PIT", 18, "CIN", 38),
    ("Monday Night Football, November 16th", "LAC", 23, "BAL", 20),
]

# The official game-centre slug for each fixture, as the scores page links it. Printed by the page
# (the "View <Away> <Home> game" link) and used only to build the game's own URL.
SLUG = {
    ("WAS", "NYG"): "commanders-at-giants-2026-reg-10",
    ("NE", "DET"): "patriots-at-lions-2026-reg-10",
    ("KC", "ATL"): "chiefs-at-falcons-2026-reg-10",
    ("HOU", "CLE"): "texans-at-browns-2026-reg-10",
    ("MIN", "GB"): "vikings-at-packers-2026-reg-10",
    ("MIA", "IND"): "dolphins-at-colts-2026-reg-10",
    ("CAR", "NO"): "panthers-at-saints-2026-reg-10",
    ("BUF", "NYJ"): "bills-at-jets-2026-reg-10",
    ("JAX", "TEN"): "jaguars-at-titans-2026-reg-10",
    ("LA", "ARI"): "rams-at-cardinals-2026-reg-10",
    ("SEA", "LV"): "seahawks-at-raiders-2026-reg-10",
    ("SF", "DAL"): "49ers-at-cowboys-2026-reg-10",
    ("PIT", "CIN"): "steelers-at-bengals-2026-reg-10",
    ("LAC", "BAL"): "chargers-at-ravens-2026-reg-10",
}

# The date the fixture was played, as the page's heading states it. Only the printed day is used;
# nothing is calculated from a kickoff time.
GAME_DATE = {
    "Thursday Night Football, November 12th": "2026-11-12",
    "Sunday, November 15th, International Game": "2026-11-15",
    "Sunday, November 15th": "2026-11-15",
    "Sunday Night Football, November 15th": "2026-11-15",
    "Monday Night Football, November 16th": "2026-11-16",
}

# Club abbreviation -> the full name the Game Book prints, so the Game Book line can be matched
# without guessing. These are the clubs' own names as printed by the league.
FULL = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys", "DET": "Detroit Lions",
    "GB": "Green Bay Packers", "HOU": "Houston Texans", "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs", "LA": "Los Angeles Rams",
    "LAC": "Los Angeles Chargers", "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings", "NE": "New England Patriots", "NO": "New Orleans Saints",
    "NYG": "New York Giants", "NYJ": "New York Jets", "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}

BOOK_LINE = re.compile(r"^\s*(VISITOR|HOME):\s+(.+?)\s{2,}((?:\d+\s+){5}\d+)\s*$")
RESULT_COLS = ["game_id", "season", "week", "official_game_date", "official_section_heading",
               "away_team", "away_score", "home_team", "home_score", "status_on_page",
               "official_url", "source_page", "official_start_time", "official_start_time_source",
               "official_start_utc", "verified_utc", "verified_by", "method"]
CMP_COLS = ["game_id", "official_url", "scores_page_away", "scores_page_away_score",
            "scores_page_home", "scores_page_home_score", "gamebook_visitor", "gamebook_visitor_total",
            "gamebook_home", "gamebook_home_total", "verdict", "scores_page_url", "gamebook_path",
            "read_utc", "read_by"]


def gamebook_totals(slug: str) -> dict[str, int]:
    """The Game Book's own VISITOR/HOME totals, read from the committed, hash-pinned text."""
    path = BOOKS / f"{slug}.p1.txt.gz"
    if not path.exists():
        raise SystemExit(f"no committed Game Book for {slug}; refusing to write a single-source final")
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    out: dict[str, int] = {}
    for line in text.splitlines():
        m = BOOK_LINE.match(line)
        if not m:
            continue
        side, club, totals = m.group(1), m.group(2).strip(), m.group(3).split()
        # The column list is Q1 Q2 Q3 Q4 OT Total; the last number is the printed Total.
        out[side] = int(totals[-1])
        out[f"{side}_club"] = club  # type: ignore[assignment]
    if set(k for k in out if not k.endswith("_club")) != {"VISITOR", "HOME"}:
        raise SystemExit(f"{path.name}: could not read both VISITOR and HOME total lines")
    return out  # type: ignore[return-value]


def carried_kickoffs() -> dict[str, dict]:
    """Kickoff times already committed in the forward schedule, with their own provenance.

    Carried over deliberately and labelled: these were transcribed from
    `/schedules/2026/by-week/reg-10`, which is the URL measured not to select the week
    (flag F-2026-11-19-08). They are used only to timestamp a pick against its game, never
    presented as a fresh read, and the `method` column names the source page per row.
    """
    if not SCHEDULE.exists():
        return {}
    with SCHEDULE.open(newline="", encoding="utf-8") as fh:
        return {r["game_id"]: r for r in csv.DictReader(fh) if r.get("week") == "10"}


def build() -> tuple[list[dict], list[dict]]:
    """Cross-check the two documents. Raises (SystemExit) on any disagreement."""
    rows: list[dict] = []
    cmp_rows: list[dict] = []
    kick = carried_kickoffs()
    for heading, away, away_pts, home, home_pts in SCORES_PAGE:
        slug = SLUG.get((away, home))
        if not slug:
            raise SystemExit(f"{away} at {home}: the scores page's link was not recorded")
        gid = f"2026_10_{away}_{home}"
        book = gamebook_totals(slug)
        # Club identity must agree before the scores are compared: a Game Book for a different
        # fixture would otherwise pass a numeric check by coincidence.
        if book["VISITOR_club"] != FULL[away] or book["HOME_club"] != FULL[home]:
            raise SystemExit(
                f"{gid}: Game Book prints {book['VISITOR_club']!r} at {book['HOME_club']!r}, "
                f"scores page prints {FULL[away]!r} at {FULL[home]!r}")
        agree = (book["VISITOR"] == away_pts) and (book["HOME"] == home_pts)
        cmp_rows.append(dict(
            game_id=gid, official_url=f"https://www.nfl.com/games/{slug}",
            scores_page_away=away, scores_page_away_score=away_pts,
            scores_page_home=home, scores_page_home_score=home_pts,
            gamebook_visitor=book["VISITOR_club"], gamebook_visitor_total=book["VISITOR"],
            gamebook_home=book["HOME_club"], gamebook_home_total=book["HOME"],
            verdict="TWO DOCUMENTS AGREE" if agree else "DISAGREE",
            scores_page_url=SCORES_URL,
            gamebook_path=f"data/evidence/official_games/gamebooks/{slug}.p1.txt.gz",
            read_utc=READ_UTC, read_by=READ_BY))
        if not agree:
            raise SystemExit(
                f"{gid}: scores page prints {away} {away_pts} / {home} {home_pts} but the Game Book "
                f"prints {book['VISITOR']} / {book['HOME']}; nothing written")
        rows.append(dict(
            game_id=gid, season="2026", week="10",
            official_game_date=GAME_DATE[heading], official_section_heading=heading,
            away_team=away, away_score=str(away_pts), home_team=home, home_score=str(home_pts),
            status_on_page="Final",
            official_url=f"https://www.nfl.com/games/{slug}",
            source_page=SCORES_URL,
            # Carried over from the committed forward schedule, labelled with the page it came from.
            # A blank would make the pre-kickoff test unanswerable for the picks on this game.
            official_start_time=kick.get(gid, {}).get("official_time_as_printed", ""),
            official_start_time_source=kick.get(gid, {}).get("source_page", ""),
            official_start_utc="",
            verified_utc=f"{READ_UTC}T00:00Z", verified_by=READ_BY,
            method=(f"two official documents agree: (1) the league's {SCORES_URL} prints the heading "
                    f"'{heading}' with {away} {away_pts} and {home} {home_pts}, read {READ_UTC} with the "
                    f"page-reading tool; (2) the league's own Game Book PDF for this fixture, captured and "
                    f"hash-pinned at data/evidence/official_games/gamebooks/{slug}.p1.txt.gz, prints VISITOR "
                    f"{book['VISITOR_club']} {book['VISITOR']} and HOME {book['HOME_club']} {book['HOME']}. "
                    f"No community mirror was used. Kickoff time carried over from "
                    f"{kick.get(gid, {}).get('source_page', '(none)')} on "
                    f"{kick.get(gid, {}).get('official_game_date', '')} "
                    f"{kick.get(gid, {}).get('official_time_as_printed', '')} as transcribed there; that "
                    f"page form is the one flagged F-2026-11-19-08, so the time is labelled, not re-asserted.")))
    if len(rows) != 14:
        raise SystemExit(f"the Week 10 scores page lists 14 fixtures; this table has {len(rows)}")
    # A final can never be a tie in the NFL's own framing for these fixtures; if a score is equal the
    # settlement arithmetic would silently grade pushes everywhere, so stop and look.
    for r in rows:
        if r["away_score"] == r["home_score"]:
            raise SystemExit(f"{r['game_id']}: equal scores read; verify by hand")
    return rows, cmp_rows


def main() -> int:
    new_rows, cmp_rows = build()
    path = FWD / "official_results.csv"
    existing: list[dict] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            existing = list(csv.DictReader(fh))
    have = {r["game_id"]: r for r in existing}
    appended, unchanged = 0, 0
    for r in new_rows:
        cur = have.get(r["game_id"])
        if cur is not None:
            if cur["away_score"] != r["away_score"] or cur["home_score"] != r["home_score"]:
                raise SystemExit(f"{r['game_id']}: the file already holds "
                                 f"{cur['away_score']}-{cur['home_score']}, this read says "
                                 f"{r['away_score']}-{r['home_score']}; refusing to overwrite evidence")
            unchanged += 1
            continue
        existing.append(r)
        appended += 1
    # Existing rows keep their committed order: this module adds evidence, it does not reshuffle a
    # file another session wrote. New rows arrive in the page's own order, as printed above.
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RESULT_COLS, lineterminator="\n")
        w.writeheader()
        for r in existing:
            w.writerow({c: r.get(c, "") for c in RESULT_COLS})
    cmp_path = FWD / "week10_finals_2026_11_20.csv"
    with cmp_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CMP_COLS, lineterminator="\n")
        w.writeheader()
        for r in cmp_rows:
            w.writerow(r)
    print(f"week 10 finals: {len(cmp_rows)} fixtures, two official documents agree on all of them")
    print(f"  official_results.csv: {appended} appended, {unchanged} already present, "
          f"{len(existing)} rows total")
    print(f"  wrote {cmp_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
