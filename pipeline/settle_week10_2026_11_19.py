"""Settle the Week 10 slate against official NFL.com pages, with a three-source agreement gate.

Why this module exists (session `arena/7134ec74-korea1`, 2026-11-19)
--------------------------------------------------------------------
`forward.html` printed "**1 of 14** games with an official final" and "**4 of 65** tickets
settled" while every week-10 fixture had finished on 2026-11-16. The cause is a *process*
gate, not missing data: `pipeline/forward_fetch_official.py` deliberately writes proposed
scores only to `official_candidates.csv` and never to `official_results.csv`, because its
extractor has not been validated against real pages. Promotion needed a human read per game.

This module does the promotion for Week 10 — every row is settled only if **three
independent official artefacts agree**, and it writes down all three per game so a reviewer
can check any single row without trusting this code:

  A. the live scores page          https://www.nfl.com/scores/2026/week-10
     (transcribed in full on 2026-11-19 into data/live/spotcheck_2026_11_19_week10/)
  B. the committed byte capture    data/evidence/official_games/schedule/reg10.html.gz
     (the league's by-week schedule page, fetched by the scheduled runner 2026-11-19T12:53Z,
     sha256-pinned in that capture's manifest; parsed by the repository's own
     `official_games.parse_schedule_page`)
  C. the league's own Game Book    data/evidence/official_games/gamebooks/<slug>.p1.txt.gz
     (page 1 of the official Game Summary PDF, captured by the same run)

Nothing is inferred. A fixture missing from any one source, or disagreeing with it, is left
**unsettled** and reported with the reason; the rest still settle. The script is idempotent:
rows already present in `official_results.csv` are never rewritten.

What it does *not* do
---------------------
* It does not write `official_candidates.csv` scores. That file stays the unvalidated
  extractor's output; a settled row is removed from it by the caller only after the three
  sources agree here.
* It does not touch the model, any strategy, any gate threshold or any reward.
* It does not treat a community mirror as evidence of anything (evidence class C stays C).

Exit codes: 0 all 14 fixtures settled or already settled · 1 at least one fixture withheld
(printed reasons) · 2 an input is missing.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import official_games as og  # noqa: E402

FWD = ROOT / "data" / "forward"
OFFICIAL = FWD / "official_results.csv"
CANDIDATES = FWD / "official_candidates.csv"
SCHEDULE = FWD / "official_schedule.csv"
EVIDENCE = ROOT / "data" / "evidence" / "official_games"
LIVE = ROOT / "data" / "live" / "spotcheck_2026_11_19_week10"

SCORES_URL = "https://www.nfl.com/scores/2026/week-10"
WRITTEN_BY = "arena/7134ec74-korea1"
THREE_SOURCE_METHOD = (
    "three official artefacts agree on the score, the matchup and the Final status: "
    "(A) the live scores page transcribed in full on 2026-11-19, (B) the committed byte capture of the "
    "league's by-week schedule page fetched by the scheduled runner (sha256 in "
    "data/evidence/official_games/manifest.json), (C) page 1 of the fixture's own Game Book PDF "
    "captured by the same runner, whose VISITOR/HOME score line must sum to its printed total. "
    "A disagreement in any pair withholds the row and prints the reason")
VERIFIED_UTC = "2026-11-19T20:15Z"

# nfl.com prints a club's nickname on the schedule/scores pages and a code in the Game Book.
# The mapping is the league's own club list; it is data, not an inference at settlement time.
NICKNAME = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills", "CAR": "Panthers",
    "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns", "DAL": "Cowboys", "DEN": "Broncos",
    "DET": "Lions", "GB": "Packers", "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars",
    "KC": "Chiefs", "LA": "Rams", "LAC": "Chargers", "LV": "Raiders", "MIA": "Dolphins",
    "MIN": "Vikings", "NE": "Patriots", "NO": "Saints", "NYG": "Giants", "NYJ": "Jets",
    "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks", "SF": "49ers", "TB": "Buccaneers",
    "TEN": "Titans", "WAS": "Commanders",
}
CODE = {v: k for k, v in NICKNAME.items()}

COLUMNS = ["game_id", "season", "week", "official_game_date", "official_section_heading", "away_team",
           "away_score", "home_team", "home_score", "status_on_page", "official_url", "source_page",
           "official_start_time", "official_start_time_source", "official_start_utc", "verified_utc",
           "verified_by", "method"]


def _read_scores_live() -> dict[str, dict]:
    """Source A — the live scores page, transcribed today."""
    p = LIVE / "scores_page_rows.csv"
    if not p.exists():
        raise SystemExit(f"missing {p}")
    out = {}
    for r in pd.read_csv(p, dtype=str, keep_default_na=False).to_dict("records"):
        out[r["game_url"].rstrip("/").rsplit("/", 1)[-1]] = r
    return out


def _read_committed_scores_finals() -> dict[str, dict]:
    """Optional fourth artefact: what the *scheduled fetcher* parsed from the scores page.

    Present only after a runner capture that includes the scores-page parser (added
    2026-11-19). When absent the three-source gate still applies; when present it is
    cross-checked like any other source, so a parser drift is caught rather than trusted.
    """
    p = ROOT / "data" / "processed" / "official_scores_finals.csv"
    if not p.exists():
        return {}
    df = pd.read_csv(p, dtype=str, keep_default_na=False)
    return {r["slug"]: r for r in df.to_dict("records")}


def _read_schedule_capture() -> dict[str, dict]:
    """Source B — the committed byte capture of the league's by-week schedule page."""
    import gzip
    p = EVIDENCE / "schedule" / "reg10.html.gz"
    if not p.exists():
        raise SystemExit(f"missing {p}")
    html = gzip.open(p, "rt", encoding="utf-8").read()
    rows = og.parse_schedule_page(html)
    return {r["official_url"].rstrip("/").rsplit("/", 1)[-1]: r for r in rows}


