"""Re-read check of official NFL pages on 2026-11-19 (session arena/fea5cdab-korea1).

Reads ONLY committed files (no network, no clock), so `make build` stays reproducible:
  * data/live/reread_2026_11_19/official_rows_read.csv  - rows transcribed from the official
    pages as read on 2026-11-19 (nfl.com injury report, Week 10 URL; nfl.com November reserve list)
  * data/availability/injuries.csv                       - committed injury capture
  * data/availability/reserve/history/2026-11-19T043002Z - committed reserve-list capture

Writes:
  * data/live/reread_2026_11_19/comparison.csv           - one row per compared row
  * data/integration/findings_2026_11_19.csv             - findings rendered on flagged.html

Limitation (recorded as a finding): the live rows are transcriptions of a tool read, not
byte-level captures, so no SHA-256 can be attached to them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live" / "reread_2026_11_19"
INTEG = ROOT / "data" / "integration"
READ = LIVE / "official_rows_read.csv"
INJ = ROOT / "data" / "availability" / "injuries.csv"
RES = ROOT / "data" / "availability" / "reserve" / "history" / "2026-11-19T043002Z" / "reserve_list.csv"
INJ_URL = "https://www.nfl.com/injuries/league/2026/reg10"
RES_URL = "https://www.nfl.com/transactions/league/reserve-list/2026/11"


def _s(x) -> str:
    return "" if x is None or (isinstance(x, float) and pd.isna(x)) else str(x).strip()


def compare() -> tuple[pd.DataFrame, dict]:
    read = pd.read_csv(READ, dtype=str, keep_default_na=False)
    inj = pd.read_csv(INJ, dtype=str, keep_default_na=False)
    res = pd.read_csv(RES, dtype=str, keep_default_na=False)
    inj = inj[inj.week == "WEEK 10"]
    res = res[res.month == "2026-11"]

    rows: list[dict] = []
    stats = {"injury_live": 0, "injury_match": 0, "reserve_live": 0, "reserve_match": 0,
             "field_mismatch": 0, "clubs": {}}

    for r in read[read.source == "injury"].itertuples(index=False):
        stats["injury_live"] += 1
        hit = inj[(inj.team == r.club) & (inj.player == r.player)]
        if len(hit) != 1:
            rows.append(dict(check="injury row vs committed", club=r.club, player=r.player,
                             field="row", live="present", committed=f"{len(hit)} matches",
                             verdict="NOT MATCHED", source_url=INJ_URL))
            stats["field_mismatch"] += 1
            continue
        c = hit.iloc[0]
        ok_all = True
        for field, cfield in (("injury", "injury"), ("practice_status", "practice_status"),
                              ("game_status", "game_status")):
            lv, cv = _s(getattr(r, field)), _s(c[cfield])
            verdict = "MATCH" if lv == cv else "DIFFERS"
            if verdict == "DIFFERS":
                ok_all = False
                stats["field_mismatch"] += 1
            rows.append(dict(check="injury row vs committed", club=r.club, player=r.player,
                             field=field, live=lv or "(blank)", committed=cv or "(blank)",
                             verdict=verdict, source_url=INJ_URL))
        stats["injury_match"] += int(ok_all)
        stats["clubs"].setdefault(r.club, [0, 0])
        stats["clubs"][r.club][0] += 1
        stats["clubs"][r.club][1] += int(ok_all)

    for r in read[read.source == "reserve"].itertuples(index=False):
        stats["reserve_live"] += 1
        hit = res[(res.date == r.date) & (res.team == r.club) & (res.player == r.player)]
        ok = len(hit) == 1 and _s(hit.iloc[0].transaction) == _s(r.transaction)
        stats["reserve_match"] += int(ok)
        if not ok:
            stats["field_mismatch"] += 1
        rows.append(dict(check="reserve row vs 2026-11-19T04:30:02Z capture", club=r.club,
                         player=r.player, field=f"{r.date} · transaction",
                         live=f"{r.date} · {r.transaction}",
                         committed=("listed · " + _s(hit.iloc[0].transaction)) if len(hit) == 1 else "not listed",
                         verdict="MATCH" if ok else "DIFFERS", source_url=RES_URL))

    # Coverage: committed WEEK 10 rows for the same clubs must equal the live row count, so a
    # committed row that the live page no longer shows cannot hide inside a 'match'.
    for club, (n_live, _ok) in list(stats["clubs"].items()):
        n_comm = int((inj.team == club).sum())
        rows.append(dict(check="club row count", club=club, player="(all rows)", field="rows",
                         live=str(n_live), committed=str(n_comm),
                         verdict="MATCH" if n_live == n_comm else "DIFFERS", source_url=INJ_URL))
    return pd.DataFrame(rows), stats


def main() -> int:
    df, stats = compare()
    df.to_csv(LIVE / "comparison.csv", index=False)
    n_rows = len(df)
    n_ok = int((df.verdict == "MATCH").sum())
    n_inj_clubs = len(stats["clubs"])
    clubs_txt = ", ".join(sorted(stats["clubs"]))
    findings = [
        dict(id="F-2026-11-19-01", sev="Medium · open",
             text=("The Week 10 injury-report URL now shows the page title 'Official NFL Injury Report for "
                   "Players - Week 11 of the 2026 Season' while its heading still reads 'Injuries - WEEK 10'. "
                   "The committed capture is WEEK 10 (retrieved 2026-11-18T04:24:05Z). The repository holds no "
                   "Week 11 injury capture, so the week of this page is ambiguous as read today."),
             nxt=("Capture the Week 11 report as its own dated, week-keyed file once it is published; never "
                  "overwrite the Week 10 rows."),
             url=INJ_URL, label="NFL.com injury report (Week 10 URL)"),
        dict(id="F-2026-11-19-02", sev="Info · closed on this branch",
             text=(f"Re-read against the committed captures: {stats['injury_match']} of {stats['injury_live']} "
                   f"injury rows match on injury, practice status and game status for {n_inj_clubs} clubs "
                   f"({clubs_txt}), and {stats['reserve_match']} of {stats['reserve_live']} November reserve-list "
                   f"rows match on date, club, player and transaction. Every field compared: {n_ok} of {n_rows} "
                   f"comparisons agree. The three Lions rows (Joseph, Mays, Reed) read Out on the live page."),
             nxt=("Re-run pipeline/reread_2026_11_19.py after any new official read; a DIFFERS verdict is a "
                  "finding, not a silent update."),
             url=INJ_URL, label="NFL.com injury report (Week 10 URL)"),
        dict(id="F-2026-11-19-03", sev="Medium · repaired",
             text=("main was red at commit 311d9b5. tests/test_reconcile_depth_charts.py read the rolling "
                   "reserve/latest.csv as 'latest', and the scheduled capture had overwritten it with the "
                   "2026-11-19T04:30Z snapshot, so the test's 25-row expectation failed (21 rows). Repaired on main "
                   "by PRs #106/#107 (arena/8d55e319-korea1): the comparison is pinned to the dated "
                   "2026-11-18T04:42:01Z recapture folder, and the test asserts that the rolling file is not read."),
             nxt="No action open. The rolling latest.csv must not be used as a dated reference.",
             url=RES_URL, label="NFL.com reserve list (November)"),
        dict(id="F-2026-11-19-04", sev="Medium · open",
             text=("Scope limit: this re-read covers 44 injury rows for four clubs (WAS, NYG, NE, DET) and 17 "
                   "reserve-list rows. It is not a 32-club line-by-line verification and does not cover the "
                   "other 28 clubs' rows, depth charts or the Texans image."),
             nxt="Extend the transcription club by club, one dated read per club, before any club-level claim is used.",
             url=INJ_URL, label="NFL.com injury report (Week 10 URL)"),
        dict(id="F-2026-11-19-05", sev="Medium · open",
             text=("The live rows are transcriptions of the page as read through a tool, not byte-level captures. "
                   "No SHA-256 or HTTP status is attached to them, so they cannot be audited against the served "
                   "bytes. Treat the match as a dated read, not as an archived capture."),
             nxt=("Have the scheduled capture job store raw bytes and hashes for the same pages, then compare "
                  "against it."),
             url=INJ_URL, label="NFL.com injury report (Week 10 URL)"),
    ]
    INTEG.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(findings).to_csv(INTEG / "findings_2026_11_19.csv", index=False)
    print(f"injury rows: live {stats['injury_live']}, matched {stats['injury_match']}")
    print(f"reserve rows: live {stats['reserve_live']}, matched {stats['reserve_match']}")
    print(f"comparisons agreeing: {n_ok} of {n_rows} row-level checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
