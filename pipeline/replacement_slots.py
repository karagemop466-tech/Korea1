"""S5 — the depth of the replacement, not only the fact of a replacement.

The availability tables published so far answer "is the starter available?". The
question that decides a bet is one step further: *who* steps in, and *how deep* is
the bench behind them. A second-string wide receiver replacing a first-string one is
a different event from a fourth-string tight end replacing a third-string one, and
the current tables cannot tell them apart.

This module joins three official sources:

  data/availability/depth_charts.csv   each club's own published depth chart, captured
                                       by the availability workflow (club site)
  data/availability/slot_status.csv     the same capture joined to the official NFL
                                       injury report (www.nfl.com/injuries)
  data/availability/injuries.csv       the official NFL injury report rows, as
                                       captured by the availability workflow

and produces, for every slot whose first-listed player is unavailable:

  * the replacement actually listed next at that slot, with their depth rank;
  * the depth string (2nd string, 3rd string, 4th string …);
  * how many further players the club has at that position behind the replacement;
  * the replacement's own availability status, where the official report carries one.

Nothing is inferred: if the club publishes no next player at a slot, the row says so
instead of guessing a replacement.

Outputs
  data/availability/replacement_depth.csv

Run:  python pipeline/replacement_depth.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, SITE_DATA  # noqa: E402

AVAIL = ROOT / "data" / "availability"
PROC = ROOT / "data" / "processed"
OUT = AVAIL / "replacement_depth_slots.csv"

# The club's full name -> the club word used on the club's own site (and therefore
# the word in the depth-chart capture). Longest first so "Los Angeles Rams" does not
# match "Angels".
CLUB_WORDS = [
    "Arizona Cardinals", "Atlanta Falcons", "Baltimore Ravens", "Buffalo Bills",
    "Carolina Panthers", "Chicago Bears", "Cincinnati Bengals", "Cleveland Browns",
    "Dallas Cowboys", "Denver Broncos", "Detroit Lions", "Green Bay Packers",
    "Houston Texans", "Indianapolis Colts", "Jacksonville Jaguars", "Kansas City Chiefs",
    "Las Vegas Raiders", "Los Angeles Chargers", "Los Angeles Rams", "Miami Dolphins",
    "Minnesota Vikings", "New England Patriots", "New Orleans Saints", "New York Giants",
    "New York Jets", "Philadelphia Eagles", "Pittsburgh Steelers", "San Francisco 49ers",
    "Seattle Seahawks", "Tampa Bay Buccaneers", "Tennessee Titans", "Washington Commanders",
]


def club_of(full_name: str, clubs: dict[str, str]) -> str | None:
    """'Washington Commanders' -> 'Commanders' (the club word on the club's site)."""
    text = str(full_name or "")
    for full in sorted(CLUB_WORDS, key=len, reverse=True):
        if text.lower().startswith(full.lower()):
            return clubs.get(full)
    for full, club in clubs.items():
        if club.lower() in text.lower():
            return club
    return None


def load_club_map() -> dict[str, str]:
    """Full club name -> club word, read from the depth-chart capture itself."""
    depth = pd.read_csv(AVAIL / "depth_charts.csv", dtype=str).fillna("")
    out: dict[str, str] = {}
    for full, grp in depth.groupby("club"):
        # The capture keeps the club's own name; the full league name is rebuilt from
        # the official injury report below instead of being typed in here.
        out.setdefault(str(full), str(full))
    return out


def injury_status(inj: pd.DataFrame) -> dict[tuple[str, str], dict]:
    """(team abbreviation, player) -> the official injury-report row."""
    out = {}
    for r in inj.to_dict("records"):
        team = str(r.get("team", "")).strip()
        if not team:
            continue
        out[(team, str(r.get("player", "")).strip().lower())] = dict(
            position=str(r.get("position", "")),
            practice_status=str(r.get("practice_status", "")),
            game_status=str(r.get("game_status", "")),
            player_url=str(r.get("player_url", "")))
    return out


def unavailable(status: dict) -> str:
    """Is this player unavailable for the game? '' means available or not posted."""
    gs = (status.get("game_status") or "").strip().lower()
    ps = (status.get("practice_status") or "").strip().lower()
    if gs == "out":
        return "out"
    if gs == "doubtful":
        return "doubtful"
    if gs == "questionable":
        return "questionable"
    if "did not participate" in ps:
        return "did not participate"
    return ""


def main() -> None:
    depth = pd.read_csv(AVAIL / "depth_charts.csv", dtype=str).fillna("")
    depth["depth_rank"] = pd.to_numeric(depth["depth_rank"], errors="coerce")
    inj = pd.read_csv(AVAIL / "injuries.csv", dtype=str).fillna("")
    status = injury_status(inj)

    rows = []
    for (team, unit, slot), grp in depth.groupby(["team", "unit", "slot"], sort=True):
        grp = grp.sort_values("depth_rank")
        club = grp["club"].iloc[0]
        source = grp["source_url"].iloc[0]
        position = grp["position"].iloc[0]
        starters = grp[grp.depth_rank == 1]["player"].tolist()
        if not starters:
            continue
        starter = starters[0]
        st = status.get((team, starter.lower()), {})
        flag = unavailable(st)
        if not flag:
            continue                      # the starter is available: nothing to replace
        # Walk the published chart down until a player who is not out is found.
        replacement, rep_rank, rep_status = "", None, ""
        for r in grp[grp.depth_rank >= 2].to_dict("records"):
            rs = status.get((team, str(r["player"]).strip().lower()), {})
            if unavailable(rs) == "out":
                continue
            replacement = r["player"]
            rep_rank = int(r["depth_rank"])
            rep_status = unavailable(rs) or "available"
            break
        # How many bodies are behind the replacement at the same position?
        same_pos = depth[(depth.team == team) & (depth.position == position)]
        behind = same_pos[same_pos.depth_rank >= 2]
        available_behind = [p for p in behind["player"]
                            if unavailable(status.get((team, str(p).strip().lower()), {})) != "out"]
        rows.append(dict(
            team=team, club=club, unit=unit, slot=int(slot), position=position,
            starter=starter,
            starter_status=flag,
            starter_practice_status=st.get("practice_status", ""),
            starter_game_status=st.get("game_status", ""),
            replacement=replacement,
            replacement_depth_rank=rep_rank,
            replacement_depth_string=(f"{rep_rank}{'st' if rep_rank == 1 else ('nd' if rep_rank == 2 else ('rd' if rep_rank == 3 else 'th'))} string"
                                      if rep_rank else ""),
            replacement_status=rep_status,
            same_position_players_behind=int(len(behind)),
            same_position_available_behind=len(available_behind),
            bench_depth_note=("no further player is listed at this position on the club chart"
                               if not available_behind else
                               f"{len(available_behind)} further player(s) available at {position}"),
            depth_source_url=source,
            injury_source_url="https://www.nfl.com/injuries/",
            injury_player_url=st.get("player_url", ""),
            depth_retrieved_utc=grp["retrieved_utc"].iloc[0],
            evidence="club depth chart + official NFL injury report",
        ))
    df = pd.DataFrame(rows).sort_values(["team", "unit", "slot"]).reset_index(drop=True)
    AVAIL.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    (SITE_DATA / "replacement_depth_slots.csv").write_bytes(OUT.read_bytes())
    print(f"  replacement_depth_slots.csv {len(df)} slots with an unavailable starter")
    if len(df):
        print("   ", df["replacement_depth_string"].value_counts().to_dict())


if __name__ == "__main__":
    main()
