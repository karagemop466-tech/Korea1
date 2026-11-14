"""P1 — price-snapshot store.

Opening and closing numbers for every market the model originates
(spread, total, moneyline home/away), each stamped with its source.
Nothing is inferred: a number the pinned archive does not carry is left
blank, never filled.

Opening numbers
---------------
nflverse/nfldata initial_lines.csv — 2021 season only, book WSGT,
spread and total lines only. The archive carries no moneyline openers and
no opening prices, so those cells are blank and flagged NOT AVAILABLE.

Closing numbers
---------------
nflverse/nfldata games.csv — the archive ships closing lines, not openers.
No official NFL source publishes betting lines, so every market row carries
the UNVERIFIED flag and links to the pinned community archive. The row's
official link (NFL schedule) is context only — it establishes that the game
is an NFL game; it is not a source for the line.

Outputs
-------
data/processed/price_snapshot.csv   the store (one row per game × market × side)
data/processed/price_snapshot.json  counts and sources
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, RAW, ROOT, sha256_of, read_json, write_json  # noqa: E402

INITIAL_LOGICAL = "data/initial_lines.csv"
GAMES_LOGICAL = "data/games.csv"
OUT_CSV = PROC / "price_snapshot.csv"
OUT_JSON = PROC / "price_snapshot.json"

MARKETS = [
    # market, side, closer line column, closer price column, opener filter
    ("SPREAD", "HOME", "spread_line", "home_spread_odds", None),
    ("TOTAL", "OVER", "total_line", "over_odds", "TOTAL"),
    ("TOTAL", "UNDER", "total_line", "under_odds", "TOTAL"),
    ("MONEYLINE", "HOME", None, "home_moneyline", None),
    ("MONEYLINE", "AWAY", None, "away_moneyline", None),
]


def pinned_url(sha: str, logical: str) -> str:
    return f"https://github.com/nflverse/nfldata/blob/{sha}/{logical}"


def main() -> None:
    manifest = read_json(ROOT / "data" / "sources.json")
    sha = manifest["upstream"]["commit_sha"]
    by_logical = {f["logical"]: f for f in manifest["files"]}
    if INITIAL_LOGICAL not in by_logical or GAMES_LOGICAL not in by_logical:
        raise RuntimeError("pinned archive must contain initial_lines.csv and games.csv")

    games = pd.read_csv(RAW / "games.csv", dtype=str)
    openers = pd.read_csv(RAW / "initial_lines.csv", dtype=str)

    opener_index: dict[tuple[str, str], float] = {}
    for r in openers.itertuples(index=False):
        opener_index[(str(r.about), str(r.side))] = float(r.line)

    url_initial = pinned_url(sha, INITIAL_LOGICAL)
    url_games = pinned_url(sha, GAMES_LOGICAL)
    official_schedule = "https://www.nfl.com/schedules/"

    rows = []
    n_games_with_market = 0
    n_openers = 0
    for r in games.itertuples(index=False):
        game_id = str(r.game_id)
        season = str(r.season)
        week = str(r.week)
        home_team = str(r.home_team)
        away_team = str(r.away_team)

        for market, side, line_col, price_col, opener_type in MARKETS:
            closer_line = closer_price = None
            if line_col is not None and hasattr(r, line_col):
                v = getattr(r, line_col)
                if pd.notna(v) and str(v).strip() not in ("", "nan", "None"):
                    closer_line = float(v)
            if price_col is not None and hasattr(r, price_col):
                v = getattr(r, price_col)
                if pd.notna(v) and str(v).strip() not in ("", "nan", "None"):
                    closer_price = float(v)

            opener_line = None
            if opener_type is None:
                key_side = home_team if side == "HOME" else away_team
                v = opener_index.get((game_id, key_side))
                if v is not None:
                    opener_line = float(v)
                    n_openers += 1
            else:
                v = opener_index.get((game_id, opener_type))
                if v is not None:
                    opener_line = float(v)
                    n_openers += 1

            if closer_line is None and closer_price is None and opener_line is None:
                continue

            rows.append(dict(
                game_id=game_id, season=season, week=week, market=market, side=side,
                opener_line=opener_line if opener_line is not None else "",
                opener_price="",
                closer_line=closer_line if closer_line is not None else "",
                closer_price=closer_price if closer_price is not None else "",
                opener_source=url_initial,
                closer_source=url_games,
                official_context=official_schedule,
                opening_available="YES" if opener_line is not None else "NO",
                flag=("Closing: community archive (closing line, unverified) · "
                      "opening: available (WSGT book, 2021 snapshot)"
                      if opener_line is not None else
                      "Closing: community archive (closing line, unverified) · "
                      "opening: NOT AVAILABLE — the archive covers 2021 openers only"),
            ))

    frame = pd.DataFrame(rows,
                         columns=["game_id", "season", "week", "market", "side",
                                  "opener_line", "opener_price", "closer_line",
                                  "closer_price", "opener_source", "closer_source",
                                  "official_context", "opening_available", "flag"])
    frame = frame.sort_values(["game_id", "market", "side"], kind="mergesort").reset_index(drop=True)
    frame.to_csv(OUT_CSV, index=False)

    n_games = frame.game_id.nunique()
    write_json(OUT_JSON, {
        "store": "price_snapshot",
        "rows": int(len(frame)),
        "games": int(n_games),
        "markets": ["SPREAD", "TOTAL", "MONEYLINE"],
        "sides": {"SPREAD": ["HOME"], "TOTAL": ["OVER", "UNDER"], "MONEYLINE": ["HOME", "AWAY"]},
        "opener_rows": int(n_openers),
        "opening_available_games": int(frame[frame.opening_available == "YES"].game_id.nunique()),
        "upstream": {"repo": "nflverse/nfldata", "commit_sha": sha,
                     "url": f"https://github.com/nflverse/nfldata/commit/{sha}"},
        "sources": {
            "initial_lines": url_initial,
            "games": url_games,
            "official_context": official_schedule,
        },
        "notes": [
            "nflverse ships closing lines, not openers; opening lines exist only for the 2021 season",
            "the archive's opener book is WSGT; opener prices are not carried by the archive",
            "there are no moneyline openers in the archive",
            "no official NFL source publishes betting lines; every price row is UNVERIFIED community data",
            "blank cells mean the value is not in the pinned archive, never an inferred value",
        ],
    })
    print(f"price snapshot: {len(frame)} rows, {n_games} games, {n_openers} opening lines")


if __name__ == "__main__":
    main()
