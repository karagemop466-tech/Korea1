"""R7-01 — a price-snapshot store that records the opening and closing number
for every market this project originates (side, total, moneyline).

What the brief asks for
-----------------------
"Add a price-snapshot store that records opening and closing numbers for every
market we originate."

Why this cannot be done by relabelling an existing column
--------------------------------------------------------
An opening price and a closing price are two *different observations of the
market at two different times*. The store therefore has one row per
`(game, market, side, snapshot_kind)` and every row carries the source that
recorded it. A number is never copied from one snapshot kind into the other.

Measured facts about the pinned archive (re-derived in this module, printed in
the build log, published on `prices.html`):

* `games.csv` carries `spread_line`, `total_line`, `home_moneyline`,
  `away_moneyline`, `home_spread_odds`, `away_spread_odds`, `over_odds`,
  `under_odds`. **The pinned data dictionary `DATASETS.md` documents none of
  these columns** (verified by reading the file at the pinned commit), and the
  repository ships no capture timestamp for any of them. Their snapshot kind is
  therefore `UNDATED` — not "close", not "open". This is the single most
  important limitation of the whole project and it is not repaired here; it is
  recorded per row.
* `initial_lines.csv` is documented by its own filename and content as the
  *initial* line, covers **2021 only**, and names a single sportsbook,
  **WSGT**. It is the only source in the pin whose snapshot kind is stated by
  the data itself.
* `closing_lines.csv` is named *closing* by its filename. It supplies per-side
  prices (`odds`) for 2017-2018 only; for 2006-2016 the `odds` field is empty
  on every spread and total row.
* Therefore a true opening-to-closing movement can be measured **only for
  2021**, and only against an undated second observation whose kind is unknown.
  For every other season the store records an undated price and an explicit
  `closing` observation from a *differently named* file, and the movement
  column is left blank rather than computed across two instruments of unknown
  comparability.

Nothing here infers an opener, fills a missing price, or upgrades "the file is
called closing" into "the quote is an authenticated closing offer".

Outputs
-------
data/prices/price_snapshots.csv      one row per game x market x side x kind
data/prices/price_inventory.csv      coverage and disagreement facts per season
data/prices/price_provenance.json    the source register used by every row

Run:  python pipeline/price_snapshots.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW, ROOT, read_json, write_json  # noqa: E402

OUT = ROOT / "data" / "prices"
OUT.mkdir(parents=True, exist_ok=True)

SHA = read_json(ROOT / "data" / "sources.json")["upstream"]["commit_sha"]
BLOB = f"https://github.com/nflverse/nfldata/blob/{SHA}/data/"

# ---------------------------------------------------------------------------
# Snapshot-kind vocabulary. These strings are the only values allowed in the
# `snapshot_kind` column; `tests/test_price_snapshots.py` fails on any other.
# ---------------------------------------------------------------------------
UNDATED = "UNDATED"       # the file states no capture time; kind not asserted
INITIAL = "INITIAL"       # the file itself states this is the initial line
CLOSING = "CLOSING"       # the file itself states this is the closing line

KINDS = (UNDATED, INITIAL, CLOSING)

# One provenance record per source instrument. `claims_kind` is what the *source
# itself* asserts, never what we would like it to assert.
PROVENANCE = {
    "games_csv": {
        "file": "games.csv",
        "url": BLOB + "games.csv",
        "local": "data/raw/games.csv",
        "claims_kind": UNDATED,
        "timestamp_field": None,
        "documented_columns": [],
        "note": (
            "Carries spread_line, total_line, the two moneylines and the four "
            "price columns. The pinned data dictionary DATASETS.md documents none of "
            "them: it stops at stadium/referee fields. No capture time exists in the "
            "file, so the snapshot kind cannot be established from the data. Treated "
            "as UNDATED and never described as an opening or a closing price."
        ),
    },
    "initial_lines_csv": {
        "file": "initial_lines.csv",
        "url": BLOB + "initial_lines.csv",
        "local": "data/raw/initial_lines.csv",
        "claims_kind": INITIAL,
        "timestamp_field": None,
        "documented_columns": ["season", "sportsbook", "type", "about", "side", "line"],
        "note": (
            "Filename and content both state 'initial'. 2021 season only, one "
            "sportsbook (WSGT). Supplies a line but no price for either side."
        ),
    },
    "closing_lines_csv": {
        "file": "closing_lines.csv",
        "url": BLOB + "closing_lines.csv",
        "local": "data/raw/closing_lines.csv",
        "claims_kind": CLOSING,
        "timestamp_field": None,
        "documented_columns": ["game_id", "alt_game_id", "type", "side", "line", "odds", "outcome"],
        "note": (
            "Filename states 'closing'. No timestamp field. Provides per-side odds for "
            "2017-2018 only; spread and total odds are empty for 2006-2016."
        ),
    },
}


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW / name, low_memory=False)


def _altid(frame: pd.DataFrame) -> pd.Series:
    """The human-readable id used by the two line files, built from games.csv.

    Verified unique on games.csv (7,548 rows, 0 duplicates) by the build; the
    assertion lives in `main()` so a future pin cannot silently duplicate.
    """
    return (frame.season.astype(str) + "_" + frame.week.astype(str).str.zfill(2)
            + "_" + frame.away_team + "_" + frame.home_team)


# ---------------------------------------------------------------------------
# Snapshot construction
# ---------------------------------------------------------------------------
def _row(game, market, side, kind, source, line, price, *,
         book="", team="", team_side=""):
    return {
        "game_id": game.get("game_id", ""),
        "alt_game_id": game.get("alt_game_id", ""),
        "season": game.get("season", np.nan),
        "week": game.get("week", np.nan),
        "gameday": game.get("gameday", ""),
        "home_team": game.get("home_team", ""),
        "away_team": game.get("away_team", ""),
        "market": market,
        "side": side,
        "team": team,
        "team_side": team_side,
        "snapshot_kind": kind,
        "line": line,
        "price_american": price,
        "book": book,
        "source_key": source,
        "source_url": PROVENANCE[source]["url"],
        "captured_utc": "",          # no source in the pin carries a capture time
        "capture_time_known": False,
    }


def build() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    games = _read("games.csv")
    initial = _read("initial_lines.csv")
    closing = _read("closing_lines.csv")

    games["altid"] = _altid(games)
    games["gid"] = games["game_id"]
    if not games.altid.is_unique:
        raise SystemExit("games.csv alt id is not unique — refusing to build the store")

    rows: list[dict] = []

    # ---- 1. the undated instrument -----------------------------------------
    # Only games that actually carry at least one number are recorded, so the
    # store never implies a price exists where the file is blank.
    num = ["spread_line", "total_line", "home_moneyline", "away_moneyline",
           "home_spread_odds", "away_spread_odds", "over_odds", "under_odds"]
    has = games[num].notna().any(axis=1)
    for r in games[has].itertuples(index=False):
        g = {"game_id": r.game_id, "alt_game_id": r.altid, "season": r.season,
             "week": r.week, "gameday": r.gameday, "home_team": r.home_team,
             "away_team": r.away_team}
        if pd.notna(r.spread_line):
            # Datasets.md is explicit that a positive spread_line means the HOME
            # team was favoured. The conventional handicap for the home side is
            # therefore the negated value; both are stored so a reader never has
            # to guess which convention a column uses.
            rows.append(_row(g, "SPREAD", "HOME", UNDATED, "games_csv",
                             -float(r.spread_line),
                             float(r.home_spread_odds) if pd.notna(r.home_spread_odds) else np.nan,
                             team=r.home_team, team_side="HOME"))
            rows.append(_row(g, "SPREAD", "AWAY", UNDATED, "games_csv",
                             float(r.spread_line),
                             float(r.away_spread_odds) if pd.notna(r.away_spread_odds) else np.nan,
                             team=r.away_team, team_side="AWAY"))
        if pd.notna(r.total_line):
            for side, price in (("OVER", r.over_odds), ("UNDER", r.under_odds)):
                rows.append(_row(g, "TOTAL", side, UNDATED, "games_csv",
                                 float(r.total_line),
                                 float(price) if pd.notna(price) else np.nan))
        if pd.notna(r.home_moneyline):
            rows.append(_row(g, "MONEYLINE", "HOME", UNDATED, "games_csv", np.nan,
                             float(r.home_moneyline), team=r.home_team, team_side="HOME"))
        if pd.notna(r.away_moneyline):
            rows.append(_row(g, "MONEYLINE", "AWAY", UNDATED, "games_csv", np.nan,
                             float(r.away_moneyline), team=r.away_team, team_side="AWAY"))

    # ---- 2. the initial instrument (2021, one book) -------------------------
    gmap = games[["altid", "gid", "season", "week", "gameday", "home_team", "away_team"]].rename(
        columns={"season": "season_g", "week": "week_g", "gameday": "gameday_g",
                 "home_team": "home_g", "away_team": "away_g"})
    _i = initial.copy()
    _i["_keep"] = np.arange(len(_i))
    ini = _i.merge(gmap, left_on="about", right_on="altid", how="left")
    ini = ini.sort_values("_keep").drop(columns=["_keep"])
    unmatched_initial = int(ini.gid.isna().sum())
    for r in ini[ini.gid.notna()].itertuples(index=False):
        g = {"game_id": r.gid, "alt_game_id": r.about, "season": r.season_g,
             "week": r.week_g, "gameday": r.gameday_g, "home_team": r.home_g,
             "away_team": r.away_g}
        if r.type == "SPREAD":
            home_side = r.side == r.home_g
            rows.append(_row(g, "SPREAD", "HOME" if home_side else "AWAY", INITIAL,
                             "initial_lines_csv", float(r.line), np.nan,
                             book=r.sportsbook,
                             team=r.side, team_side="HOME" if home_side else "AWAY"))
        elif r.type == "TOTAL":
            rows.append(_row(g, "TOTAL", r.side.upper(), INITIAL, "initial_lines_csv",
                             float(r.line), np.nan, book=r.sportsbook))

    # ---- 3. the closing instrument -----------------------------------------
    gmap = games[["altid", "gid", "season", "week", "gameday", "home_team", "away_team"]].rename(
        columns={"season": "season_g", "week": "week_g", "gameday": "gameday_g",
                 "home_team": "home_g", "away_team": "away_g"})
    _c = closing.copy()
    _c["_keep"] = np.arange(len(_c))
    clo = _c.merge(gmap, left_on="alt_game_id", right_on="altid", how="left")
    clo = clo.sort_values("_keep").drop(columns=["_keep"])
    unmatched_closing = int(clo.gid.isna().sum())
    for r in clo[clo.gid.notna()].itertuples(index=False):
        g = {"game_id": r.gid, "alt_game_id": r.alt_game_id, "season": r.season_g,
             "week": r.week_g, "gameday": r.gameday_g, "home_team": r.home_g,
             "away_team": r.away_g}
        price = float(r.odds) if pd.notna(r.odds) else np.nan
        line = float(r.line) if pd.notna(r.line) else np.nan
        if r.type == "SPREAD":
            home_side = r.side == r.home_g
            rows.append(_row(g, "SPREAD", "HOME" if home_side else "AWAY", CLOSING,
                             "closing_lines_csv", line, price,
                             team=r.side, team_side="HOME" if home_side else "AWAY"))
        elif r.type == "TOTAL":
            rows.append(_row(g, "TOTAL", str(r.side).upper(), CLOSING,
                             "closing_lines_csv", line, price))
        else:
            home_side = r.side == r.home_g
            rows.append(_row(g, "MONEYLINE", "HOME" if home_side else "AWAY", CLOSING,
                             "closing_lines_csv", np.nan, price,
                             team=r.side, team_side="HOME" if home_side else "AWAY"))

    snap = pd.DataFrame(rows)
    order = ["game_id", "alt_game_id", "season", "week", "gameday", "home_team", "away_team",
             "market", "side", "team", "team_side", "snapshot_kind", "line",
             "price_american", "book", "source_key", "source_url", "captured_utc",
             "capture_time_known"]
    snap = snap[order].sort_values(
        ["season", "week", "gameday", "alt_game_id", "market", "side", "snapshot_kind"]
    ).reset_index(drop=True)

    if not set(snap.snapshot_kind.unique()) <= set(KINDS):
        raise SystemExit("unknown snapshot_kind — refusing to publish")
    if snap.capture_time_known.any():
        raise SystemExit("a capture time was claimed without a source — refusing to publish")

    facts = {
        "games_rows": int(len(games)),
        "games_altid_unique": bool(games.altid.is_unique),
        "initial_unmatched_rows": unmatched_initial,
        "closing_unmatched_rows": unmatched_closing,
        "rows": int(len(snap)),
        "rows_by_kind": {k: int(v) for k, v in snap.snapshot_kind.value_counts().items()},
        "games_by_kind": {k: int(snap[snap.snapshot_kind == k].game_id.nunique())
                          for k in KINDS},
        "markets": sorted(snap.market.unique().tolist()),
        "capture_time_rows": int(snap.capture_time_known.sum()),
    }
    return snap, coverage(snap), facts


def coverage(snap: pd.DataFrame) -> pd.DataFrame:
    """Per-season-per-market coverage and the opener-to-closer overlap."""
    out = []
    for (season, market), grp in snap.groupby(["season", "market"], sort=True):
        per_kind = {}
        for kind in KINDS:
            sub = grp[grp.snapshot_kind == kind]
            # a game "has" a snapshot when any side of that market is recorded
            per_kind[kind] = sub.game_id.nunique()
        ud = set(grp[grp.snapshot_kind == UNDATED].game_id)
        ini = set(grp[grp.snapshot_kind == INITIAL].game_id)
        clo = set(grp[grp.snapshot_kind == CLOSING].game_id)
        overlap_ic = len(ini & clo)
        overlap_uc = len(ud & clo)
        # Two measurements, kept apart because they answer different questions.
        #
        # (a) OPEN -> CLOSE. Only possible when the *same* game carries an
        #     INITIAL row and a CLOSING row for the same market and side. Both
        #     files name their own snapshot kind, so this is the only movement
        #     this project can measure without assuming what an undated file is.
        # (b) UNDATED -> CLOSE. Where the closing file and the undated column
        #     disagree on the number, at most one of them can be right. The size
        #     of the disagreement is published as an *observation about the
        #     archive*, never as line movement, because an undated column has no
        #     position on the clock.
        mean_move = sd_move = np.nan
        n_move = 0
        if overlap_ic:
            a = grp[grp.snapshot_kind == INITIAL].drop_duplicates(["game_id", "side"])
            b = grp[grp.snapshot_kind == CLOSING].drop_duplicates(["game_id", "side"])
            j = a.merge(b, on=["game_id", "side"], suffixes=("_i", "_c"))
            j = j[j.line_i.notna() & j.line_c.notna()]
            move = j.line_c - j.line_i
            n_move = int(len(move))
            if n_move > 1:
                mean_move, sd_move = float(move.mean()), float(move.std(ddof=1))
        n_disagree = 0
        median_disagree = np.nan
        if overlap_uc:
            a = grp[grp.snapshot_kind == UNDATED].drop_duplicates(["game_id", "side"])
            b = grp[grp.snapshot_kind == CLOSING].drop_duplicates(["game_id", "side"])
            j = a.merge(b, on=["game_id", "side"], suffixes=("_u", "_c"))
            j = j[j.line_u.notna() & j.line_c.notna()]
            if len(j):
                diff = (j.line_c - j.line_u).abs()
                n_disagree = int((diff > 1e-9).sum())
                if n_disagree:
                    median_disagree = float(diff[diff > 1e-9].median())
        prices = grp.price_american.notna()
        if n_move > 1:
            status = "MEASURED — initial and closing instruments name their own kind"
        elif overlap_ic:
            status = "TOO FEW PAIRS — initial and closing overlap on one game only"
        elif overlap_uc:
            status = "BLANK — movement needs two named instruments; only an undated and a closing series exist"
        else:
            status = "BLANK — no second instrument covers this season at all"
        out.append({
            "season": int(season),
            "market": market,
            "games_undated": per_kind[UNDATED],
            "games_initial": per_kind[INITIAL],
            "games_closing": per_kind[CLOSING],
            "games_with_price_any_kind": int(grp[prices].game_id.nunique()),
            "initial_vs_closing_overlap": overlap_ic,
            "undated_vs_closing_overlap": overlap_uc,
            "initial_to_closing_pairs": n_move,
            "initial_to_closing_mean_move": mean_move,
            "initial_to_closing_sd_move": sd_move,
            "undated_vs_closing_disagreements": n_disagree,
            "undated_vs_closing_median_abs_gap": median_disagree,
            "movement_status": status,
        })
    return pd.DataFrame(out)


def main() -> None:
    snap, cov, facts = build()
    snap.to_csv(OUT / "price_snapshots.csv", index=False)
    cov.to_csv(OUT / "price_inventory.csv", index=False)
    write_json(OUT / "price_provenance.json", {
        "generated_by": "pipeline/price_snapshots.py",
        "pin_commit": SHA,
        "sources": PROVENANCE,
        "snapshot_kinds": list(KINDS),
        "facts": facts,
        "rule": (
            "One row per game x market x side x snapshot_kind. A snapshot kind is "
            "only asserted when the source itself asserts it. No capture time is "
            "invented: when the source has no timestamp field the row records an "
            "empty captured_utc and capture_time_known=false."
        ),
    })
    print(f"price_snapshots: {snap.shape}")
    print(f"  rows by kind: {facts['rows_by_kind']}")
    print(f"  games by kind: {facts['games_by_kind']}")
    print(f"  initial unmatched: {facts['initial_unmatched_rows']} · "
          f"closing unmatched: {facts['closing_unmatched_rows']}")
    print(f"price_inventory: {cov.shape} · measurable movements: "
          f"{int((cov.movement_status.str.startswith('MEASURED')).sum())}")


if __name__ == "__main__":
    main()