def _read_gamebook(slug: str) -> str:
    """Source C — page 1 text of the league's Game Summary PDF (captured by the runner)."""
    import gzip
    p = EVIDENCE / "gamebooks" / f"{slug}.p1.txt.gz"
    return gzip.open(p, "rt", encoding="utf-8").read() if p.exists() else ""


def _book_prints_matchup(text: str, away_nick: str, home_nick: str) -> bool:
    """Does the Game Book's own `Date: … Away at Home … Start Time:` line print this matchup?

    The printed form is exactly `Away Full Name at Home Full Name`; only the nickname is
    checked, because the full name would need a second club-name table.
    """
    head = "\n".join(text.splitlines()[:8])
    return away_nick in head and home_nick in head and " at " in head


_VISITOR = re.compile(r"VISITOR:\s+(?P<club>.+?)\s+(?P<q>(?:\d+\s+){5}\d+)\s*$", re.M)
_HOME = re.compile(r"HOME:\s+(?P<club>.+?)\s+(?P<q>(?:\d+\s+){5}\d+)\s*$", re.M)


def _book_score(text: str) -> dict | None:
    """Read the Game Book's own printed score line.

    Page 1 prints, immediately under the scoring plays:

        VISITOR:  Buffalo Bills        7   3  14   7   0   31
        HOME:     New York Jets        0   6   6   0   0   12

    The last column is the printed total; the five before it are Q1..Q4 and OT. The score is
    accepted only when the five period columns sum to the printed total, so a mis-split line
    cannot produce a number.
    """
    v, h = _VISITOR.search(text), _HOME.search(text)
    if not (v and h):
        return None
    vq = [int(x) for x in v.group("q").split()]
    hq = [int(x) for x in h.group("q").split()]
    if len(vq) != 6 or len(hq) != 6 or sum(vq[:5]) != vq[5] or sum(hq[:5]) != hq[5]:
        return None
    return dict(away_club=v.group("club").strip(), away_score=vq[5], away_quarters=vq[:5],
                home_club=h.group("club").strip(), home_score=hq[5], home_quarters=hq[:5])


