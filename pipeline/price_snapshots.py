"""U3 (session arena/fcba7eb5-korea1, 2026-11-14) — the price-snapshot store.

Brief: "records opening and closing numbers for every market we originate."

What the store is
-----------------
One row per originated market per game, for every game the engine has originated
(6,073 walk-forward games 2004–2026 in data/processed/originated_lines.csv, plus the
164 upcoming games in data/processed/originated_upcoming.csv). Each game has three
markets, originated in this fixed order (the origination order from the brief):

    1  SPREAD      the side: fair margin (home-favoured positive, repo convention)
    2  TOTAL       the total: fair combined points
    3  MONEYLINE   the moneyline, derived from the same margin distribution

The originated (fair) value is ours and is reproducible from the committed inputs.

What the store is NOT
---------------------
Opening and closing columns are filled only from an official or operator-timestamped
quote. The repository holds none (data/processed/validation_config.json:
"official_quote_source_available": false). So every opening and closing cell is blank
and carries the status UNVERIFIED. The pinned community closing values (nflverse,
`market_spread`, `market_total`, `market_home_ml`, `market_away_ml`) exist for many
games. They are research inputs, not official numbers, and they are deliberately NOT
copied into the opening or closing columns. Counts of them are published per season
in data/governance/price_snapshot_coverage.csv so the gap is measured, not hidden.

For the 14 frozen forward games, the originated values carry the ledger freeze time and
the ledger entry hash (data/forward/cards.csv). For the rest, origination time is not
recorded, because the walk-forward values were reconstructed after the fact.

Outputs
-------
  data/forward/price_snapshots.csv                 the store (one row per market)
  data/governance/price_snapshot_coverage.csv      per-season coverage counts

Run:  python pipeline/price_snapshots.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROC = ROOT / "data" / "processed"
FWD = ROOT / "data" / "forward"
GOV = ROOT / "data" / "governance"

MARKETS = [(1, "SPREAD"), (2, "TOTAL"), (3, "MONEYLINE")]
UNVERIFIED_OPEN = "UNVERIFIED"          # legend: no official or operator-timestamped opening quote on file
UNVERIFIED_CLOSE = "UNVERIFIED"         # legend: no official or operator-timestamped closing quote on file
NOT_RECORDED = "not recorded"           # legend: walk-forward value reconstructed after the event

STORE_COLUMNS = [
    "market_row_id", "game_id", "season", "week", "gameday", "home_team", "away_team",
    "origination_order", "market", "originated_value", "originated_home_ml", "originated_away_ml",
    "originated_units", "originated_utc", "ledger_entry_hash",
    "opening_value", "opening_utc", "opening_source", "opening_status",
    "closing_value", "closing_utc", "closing_source", "closing_status",
    "fair_source",
]


def _num(x, nd: int = 2):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return ""
    if math.isnan(v):
        return ""
    return round(v, nd)


def _ml(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return ""
    if math.isnan(v):
        return ""
    return int(round(v))


def load_games() -> pd.DataFrame:
    """Walk-forward originations plus the upcoming slate, one row per game."""
    lines = pd.read_csv(PROC / "originated_lines.csv", low_memory=False)
    up = pd.read_csv(PROC / "originated_upcoming.csv", low_memory=False)
    lines["_src"] = "data/processed/originated_lines.csv"
    up["_src"] = "data/processed/originated_upcoming.csv"
    both = pd.concat([lines, up], ignore_index=True)
    dup = both.duplicated("game_id", keep="last")
    both = both[~dup].copy()
    return both.sort_values(["season", "week", "gameday", "game_id"]).reset_index(drop=True)


def frozen_forward() -> dict:
    """game_id -> (frozen_utc, entry_hash) for the games frozen in the forward ledger."""
    p = FWD / "cards.csv"
    if not p.exists():
        return {}
    c = pd.read_csv(p, dtype=str, keep_default_na=False)
    out = {}
    for r in c.to_dict("records"):
        out[r["game_id"]] = (r.get("frozen_utc", ""), r.get("entry_hash", ""))
    return out


def build_store(games: pd.DataFrame, frozen: dict) -> pd.DataFrame:
    rows = []
    for g in games.to_dict("records"):
        gid = g["game_id"]
        frz_utc, frz_hash = frozen.get(gid, ("", ""))
        src = g["_src"]
        for order, market in MARKETS:
            if market == "SPREAD":
                val, home_ml, away_ml, units = _num(g.get("fair_spread")), "", "", \
                    "pts home-margin (+ = home fav)"
            elif market == "TOTAL":
                val, home_ml, away_ml, units = _num(g.get("fair_total")), "", "", "pts combined"
            else:
                val, home_ml, away_ml, units = "", _ml(g.get("originated_home_ml")), \
                    _ml(g.get("originated_away_ml")), "American fair (pre-hold)"
            rows.append({
                "market_row_id": f"{gid}|{market}",
                "game_id": gid,
                "season": int(g["season"]),
                "week": int(g["week"]),
                "gameday": g.get("gameday", ""),
                "home_team": g["home_team"],
                "away_team": g["away_team"],
                "origination_order": order,
                "market": market,
                "originated_value": val,
                "originated_home_ml": home_ml,
                "originated_away_ml": away_ml,
                "originated_units": units,
                "originated_utc": frz_utc or NOT_RECORDED,
                "ledger_entry_hash": frz_hash,
                "opening_value": "",
                "opening_utc": "",
                "opening_source": "",
                "opening_status": UNVERIFIED_OPEN,
                "closing_value": "",
                "closing_utc": "",
                "closing_source": "",
                "closing_status": UNVERIFIED_CLOSE,
                "fair_source": src,
            })
    return pd.DataFrame(rows, columns=STORE_COLUMNS)


def coverage(store: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Per-season counts. community_close_present counts games whose pinned community close
    exists; those values are not copied into the store."""
    has_comm = games.market_spread.notna() & games.market_total.notna()
    g = games.assign(_comm=has_comm)
    out = []
    for season, sub in store.groupby("season"):
        gs = g[g.season == season]
        out.append({
            "season": int(season),
            "games_originated": int(sub.game_id.nunique()),
            "markets_originated": int(len(sub)),
            "frozen_before_kickoff": int((sub.originated_utc != NOT_RECORDED).sum()),
            "opening_verified": int((sub.opening_value != "").sum()),
            "closing_verified": int((sub.closing_value != "").sum()),
            "community_close_present_games": int(gs._comm.sum()),
            "community_close_copied_to_store": 0,
        })
    return pd.DataFrame(out)


def main() -> None:
    games = load_games()
    store = build_store(games, frozen_forward())
    cov = coverage(store, games)
    FWD.mkdir(parents=True, exist_ok=True)
    GOV.mkdir(parents=True, exist_ok=True)
    store.to_csv(FWD / "price_snapshots.csv", index=False)
    cov.to_csv(GOV / "price_snapshot_coverage.csv", index=False)
    print(f"  price_snapshots.csv {len(store)} markets from {store.game_id.nunique()} games")
    print(f"  opening verified {int((store.opening_value != '').sum())} · "
          f"closing verified {int((store.closing_value != '').sum())}")


if __name__ == "__main__":
    main()
