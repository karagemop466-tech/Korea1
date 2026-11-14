"""T30/T31 — gameday lineup-deficiency engine (starter / 2nd / 3rd / 4th string).

What this module does
---------------------
It joins an **official NFL.com injury report capture** to each club's **official depth
chart** and reports, for every player who carries a game designation (Out / Doubtful /
Questionable), which string he is (1st, 2nd, 3rd, 4th) and which player the club lists
next at that position — i.e. the deficiency a lineup actually has to absorb.

It is deliberately written as a *reusable join* rather than a one-off table:

* it reads whatever capture is committed under ``data/availability/`` (the scheduled
  workflow rewrites that file), so every future run produces a fresh table;
* it also reads the hand-verified capture in ``data/review/`` when that capture is
  newer, and publishes the **drift** between the two;
* nothing is inferred. A player the club does not list has a blank string, a blank
  next-man-up and a ``NO_DEPTH_MATCH`` tier. Blank official cells stay blank.

Evidence classes are never mixed: the injury designation and the practice status are
official NFL.com observations; the string order is the club's own published chart,
which most clubs label "unofficial"; the join and the tier label are this project's
computation and are labelled as such on the page.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, write_json  # noqa: E402

AV = ROOT / "data" / "availability"
RV = ROOT / "data" / "review"

URL_INJURIES = "https://www.nfl.com/injuries/"
URL_SCORES = "https://www.nfl.com/scores/2026/week-10"

# The NFL.com injury page prints "LAR" for the Rams; the club depth charts and the
# committed capture use "LA". This map is a label translation, not a data edit.
TEAM_ALIAS = {"LAR": "LA", "LA": "LA", "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE",
              "HST": "HOU", "IND": "IND", "JAX": "JAX", "MIA": "MIA", "MIN": "MIN",
              "NE": "NE", "NO": "NO", "NYG": "NYG", "NYJ": "NYJ", "PHI": "PHI",
              "PIT": "PIT", "SD": "LAC", "SF": "SF", "SEA": "SEA", "TB": "TB",
              "TEN": "TEN", "WAS": "WAS", "GB": "GB", "DET": "DET", "KC": "KC",
              "ATL": "ATL", "BUF": "BUF", "CAR": "CAR", "CHI": "CHI", "CIN": "CIN",
              "DAL": "DAL", "DEN": "DEN", "LV": "LV"}

# Official club site for every club, from pipeline/fetch_availability.TEAMS. Used so that a
# row whose chart failed to parse still carries a link to the official page it came from.
CLUB_DEPTH_URL = {
    "ARI": "https://www.azcardinals.com/team/depth-chart",
    "ATL": "https://www.atlantafalcons.com/team/depth-chart",
    "BAL": "https://www.baltimoreravens.com/team/depth-chart",
    "BUF": "https://www.buffalobills.com/team/depth-chart",
    "CAR": "https://www.panthers.com/team/depth-chart",
    "CHI": "https://www.chicagobears.com/team/depth-chart",
    "CIN": "https://www.bengals.com/team/depth-chart",
    "CLE": "https://www.clevelandbrowns.com/team/depth-chart",
    "DAL": "https://www.dallascowboys.com/team/depth-chart",
    "DEN": "https://www.denverbroncos.com/team/depth-chart",
    "DET": "https://www.detroitlions.com/team/depth-chart",
    "GB": "https://www.packers.com/team/depth-chart",
    "HOU": "https://www.houstontexans.com/team/depth-chart",
    "IND": "https://www.colts.com/team/depth-chart",
    "JAX": "https://www.jaguars.com/team/depth-chart",
    "KC": "https://www.chiefs.com/team/depth-chart",
    "LV": "https://www.raiders.com/team/depth-chart",
    "LAC": "https://www.chargers.com/team/depth-chart",
    "LA": "https://www.therams.com/team/depth-chart",
    "MIA": "https://www.miamidolphins.com/team/depth-chart",
    "MIN": "https://www.vikings.com/team/depth-chart",
    "NE": "https://www.patriots.com/team/depth-chart",
    "NO": "https://www.neworleanssaints.com/team/depth-chart",
    "NYG": "https://www.giants.com/team/depth-chart",
    "NYJ": "https://www.newyorkjets.com/team/depth-chart",
    "PHI": "https://www.philadelphiaeagles.com/team/depth-chart",
    "PIT": "https://www.steelers.com/team/depth-chart",
    "SF": "https://www.49ers.com/team/depth-chart",
    "SEA": "https://www.seahawks.com/team/depth-chart",
    "TB": "https://www.buccaneers.com/team/depth-chart",
    "TEN": "https://www.tennesseetitans.com/team/depth-chart",
    "WAS": "https://www.commanders.com/team/depth-chart",
}

# Jersey numbers are part of some clubs' depth-chart markup (all 57 Green Bay rows carry
# them). They are stripped for matching only; the displayed name is left as published.
_JERSEY = re.compile(r"^\s*\d{1,2}\s+")
_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")
_ODD = re.compile(r"[^a-z0-9 ]+")


def norm_name(name: str) -> str:
    """Normalise a player name for matching only. Never used for display."""
    s = str(name or "").lower()
    s = _JERSEY.sub("", s)
    s = s.replace("'", "").replace(".", " ").replace("-", " ")
    s = _ODD.sub(" ", s)
    s = _SUFFIX.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def string_label(rank: int | None) -> str:
    return {1: "1st string", 2: "2nd string", 3: "3rd string",
            4: "4th string"}.get(rank, f"{rank}th string" if rank else "")


# ---------------------------------------------------------------------------
# Depth-chart index
# ---------------------------------------------------------------------------
def load_depth() -> tuple[dict, dict, dict]:
    """Return (slot_index, player_index, club_meta).

    slot_index[(team, unit, slot, position)] -> [(rank, player, player_url), ...] sorted
    player_index[(team, norm_name)]          -> [(unit, slot, position, rank, player), ...]
    club_meta[team]                          -> {club, source_url, retrieved_utc, rows}
    """
    slot_index: dict[tuple, list[tuple]] = defaultdict(list)
    player_index: dict[tuple, list[tuple]] = defaultdict(list)
    club_meta: dict[str, dict] = {}
    for r in read_csv(AV / "depth_charts.csv"):
        team = TEAM_ALIAS.get(r["team"].strip(), r["team"].strip())
        try:
            rank = int(r["depth_rank"])
        except (TypeError, ValueError):
            continue
        key = (team, r["unit"], r["slot"], r["position"])
        slot_index[key].append((rank, r["player"].strip(), r["player_url"]))
        player_index[(team, norm_name(r["player"]))].append(
            (r["unit"], r["slot"], r["position"], rank, r["player"].strip()))
        m = club_meta.setdefault(team, {"club": r["club"], "source_url": r["source_url"],
                                        "retrieved_utc": r["retrieved_utc"], "rows": 0})
        m["rows"] += 1
    for k in slot_index:
        slot_index[k].sort()
    return slot_index, player_index, club_meta


# ---------------------------------------------------------------------------
# The join
# ---------------------------------------------------------------------------
def next_in_slot(slot_index, team, unit, slot, position, rank):
    """The player the club lists immediately after `rank` at this position group."""
    for rk, nm, url in slot_index.get((team, unit, slot, position), []):
        if rk == rank + 1:
            return nm, url, rk
    return "", "", None


def parallel_in_position(slot_index, team, unit, position, exclude_slot):
    """Other position groups with the same label (e.g. a second WR row)."""
    out = []
    for (t, u, s, p), rows in slot_index.items():
        if t == team and u == unit and p == position and s != exclude_slot:
            out += [(rk, nm) for rk, nm, _ in rows]
    return sorted(out)


def deficiency_rows(inj: list[dict], slot_index, player_index, club_meta,
                    *, source_url: str, verified_utc: str) -> list[dict]:
    """Join one official injury capture to the depth charts."""
    status_of: dict[tuple, str] = {}
    practice_of: dict[tuple, str] = {}
    for r in inj:
        team = TEAM_ALIAS.get(r["team"].strip(), r["team"].strip())
        status_of[(team, norm_name(r["player"]))] = (r.get("game_status") or "").strip()
        practice_of[(team, norm_name(r["player"]))] = (r.get("practice_status") or "").strip()

    out = []
    for r in inj:
        team = TEAM_ALIAS.get(r["team"].strip(), r["team"].strip())
        status = (r.get("game_status") or "").strip()
        if status not in ("Out", "Doubtful", "Questionable"):
            continue  # a blank designation is not a deficiency; it is an unknown
        nm = norm_name(r["player"])
        meta = club_meta.get(team, {})
        slots = player_index.get((team, nm), [])
        if not slots:
            out.append(dict(
                team=team, club=r.get("club", ""), opponent=r.get("opponent", ""),
                kickoff_slot=r.get("kickoff_slot", ""), unit="", slot="", position="",
                player=r["player"], position_reported=r.get("position", ""),
                injury=r.get("injury", ""), practice_status=r.get("practice_status", ""),
                game_status=status, string="", next_listed="", next_string="",
                next_game_status="", parallel_at_position="",
                deficiency_tier="NO_DEPTH_MATCH",
                deficiency_note=("club published no depth-chart row for this player"
                                 if meta.get("rows") else "club depth chart not captured"),
                depth_source_url=meta.get("source_url") or CLUB_DEPTH_URL.get(team, ""),
                injury_source_url=source_url,
                depth_retrieved_utc=meta.get("retrieved_utc", ""),
                injury_retrieved_utc=verified_utc))
            continue
        for unit, slot, position, rank, published in slots:
            nxt, nxt_url, nxt_rank = next_in_slot(slot_index, team, unit, slot, position, rank)
            nxt_status = status_of.get((team, norm_name(nxt)), "") if nxt else ""
            par = parallel_in_position(slot_index, team, unit, position, slot)
            tier = f"{status.upper()}_{rank}TH_STRING"
            note = ""
            if nxt and nxt_status in ("Out", "Doubtful"):
                tier += "_NEXT_ALSO_OUT"
                note = (f"the next listed player ({nxt}) also carries an "
                        f"{nxt_status} designation")
            elif not nxt:
                note = "no deeper player listed at this position group"
            out.append(dict(
                team=team, club=r.get("club", ""), opponent=r.get("opponent", ""),
                kickoff_slot=r.get("kickoff_slot", ""), unit=unit, slot=slot,
                position=position, player=r["player"],
                position_reported=r.get("position", ""), injury=r.get("injury", ""),
                practice_status=r.get("practice_status", ""), game_status=status,
                string=string_label(rank), next_listed=nxt, next_string=string_label(nxt_rank),
                next_game_status=nxt_status,
                parallel_at_position="; ".join(f"{string_label(rk)} {n}" for rk, n in par[:4]),
                deficiency_tier=tier, deficiency_note=note,
                depth_source_url=meta.get("source_url") or CLUB_DEPTH_URL.get(team, ""),
                injury_source_url=source_url,
                depth_retrieved_utc=meta.get("retrieved_utc", ""),
                injury_retrieved_utc=verified_utc))
    out.sort(key=lambda d: ({"Out": 0, "Doubtful": 1, "Questionable": 2}[d["game_status"]],
                            d["team"], d["unit"], d["position"], d["player"]))
    return out


def unit_summary(rows: list[dict]) -> list[dict]:
    agg: dict[tuple, dict] = {}
    for r in rows:
        k = (r["team"], r["club"], r["opponent"], r["unit"])
        d = agg.setdefault(k, dict(
            team=r["team"], club=r["club"], opponent=r["opponent"], unit=r["unit"],
            out_1st=0, out_deeper=0, doubtful=0, questionable=0, next_also_out=0,
            no_depth_match=0, positions=[], depth_source_url=r["depth_source_url"],
            injury_source_url=r["injury_source_url"]))
        st = r["game_status"]
        if r["deficiency_tier"] == "NO_DEPTH_MATCH":
            d["no_depth_match"] += 1
        elif st == "Out":
            if r["string"] == "1st string":
                d["out_1st"] += 1
            else:
                d["out_deeper"] += 1
        elif st == "Doubtful":
            d["doubtful"] += 1
        else:
            d["questionable"] += 1
        if r["deficiency_tier"].endswith("_NEXT_ALSO_OUT"):
            d["next_also_out"] += 1
        if r["position"]:
            d["positions"].append(r["position"])
    out = []
    for d in agg.values():
        d["positions"] = ", ".join(sorted(set(d["positions"])))
        out.append(d)
    out.sort(key=lambda d: (d["team"], d["unit"]))
    return out


# ---------------------------------------------------------------------------
# Drift between two captures of the same official page
# ---------------------------------------------------------------------------
def drift_rows(committed: list[dict], verified: list[dict]) -> tuple[list[dict], dict]:
    """Compare the scheduled capture with the hand-verified read of the same page."""
    def key(r):
        return (TEAM_ALIAS.get(r["team"].strip(), r["team"].strip()), norm_name(r["player"]))

    cmap = {key(r): r for r in committed}
    vmap = {key(r): r for r in verified}
    rows = []
    for k in sorted(set(cmap) | set(vmap)):
        c, v = cmap.get(k), vmap.get(k)
        if c is None:
            rows.append(dict(team=k[0], player=(v or {}).get("player", k[1]),
                             field="(whole row)", captured="(absent)",
                             verified=(v or {}).get("game_status") or "(blank)",
                             kind="ROW_MISSING_FROM_CAPTURE",
                             injury_source_url=URL_INJURIES))
            continue
        if v is None:
            rows.append(dict(team=k[0], player=c.get("player", k[1]), field="(whole row)",
                             captured=c.get("game_status") or "(blank)", verified="(absent)",
                             kind="ROW_NOT_IN_VERIFIED_READ",
                             injury_source_url=URL_INJURIES))
            continue
        for field in ("practice_status", "game_status", "injury"):
            cv, vv = (c.get(field) or "").strip(), (v.get(field) or "").strip()
            if cv != vv:
                rows.append(dict(team=k[0], player=c.get("player", k[1]), field=field,
                                 captured=cv or "(blank)", verified=vv or "(blank)",
                                 kind="VALUE_CHANGED", injury_source_url=URL_INJURIES))
    summary = dict(
        committed_rows=len(committed), verified_rows=len(verified),
        changed_rows=len(rows),
        committed_with_designation=sum(1 for r in committed if (r.get("game_status") or "").strip()),
        verified_with_designation=sum(1 for r in verified if (r.get("game_status") or "").strip()),
        by_kind=dict(Counter(r["kind"] for r in rows)),
        by_team=dict(sorted(Counter(r["team"] for r in rows).items())),
    )
    return rows, summary


# ---------------------------------------------------------------------------
def main() -> int:
    slot_index, player_index, club_meta = load_depth()

    committed = read_csv(AV / "injuries.csv")
    verified = read_csv(RV / "nfl_injuries_2026_11_13.csv")
    if not committed and not verified:
        print("no injury capture found; nothing to join")
        return 1

    committed_utc = committed[0].get("retrieved_utc", "") if committed else ""
    verified_utc = verified[0].get("verified_utc", "") if verified else ""

    # Publish the join for whichever capture is newer, and the drift between them.
    use_verified = bool(verified) and (not committed or verified_utc >= committed_utc)
    src = verified if use_verified else committed
    src_utc = verified_utc if use_verified else committed_utc
    rows = deficiency_rows(src, slot_index, player_index, club_meta,
                           source_url=URL_INJURIES, verified_utc=src_utc)
    usum = unit_summary(rows)

    DEF_COLS = ["team", "club", "opponent", "kickoff_slot", "unit", "slot", "position",
                "player", "position_reported", "injury", "practice_status", "game_status",
                "string", "next_listed", "next_string", "next_game_status",
                "parallel_at_position", "deficiency_tier", "deficiency_note",
                "depth_source_url", "injury_source_url", "depth_retrieved_utc",
                "injury_retrieved_utc"]
    write_csv(RV / "gameday_deficiency.csv", DEF_COLS, rows)

    SUM_COLS = ["team", "club", "opponent", "unit", "out_1st", "out_deeper", "doubtful",
                "questionable", "next_also_out", "no_depth_match", "positions",
                "depth_source_url", "injury_source_url"]
    write_csv(RV / "gameday_unit_summary.csv", SUM_COLS, usum)

    drift, dsum = drift_rows(committed, verified)
    DR_COLS = ["team", "player", "field", "captured", "verified", "kind",
               "injury_source_url"]
    write_csv(RV / "capture_drift.csv", DR_COLS, drift)

    tiers = Counter(r["deficiency_tier"] for r in rows)
    summary = dict(
        generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        capture_used="data/review/nfl_injuries_2026_11_13.csv" if use_verified
                     else "data/availability/injuries.csv",
        capture_utc=src_utc,
        committed_capture_utc=committed_utc,
        verified_capture_utc=verified_utc,
        injury_rows_used=len(src),
        deficiency_rows=len(rows),
        teams=len({r["team"] for r in rows}),
        clubs_with_depth_chart=len(club_meta),
        clubs_without_depth_chart=sorted(
            {r["team"] for r in src} - set(club_meta)),
        out_1st=sum(1 for r in rows if r["deficiency_tier"].startswith("OUT_1")),
        out_deeper=sum(1 for r in rows if r["game_status"] == "Out"
                       and r["string"] not in ("", "1st string")),
        doubtful=sum(1 for r in rows if r["game_status"] == "Doubtful"),
        questionable=sum(1 for r in rows if r["game_status"] == "Questionable"),
        next_also_out=sum(1 for r in rows if r["deficiency_tier"].endswith("_NEXT_ALSO_OUT")),
        no_depth_match=tiers.get("NO_DEPTH_MATCH", 0),
        tier_counts=dict(sorted(tiers.items())),
        drift=dsum,
    )
    write_json(RV / "gameday_summary.json", summary)

    print(f"deficiency rows={len(rows)} teams={summary['teams']} "
          f"out_1st={summary['out_1st']} out_deeper={summary['out_deeper']} "
          f"doubtful={summary['doubtful']} questionable={summary['questionable']} "
          f"next_also_out={summary['next_also_out']} no_depth_match={summary['no_depth_match']}")
    print(f"capture used: {summary['capture_used']} @ {src_utc}")
    print(f"drift rows={len(drift)} committed={dsum['committed_rows']} "
          f"verified={dsum['verified_rows']} "
          f"designations {dsum['committed_with_designation']} -> {dsum['verified_with_designation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