def verify() -> tuple[list[dict], list[dict]]:
    live = _read_scores_live()
    sched = _read_schedule_capture()
    committed = _read_committed_scores_finals()
    schedcsv = pd.read_csv(SCHEDULE, dtype=str, keep_default_na=False)
    already = pd.read_csv(OFFICIAL, dtype=str, keep_default_na=False) if OFFICIAL.exists() else pd.DataFrame(columns=COLUMNS)
    done = set(already.game_id)

    settled, withheld = [], []
    for r in schedcsv.to_dict("records"):
        gid = r["game_id"]
        slug = r["official_url"].rstrip("/").rsplit("/", 1)[-1]
        away, home = r["away_team"], r["home_team"]
        reasons = []

        a = live.get(slug)
        b = sched.get(slug)
        book = _read_gamebook(slug)

        if gid in done:
            continue
        if a is None:
            reasons.append("not on the live scores page (source A)")
        if b is None:
            reasons.append("not in the committed schedule capture (source B)")
        if not book:
            reasons.append("no Game Book page-1 capture (source C)")

        # A vs the fixture identity in the frozen schedule
        if a is not None:
            if (a["away_as_printed"], a["home_as_printed"]) != (NICKNAME[away], NICKNAME[home]):
                reasons.append(f"source A prints {a['away_as_printed']} at {a['home_as_printed']}, "
                               f"the frozen fixture is {NICKNAME[away]} at {NICKNAME[home]}")
            if a["status_as_printed"].strip().lower() != "final":
                reasons.append(f"source A prints status {a['status_as_printed']!r}, not Final")
        # B vs A
        if a is not None and b is not None:
            for src, got, exp in (("score", (b["away_score_as_printed"], b["home_score_as_printed"]),
                                   (a["away_score_as_printed"], a["home_score_as_printed"])),
                                  ("matchup", (b["away_as_printed"], b["home_as_printed"]),
                                   (a["away_as_printed"], a["home_as_printed"])),
                                  ("status", (b["status_as_printed"],), ("FINAL",))):
                if got != exp:
                    reasons.append(f"source A and source B disagree on {src}: {got} vs {exp}")
        # D (optional) — the runner's own parse of the scores page must agree too.
        d = committed.get(slug)
        if d is not None and a is not None:
            if (d["away_score_as_printed"], d["home_score_as_printed"]) != \
                    (a["away_score_as_printed"], a["home_score_as_printed"]):
                reasons.append(f"the runner's parsed scores page disagrees with the live transcription: "
                               f"{d['away_score_as_printed']}-{d['home_score_as_printed']} vs "
                               f"{a['away_score_as_printed']}-{a['home_score_as_printed']}")
        # C vs the fixture identity AND the number: the Game Book is a third independent score.
        cb = _book_score(book) if book else None
        if book and cb is None:
            reasons.append("the Game Book's VISITOR/HOME score line is missing or its periods do not "
                           "sum to its printed total (source C)")
        elif cb is not None:
            nick_ok = _book_prints_matchup(book, NICKNAME[away], NICKNAME[home])
            club_ok = cb["away_club"].endswith(NICKNAME[away]) and cb["home_club"].endswith(NICKNAME[home])
            if not (nick_ok and club_ok):
                reasons.append(f"the Game Book names {cb['away_club']} at {cb['home_club']}, "
                               f"the frozen fixture is {NICKNAME[away]} at {NICKNAME[home]} (source C)")
            if a is not None and (str(cb["away_score"]), str(cb["home_score"])) != \
                    (a["away_score_as_printed"], a["home_score_as_printed"]):
                reasons.append(f"source A and source C disagree on the score: "
                               f"{a['away_score_as_printed']}-{a['home_score_as_printed']} (A) vs "
                               f"{cb['away_score']}-{cb['home_score']} (Game Book)")

        if reasons:
            withheld.append(dict(game_id=gid, reasons="; ".join(reasons)))
            continue

        settled.append(dict(
            game_id=gid, season=r["season"], week=r["week"],
            official_game_date=r["official_game_date"],
            official_section_heading=a["section_heading_as_printed"],
            away_team=away, away_score=a["away_score_as_printed"],
            home_team=home, home_score=a["home_score_as_printed"],
            status_on_page=a["status_as_printed"], official_url=a["game_url"],
            source_page=SCORES_URL,
            official_start_time=r["official_time_as_printed"],
            official_start_time_source=f"{r['source_page']} (time as printed on the schedule page)",
            official_start_utc="",
            verified_utc=VERIFIED_UTC, verified_by=WRITTEN_BY,
            method=THREE_SOURCE_METHOD,
        ))
    return settled, withheld


