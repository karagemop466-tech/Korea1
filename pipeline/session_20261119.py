"""Session arena/db0e98e2-korea1 (2026-11-19): reserve-page window check and register repair.

Reads committed files only, plus one verbatim live read of the official NFL.com November
reserve-list page taken during this session (transcribed below and asserted against the
2026-11-19T04:30:02Z capture before anything is written). No network access at build time.

Writes:
  data/live/spotcheck_2026_11_19/reserve_list_2026_11_live_read.csv
  data/integration/flagged_2026_11_19.csv
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AV = ROOT / "data" / "availability"
HIST = AV / "reserve" / "history"
SPOT = ROOT / "data" / "live" / "spotcheck_2026_11_19"
INTEG = ROOT / "data" / "integration"
URL_RES = "https://www.nfl.com/transactions/league/reserve-list/2026/11"
URL_INJ = "https://www.nfl.com/injuries/league/2026/reg10"
READ_UTC = "2026-11-19"  # date of the live read recorded below

# Verbatim rows of the live page (date as printed, team abbreviation, player, transaction),
# in page order, read 2026-11-19 from https://www.nfl.com/transactions/league/reserve-list/2026/11
LIVE_ROWS = [
    ("11/18", "PIT", "Mason McCormick", "Reserve/Injured"),
    ("11/18", "KC", "Jared Wiley", "Reserve/Injured"),
    ("11/18", "DET", "Aidan Hutchinson", "Reserve/Injured"),
    ("11/18", "MIN", "Bo Richter", "Reserve/Injured"),
    ("11/17", "HOU", "Azeez Al-Shaair", "Reserve/Injured"),
    ("11/17", "MIA", "Zeek Biggers", "Reserve/Injured"),
    ("11/17", "MIA", "Jordan Phillips", "Reserve/Injured"),
    ("11/17", "ARI", "Andrew Wingard", "Reserve/Injured"),
    ("11/17", "ARI", "Jordan Burch", "Reserve/Injured"),
    ("11/17", "BUF", "Ar'maj Reed-Adams", "Reserve/Injured"),
    ("11/17", "IND", "Jaylon Carlies", "Reserve/Injured"),
    ("11/17", "TEN", "Wan'Dale Robinson", "Reserve/Injured"),
    ("11/16", "LA", "Dylan McMahon", "Reserve/Injured"),
    ("11/16", "LAC", "Branson Taylor", "Reserve/Injured"),
    ("11/14", "NO", "Christen Miller", "Reserve/Injured"),
    ("11/14", "NE", "TreVeyon Henderson", "Reserve/Injured"),
    ("11/14", "CLE", "Michael Burton", "Reserve/Injured"),
    ("11/14", "IND", "Mo Alie-Cox", "Reserve/Injured"),
    ("11/14", "IND", "Akeem Davis-Gaither", "Reserve/Injured"),
    ("11/14", "TEN", "Peter Skoronski", "Reserve/Injured"),
    ("11/14", "TEN", "Tommy Townsend", "Reserve/Injured"),
    ("11/14", "DAL", "Tyler Goodson", "Reserve/Injured"),
    ("11/14", "GB", "Josh Whyle", "Reserve/Injured"),
    ("11/12", "LA", "Puka Nacua", "Reserve/Injured"),
    ("11/10", "LA", "Jordan Whittington", "Reserve/Injured"),
]


def _key(d: str, t: str, p: str) -> tuple[str, str, str]:
    return d, t, p


def _load_month(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    return d[d.month == "2026-11"]


def build() -> dict:
    live = [(f"2026-11-{ds.split('/')[1]}", t, p, tr) for ds, t, p, tr in LIVE_ROWS]
    live_keys = {_key(d, t, p) for d, t, p, _ in live}

    c1118 = _load_month(HIST / "2026-11-18T044201Z" / "reserve_list.csv")
    c1119 = _load_month(HIST / "2026-11-19T043002Z" / "reserve_list.csv")
    k1118 = set(zip(c1118.date, c1118.team, c1118.player))
    k1119 = set(zip(c1119.date, c1119.team, c1119.player))

    # Transcription check: the live read must equal the 2026-11-19 capture exactly.
    assert len(live) == 25, len(live)
    assert live_keys == k1119, (sorted(live_keys ^ k1119))

    dropped = sorted(k1118 - k1119)   # on the 11-18 capture, gone from the 11-19 page
    added = sorted(k1119 - k1118)     # new on the 11-19 page
    assert len(dropped) == 4 and len(added) == 4, (dropped, added)

    SPOT.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(
        [dict(read_utc_date=READ_UTC, source_url=URL_RES, date_as_printed=ds, date=d,
              team=t, player=p, transaction=tr,
              on_2026_11_18_capture="yes" if (d, t, p) in k1118 else "no",
              on_2026_11_19_capture="yes" if (d, t, p) in k1119 else "no")
         for ds, (d, t, p, tr) in zip([r[0] for r in LIVE_ROWS], live)]
    )
    out.to_csv(SPOT / "reserve_list_2026_11_live_read.csv", index=False)

    return dict(
        live_rows=len(live), dropped=dropped, added=added,
        cap1118_rows=len(k1118), cap1119_rows=len(k1119),
    )


FLAG_COLS = ["id", "severity", "finding", "next", "source_label", "source_url"]


def flags(stats: dict) -> pd.DataFrame:
    def fmt(rows: list[tuple[str, str, str]]) -> str:
        return "; ".join(f"{p} ({t}, {d[5:].replace('-', '/')})" for d, t, p in rows)

    f52 = (
        "NFL.com November reserve page is not shown to be a complete record (fixed-size window not confirmed). The 2026-11-18T04:42:01Z "
        "capture and the 2026-11-19T04:30:02Z capture each hold 25 November rows, and the live page read on "
        f"2026-11-19 shows the same 25 rows as the 2026-11-19 capture (all 25 match on date, club and player). Four rows dated 11/10 that were on the 2026-11-18 capture are no longer on the page: "
        f"{fmt(stats['dropped'])}. Four rows dated 11/18 were added: {fmt(stats['added'])}. The page gives no "
        "reason for the removals. Malik Willis's reserve listing is therefore present only in the retained "
        "2026-11-18 capture. The same rolling-window pattern is recorded as F-57 on the Flagged page (2026-09 and 2026-10 pages); this row adds a second capture pair that shows it."
    )
    f53 = (
        "Repaired: data/availability/reserve/latest.csv is a rolling file. Once the 2026-11-19 capture overwrote it, "
        "code that labelled it as the 2026-11-18 capture and tests/test_reconcile_depth_charts.py failed on main "
        "(base commit 311d9b5). The sibling session's commit 37816e4 pins compare_reserve() to "
        "history/2026-11-18T044201Z and reports the rolling file as 'recapture'. This branch pins the remaining reader "
        "(the F-48 narrative in pipeline/session_20261118.py facts()) to the same immutable capture."
    )
    rows = [
        dict(id="F-2026-11-19-06", severity="High · open",
             finding=f52,
             next=("Treat any November reserve-list row absent from the page as 'not on the page at capture time', "
                   "never as 'available'. Keep every dated history capture (already done). Owner: confirm with NFL.com "
                   "whether the page is limited to a fixed number of rows, and whether older rows are archived elsewhere, "
                   "before any row-absence test is used as a gate."),
             source_label="NFL.com reserve list, November 2026", source_url=URL_RES),
        dict(id="F-2026-11-19-07", severity="Medium · repaired in this session",
             finding=f53,
             next="No further action. The retained history folders are the only source for 2026-11-18 comparisons.",
             source_label="NFL.com reserve list, November 2026", source_url=URL_RES),
        dict(id="F-2026-11-19-09", severity="High · repaired in this branch",
             finding=(
                 "Dated comparisons read the rolling availability files that the scheduled fetch rewrites, so "
                 "the first fresh capture would have moved verified verdicts: pipeline/req_annex_2026_11_18.py "
                 "died in every availability run since 2026-11-18T19:24Z (KC omission pin read 3 against an "
                 "expected 1; runs 44380205336..44611301993, red at Makefile:94), and past that pin the same "
                 "class would have flipped claim_checks C-07/C-11, reread F-2026-11-19-02, the 120-row "
                 "spot-check, register-evidence R51 facts, the lineup-claim quote test and four live-verify "
                 "grade tests (measured on the fresh-capture runner, runs 44617589555 and 44619561243: 4 failed, "
                 "426 passed). Repaired by pinning every dated reader to data/availability/history/2026-11-18/ "
                 "(C-02 keeps the active capture), plus a schema-stable internal-consistency CSV so a clean "
                 "capture can no longer write a 0-byte file that aborts render_site. Verified by the "
                 "fresh-capture runner: build and full suite green on a real fetched week-11 capture."),
             next=("Never re-point a dated comparison at a rolling file; a new capture adds a new dated "
                   "baseline, it does not move an old one. The scheduled availability job now converges the "
                   "derived registers its capture feeds before it commits (reserve-list.yml)."),
             source_label="NFL.com injury report (Week 10 URL)", source_url=URL_INJ),
    ]
    return pd.DataFrame(rows, columns=FLAG_COLS)


def main() -> None:
    stats = build()
    df = flags(stats)
    INTEG.mkdir(parents=True, exist_ok=True)
    df.to_csv(INTEG / "flagged_2026_11_19.csv", index=False)
    print(f"live rows {stats['live_rows']} · dropped {len(stats['dropped'])} · added {len(stats['added'])} · "
          f"flags {len(df)}")


if __name__ == "__main__":
    main()
