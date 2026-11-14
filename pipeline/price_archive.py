"""BF1 (session `arena/bfcd9879-korea1`) — the price-archive store (renamed from
`price_snapshots.py` after the parallel session `arena/fcba7eb5-korea1` merged a
module of that name; theirs is kept unchanged and remains canonical for the
strict blank-cell store, this module holds the archive-populated view).

Records, for **every market the pipeline originates** (spread, total, home
moneyline, away moneyline), every price snapshot the repository actually holds:

===================  ==========================================================
column               meaning
===================  ==========================================================
``open_price``       opening number, Sportsbook Review 10-year archive
                     (2011–2021 only), tier ``verified_third_party``
``archive_close``    closing number, same archive (moneyline is published as a
                     single daily price, so the archive has no separate ML open)
``pin_close``        closing line inside the pinned nflverse snapshot
                     (settled games, 1999–2026), hash-verified file
``freeze_market``    market number at the moment our line was frozen —
                     forward-ledger audit sets for 2026 W8–W9
                     (``published_lines.csv``) and the W10 freeze card
                     (``cards.csv``, frozen 2026-11-12T13:26:48Z)
``our_frozen_line``  the line this pipeline originated at the same freeze
===================  ==========================================================

Rules this module obeys, from the brief:

* nothing is inferred — a snapshot that does not exist stays blank and carries
  an explicit ``*_flag`` saying exactly why it is blank;
* every row carries an official NFL URL for its game, so a reviewer can check
  the fixture on an official page (the ``/scores/<season>/week-<n>`` pattern
  was fetched and confirmed live on 2026-11-14 for 2004 week 1; no postseason
  pattern has been confirmed, so those rows use the official schedules root
  and say so);
* no price on this page is described as official: the NFL publishes no odds,
  so every quote here is third-party, community or ledger-frozen and gate
  **G1 fails** for all of them. The store records *our captures*; it does not
  authenticate a bookmaker offer.

Archive join: the SBR archive labels the relocated franchises with their
**current** codes for every season (LV, LAC, LAR) while the pinned snapshot
uses the codes in force that season (OAK, SD, STL → LA). The alias map below
is season-aware and is asserted by ``tests/test_price_snapshot_store.py``.

Outputs (both committed, deterministic — no run timestamps):

* ``data/processed/price_archive.csv``          — one row per game × market
* ``data/processed/price_archive_coverage.csv``  — per season × market counts
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json  # noqa: E402

LAB_GAMES = ROOT / "data" / "lab" / "games.csv"
PIN = ROOT / "data" / "processed" / "games_model.csv"
LEDGER = ROOT / "data" / "forward" / "published_lines.csv"
CARDS = ROOT / "data" / "forward" / "cards.csv"
GRADED = ROOT / "data" / "forward" / "graded_cards.csv"
OFFICIAL_RESULTS = ROOT / "data" / "forward" / "official_results.csv"

MARKETS = ["SPREAD", "TOTAL", "ML_HOME", "ML_AWAY"]

QUOTE_STATUS = ("NOT AN AUTHENTICATED BOOKMAKER QUOTE · third-party archive, "
                "pinned community close or ledger freeze · gate G1 fails")

# The archive covers 2011–2021 only (verified from its own season column; see
# data/lab/sources.json, source id SBR-10Y).
ARCHIVE_SEASONS = range(2011, 2022)

# Season-aware code aliases: archive current-code -> pin code in force that
# season. Only the three relocated franchises differ; every other club uses the
# same code in both files.
def _pin_code(code: str, season: int) -> str:
    if code == "LV":
        return "OAK" if season <= 2019 else "LV"
    if code == "LAC":
        return "SD" if season <= 2016 else "LAC"
    if code == "LAR":
        return "STL" if season <= 2015 else "LA"
    return code


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _schedule_url(season: int, week: int, game_type: str) -> tuple[str, str]:
    if str(game_type).upper() == "REG":
        return (f"https://www.nfl.com/scores/{int(season)}/week-{int(week)}",
                "verified pattern: fetched 2026-11-14 for 2004 week 1")
    return ("https://www.nfl.com/schedules/",
            "POSTSEASON PATTERN NOT VERIFIED — official schedules root used")


def _f(x) -> float | None:
    try:
        if x is None or x == "" or pd.isna(x):
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def main() -> int:
    pin_sha = read_json(ROOT / "data/sources.json")["upstream"]["commit_sha"]
    gm = pd.read_csv(PIN)
    lab = pd.read_csv(LAB_GAMES)
    lab_sha = _sha256(LAB_GAMES)

    # ---- archive lookup keyed by (season, date, pin-code home/away) --------
    # The archive dates some games a day early or late (2015 W6 stored on
    # 10-17 for 10-18; NE@KC 2014 stored 09-30 for 09-29; MIA@NO 2021 stored
    # 12-28 for 12-27), and it excludes the Super Bowl entirely (10 rows were
    # dropped as neutral-site at ingest — data/lab/integrity.json). The join
    # therefore falls back to a ±1-day window that must still match the exact
    # season and both club codes, and must hit exactly one archive row.
    lab["_h"] = [_pin_code(h, s) for h, s in zip(lab.home, lab.season)]
    lab["_a"] = [_pin_code(a, s) for a, s in zip(lab.away, lab.season)]
    lab["_key"] = (lab.season.astype(str) + "|" + lab.date.astype(str) + "|"
                   + lab._h + "|" + lab._a)
    if lab["_key"].duplicated().any():
        raise SystemExit("archive key is not unique; refusing to guess a join")
    arch = lab.set_index("_key")
    by_clubs: dict[tuple, list[tuple[int, int]]] = {}
    for pos, (season_, h_, a_, date_) in enumerate(
            zip(lab.season, lab._h, lab._a, lab.date)):
        by_clubs.setdefault((int(season_), h_, a_), []).append(
            (int(date_), pos))

    def _lookup(season: int, gameday: str, home: str, away: str):
        """Return (archive row, match kind) or (None, 'none').

        Exact (season, date, both clubs) wins. Otherwise a ±1-day window is
        searched, still requiring the exact season and both club codes, and
        exactly one candidate: identity is confirmed by the clubs, never
        guessed from proximity alone.
        """
        try:
            base = int(str(gameday).replace("-", ""))
        except (TypeError, ValueError):
            return None, "none"
        exact = f"{season}|{base}|{home}|{away}"
        if exact in arch.index:
            return arch.loc[exact], "exact"
        from datetime import date as _date, timedelta
        d0 = _date(base // 10000, (base // 100) % 100, base % 100)
        window = {int((d0 + timedelta(days=k)).strftime("%Y%m%d"))
                  for k in (-1, 1)}
        hits = [(dt, pos) for dt, pos in by_clubs.get((int(season), home, away), [])
                if dt in window]
        if len(hits) == 1:
            kind = "date_minus_1" if hits[0][0] < base else "date_plus_1"
            return lab.iloc[hits[0][1]], kind
        return None, "none"

    # ---- official results (post-pin reads) for dates and URLs --------------
    off = {}
    if OFFICIAL_RESULTS.exists():
        o = pd.read_csv(OFFICIAL_RESULTS, dtype=str, keep_default_na=False)
        for r in o.to_dict("records"):
            off[r["game_id"]] = r

    rows: list[dict] = []
    games: dict[str, dict] = {}

    def emit(game_id, season, week, gameday, matchup, game_type, market,
             open_price, open_flag, arch_close, arch_flag, archive_match,
             pin_close, pin_flag, freeze_market, freeze_flag, our_line,
             status_note):
        # Game-level facts are stored once (price_archive_games.csv) and
        # referenced by game_id; repeating them on every market row would
        # triple the file without adding information.
        if game_id not in games:
            url, url_kind = _schedule_url(season, week, game_type)
            if (game_id in off
                    and off[game_id].get("official_url", "").startswith("https://www.nfl.com/")):
                url = off[game_id]["official_url"]
                url_kind = "official game centre read on NFL.com"
            games[game_id] = dict(
                game_id=game_id, season=int(season), week=int(week),
                gameday=gameday, matchup=matchup, game_status=status_note,
                official_url=url, official_url_kind=url_kind)
        diff = None
        if arch_close is not None and pin_close is not None:
            diff = round(arch_close - pin_close, 4)
        rows.append(dict(
            snapshot_id=f"{game_id}:{market}", game_id=game_id,
            season=int(season), market=market, our_frozen_line=our_line,
            open_price=open_price, open_flag=open_flag,
            archive_close=arch_close, archive_close_flag=arch_flag,
            archive_match=archive_match,
            pin_close=pin_close, pin_close_flag=pin_flag,
            freeze_market=freeze_market, freeze_flag=freeze_flag,
            archive_minus_pin=diff,
        ))

    # ---- 1. every settled game in the pinned snapshot ----------------------
    for r in gm.itertuples():
        a, a_match = _lookup(int(r.season), r.gameday, r.home_team, r.away_team)
        season = int(r.season)
        in_arch = season in ARCHIVE_SEASONS
        matchup = f"{r.away_team} @ {r.home_team}"
        for mkt in MARKETS:
            # open (archive has no moneyline open — single daily price only)
            v_open = None
            if a is not None:
                v_open = {"SPREAD": a.open_spread_home, "TOTAL": a.open_total,
                          "ML_HOME": None, "ML_AWAY": None}.get(mkt)
            vo = _f(v_open)
            if vo is not None:
                open_price, open_flag = vo, "OK"
            elif not in_arch:
                open_price, open_flag = None, "NO_OPEN_SOURCE_FOR_SEASON"
            elif a is None:
                open_price, open_flag = None, "GAME_NOT_IN_ARCHIVE"
            elif mkt.startswith("ML"):
                open_price, open_flag = None, "NO_ML_OPEN_IN_ARCHIVE"
            else:
                open_price, open_flag = None, "NO_OPEN_PRICE_IN_ARCHIVE"
            # archive close
            v_ac = None
            if a is not None:
                v_ac = {"SPREAD": a.close_spread_home, "TOTAL": a.close_total,
                        "ML_HOME": a.home_ml, "ML_AWAY": a.away_ml}.get(mkt)
            vac = _f(v_ac)
            if vac is not None:
                arch_close = vac
                arch_flag = "OK" if not mkt.startswith("ML") else "OK_SINGLE_DAILY_PRICE"
            elif not in_arch:
                arch_close, arch_flag = None, "NO_ARCHIVE_FOR_SEASON"
            elif a is None:
                arch_close, arch_flag = None, "GAME_NOT_IN_ARCHIVE"
            else:
                arch_close, arch_flag = None, "MISSING_IN_ARCHIVE"
            # pinned close (settled games: the pin carries the closing line)
            v_pc = {"SPREAD": r.market_spread, "TOTAL": r.market_total,
                    "ML_HOME": r.market_home_ml, "ML_AWAY": r.market_away_ml}.get(mkt)
            pcv = _f(v_pc)
            if pcv is not None:
                pin_close, pin_flag = pcv, "OK"
            else:
                pin_close, pin_flag = None, "MISSING_IN_PIN"
            emit(r.game_id, r.season, r.week, r.gameday, matchup, r.game_type,
                 mkt, open_price, open_flag, arch_close, arch_flag, a_match,
                 pin_close, pin_flag, None, "NOT_IN_FORWARD_LEDGER", None,
                 "SETTLED_AT_PIN")

    # ---- 2. forward-ledger audit sets for 2026 W8–W9 -----------------------
    if LEDGER.exists():
        fl = pd.read_csv(LEDGER, dtype=str, keep_default_na=False)
        # The audit published the same game under sets A/C/D. The *market*
        # mirrors come from the same pin and must agree across sets; our own
        # line legitimately differs per set (that is what the audit compares).
        # Record the market once, and our line from set D (the canonical board
        # that is on the site); assert the mirrors instead of assuming them.
        seen: dict[str, dict] = {}
        for r in fl.to_dict("records"):
            gid = r["game_id"]
            if gid in seen:
                prev = seen[gid]
                for c in ("mirror_spread_at_pin", "mirror_total_at_pin",
                          "mirror_close_spread", "mirror_close_total"):
                    if prev[c] != r[c]:
                        raise SystemExit(f"ledger mirrors disagree for {gid}:{c}")
                if r.get("set") == "D":
                    prev["line_spread"] = r["line_spread"]
                    prev["line_total"] = r["line_total"]
                    prev["_set"] = "D"
                continue
            seen[gid] = {**r, "_set": r.get("set", "")}
        for gid, r in seen.items():
            o = off.get(gid, {})
            season, week = int(r["season"]) if r.get("season") else 2026, int(r["week"])
            gameday = o.get("official_game_date", "")
            matchup = f"{r['away_team']} @ {r['home_team']}"
            status = f"SETTLED_POST_PIN_W8_W9 (our line from ledger set {r['_set']})"
            for mkt, m_col, close_col, line_col in (
                    ("SPREAD", "mirror_spread_at_pin", "mirror_close_spread", "line_spread"),
                    ("TOTAL", "mirror_total_at_pin", "mirror_close_total", "line_total")):
                fz, cl, our = _f(r[m_col]), _f(r[close_col]), _f(r[line_col])
                emit(gid, season, week, gameday, matchup, "REG", mkt,
                     None, "NO_OPEN_SOURCE_FOR_SEASON",
                     None, "NO_ARCHIVE_FOR_SEASON", "not_applicable",
                     cl, "LEDGER_MIRROR_CLOSE" if cl is not None else "NO_CLOSE_IN_LEDGER",
                     fz, "OK" if fz is not None else "MISSING_IN_LEDGER",
                     our, status)
            for mkt in ("ML_HOME", "ML_AWAY"):
                emit(gid, season, week, gameday, matchup, "REG", mkt,
                     None, "NO_OPEN_SOURCE_FOR_SEASON",
                     None, "NO_ARCHIVE_FOR_SEASON", "not_applicable",
                     None, "NO_ML_IN_LEDGER_MIRROR",
                     None, "NO_ML_IN_LEDGER_MIRROR", None,
                     status)

    # ---- 3. the 2026 W10 freeze card --------------------------------------
    if CARDS.exists():
        cards = pd.read_csv(CARDS, dtype=str, keep_default_na=False)
        graded = {}
        if GRADED.exists():
            for r in pd.read_csv(GRADED, dtype=str,
                                 keep_default_na=False).to_dict("records"):
                graded[r["game_id"]] = r
        for r in cards.to_dict("records"):
            gid = r["game_id"]
            g = graded.get(gid, {})
            settled = g.get("official_home_score", "") not in ("", None)
            status = "SETTLED_POST_PIN_W10" if settled else "SCHEDULED_W10_FREEZE"
            matchup = f"{r['away_team']} @ {r['home_team']}"
            season, week, gameday = int(r["season"]), int(r["week"]), r["gameday"]
            for mkt, fz_col, our_col, close_col in (
                    ("SPREAD", "market_spread", "fair_spread", "mirror_close_spread"),
                    ("TOTAL", "market_total", "fair_total", "mirror_close_total"),
                    ("ML_HOME", "market_home_ml", "originated_home_ml", None),
                    ("ML_AWAY", "market_away_ml", "originated_away_ml", None)):
                fz, our = _f(r[fz_col]), _f(r[our_col])
                cl = _f(g.get(close_col)) if close_col and g else None
                if close_col is None:
                    close, close_flag = None, "NO_ML_CLOSE_IN_SOURCE"
                elif cl is not None:
                    close, close_flag = cl, "LEDGER_MIRROR_CLOSE"
                elif settled:
                    close, close_flag = None, "MISSING_IN_GRADED_CARD"
                else:
                    close, close_flag = None, "NOT_YET_SETTLED"
                emit(gid, season, week, gameday, matchup, "REG", mkt,
                     None, "NO_OPEN_SOURCE_FOR_SEASON",
                     None, "NO_ARCHIVE_FOR_SEASON", "not_applicable",
                     close, close_flag,
                     fz, "OK" if fz is not None else "MISSING_IN_CARD",
                     our, status)

    out = pd.DataFrame(rows)
    out.to_csv(PROC / "price_archive.csv", index=False, float_format="%.6g")
    pd.DataFrame(games.values()).to_csv(PROC / "price_archive_games.csv",
                                        index=False)

    # ---- coverage summary --------------------------------------------------
    cov = (out.groupby(["season", "market"], as_index=False)
           .agg(games=("game_id", "count"),
                open_snapshots=("open_price", "count"),
                archive_closes=("archive_close", "count"),
                pin_closes=("pin_close", "count"),
                freeze_snapshots=("freeze_market", "count")))
    cov["archive_sha256_12"] = lab_sha[:12]
    cov["pin_commit_12"] = pin_sha[:12]
    cov["quote_status"] = QUOTE_STATUS
    cov.to_csv(PROC / "price_archive_coverage.csv", index=False)

    print(f"price_archive: {len(out)} rows across {out.game_id.nunique()} games")
    for col in ("open_price", "archive_close", "pin_close", "freeze_market"):
        print(f"  {col}: {int(out[col].notna().sum())}")
    print(f"  archive sha256[:12]={lab_sha[:12]} pin={pin_sha[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
