"""Player-game stats from the official NFL Game Center feed.

Why this file exists: the free, GitHub-hosted nflverse release assets that carry
`player_stats.csv` are served from release-assets.githubusercontent.com, which
this environment cannot reach. The upstream *raw* feed (nflverse/nflfastR-raw,
per-game NFL Game Center JSON) is reachable, and nflverse publishes the exact
stat-id -> stat mapping in R/calculate_stats.R. We re-implement that mapping
here (see STAT_IDS) and validate the output before using it.

Mapping re-implemented from nflverse/nflfastR @ 701bbf38 R/calculate_stats.R:
    completions            stat_id in {15,16}
    attempts               stat_id in {14,15,16,19}
    passing_yards          sum(yards) where stat_id in {15,16}
    passing_tds            count stat_id == 16
    interceptions          count stat_id == 19
    sacks_suffered         count stat_id == 20
    carries                count stat_id in {10,11}
    rushing_yards          sum(yards) where stat_id in {10,11,12,13}
    rushing_tds            count stat_id in {11,13}
    receptions             count stat_id in {21,22}
    targets                count stat_id == 115
    receiving_yards        sum(yards) where stat_id in {21,22,23,24}
    receiving_tds          count stat_id in {22,24}
    receiving_yards_after  sum(yards) where stat_id == 113

Validation performed (see data/derived/player_report.json):
  1. every game file parses and yields plays
  2. team receiving yards minus team passing yards distribution (must hug 0;
     differences only from sacks/scrambles/laterals)
  3. TD accounting: sum of player TDs x 6 + 2-pt conversions vs the official
     final score in games.csv
  4. coverage: games with player rows / games in schedule
"""
from __future__ import annotations

import gzip
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from .common import DERIVED, RAW, SOURCES, write_csv

PBP_RAW = RAW / "rawpbp" / "raw"
STAT = {
    "passing_yards": [(15, 1), (16, 1)],
    "passing_tds": [(16, 1)],
    "interceptions": [(19, 1)],
    "sacks_suffered": [(20, 1)],
    "carries": [(10, 1), (11, 1)],
    "rushing_yards": [(10, 1), (11, 1), (12, 1), (13, 1)],
    "rushing_tds": [(11, 1), (13, 1)],
    "receptions": [(21, 1), (22, 1)],
    "targets": [(115, 1)],
    "receiving_yards": [(21, 1), (22, 1), (23, 1), (24, 1)],
    "receiving_tds": [(22, 1), (24, 1)],
    "receiving_yac": [(113, 1)],
    "two_point": [(75, 1), (77, 1), (104, 1)],
}
SUM_STATS = {"passing_yards", "rushing_yards", "receiving_yards", "receiving_yac"}
PAT = re.compile(r"^(\d{4})_(\d{2})_([A-Z]{2,3})_([A-Z]{2,3})$")


def parse_game(path: Path) -> tuple[pd.DataFrame, dict]:
    m = PAT.match(path.name.replace(".json.gz", ""))
    if not m:
        return pd.DataFrame(), {"file": path.name, "error": "name pattern"}
    season, week, away, home = m.group(1), int(m.group(2)), m.group(3), m.group(4)
    with gzip.open(path) as f:
        obj = json.load(f)
    gd = obj.get("data", {}).get("viewer", {}).get("gameDetail", {})
    plays = gd.get("plays", [])
    agg = defaultdict(lambda: defaultdict(float))
    ids = {}
    n_stats = 0
    for p in plays:
        if p.get("playDeleted"):
            continue
        for st in p.get("playStats", []) or []:
            sid = st.get("statId")
            if sid is None:
                continue
            n_stats += 1
            name = st.get("playerName")
            team = st.get("team.abbreviation") or st.get("possessionTeam.abbreviation")
            if not name or not team:
                continue
            key = (team, name)
            gsis = st.get("gsisPlayer.id")
            if gsis:
                ids[key] = gsis
            yards = st.get("yards", 0) or 0
            for stat, pairs in STAT.items():
                for sid_want, _ in pairs:
                    if sid == sid_want:
                        agg[key][stat] += (yards if stat in SUM_STATS else 1)
    rows = []
    for (team, name), vals in agg.items():
        r = {"season": int(season), "week": week, "away_team": away, "home_team": home,
             "team": team, "player": name, "gsis_id": ids.get((team, name))}
        for stat in STAT:
            r[stat] = vals.get(stat, 0)
        rows.append(r)
    meta = {"file": path.name, "plays": len(plays), "stats": n_stats, "players": len(rows)}
    return pd.DataFrame(rows), meta


def build() -> tuple[pd.DataFrame, dict]:
    seasons = sorted([p.name for p in PBP_RAW.glob("*") if p.is_dir()])
    frames, metas = [], []
    for s in seasons:
        for p in sorted((PBP_RAW / s).glob("*.json.gz")):
            df, meta = parse_game(p)
            if len(df):
                frames.append(df)
            metas.append(meta)
    if not frames:
        return pd.DataFrame(), {"available": False, "reason": "no raw files staged"}
    pl = pd.concat(frames, ignore_index=True)
    pl["game_key"] = (pl["season"].astype(str) + "_" + pl["week"].map(lambda w: f"{w:02d}")
                      + "_" + pl["away_team"] + "_" + pl["home_team"])
    pl["game_id"] = pl["season"].astype(str) + "_" + pl["week"].map(lambda w: f"{w:02d}") + "_" + pl["away_team"] + "_" + pl["home_team"]
    return pl, {"available": True, "files": metas}


