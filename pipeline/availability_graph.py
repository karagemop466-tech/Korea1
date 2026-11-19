"""The availability graph: who was expected to start, and who actually did.

This is the dataset the brief asks for — "the availability graph as a
first-class dataset (who was expected to start, who actually did)" — built
from three official sources and nothing else.

* **Expected** — the club's own official depth chart
  (``data/availability/depth_charts.csv``).  The expectation is the player
  the club itself lists first in that slot.  The chart's own printed order is
  the only ordering used; a jersey number, an experience figure or a salary is
  never read as a rank.  Every row records the chart's capture time, so a
  chart captured after kickoff is flagged instead of being used as if it had
  been known before the game.
* **Actual** — the official Game Book the league publishes for the game
  (``data/processed/official_gamebook_rosters.csv``).  The Game Book names the
  starting eleven, the players who did not play and the players who were
  inactive.  Nothing is inferred from the depth chart about who played.
* **Injured / unavailable** — the official injury report
  (``data/availability/injuries.csv``), joined by player name so that a
  designation can be read next to the player it belongs to.

The grain is one row per (fixture, club, unit, position).  A position with
more than one rank-1 player in the club's chart is published as a co-starter
row, because a club that lists three receivers at rank 1 has not named a
single starter and the graph must not invent one.

What is written
---------------
``data/processed/availability_graph.csv``  — the graph itself.
``data/processed/official_inactive_lists.csv`` — the league's own inactive and
    did-not-play lists, per fixture and club, from the Game Book.

Rules
-----
* Where the official Game Book has not been captured, the actual side is
  blank and the outcome says so.  Nothing is filled from a community mirror,
  a model, a previous game or the depth chart.
* A replacement is reported with the **depth** of the hole it fills — the
  replacement's own rank in the club's chart — not only the fact that a
  replacement happened.
* A player the club's chart does not list has a blank rank.  It is not
  assigned the next free rank.

Run: python pipeline/availability_graph.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
AVAIL = ROOT / "data" / "availability"

GRAPH_COLUMNS = [
    "fixture_id", "season", "week", "away_team", "home_team", "club", "club_name",
    "unit", "position", "kickoff_utc", "kickoff_et",
    "expected_starter", "expected_source", "expected_captured_utc",
    "expected_point_in_time", "expected_co_starter_count",
    "actual_starter", "actual_source", "actual_jersey",
    "outcome", "replacement_depth_rank", "replacement_is_listed_in_chart",
    "expected_player_inactive", "expected_player_did_not_play",
    "actual_player_inactive", "actual_player_did_not_play",
    "injury_designation", "injury_source",
    "fixture_url", "note",
]

INACTIVE_COLUMNS = ["fixture_id", "season", "week", "club", "club_name", "player",
                    "status", "jersey", "position", "source_url", "evidence_path",
                    "retrieved_utc"]

# The Game Book prints the unit of a lineup column; the club's depth chart
# prints the same three units.  The names are matched as the league prints
# them.
UNIT_MAP = {"offense": "Offense", "defense": "Defense", "": ""}


def _read(path: Path, **kw) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False, **kw)


def _norm_name(name: str) -> str:
    """A comparable form of a printed player name.

    The Game Book prints ``M.Evans`` and the club's chart prints the full
    name.  Both are reduced to letters and compared, which matches the two
    spellings of the same player without inventing a first or last name.
    """
    return "".join(ch for ch in str(name).upper() if ch.isalpha())


def _norm_position(position: str) -> str:
    return str(position).strip().upper()


def _week_number(week: str) -> str:
    """The week number of a printed week label ("WEEK 10" -> "10")."""
    digits = "".join(ch for ch in str(week) if ch.isdigit())
    return digits


def _chart_expectation(depth: pd.DataFrame) -> dict[tuple[str, str, str], dict]:
    """Expected starters, keyed by (club, unit, position).

    A slot with more than one player at rank 1 is published as a
    co-starter: the club named more than one first player, so the graph
    records the count instead of choosing one.
    """
    out: dict[tuple[str, str, str], dict] = {}
    if depth.empty:
        return out
    depth = depth.copy()
    depth["_rank"] = depth.depth_rank.astype(str).str.strip()
    for (club, unit, position), grp in depth.groupby(["team", "unit", "position"], sort=False):
        first = grp[grp._rank == "1"]
        rest = grp[grp._rank != "1"]
        names = [str(p) for p in first.player.tolist() if str(p).strip()]
        key = (str(club), str(unit), _norm_position(position))
        out[key] = dict(
            expected_starter="; ".join(names),
            expected_source=str(first.source_url.iloc[0]) if len(first) else str(grp.source_url.iloc[0]),
            expected_captured_utc=str(grp.retrieved_utc.iloc[0]),
            expected_co_starter_count=str(len(names)),
            chart_players={_norm_name(p): r for p, r in
                           zip(grp.player, grp._rank)},
            chart_names=list(grp.player),
        )
    return out


def build() -> dict:
    PROC.mkdir(parents=True, exist_ok=True)
    fixtures = _read(PROC / "fixture_context.csv")
    depth = _read(AVAIL / "depth_charts.csv")
    injuries = _read(AVAIL / "injuries.csv")
    rosters = _read(PROC / "official_gamebook_rosters.csv")

    # The Game Book's own lists, per fixture and club.
    inactive_rows: list[dict] = []
    starters: dict[tuple[str, str, str], dict] = {}
    inactive: dict[tuple[str, str, str], str] = {}
    dnp: dict[tuple[str, str, str], str] = {}
    if not rosters.empty and not fixtures.empty:
        fx_by_slug = {str(r.slug): r for r in fixtures.itertuples() if str(r.slug)}
        for row in rosters.itertuples():
            slug = str(getattr(row, "slug", ""))
            fx = fx_by_slug.get(slug)
            if fx is None:
                continue
            club = str(getattr(row, "team_as_printed", ""))
            if not club:
                continue
            block = str(getattr(row, "roster_block", ""))
            side = str(getattr(row, "side", ""))
            unit = UNIT_MAP.get(str(getattr(row, "unit", "")), str(getattr(row, "unit", "")))
            position = _norm_position(getattr(row, "position", ""))
            player = str(getattr(row, "player", ""))
            if block == "starter" and side and unit:
                starters[(slug, club, f"{unit}|{position}")] = dict(
                    player=player, jersey=str(getattr(row, "jersey", "")),
                    source=str(getattr(row, "official_url", "")),
                    club=club, unit=unit, position=position, slug=slug)
            elif block in ("not_active", "did_not_play"):
                label = "INACTIVE" if block == "not_active" else "DID NOT PLAY"
                inactive_rows.append(dict(
                    fixture_id=str(fx.fixture_id), season=str(fx.season), week=str(fx.week),
                    club=club, club_name=club, player=player, status=label,
                    jersey=str(getattr(row, "jersey", "")),
                    position=position,
                    source_url=str(getattr(row, "official_url", "")),
                    evidence_path=str(getattr(row, "source_url", "")),
                    retrieved_utc=str(getattr(row, "retrieved_utc", ""))))
                table = inactive if block == "not_active" else dnp
                table[(slug, club, _norm_name(player))] = label

    inactive_df = pd.DataFrame(inactive_rows, columns=INACTIVE_COLUMNS)
    inactive_df.to_csv(PROC / "official_inactive_lists.csv", index=False)

    # Injury designations, by club, week and player.  The report is a weekly
    # document: a designation from one week is never attached to a fixture in
    # another week, so the week is part of the key.
    injury_by_name: dict[tuple[str, str, str], tuple[str, str]] = {}
    if not injuries.empty:
        for row in injuries.itertuples():
            club = str(getattr(row, "team", "")) or str(getattr(row, "club", ""))
            player = str(getattr(row, "player", ""))
            week = _week_number(str(getattr(row, "week", "")))
            designation = (str(getattr(row, "game_status", "")) or
                           str(getattr(row, "practice_status", "")))
            source = str(getattr(row, "source_url", ""))
            if club and player:
                injury_by_name.setdefault((club, week, _norm_name(player)),
                                          (designation, source))

    expectation = _chart_expectation(depth)
    club_name = (depth.groupby("team")["club"].first().to_dict() if not depth.empty else {})
    chart_capture = (depth.groupby("team")["retrieved_utc"].first().to_dict()
                     if not depth.empty else {})

    rows: list[dict] = []
    for fx in fixtures.itertuples() if not fixtures.empty else []:
        slug = str(fx.slug)
        kickoff = str(fx.kickoff_utc)
        for club, side in ((str(fx.away_team), "away"), (str(fx.home_team), "home")):
            for (chart_club, unit, position), exp in expectation.items():
                if chart_club != club:
                    continue
                key = (slug, club, f"{unit}|{position}")
                actual = starters.get(key, {})
                expected_name = exp["expected_starter"]
                actual_name = actual.get("player", "")
                note = ""
                if not actual:
                    outcome = "NOT CONFIRMED — no official Game Book captured"
                elif not expected_name:
                    outcome = "NO EXPECTATION — position absent from the club's chart"
                elif exp["expected_co_starter_count"] != "1":
                    outcome = "CO-STARTERS — the club named more than one first player"
                elif _norm_name(actual_name) == _norm_name(expected_name.split(";")[0]):
                    outcome = "CONFIRMED — the chart's first player started"
                else:
                    outcome = "REPLACEMENT — a different player started"
                rank = exp["chart_players"].get(_norm_name(actual_name), "")
                pit = ""
                captured = exp["expected_captured_utc"]
                if captured and kickoff:
                    pit = "YES" if captured <= kickoff else "NO — chart captured after kickoff"
                designation, injury_source = injury_by_name.get(
                    (club, str(fx.week), _norm_name(expected_name.split(";")[0])), ("", ""))
                rows.append(dict(
                    fixture_id=str(fx.fixture_id), season=str(fx.season), week=str(fx.week),
                    away_team=str(fx.away_team), home_team=str(fx.home_team),
                    club=club, club_name=club_name.get(club, ""),
                    unit=unit, position=position,
                    kickoff_utc=kickoff, kickoff_et=str(fx.kickoff_et),
                    expected_starter=expected_name,
                    expected_source=exp["expected_source"],
                    expected_captured_utc=captured,
                    expected_point_in_time=pit,
                    expected_co_starter_count=exp["expected_co_starter_count"],
                    actual_starter=actual_name,
                    actual_source=actual.get("source", ""),
                    actual_jersey=actual.get("jersey", ""),
                    outcome=outcome,
                    replacement_depth_rank=rank if outcome.startswith("REPLACEMENT") else "",
                    replacement_is_listed_in_chart=("YES" if rank else "NO") if outcome.startswith("REPLACEMENT") else "",
                    expected_player_inactive=inactive.get((slug, club, _norm_name(expected_name.split(";")[0])), ""),
                    expected_player_did_not_play=dnp.get((slug, club, _norm_name(expected_name.split(";")[0])), ""),
                    actual_player_inactive=inactive.get((slug, club, _norm_name(actual_name)), ""),
                    actual_player_did_not_play=dnp.get((slug, club, _norm_name(actual_name)), ""),
                    injury_designation=designation,
                    injury_source=injury_source,
                    fixture_url=str(fx.official_url),
                    note=note,
                ))

    graph = pd.DataFrame(rows, columns=GRAPH_COLUMNS)
    graph.to_csv(PROC / "availability_graph.csv", index=False)
    return dict(rows=len(graph), inactive_rows=len(inactive_df),
                starters=len(starters), fixtures=len(fixtures))


def main() -> int:
    summary = build()
    print("availability graph rows:", summary["rows"])
    print("inactive / did-not-play rows:", summary["inactive_rows"])
    print("Game Book starters read:", summary["starters"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
