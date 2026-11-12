"""T14b — join the official injury report to the official club depth charts.

Reads only the committed snapshot in data/availability/ (written by
pipeline/fetch_availability.py on a GitHub runner). Pure standard library, deterministic.

What it states, and nothing more
--------------------------------
For every depth-chart slot the club publishes, it reports the first-listed player, that
player's line on the league injury report (if he has one), and — when the first-listed
player is designated Out or Doubtful — the next player the club lists in that slot who is
not himself designated Out or Doubtful, with his published depth rank (2nd / 3rd / 4th
string). It does not predict who will start, does not estimate a point value, and does not
fill any cell that is empty on the official page.

Name matching is exact after a documented normalisation (case, punctuation, and the
suffixes Jr/Sr/II/III/IV/V are ignored) within the same club. Players on the injury report
that cannot be matched to the club's depth chart are listed separately, never guessed.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AV = ROOT / "data" / "availability"
UNAVAILABLE = {"out", "doubtful"}
ORDINAL = {1: "1st string", 2: "2nd string", 3: "3rd string", 4: "4th string"}

SLOT_COLS = ["team", "club", "opponent", "unit", "slot", "position", "first_listed", "first_listed_url",
             "practice_status", "game_status", "flag", "next_listed", "next_listed_rank",
             "next_listed_status", "depth_source_url", "injury_source_url",
             "depth_retrieved_utc", "injury_retrieved_utc"]
UNIT_COLS = ["team", "club", "opponent", "unit", "slots_published", "first_listed_out",
             "first_listed_doubtful", "first_listed_questionable", "first_listed_dnp_no_status",
             "backups_out_or_doubtful", "positions_affected", "depth_source_url", "injury_source_url"]
UNMATCHED_COLS = ["team", "club", "player", "position", "injury", "practice_status", "game_status",
                  "reason", "player_url", "source_url"]


def norm(name: str) -> str:
    s = re.sub(r"[.'’`]", "", name.lower()).replace("-", " ")
    toks = [t for t in s.split() if t not in {"jr", "sr", "ii", "iii", "iv", "v"}]
    return " ".join(toks)


def ordinal(rank: int) -> str:
    return ORDINAL.get(rank, f"{rank}th string")


def read(path: Path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write(path: Path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader(); w.writerows(rows)


def build(inj: list[dict], depth: list[dict]):
    """Return (slot rows, unit rows, unmatched rows). Pure function, unit-tested."""
    report = {}
    for r in inj:
        report[(r["team"], norm(r["player"]))] = r
    opponent = {r["team"]: r["opponent"] for r in inj}
    inj_time = {r["team"]: r["retrieved_utc"] for r in inj}

    slots = {}
    for r in depth:
        slots.setdefault((r["team"], int(r["slot"])), []).append(r)
    on_chart = {(r["team"], norm(r["player"])) for r in depth}

    slot_rows, unit = [], {}
    for (team, slot), players in sorted(slots.items()):
        players.sort(key=lambda r: int(r["depth_rank"]))
        first_rank = int(players[0]["depth_rank"])
        firsts = [p for p in players if int(p["depth_rank"]) == first_rank]
        rest = [p for p in players if int(p["depth_rank"]) > first_rank]
        base = players[0]
        key = (team, base["unit"])
        u = unit.setdefault(key, dict(team=team, club=base["club"], opponent=opponent.get(team, ""),
                                      unit=base["unit"], slots_published=0, first_listed_out=0,
                                      first_listed_doubtful=0, first_listed_questionable=0,
                                      first_listed_dnp_no_status=0, backups_out_or_doubtful=0,
                                      positions_affected=[], depth_source_url=base["source_url"],
                                      injury_source_url="https://www.nfl.com/injuries/" if team in opponent else ""))
        u["slots_published"] += 1
        for b in rest:
            st = report.get((team, norm(b["player"])), {}).get("game_status", "").strip().lower()
            if st in UNAVAILABLE:
                u["backups_out_or_doubtful"] += 1
        for first in firsts:
            rep = report.get((team, norm(first["player"])), {})
            status = rep.get("game_status", "").strip()
            practice = rep.get("practice_status", "").strip()
            flag, nxt, nxt_rank, nxt_status = "", "", "", ""
            low = status.lower()
            if low == "out":
                flag = "FIRST-LISTED OUT"; u["first_listed_out"] += 1
            elif low == "doubtful":
                flag = "FIRST-LISTED DOUBTFUL"; u["first_listed_doubtful"] += 1
            elif low == "questionable":
                flag = "FIRST-LISTED QUESTIONABLE"; u["first_listed_questionable"] += 1
            elif not status and practice.lower().startswith("did not participate"):
                flag = "FIRST-LISTED DID NOT PRACTICE (no game status posted)"
                u["first_listed_dnp_no_status"] += 1
            if low in UNAVAILABLE:
                u["positions_affected"].append(first["position"])
                for b in rest:
                    b_rep = report.get((team, norm(b["player"])), {})
                    if b_rep.get("game_status", "").strip().lower() in UNAVAILABLE:
                        continue
                    nxt, nxt_rank = b["player"], ordinal(int(b["depth_rank"]))
                    nxt_status = b_rep.get("game_status", "").strip() or b_rep.get("practice_status", "").strip()
                    break
                else:
                    nxt = ""
                    nxt_rank = "no other available player listed in this slot"
            slot_rows.append(dict(team=team, club=first["club"], opponent=opponent.get(team, ""),
                                  unit=first["unit"], slot=slot, position=first["position"],
                                  first_listed=first["player"], first_listed_url=first["player_url"],
                                  practice_status=practice, game_status=status, flag=flag,
                                  next_listed=nxt, next_listed_rank=nxt_rank, next_listed_status=nxt_status,
                                  depth_source_url=first["source_url"],
                                  injury_source_url="https://www.nfl.com/injuries/" if rep else "",
                                  depth_retrieved_utc=first["retrieved_utc"],
                                  injury_retrieved_utc=inj_time.get(team, "")))
    unit_rows = []
    for u in unit.values():
        u["positions_affected"] = " ".join(u["positions_affected"])
        unit_rows.append(u)
    teams_with_chart = {r["team"] for r in depth}
    unmatched = []
    for r in inj:
        if (r["team"], norm(r["player"])) in on_chart:
            continue
        reason = ("club depth chart not machine-readable at capture" if r["team"] not in teams_with_chart
                  else "name on injury report not found on the club's published depth chart")
        unmatched.append(dict(team=r["team"], club=r["club"], player=r["player"], position=r["position"],
                              injury=r["injury"], practice_status=r["practice_status"],
                              game_status=r["game_status"], reason=reason,
                              player_url=r["player_url"], source_url=r["source_url"]))
    return slot_rows, unit_rows, unmatched


def main() -> None:
    inj, depth = read(AV / "injuries.csv"), read(AV / "depth_charts.csv")
    slot_rows, unit_rows, unmatched = build(inj, depth)
    write(AV / "slot_status.csv", SLOT_COLS, slot_rows)
    write(AV / "unit_summary.csv", UNIT_COLS, unit_rows)
    write(AV / "unmatched_report_players.csv", UNMATCHED_COLS, unmatched)
    flagged = sum(1 for r in slot_rows if r["flag"])
    summary = dict(injury_rows=len(inj), depth_rows=len(depth), slots=len(slot_rows),
                   slots_flagged=flagged,
                   first_listed_out=sum(1 for r in slot_rows if r["game_status"].lower() == "out"),
                   unmatched_report_players=len(unmatched),
                   teams_on_injury_report=len({r["team"] for r in inj}),
                   clubs_with_depth_chart=len({r["team"] for r in depth}))
    (AV / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print("availability:", summary)


if __name__ == "__main__":
    main()