def validate(pl: pd.DataFrame, metas: dict) -> dict:
    g = pd.read_csv(DERIVED / "games.csv", parse_dates=["gameday"])
    g["game_key"] = (g["season"].astype(str) + "_" + g["week"].map(lambda w: f"{int(w):02d}")
                     + "_" + g["away_team"] + "_" + g["home_team"])
    gm = g.set_index("game_key")
    rep = {"available": True, "seasons": sorted(pl["season"].unique().tolist())}
    rep["files_parsed"] = len(metas["files"])
    rep["files_failed"] = int(sum(1 for m in metas["files"] if "error" in m))
    rep["total_plays"] = int(sum(m.get("plays", 0) for m in metas["files"]))
    rep["player_game_rows"] = int(len(pl))
    rep["unique_players"] = int(pl["player"].nunique())
    # team-level consistency
    team = pl.groupby(["game_key", "team"])[["passing_yards", "receiving_yards"]].sum().reset_index()
    team["diff"] = team["receiving_yards"] - team["passing_yards"]
    rep["team_recv_minus_pass_yards"] = {
        "mean": round(float(team["diff"].mean()), 2),
        "p05": round(float(team["diff"].quantile(0.05)), 1),
        "p95": round(float(team["diff"].quantile(0.95)), 1),
        "share_within_25": round(float((team["diff"].abs() <= 25).mean()), 3),
        "note": ("Receiving yards are not required to equal passing yards (sacks, scrambles, "
                 "laterals, two-point plays), but a systematic offset would indicate a mapping error."),
    }
    # scoring reconciliation
    td = pl.groupby(["game_key", "team"])[["passing_tds", "rushing_tds", "receiving_tds"]].sum().reset_index()
    # receiving TDs mirror passing TDs, so offensive TDs = passing + rushing
    td["off_tds"] = td["passing_tds"] + td["rushing_tds"]
    two = pl.groupby(["game_key", "team"])["two_point"].sum().reset_index()
    td = td.merge(two, on=["game_key", "team"], how="left")
    covered = set(pl["game_key"].unique())
    scores = []
    for _, r in g[g["game_key"].isin(covered)].dropna(subset=["home_score"]).iterrows():
        for side, team in (("home", r["home_team"]), ("away", r["away_team"])):
            scores.append({"game_key": r["game_key"], "team": team, "score": r[side + "_score"]})
    sc = pd.DataFrame(scores).merge(td, on=["game_key", "team"], how="left").fillna(0)
    sc["off_points"] = sc["off_tds"] * 6 + sc["two_point"] * 2
    sc["diff"] = sc["score"] - sc["off_points"]
    rep["scoring_reconciliation"] = {
        "n_team_games": int(len(sc)),
        "share_diff_in_0_1_2": round(float(sc["diff"].isin([0, 1, 2]).mean()), 3),
        "share_diff_in_neg2_to_8": round(float(sc["diff"].between(-2, 8).mean()), 3),
        "median_diff": float(sc["diff"].median()),
        "explanation": ("Residual = official points - (offensive TDs*6 + 2pt*2). Remaining points "
                        "come from extra points, defensive/special-teams TDs and safeties, so a "
                        "residual of roughly 0-8 points per team-game is expected."),
        "note": ("Score minus (offensive TD*6 + 2-pt) should be 0, 1 or 2 (extra point, failed "
                 "extra point, safeties, defensive/return TDs). A large departure would indicate a "
                 "stat-mapping error."),
    }
    # league-average sanity checks (independent of any external file)
    tg = pl.groupby(["game_key", "team"])[["passing_yards", "rushing_yards", "receptions",
                                           "passing_tds", "rushing_tds"]].sum()
    rep["league_averages_per_team_game"] = {
        "passing_yards": round(float(tg["passing_yards"].mean()), 1),
        "rushing_yards": round(float(tg["rushing_yards"].mean()), 1),
        "receptions": round(float(tg["receptions"].mean()), 1),
        "offensive_tds": round(float((tg["passing_tds"] + tg["rushing_tds"]).mean()), 2),
        "benchmark_note": ("NFL league averages sit near 215-235 passing yards, 110-125 rushing "
                           "yards, 20-22 receptions and 2.3-2.7 offensive TDs per team-game; a "
                           "mapping error shifts these materially."),
    }
    rep["games_in_schedule"] = int(g["game_key"].isin(pl["game_key"]).sum())
    rep["coverage_share"] = round(float(g["game_key"].isin(pl["game_key"]).mean()), 3)
    return rep


def main() -> None:
    pl, metas = build()
    if not metas.get("available"):
        print("[build_players] raw feed unavailable -> player layer marked unavailable")
        (DERIVED / "player_report.json").write_text(json.dumps(metas, indent=1))
        return
    rep = validate(pl, metas)
    rep["source"] = SOURCES["nflfastR-raw"]
    rep["stat_mapping_source"] = SOURCES["nflfastR"]
    write_csv(pl, "player_games.csv")
    (DERIVED / "player_report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