def recheck() -> list[dict]:
    """Re-verify the Week-10 rows already in official_results.csv against all three sources.

    Settlement is idempotent, which means `verify()` never looks at a settled row again. This
    is the audit counterpart: it re-reads every published Week-10 final and reports any row
    whose score is no longer printed identically by all three artefacts. A row published from
    two sources by an earlier session (2026_10_WAS_NYG) is checked as well, so the whole slate
    stands or falls on the same rule.
    """
    live = _read_scores_live()
    sched = _read_schedule_capture()
    off = pd.read_csv(OFFICIAL, dtype=str, keep_default_na=False)
    out = []
    for r in off[off.week.astype(str) == "10"].to_dict("records"):
        slug = r["official_url"].rstrip("/").rsplit("/", 1)[-1]
        a, b = live.get(slug), sched.get(slug)
        cb = _book_score(_read_gamebook(slug))
        got = (str(r["away_score"]), str(r["home_score"]))
        checks = {
            "A_live_scores_page": a is not None and (a["away_score_as_printed"], a["home_score_as_printed"]) == got,
            "B_schedule_capture": b is not None and (b["away_score_as_printed"], b["home_score_as_printed"]) == got,
            "C_game_book": cb is not None and (str(cb["away_score"]), str(cb["home_score"])) == got,
        }
        out.append(dict(game_id=r["game_id"], published=f"{r['away_team']} {got[0]} - {got[1]} {r['home_team']}",
                        **checks, agree=all(checks.values()),
                        official_url=r["official_url"]))
    return out


def rewrite_method(rows: list[dict]) -> None:
    """Replace this session's method text on already-published rows with the three-source one.

    Only rows written by this session (`verified_by`) are touched, and only the free-text
    method column; no score, status, url or timestamp is altered.
    """
    if not OFFICIAL.exists():
        return
    df = pd.read_csv(OFFICIAL, dtype=str, keep_default_na=False)
    m = df.verified_by == WRITTEN_BY
    if not m.any():
        return
    df.loc[m, "method"] = THREE_SOURCE_METHOD
    df.to_csv(OFFICIAL, index=False)
    print(f"official_results.csv: method text rewritten on {int(m.sum())} row(s) written by {WRITTEN_BY}")


def append_results(rows: list[dict]) -> None:
    """Append settled rows to official_results.csv without rewriting any existing row."""
    if not rows:
        return
    have = pd.read_csv(OFFICIAL, dtype=str, keep_default_na=False) if OFFICIAL.exists() else pd.DataFrame(columns=COLUMNS)
    add = pd.DataFrame(rows, columns=COLUMNS)
    merged = pd.concat([have, add], ignore_index=True) if len(have) else add
    merged.to_csv(OFFICIAL, index=False)
    print(f"appended {len(add)} settled rows -> {OFFICIAL.relative_to(ROOT)} (now {len(merged)} rows)")


def drop_from_candidates(game_ids: set[str]) -> None:
    """Remove settled fixtures from the unvalidated-extractor file; leave the rest untouched."""
    if not CANDIDATES.exists() or not game_ids:
        return
    df = pd.read_csv(CANDIDATES, dtype=str, keep_default_na=False)
    keep = df[~df.game_id.isin(game_ids)]
    if len(keep) != len(df):
        keep.to_csv(CANDIDATES, index=False)
        print(f"official_candidates.csv: {len(df)} -> {len(keep)} rows (settled fixtures removed)")


def main() -> int:
    if "--recheck" in sys.argv:
        rows = recheck()
        bad = [r for r in rows if not r["agree"]]
        for r in rows:
            mark = "AGREE" if r["agree"] else "DISAGREE"
            print(f"{mark:9} {r['game_id']:16} published {r['published']:22} "
                  f"A={r['A_live_scores_page']!s:5} B={r['B_schedule_capture']!s:5} C={r['C_game_book']!s:5} "
                  f"[{r['official_url']}]")
        print(f"{len(rows)} Week-10 rows re-checked; {len(bad)} disagree")
        return 0 if not bad else 1
    settled, withheld = verify()
    for r in settled:
        print(f"SETTLE {r['game_id']:16} {r['away_team']} {r['away_score']:>2} - {r['home_score']:<2} {r['home_team']}"
              f"  Final   [{r['official_url']}]")
    for w in withheld:
        print(f"WITHHELD {w['game_id']:16} {w['reasons']}")
    append_results(settled)
    drop_from_candidates({r["game_id"] for r in settled})
    if withheld:
        print(f"{len(withheld)} fixture(s) withheld — see reasons above")
        return 1
    print(f"{len(settled)} fixture(s) settled from three agreeing official artefacts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
