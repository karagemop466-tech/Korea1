"""R1 (2026-11-13) — line-level reconciliation of the automated depth-chart capture.

The official club pages were read with the page-fetch tool on 2026-11-13 and transcribed
below, one row per official table row, in page order. Each official cell is compared with
the automated capture in data/availability/depth_charts.csv (unit, slot order, depth_rank).
Nothing is filled in: a cell the official page does not show stays out of the comparison.

Run: python scripts/reconcile_availability_2026_11_13.py
Writes: data/governance/availability_reconciliation_2026_11_13.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPTH = ROOT / "data" / "availability" / "depth_charts.csv"
OUT = ROOT / "data" / "governance" / "availability_reconciliation_2026_11_13.csv"
CHECKED = "2026-11-13"

# Official page transcriptions: (unit, position, [player per depth_rank in page order])
OFFICIAL = {
    "ARI": ("https://www.azcardinals.com/team/depth-chart", [
        ("Offense", "WR", ["Reggie Virgil", "Harrison Wallace III"]),
        ("Offense", "LT", ["Jayden Williams", "Jedrick Wills"]),
        ("Offense", "LG", ["Isaac Seumalo", "Hayden Conner"]),
        ("Offense", "C", ["Hjalte Froholdt", "Kingsley Eguakun"]),
        ("Offense", "RG", ["Isaiah Adams", "Jon Gaines II"]),
        ("Offense", "RT", ["Elijah Wilkinson", "Josh Fryar", "Albert Reese"]),
        ("Offense", "TE", ["Trey McBride"]),
        ("Offense", "TE", ["Elijah Higgins", "Teagan Quitoriano"]),
        ("Offense", "WR", ["Simi Fehoko", "Devin Duvernay"]),
        ("Offense", "QB", ["Carson Beck", "Josh Johnson", "Joey Aguilar"]),
        ("Offense", "RB", ["Tyler Allgeier", "Bam Knight", "Evan Hull"]),
        ("Defense", "DT", ["Dante Stills", "Darius Robinson"]),
        ("Defense", "NT", ["Roy Lopez", "Andrew Billings"]),
        ("Defense", "DT", ["Walter Nolen III", "L.J. Collier"]),
        ("Defense", "OLB", ["Josh Sweat", "Jordan Burch", "Eku Leota"]),
        ("Defense", "ILB", ["Jack Gibbens", "Karson Sharar"]),
        ("Defense", "ILB", ["Mack Wilson Sr.", "Cody Simon"]),
        ("Defense", "OLB", ["Zaven Collins", "Baron Browning"]),
        ("Defense", "CB", ["Denzel Burke", "Starling Thomas V"]),
        ("Defense", "CB", ["Max Melton", "Kei'Trel Clark"]),
        ("Defense", "CB", ["Kalen King", "Garrett Williams"]),
        ("Defense", "S", ["Andrew Wingard", "Kitan Crawford"]),
        ("Defense", "S", ["Budda Baker", "Dadrion Taylor-Demerson"]),
        ("Special Teams", "K", ["Chad Ryland"]),
        ("Special Teams", "P", ["Blake Gillikin"]),
        ("Special Teams", "LS", ["Casey Kreiter"]),
        ("Special Teams", "H", ["Blake Gillikin"]),
        ("Special Teams", "KR", ["Devin Duvernay", "Max Melton", "Harrison Wallace III"]),
        ("Special Teams", "PR", ["Devin Duvernay", "Harrison Wallace III"]),
    ]),
    "WAS": ("https://www.commanders.com/team/depth-chart", [
        ("Offense", "WR", ["Terry McLaurin", "Treylon Burks"]),
        ("Offense", "LT", ["Brandon Coleman", "Andrew Wylie"]),
        ("Offense", "LG", ["Chris Paul", "Tanoa Togiai"]),
        ("Offense", "C", ["Nick Allegretti", "Matt Gulbin"]),
        ("Offense", "RG", ["Sam Cosmi", "Tanoa Togiai"]),
        ("Offense", "RT", ["Josh Conerly Jr.", "Andrew Wylie"]),
        ("Offense", "TE", ["Chig Okonkwo", "Ben Sinnott"]),
        ("Offense", "TE", ["John Bates", "Colson Yankoff"]),
        ("Offense", "WR", ["Stefon Diggs", "Jaylin Lane"]),
        ("Offense", "WR", ["Dyami Brown", "Antonio Williams", "Luke McCaffrey"]),
        ("Offense", "QB", ["Jayden Daniels", "Marcus Mariota", "Athan Kaliakmanis"]),
        ("Offense", "RB", ["Jacory Croskey-Merritt", "Rachaad White", "Austin Ekeler"]),
        ("Defense", "DL", ["Daron Payne"]),
        ("Defense", "DL", ["Tim Settle", "Shy Tuttle"]),
        ("Defense", "DL", ["Javon Kinlaw", "Charles Omenihu"]),
        ("Defense", "OLB", ["Odafe Oweh", "Joshua Josephs"]),
        ("Defense", "LB", ["Sonny Styles", "Kain Medrano"]),
        ("Defense", "LB", ["Frankie Luvu", "Kain Medrano"]),
        ("Defense", "OLB", ["K'Lavon Chaisson", "Dorance Armstrong", "Javontae Jean-Baptiste"]),
        ("Defense", "CB", ["Amik Robertson", "Rasul Douglas"]),
        ("Defense", "CB", ["Mike Sainristil", "Fabian Moreau"]),
        ("Defense", "SS", ["Nick Cross", "Tyler Owens"]),
        ("Defense", "FS", ["Jeremy Reaves", "Quan Martin", "Percy Butler"]),
        ("Special Teams", "P", ["Tress Way"]),
        ("Special Teams", "K", ["Drew Stevens"]),
        ("Special Teams", "H", ["Tress Way"]),
        ("Special Teams", "LS", ["Tyler Ott"]),
        ("Special Teams", "KR", ["Luke McCaffrey", "Jaylin Lane", "Dyami Brown"]),
        ("Special Teams", "PR", ["Jaylin Lane", "Luke McCaffrey", "Treylon Burks"]),
    ]),
}


TIED_CELLS = {("ARI", "Defense", "OLB", 18)}  # "Zaven Collins [Baron Browning]" in one cell


def load_auto():
    out: dict[str, list[tuple[str, str, list[str]]]] = {}
    seen: dict[tuple, int] = {}
    with open(DEPTH, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            key = (r["team"], r["unit"], r["slot"], r["position"])
            out.setdefault(r["team"], [])
            if key not in seen:
                seen[key] = len(out[r["team"]])
                out[r["team"]].append((r["unit"], r["position"], []))
            out[r["team"]][seen[key]][2].append((int(r["depth_rank"]), r["player"]))
    return {t: [(u, p, [n for _, n in sorted(v)]) for u, p, v in rows] for t, rows in out.items()}


def main() -> int:
    auto = load_auto()
    rows_out = []
    mism = 0
    for team, (url, official) in OFFICIAL.items():
        a = auto.get(team, [])
        if len(a) != len(official):
            print(f"{team}: row count differs official={len(official)} automated={len(a)}")
        for i, (unit, pos, names) in enumerate(official):
            au = a[i] if i < len(a) else (None, None, [])
            same = (au[0] == unit and au[1] == pos and au[2] == names)
            if not same and (team, unit, pos, i + 1) not in TIED_CELLS:
                mism += 1
            # A cell holding two names with no rank order on the page is a tie: the capture
            # stores both at rank 1 and orders them alphabetically, so only the set is compared.
            tie = (team, unit, pos, i + 1) in TIED_CELLS
            for rank, name in enumerate(names, 1):
                auto_name = au[2][rank - 1] if rank - 1 < len(au[2]) else ""
                if tie:
                    result = "TIE IN CELL (set matches)" if set(au[2]) == set(names) else "MISMATCH"
                    rank_label = "1 (tied)"
                else:
                    result = "MATCH" if auto_name == name else ("MISMATCH" if auto_name else "NOT IN CAPTURE")
                    rank_label = str(rank)
                rows_out.append(dict(
                    club=team, unit=unit, position_row=i + 1, position=pos, depth_rank=rank_label,
                    official_player=name, automated_player=(", ".join(au[2]) if tie else auto_name),
                    result=result, official_source=url, checked_utc=CHECKED))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()), lineterminator="\n")
        w.writeheader(); w.writerows(rows_out)
    n = len(rows_out)
    m = sum(1 for r in rows_out if r["result"] in ("MATCH", "TIE IN CELL (set matches)"))
    print(f"cells checked={n} match_or_tie={m} other={n-m} row-level order differences={mism}")
    im, it = reconcile_injuries()
    print(f"injury rows sampled (WAS, NYG): {it}; exact matches: {im}")
    return 0



# ---- Injury report sample: WAS and NYG rows read from https://www.nfl.com/injuries/league/2026/reg10 ----
# (player, position, injury, practice status, game status) exactly as printed; "" = blank cell on the page.
INJ_URL = "https://www.nfl.com/injuries/league/2026/reg10"
INJ_OFFICIAL = {
    "WAS": [
        ("John Bates", "TE", "", "Full Participation in Practice", ""),
        ("Treylon Burks", "WR", "", "Did Not Participate In Practice", ""),
        ("Jayden Daniels", "QB", "", "Full Participation in Practice", ""),
        ("Matt Gulbin", "C", "", "Full Participation in Practice", ""),
        ("Chig Okonkwo", "TE", "", "Full Participation in Practice", ""),
        ("Lucas Patrick", "C", "Concussion", "Did Not Participate In Practice", "Out"),
        ("Amik Robertson", "CB", "", "Limited Participation in Practice", ""),
        ("Shy Tuttle", "DT", "", "Full Participation in Practice", ""),
        ("Colson Yankoff", "TE", "Knee", "Did Not Participate In Practice", "Out"),
    ],
    "NYG": [
        ("Abdul Carter", "LB", "", "Full Participation in Practice", ""),
        ("Jermaine Eluemunor", "T", "", "Full Participation in Practice", ""),
        ("Malik Harrison", "LB", "Groin", "Limited Participation in Practice", "Questionable"),
        ("Colton Hood", "CB", "", "Full Participation in Practice", ""),
        ("Theo Johnson", "TE", "", "Full Participation in Practice", ""),
        ("Charlie Jones", "WR", "", "Full Participation in Practice", ""),
        ("J.J. McCarthy", "QB", "", "Full Participation in Practice", ""),
        ("Darnell Mooney", "WR", "", "Full Participation in Practice", ""),
        ("Malik Nabers", "WR", "", "Full Participation in Practice", ""),
        ("Cam Skattebo", "RB", "", "Full Participation in Practice", ""),
        ("Andrew Thomas", "T", "", "Full Participation in Practice", ""),
    ],
}
INJ_OUT = ROOT / "data" / "governance" / "injury_reconciliation_2026_11_13.csv"


def reconcile_injuries() -> tuple[int, int]:
    snap: dict[str, list[tuple]] = {}
    with open(ROOT / "data" / "availability" / "injuries.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            snap.setdefault(r["team"], []).append(
                (r["player"], r["position"], r["injury"], r["practice_status"], r["game_status"]))
    out, matched, total = [], 0, 0
    for team, official in INJ_OFFICIAL.items():
        s = snap.get(team, [])
        s_by_name = {x[0]: x for x in s}
        for off in official:
            total += 1
            got = s_by_name.get(off[0])
            if got is None:
                res = "NOT IN SNAPSHOT"
            elif tuple(got) == off:
                res = "MATCH"; matched += 1
            else:
                res = "MISMATCH"
            out.append(dict(club=team, player=off[0], official_position=off[1], snapshot_position=got[1] if got else "",
                            official_injury=off[2], snapshot_injury=got[2] if got else "",
                            official_practice=off[3], snapshot_practice=got[3] if got else "",
                            official_game=off[4], snapshot_game=got[4] if got else "",
                            result=res, official_source=INJ_URL, checked_utc=CHECKED))
        extra = [x[0] for x in s if x[0] not in {o[0] for o in official}]
        out.append(dict(club=team, player="(snapshot rows not on the sampled official table)",
                        official_position="", snapshot_position="", official_injury="", snapshot_injury="",
                        official_practice="", snapshot_practice="", official_game="", snapshot_game="",
                        result=f"SNAPSHOT EXTRA ROWS: {len(extra)}" if not extra else
                        f"SNAPSHOT EXTRA ROWS: {', '.join(extra)}", official_source=INJ_URL, checked_utc=CHECKED))
    with open(INJ_OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()), lineterminator="\n")
        w.writeheader(); w.writerows(out)
    # downloadable copies for the published site (the page links these files)
    import shutil
    for src in (OUT, INJ_OUT):
        shutil.copyfile(src, ROOT / "assets" / "data" / src.name)
    return matched, total


if __name__ == "__main__":
    sys.exit(main())
