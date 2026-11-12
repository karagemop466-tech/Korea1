"""Injury and lineup-availability engine.

Answers one question the line-origination models cannot: **who is actually
available to play, and does a team have to start a backup?**

Two evidence classes, kept apart:

* **Official current-week status** (tier: official NFL) — parsed from the
  staged `nfl.com/injuries` snapshot. These are the NFL's own practice and game
  statuses, transcribed verbatim.
* **Depth ordering** — "1st / 2nd / 3rd string" is not published by the NFL.
  Two ways are used, both labelled:
    - current week: order each team's quarterbacks by games **started** in the
      pinned schedule archive (`games.csv`, GSIS-derived). This is an ordering
      derived from an official game record, not a depth chart.
    - 2006-2019: the community roster mirror (`rosters.csv`, Pro Football
      Reference via nflverse) is the only source with full position rosters
      reachable in this environment. It ends in 2019, so it cannot rank a 2026
      depth chart. Values from it are community-derived and labelled unverified.

Run:  python pipeline/injuries.py
Out:  data/processed/injury_position_pressure.csv
      data/processed/injury_qb_depth.csv
      data/processed/lineup_deficiency.csv
      data/processed/roster_depth_history.csv
      data/processed/lineup_deficiency_history.csv
      data/processed/injury_impact_history.csv
      data/processed/injury_gaps.csv
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, RAW, ROOT, fmt, write_json  # noqa: E402
from fetch_injuries import NF_TEAMS, POSITION_MAP  # noqa: E402

NFL_INJURIES_URL = "https://www.nfl.com/injuries/"
NFL_TEAM_PAGE = "https://www.nfl.com/teams/"
ROSTER_ARCHIVE_URL = ("https://github.com/nflverse/nfldata/blob/"
                      + json.loads((ROOT / "data" / "sources.json").read_text())["upstream"]["commit_sha"]
                      + "/data/rosters.csv")

SEVERITY_RULE = ("High = 3+ unavailable entries in the group on the cited report; "
                 "Medium = 2; Low = 1; blank = 0 unavailable entries")

# position group -> side of the ball
GROUP_SIDE = {"QB": "O", "RB": "O", "WR": "O", "TE": "O", "OL": "O", "K": "O", "P": "O",
              "LS": "O", "DL": "D", "LB": "D", "CB": "D", "S": "D"}

# position groups whose starters matter most for line movement
KEY_GROUPS = ["QB", "RB", "WR", "TE", "OL", "DL", "LB", "CB", "S"]


def norm(name: str) -> str:
    """Normalise a player name so `D.J. Reed` and `DJ Reed` join."""
    s = re.sub(r"[^A-Za-z0-9]+", " ", str(name)).strip().lower()
    s = re.sub(r"\s+", " ", s)
    for suffix in ("jr", "sr", "iii", "ii", "iv"):
        s = re.sub(rf"\s{suffix}$", "", s)
    return s


# The schedule archive uses historical franchise codes that differ from the
# codes nfl.com prints today. Alias them so a team joins to one identifier.
ARCHIVE_ALIASES = {"LA": "LAR", "STL": "LAR", "OAK": "LV", "SD": "LAC", "SFO": "SF",
                   "GNB": "GB", "WT": "WAS", "TAM": "TB", "RAI": "LV", "KAN": "KC",
                   "SDG": "LAC", "RAI": "LV", "CLE": "CLE"}


def canonical_archive_team(code: str) -> str:
    return ARCHIVE_ALIASES.get(str(code).strip().upper(), str(code).strip().upper())


def load_snapshot():
    rep = pd.read_csv(PROC / "injury_report.csv")
    # The verbatim official snapshot is committed under data/evidence/ (data/raw/
    # is gitignored); accept either location so a clean checkout rebuilds.
    candidates = [ROOT / "data" / "evidence" / "nfl_injuries", RAW / "nfl_injuries"]
    paths = []
    for d in candidates:
        if d.exists():
            paths += sorted(d.glob("*/manifest.json"))
    if not paths:
        raise RuntimeError("no staged official injury snapshot under data/evidence/ or data/raw/")
    man = json.loads(paths[-1].read_text())
    return rep, man


def position_pressure(rep: pd.DataFrame) -> pd.DataFrame:
    """Official per-team, per-position-group availability pressure."""
    g = rep.groupby(["team", "position_group"], sort=False).agg(
        players_listed=("player", "size"),
        full=("practice_status", lambda s: int((s == "Full Participation in Practice").sum())),
        limited=("practice_status", lambda s: int((s == "Limited Participation in Practice").sum())),
        dnp=("practice_status", lambda s: int((s == "Did Not Participate In Practice").sum())),
        ruled_out=("game_status", lambda s: int((s == "Out").sum())),
        questionable=("game_status", lambda s: int((s == "Questionable").sum())),
    ).reset_index()
    g["unavailable"] = g.ruled_out + g.dnp
    g["unavailable_rate"] = np.where(g.players_listed > 0, g.unavailable / g.players_listed, np.nan)
    g["starters_at_risk"] = g.unavailable >= 1
    g["severity"] = np.select(
        [g.unavailable >= 3, g.unavailable == 2, g.unavailable == 1, g.unavailable == 0],
        ["High", "Medium", "Low", ""], default="")
    g["side"] = g.position_group.map(GROUP_SIDE).fillna("")
    g["source_url"] = NFL_INJURIES_URL
    g["evidence_class"] = "official NFL injury report"
    g["denominator_note"] = ("counts players listed on the cited report, not the full roster; "
                             "the report is an update list, not a census")
    return g.sort_values(["team", "position_group"]).reset_index(drop=True)


def qb_depth_current(rep: pd.DataFrame, games: pd.DataFrame,
                     news: pd.DataFrame | None = None) -> pd.DataFrame:
    """Depth ordering from games started, joined to the official statuses.

    Only *played* regular-season games count as a start. The schedule archive
    also carries future scheduled games with blank scores and blank quarterback
    names; those are excluded rather than treated as a name called "nan".
    """
    cur = games[(games.season == 2026) & (games.game_type == "REG")
                & games.home_score.notna() & games.away_score.notna()].copy()
    for c in ("home_team", "away_team"):
        cur[c] = cur[c].map(canonical_archive_team)
    starts = {}
    for _, r in cur.iterrows():
        for side in ("home", "away"):
            nm = r.get(f"{side}_qb_name")
            tid = r.get(f"{side}_qb_id")
            if pd.isna(nm) or pd.isna(tid):
                continue
            nm = str(nm).strip()
            if norm(nm) in ("", "nan", "none"):
                continue
            team = canonical_archive_team(r[f"{side}_team"])
            k = (team, nm)
            starts.setdefault(k, {"id": str(tid).strip(), "n": 0})
            starts[k]["n"] += 1
    rows = []
    for (team, nm), v in sorted(starts.items()):
        rows.append({"team": team, "qb": nm, "qb_id": v["id"], "starts_2026": v["n"]})
    sq = pd.DataFrame(rows)
    sq["norm"] = sq.qb.map(norm)

    # A quarterback with zero starts never appears in the schedule archive, but
    # the official report lists the team's quarterbacks. Union them in so a
    # first-time starter named only in the report is not silently dropped.
    rep_qb = rep[rep.position == "QB"].copy()
    rep_qb["norm"] = rep_qb.player.map(norm)
    have = set(zip(sq.team, sq.norm))
    extra = [{"team": t, "qb": p, "qb_id": "", "starts_2026": 0,
              "norm": n, "tier_basis": "listed on the official injury report; no start recorded"}
             for t, p, n in rep_qb[["team", "player", "norm"]].itertuples(index=False)
             if (t, n) not in have and n not in ("", "nan")]
    if extra:
        sq = pd.concat([sq, pd.DataFrame(extra)], ignore_index=True)
    sq["tier_basis"] = sq.tier_basis.fillna(
        "ordering by games started in the pinned schedule archive")

    rep2 = rep.copy()
    rep2["norm"] = rep2.player.map(norm)
    status = (rep2[rep2.position == "QB"]
              .groupby(["team", "norm"])
              .agg(practice_status=("practice_status", "first"),
                   game_status=("game_status", "first"),
                   injury=("injury", "first"))
              .reset_index())
    sq = sq.merge(status, on=["team", "norm"], how="left")
    sq["status_class"] = np.where(sq.game_status == "Out", "ruled out",
                                  np.where(sq.practice_status == "Did Not Participate In Practice",
                                           "did not practice", "listed / other"))
    sq = sq.sort_values(["team", "starts_2026", "qb"], ascending=[True, False, True])
    sq["tier"] = sq.groupby("team").cumcount() + 1
    haystack = " ".join(news.headline.astype(str)).lower() if news is not None and len(news) else ""
    out = []
    for team, grp in sq.groupby("team"):
        grp = grp.sort_values("tier")
        # String match only: a team is flagged when one of its quarterback names
        # appears in an official headline. No entity resolution, no inference.
        named = sorted({x for x in grp.qb.tolist() if norm(x) and norm(x) in haystack})
        avail = grp[grp.game_status != "Out"]
        expected_tier = int(avail.tier.min()) if len(avail) else None
        t1 = grp[grp.tier == 1]
        t2 = grp[grp.tier == 2]
        t3 = grp[grp.tier == 3]
        out.append({
            "team": team,
            "tier1_qb": t1.qb.iloc[0] if len(t1) else "",
            "tier1_starts": int(t1.starts_2026.iloc[0]) if len(t1) else 0,
            "tier1_status": t1.status_class.iloc[0] if len(t1) else "",
            "tier2_qb": t2.qb.iloc[0] if len(t2) else "",
            "tier2_starts": int(t2.starts_2026.iloc[0]) if len(t2) else 0,
            "tier2_status": t2.status_class.iloc[0] if len(t2) else "",
            "tier3_qb": t3.qb.iloc[0] if len(t3) else "",
            "tier3_starts": int(t3.starts_2026.iloc[0]) if len(t3) else 0,
            "tier3_status": t3.status_class.iloc[0] if len(t3) else "",
            "expected_starting_tier": expected_tier,
            "backup_expected": bool(expected_tier is not None and expected_tier >= 2),
            "third_string_expected": bool(expected_tier is not None and expected_tier >= 3),
            "qbs_on_team": int(len(grp)),
            "official_news_mentions_qb": bool(named),
            "official_news_qb_names": ", ".join(named),
            "news_and_report_gap": bool(named and not grp.game_status.eq("Out").any()),
            "news_note": ("official nfl.com headlines on the cited page name this team's "
                          "quarterbacks; the injury-report table itself carries no ruling-out "
                          "status for them"),
            "depth_method": ("ordering by games started in the pinned schedule archive; "
                             "the NFL does not publish depth charts"),
            "source_url": NFL_INJURIES_URL,
            "status_source_url": NFL_INJURIES_URL,
        })
    return pd.DataFrame(out).sort_values("team").reset_index(drop=True)


def lineup_deficiency_current(pressure: pd.DataFrame, qb: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in pressure.iterrows():
        team, grp = r.team, r.position_group
        if team not in set(qb.team):
            tier_note = "not computable — no depth ordering available for this team"
            forced_tier = ""
        else:
            q = qb[qb.team == team]
            if grp == "QB":
                forced_tier = int(q.expected_starting_tier.iloc[0]) if pd.notna(q.expected_starting_tier.iloc[0]) else ""
                tier_note = ("tier from games started in the pinned schedule archive; "
                             "statuses from the official injury report")
            else:
                forced_tier = ""
                tier_note = "not computable — the 2026 roster depth archive is unavailable"
        rows.append({
            "team": team, "position_group": grp, "side": r.side,
            "players_listed": int(r.players_listed),
            "ruled_out": int(r.ruled_out), "did_not_practice": int(r.dnp),
            "limited": int(r.limited), "full": int(r.full),
            "starters_unavailable": int(r.starters_at_risk),
            "expected_backup_tier": forced_tier,
            "tier_evidence": tier_note,
            "severity": r.severity,
            "status_source_url": NFL_INJURIES_URL,
            "roster_source_url": NFL_TEAM_PAGE,
            "roster_tier": "official NFL team roster page (composition); depth order unavailable",
        })
    return pd.DataFrame(rows)


def roster_depth_history() -> pd.DataFrame:
    """Community roster mirror: position-group depth by season (2006-2019)."""
    ros = pd.read_csv(RAW / "nfl_rosters" / "rosters.csv")
    ros["team"] = ros.team.map(canonical_archive_team)
    ros["pos_group"] = ros.position.map(lambda p: POSITION_MAP.get(p, ("", p))[1])
    ros = ros[ros.pos_group.notna() & ros.pos_group.ne("")]
    ros = ros[(ros.games > 0) | (ros.starts > 0)]
    rows = []
    for (season, team), grp in ros.groupby(["season", "team"]):
        for pos_group, pg in grp.groupby("pos_group"):
            pg = pg.sort_values(["starts", "av", "games"], ascending=False)
            rows.append({
                "season": int(season), "team": team, "position_group": pos_group,
                "side": pg.side.iloc[0],
                "rostered": int(len(pg)),
                "starters": int((pg.starts > 0).sum()),
                "tier1": pg.full_name.iloc[0] if len(pg) else "",
                "tier1_starts": float(pg.starts.iloc[0]) if len(pg) else 0.0,
                "tier2": pg.full_name.iloc[1] if len(pg) > 1 else "",
                "tier2_starts": float(pg.starts.iloc[1]) if len(pg) > 1 else 0.0,
                "tier3": pg.full_name.iloc[2] if len(pg) > 2 else "",
                "tier3_starts": float(pg.starts.iloc[2]) if len(pg) > 2 else 0.0,
                "tier4": pg.full_name.iloc[3] if len(pg) > 3 else "",
                "tier4_starts": float(pg.starts.iloc[3]) if len(pg) > 3 else 0.0,
                "source_url": ROSTER_ARCHIVE_URL,
                "tier": "community mirror of Pro Football Reference — unverified",
            })
    return pd.DataFrame(rows)


def lineup_deficiency_history(games: pd.DataFrame, depth: pd.DataFrame) -> pd.DataFrame:
    """Games where the starting quarterback was not the team's tier-1 QB.

    Tier comes from the community roster mirror (`rosters.csv`, ordered by games
    started that season). Games are melted to one row per (game, side) and joined
    on (season, team, normalised name); the roster archive covers 2006-2019, so
    only those seasons can be joined.
    """
    ros = pd.read_csv(RAW / "nfl_rosters" / "rosters.csv")
    ros["team"] = ros.team.map(canonical_archive_team)
    ros = ros[ros.position == "QB"].copy()
    ros["norm"] = ros.full_name.map(norm)
    ros = ros.sort_values(["season", "team", "starts", "av", "games"],
                          ascending=[True, True, False, False, False])
    ros["tier"] = ros.groupby(["season", "team"]).cumcount() + 1

    def melt_side(side):
        d = games[["game_id", "season", "week", "home_score", "away_score"]].copy()
        d["team"] = games[f"{side}_team"].map(canonical_archive_team)
        d["qb_name"] = games[f"{side}_qb_name"]
        d["qb_id"] = games[f"{side}_qb_id"]
        d["side"] = side
        d["points_scored"] = games.home_score if side == "home" else games.away_score
        d["points_allowed"] = games.away_score if side == "home" else games.home_score
        return d

    long = pd.concat([melt_side("home"), melt_side("away")], ignore_index=True)
    long = long[long.qb_name.notna() & long.qb_name.astype(str).str.strip().ne("")]
    long = long[long.qb_id.notna() & long.qb_id.astype(str).str.strip().ne("")]
    long["norm"] = long.qb_name.map(norm)
    if "game_type" in games.columns:
        long = long.merge(games[["game_id", "game_type"]], on="game_id", how="left")
        long = long[long.game_type.fillna("REG") == "REG"]

    joined = long.merge(
        ros[["season", "team", "norm", "tier", "full_name", "starts"]],
        on=["season", "team", "norm"], how="inner")
    joined["backup_started"] = joined.tier >= 2
    joined["margin"] = joined.points_scored - joined.points_allowed
    joined["won"] = joined.points_scored > joined.points_allowed
    return joined[[
        "game_id", "season", "week", "team", "side", "qb_name", "qb_id", "tier",
        "backup_started", "points_scored", "points_allowed", "margin", "won",
        "full_name", "starts", "game_type"]].rename(columns={
            "qb_name": "starting_qb", "tier": "qb_tier"})





def impact_history(df: pd.DataFrame) -> pd.DataFrame:
    """Research estimate: team results with a backup QB starting vs tier-1."""
    if df.empty:
        return pd.DataFrame()
    first = df[df.qb_tier == 1]
    backup = df[df.qb_tier >= 2]
    out = []

    def block(name, sub):
        if sub.empty:
            return {"group": name, "games": 0}
        return {
            "group": name, "games": int(len(sub)),
            "points_scored": float(sub.points_scored.mean()),
            "points_allowed": float(sub.points_allowed.mean()),
            "margin": float(sub.margin.mean()),
            "win_rate": float(sub.won.mean()),
        }

    for name, sub in (("tier-1 starter", first), ("backup (tier >= 2) starter", backup)):
        out.append(block(name, sub))
    res = pd.DataFrame(out)
    res["point_differential"] = res.points_scored - res.points_allowed
    res["estimate_class"] = ("research estimate from community roster mirror + schedule archive; "
                             "not an official measurement; not causal")
    res["source_url"] = ROSTER_ARCHIVE_URL
    return res


def gaps(rep: pd.DataFrame, man: dict) -> pd.DataFrame:
    rows = [
        {"gap_id": "GAP-INJ-01", "severity": "High", "gap":
         "No official historical injury-report archive",
         "effect": "Injury status cannot be replayed for past seasons; lineup-deficiency "
                   "signals are limited to the current snapshot.",
         "why": "The NFL publishes a current-week injury report only; no public official "
                "archive of weekly reports exists.",
         "how_to_close": "License or archive weekly official injury reports per season; "
                         "or reconstruct availability from official inactive lists.",
         "status": "open"},
        {"gap_id": "GAP-INJ-02", "severity": "High", "gap":
         "No official roster-depth archive for 2020-2026",
         "effect": "Depth tier (1st/2nd/3rd string) is not computable from official data "
                   "for the current season.",
         "why": "The only reachable roster source (nflverse/nfldata rosters.csv, a "
                "community mirror of Pro Football Reference) ends at the 2019 season.",
         "how_to_close": "Archive official NFL team roster pages per week, or obtain a "
                         "licensed depth-chart feed.",
         "status": "open"},
        {"gap_id": "GAP-INJ-03", "severity": "Medium", "gap":
         "The injury report is an update list, not a roster census",
         "effect": "A zero count means 'no entry on this report', not 'no injuries'.",
         "why": "The cited page lists players with a status update for the week's games.",
         "how_to_close": "Join against a full team roster before computing rates.",
         "status": "open"},
        {"gap_id": "GAP-INJ-04", "severity": "Medium", "gap":
         "Snapshot scope: 14 of the week's games at retrieval time",
         "effect": "4 NFL teams were absent from the cited page when it was captured.",
         "why": f"The page listed {man['scope_observed']['games_listed']} games / "
                f"{man['scope_observed']['teams_listed']} teams at "
                f"{man['retrieved_utc']}.",
         "how_to_close": "Re-capture after the weekly report is finalised; do not treat "
                         "the missing teams as injury-free.",
         "status": "open"},
        {"gap_id": "GAP-INJ-05", "severity": "Low", "gap":
         "Shell egress blocks nfl.com",
         "effect": "The official page cannot be fetched by the pipeline itself; the "
                   "snapshot is staged by the agent's page-fetch tool.",
         "why": "TLS handshake to www.nfl.com is refused by the sandbox allowlist.",
         "how_to_close": "Run the capture in an environment with nfl.com reachable, or "
                         "schedule an authenticated capture.",
         "status": "open"},
        {"gap_id": "GAP-INJ-06", "severity": "Low", "gap":
         "Player identity joins by name",
         "effect": "QB statuses are matched to schedule-archive QB names by normalised "
                   "text, not by a shared official player ID.",
         "why": "games.csv carries GSIS quarterback ids; rosters.csv carries Pro Football "
                "Reference ids; the two id spaces do not overlap.",
         "how_to_close": "Join on a stable official player id (NFL GSIS player id) once "
                         "available in both sources.",
         "status": "open"},
        {"gap_id": "GAP-INJ-07", "severity": "Medium", "gap":
         "The community roster mirror's 2019 season carries no appearance statistics",
         "effect": "Depth ranking stops at 2018; the 2019 roster rows cannot be ordered "
                   "by games started.",
         "why": "rosters.csv carries 2,479 rows for 2019 with games, starts and av all "
                "blank, while 2006-2018 carry them.",
         "how_to_close": "Treat 2019 as roster-only, or source 2019 appearance data from "
                         "an official or licensed provider.",
         "status": "open"},
    ]
    out = pd.DataFrame(rows)
    out["snapshot_id"] = man["snapshot_id"]
    out["source_url"] = NFL_INJURIES_URL
    return out


def main() -> None:
    rep, man = load_snapshot()
    games = pd.read_csv(RAW / "games.csv")
    news = (pd.read_csv(PROC / "injury_news.csv")
            if (PROC / "injury_news.csv").exists() else pd.DataFrame())

    pressure = position_pressure(rep)
    pressure.to_csv(PROC / "injury_position_pressure.csv", index=False)

    qb = qb_depth_current(rep, games, news)
    qb.to_csv(PROC / "injury_qb_depth.csv", index=False)

    deficiency = lineup_deficiency_current(pressure, qb)
    deficiency.to_csv(PROC / "lineup_deficiency.csv", index=False)

    depth = roster_depth_history()
    depth.to_csv(PROC / "roster_depth_history.csv", index=False)

    hist = lineup_deficiency_history(games, depth)
    hist.to_csv(PROC / "lineup_deficiency_history.csv", index=False)
    impact = impact_history(hist)
    impact.to_csv(PROC / "injury_impact_history.csv", index=False)

    gaps_df = gaps(rep, man)
    gaps_df.to_csv(PROC / "injury_gaps.csv", index=False)

    write_json(PROC / "injury_summary.json", {
        "snapshot_id": man["snapshot_id"],
        "retrieved_utc": man["retrieved_utc"],
        "source_url": man["source_url"],
        "teams_listed": int(len(set(rep.team))),
        "games_listed": int(len(pd.read_csv(PROC / "injury_game_list.csv"))),
        "player_rows": int(len(rep)),
        "ruled_out_rows": int((rep.game_status == "Out").sum()),
        "did_not_practice_rows": int((rep.practice_status == "Did Not Participate In Practice").sum()),
        "teams_backup_qb_expected": int(qb.backup_expected.sum()),
        "teams_third_string_expected": int(qb.third_string_expected.sum()),
        "groups_high_severity": int((pressure.severity == "High").sum()),
        "official_news_headlines": int(len(news)),
        "teams_qb_named_in_official_news": int(qb.official_news_mentions_qb.sum()),
        "teams_news_report_gap": int(qb.news_and_report_gap.sum()),
        "severity_rule": SEVERITY_RULE,
    })
    print(f"snapshot {man['snapshot_id']}: {len(rep)} rows, "
          f"{qb.backup_expected.sum()} teams with a backup QB expected, "
          f"{qb.third_string_expected.sum()} with a third-string QB expected")
    print(f"official news headlines: {len(news)}; "
          f"{qb.official_news_mentions_qb.sum()} teams have a QB named in them")
    print(f"historical roster depth rows: {len(depth)}; "
          f"historical backup-QB games: {int(hist.backup_started.sum()) if not hist.empty else 0}")
    print("wrote injury / availability tables to data/processed/")


if __name__ == "__main__":
    main()
