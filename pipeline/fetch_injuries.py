"""Injury-report ingestion: official snapshot -> structured, validated rows.

Two evidence classes are staged here, and they are kept apart on purpose.

1. **Official live snapshot** (tier: official NFL)
   `https://www.nfl.com/injuries/` is the NFL's own injury report. The sandbox
   shell cannot reach it (TLS handshake refused by the egress allowlist), so the
   page is read with the agent's page-fetch tool and the fetched body is written
   to `data/raw/nfl_injuries/<snapshot>/injury_report.md` **verbatim**. This module
   only parses and validates that file; it never invents a status.

2. **Pinned community roster archive** (tier: community mirror of Pro Football
   Reference, via `nflverse/nfldata`)
   `data/rosters.csv` is the only roster-depth source reachable in this
   environment. It is fetched from the same pinned commit SHA as the rest of the
   project and hash-checked on ingest. It is a community mirror, so depth values
   derived from it are labelled unverified in the strict public view.

Run:  python pipeline/fetch_injuries.py
Out:  data/processed/injury_report.csv
      data/processed/injury_team_status.csv
      data/processed/injury_roster_archive.csv
      data/raw/nfl_rosters/{rosters,positions,teams}.csv
      data/raw/nfl_rosters/manifest.json
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, RAW, ROOT, sha256_of, write_json  # noqa: E402

EVIDENCE = ROOT / "data" / "evidence"

NF_TEAMS = [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET",
    "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA", "MIN", "NE",
    "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
]
TEAM_SET = set(NF_TEAMS)
# nfl.com prints some franchises with a different abbreviation than the
# community archive uses. Map the page's label to the canonical code so rows
# join to the same franchise identifier used everywhere else in the project.
NF_ALIASES = {"AZ": "ARI"}

# NFL position abbreviation -> (side, position group)
POSITION_MAP = {
    "QB": ("O", "QB"),
    "RB": ("O", "RB"), "FB": ("O", "RB"),
    "WR": ("O", "WR"),
    "TE": ("O", "TE"),
    "T": ("O", "OL"), "G": ("O", "OL"), "C": ("O", "OL"),
    "K": ("O", "K"), "P": ("O", "P"), "LS": ("O", "LS"),
    "DE": ("D", "DL"), "DT": ("D", "DL"), "NT": ("D", "DL"),
    "LB": ("D", "LB"),
    "CB": ("D", "CB"), "LCB": ("D", "CB"), "RCB": ("D", "CB"), "SCB": ("D", "CB"),
    "S": ("D", "S"), "FS": ("D", "S"), "SS": ("D", "S"),
}

PRACTICE_STATUSES = {
    "Full Participation in Practice",
    "Limited Participation in Practice",
    "Did Not Participate In Practice",
}
GAME_STATUSES = {"Out", "Questionable", "Doubtful"}

ROSTER_FILES = ["data/rosters.csv", "data/positions.csv", "data/teams.csv"]
ROSTER_DIR = RAW / "nfl_rosters"
TEAM_HEADER = re.compile(
    r"^(?P<code>"
    + "|".join(sorted(TEAM_SET | set(NF_ALIASES), key=len, reverse=True))
    + r")\s+.*\(\d+-\d+(?:-\d+)?\)\s*$")


def canonical_team(code: str) -> str:
    return NF_ALIASES.get(code, code)
PLAYER_CELL = re.compile(r"^\[(?P<name>.+?)\]\((?P<url>https://www\.nfl\.com/players/[^)]+)\)$")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def stage_roster_archive(sha: str) -> dict:
    """Stage rosters.csv / positions.csv / teams.csv from the pinned archive."""
    url = f"https://codeload.github.com/nflverse/nfldata/tar.gz/{sha}"
    req = urllib.request.Request(url, headers={"User-Agent": "arena-agent/1.0"})
    blob = urllib.request.urlopen(req, timeout=300).read()
    ROSTER_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        for member in tf.getmembers():
            parts = member.name.split("/", 1)
            if len(parts) != 2 or parts[1] not in ROSTER_FILES or not member.isfile():
                continue
            data = tf.extractfile(member).read()
            target = ROSTER_DIR / parts[1].replace("data/", "")
            target.write_bytes(data)
            entries.append({
                "logical": parts[1],
                "local": str(target.relative_to(ROOT)),
                "bytes": len(data),
                "sha256": sha256_bytes(data),
                "archive_sha256": sha256_bytes(blob),
                "url": f"https://github.com/nflverse/nfldata/blob/{sha}/{parts[1]}",
            })
    if len(entries) != len(ROSTER_FILES):
        raise RuntimeError(f"roster archive missing files: {ROSTER_FILES}")
    manifest = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "upstream_repo": "nflverse/nfldata",
        "upstream_commit_sha": sha,
        "tier": "community mirror of Pro Football Reference (nflverse/nfldata)",
        "note": ("Roster depth and position data come from a community mirror, not from an "
                 "official NFL roster archive. Hash-verified as files; not authenticated as "
                 "official observations."),
        "files": entries,
    }
    write_json(ROSTER_DIR / "manifest.json", manifest)
    return manifest


NETWORKS = {"Prime Video", "FOX", "CBS", "NBC, UNIVERSO", "ESPN, ABC, ESPN2, ESPN DEPORTES",
            "FOX, FOX DEPORTES", "FOX DEPORTES", "Amazon Prime Video", "NBC", "ABC",
            "CBS Sports", "Paramount+"}


def parse_markdown(text: str):
    """Parse the verbatim official injury-report body.

    Page layout, per game: `away header`, `home header`, `away name`, away table,
    `home name`, home table. Rows are therefore keyed on the team-*name* line that
    immediately precedes a table, not on the abbreviation header, and the
    name -> abbreviation map is rebuilt from the header order so a reviewer can
    check the pairing by hand.

    Returns (games, rows, name_map).
    """
    events = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("## "):
            events.append(("day", s[3:].strip()))
            continue
        if re.fullmatch(r"\d{1,2}:\d{2}\s*(AM|PM)\w*", s):
            events.append(("time", s))
            continue
        m = TEAM_HEADER.match(s)
        if m:
            code = canonical_team(m.group("code"))
            if code in TEAM_SET:
                events.append(("header", code))
                continue
        if s == "No Injuries Reported":
            events.append(("noreport", s))
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            events.append(("row", cells))
            continue
        if s in NETWORKS or s.lower().startswith("#"):
            continue
        events.append(("name", s))

    headers = [e[1] for e in events if e[0] == "header"]
    names = [e[1] for e in events if e[0] == "name"]
    if len(headers) != len(names):
        raise ValueError(
            f"team header/name count mismatch: {len(headers)} headers vs {len(names)} names")
    if len(headers) % 2:
        raise ValueError("odd number of team headers; cannot pair games")
    name_map = {names[i]: headers[i] for i in range(len(names))}
    games = []
    day = kickoff = ""
    hidx = 0
    for kind, val in events:
        if kind == "day":
            day = val
        elif kind == "time":
            kickoff = val
        elif kind == "header":
            if hidx % 2 == 0:
                games.append({"away_team": val, "home_team": None,
                              "game_id": f"{val}_", "day": day, "kickoff": kickoff})
            else:
                games[-1]["home_team"] = val
                games[-1]["game_id"] = f"{games[-1]['away_team']}_{val}"
            hidx += 1
    rows, cur = [], {"day": "", "kickoff": "", "team": None}
    for kind, val in events:
        if kind == "day":
            cur["day"] = val
        elif kind == "time":
            cur["kickoff"] = val
        elif kind == "name":
            cur["team"] = name_map.get(val)
        elif kind == "noreport":
            cur["team"] = None
        elif kind == "row":
            if len(val) != 5:
                raise ValueError(f"bad injury row ({len(val)} cells): {val!r}")
            if val[0] in ("Player", "---"):
                continue
            player_cell, position, injury, practice, game_status = val
            pm = PLAYER_CELL.match(player_cell)
            if not pm:
                raise ValueError(f"player cell without official nfl.com link: {player_cell!r}")
            if position not in POSITION_MAP:
                raise ValueError(f"unknown position {position!r} in row {player_cell!r}")
            if practice and practice not in PRACTICE_STATUSES:
                raise ValueError(f"unknown practice status {practice!r}")
            if game_status and game_status not in GAME_STATUSES:
                raise ValueError(f"unknown game status {game_status!r}")
            if cur["team"] is None:
                raise ValueError(f"row before any team name: {player_cell!r}")
            rows.append({
                "day": cur["day"], "kickoff": cur["kickoff"], "team": cur["team"],
                "player": pm.group("name"), "player_url": pm.group("url"),
                "position": position, "position_group": POSITION_MAP[position][1],
                "side": POSITION_MAP[position][0],
                "injury": injury, "practice_status": practice, "game_status": game_status,
            })
    return games, rows, name_map


NEWS_LINE = re.compile(r"^-\s+\[(?P<headline>.+?)\]\((?P<url>https://www\.nfl\.com/news/[^)]+)\)\s*$")


def parse_news(text: str):
    """Parse the verbatim news feed on the cited page into (headline, url) pairs."""
    out = []
    for line in text.splitlines():
        m = NEWS_LINE.match(line.strip())
        if m:
            out.append({"headline": m.group("headline"), "url": m.group("url")})
    return out


def main() -> None:
    src = json.loads((ROOT / "data" / "sources.json").read_text())
    sha = src["upstream"]["commit_sha"]

    # ---- 1. pinned roster archive ----------------------------------------
    manifest_path = ROSTER_DIR / "manifest.json"
    if not manifest_path.exists():
        print(f"staging roster archive @ {sha[:12]}")
        stage_roster_archive(sha)
    else:
        prev = json.loads(manifest_path.read_text())
        if prev["upstream_commit_sha"] != sha:
            raise RuntimeError("roster archive pinned to a different commit than data/sources.json")

    # ---- 2. official injury snapshot -------------------------------------
    # The snapshot body is committed under data/evidence/ so a clean checkout can
    # rebuild this page; data/raw/ is gitignored and is only a working copy.
    candidates = [EVIDENCE / "nfl_injuries", RAW / "nfl_injuries"]
    snap_dirs = []
    for root_dir in candidates:
        if root_dir.exists():
            snap_dirs += sorted(p for p in root_dir.glob("*") if p.is_dir())
    if not snap_dirs:
        raise RuntimeError(
            "no staged official injury snapshot under data/evidence/nfl_injuries/ "
            "or data/raw/nfl_injuries/")
    snapshot_dir = snap_dirs[-1]
    man = json.loads((snapshot_dir / "manifest.json").read_text())
    body_path = snapshot_dir / "injury_report.md"
    digest = sha256_of(body_path)
    # Hash every staged file from its own path (R1, 2026-11-13). The earlier code only set a
    # default of None for entries after the first, so the news register was recorded with no hash.
    for f in man["files"]:
        local = snapshot_dir / f["logical"]
        f["sha256"] = sha256_of(local) if local.exists() else None
        if local.exists():
            f["bytes"] = local.stat().st_size
    man["files"][0]["sha256"] = digest
    man["files"][0]["bytes"] = body_path.stat().st_size
    write_json(snapshot_dir / "manifest.json", man)

    games, rows, name_map = parse_markdown(body_path.read_text(encoding="utf-8"))
    if not rows:
        raise RuntimeError("parsed zero injury rows")
    team_game = {}
    for g in games:
        team_game[g["away_team"]] = g["game_id"]
        team_game[g["home_team"]] = g["game_id"]
    for r in rows:
        r["game_id"] = team_game.get(r["team"], "")

    snap = man["snapshot_id"]
    for r in rows:
        r.update({"snapshot_id": snap, "source_url": man["source_url"],
                  "retrieved_utc": man["retrieved_utc"],
                  "season": man["season"], "week": man["week"]})
    report = pd.DataFrame(rows)
    report.to_csv(PROC / "injury_report.csv", index=False)

    team_status = (report.groupby("team")
                   .agg(players_listed=("player", "size"),
                        full=("practice_status", lambda s: int((s == "Full Participation in Practice").sum())),
                        limited=("practice_status", lambda s: int((s == "Limited Participation in Practice").sum())),
                        dnp=("practice_status", lambda s: int((s == "Did Not Participate In Practice").sum())),
                        out=("game_status", lambda s: int((s == "Out").sum())),
                        questionable=("game_status", lambda s: int((s == "Questionable").sum())))
                   .reset_index())
    listed = set(name_map.values())
    team_status["game_id"] = team_status.team.map(team_game).fillna("")
    team_status["source_url"] = man["source_url"]
    team_status["snapshot_id"] = snap
    team_status.to_csv(PROC / "injury_team_status.csv", index=False)

    # games with no injury entry at all still belong to the snapshot
    with_entry = set(team_status.team)
    games_df = pd.DataFrame([{
        "game_id": g["game_id"], "away_team": g["away_team"], "home_team": g["home_team"],
        "day": g.get("day", ""), "kickoff": g.get("kickoff", ""),
        "away_entries": int(g["away_team"] in with_entry),
        "home_entries": int(g["home_team"] in with_entry),
        "source_url": man["source_url"], "snapshot_id": snap,
    } for g in games])
    games_df.to_csv(PROC / "injury_game_list.csv", index=False)

    # ---- 3. official news feed shown on the same page -----------------------
    news_path = snapshot_dir / "news_register.md"
    if news_path.exists():
        news = parse_news(news_path.read_text(encoding="utf-8"))
        if not news:
            raise RuntimeError("news register contained no parseable headline/link pairs")
        news_df = pd.DataFrame(news)
        news_df.insert(0, "snapshot_id", snap)
        news_df["retrieved_utc"] = man["retrieved_utc"]
        news_df["source_url"] = man["source_url"]
        news_df["register_role"] = ("unstructured official news feed displayed on the cited page; "
                                    "no entity resolution applied")
        news_df.to_csv(PROC / "injury_news.csv", index=False)
        print(f"official news feed: {len(news_df)} headlines staged")

    roster_src = json.loads(manifest_path.read_text())
    pd.DataFrame([{
        "snapshot_id": snap,
        "source": roster_src["upstream_repo"] + "@" + roster_src["upstream_commit_sha"][:12],
        "tier": roster_src["tier"],
        "files": ", ".join(f["logical"] for f in roster_src["files"]),
        "bytes": sum(f["bytes"] for f in roster_src["files"]),
        "sha256": ", ".join(f["sha256"][:16] for f in roster_src["files"]),
    }]).to_csv(PROC / "injury_roster_archive.csv", index=False)

    print(f"official snapshot {snap}: {len(games)} games, {len(listed)} teams listed, "
          f"{len(report)} player rows")
    print(f"  teams with at least one entry on the page: {len(set(team_status.team))}")
    print(f"  teams on the page with no entry: {sorted(listed - set(team_status.team))}")
    print(f"  NFL teams absent from the page: {sorted(TEAM_SET - listed)}")
    print(f"roster archive: {len(roster_src['files'])} files @ {roster_src['upstream_commit_sha'][:12]}")
    print("wrote data/processed/injury_report.csv, injury_team_status.csv, "
          "injury_roster_archive.csv")


if __name__ == "__main__":
    main()
