#!/usr/bin/env python3
"""Transcribe four official club depth charts, read 2026-11-18, into the dated
verification baseline used by `pipeline/live_verify_depth.py`.

Why this file exists
---------------------
The verification baseline `data/live/official_depth_extract_2026_11_13.csv` was
transcribed by hand from the same four official club pages on 2026-11-13. Club
depth charts move every week (injuries, IR moves, mid-season signings), so a
hand transcription goes stale: on 2026-11-18 the Commanders page no longer
matched the 2026-11-13 transcription in 14 of 29 slots, the Giants page in 3 of
29 and the Lions page in 1 of 28, while the Patriots page still matched in all
29. A stale baseline makes a *correct* parser look broken, and it made the
regression suite red on `main`.

This script re-reads the four official pages on a stated date and writes a new
dated baseline. Every row below is a literal transcription of what the official
page showed at read time; nothing is inferred, and no player name is added or
removed by judgement. The write is idempotent: the output depends only on this
file, so a re-run reproduces the committed artefact exactly.

Read date: 2026-11-18 (UTC). Sources:
  WAS  https://www.commanders.com/team/depth-chart
  NYG  https://www.giants.com/team/depth-chart
  DET  https://www.detroitlions.com/team/depth-chart
  NE   https://www.patriots.com/team/depth-chart

Usage: python scripts/transcribe_depth_charts_2026_11_18.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "live" / "official_depth_extract_2026_11_18.csv"
READ_DATE = "2026-11-18"

WAS_URL = "https://www.commanders.com/team/depth-chart"
NYG_URL = "https://www.giants.com/team/depth-chart"
DET_URL = "https://www.detroitlions.com/team/depth-chart"
NE_URL = "https://www.patriots.com/team/depth-chart"

# (position, [players in the order the official page lists them])
WAS_OFFENSE = [
    ("WR", ["Treylon Burks", "Van Jefferson"]),
    ("LT", ["Brandon Coleman", "Andrew Wylie"]),
    ("LG", ["Chris Paul", "Nick Allegretti"]),
    ("C", ["Lucas Patrick", "Matt Gulbin"]),
    ("RG", ["Sam Cosmi", "Tanoa Togiai"]),
    ("RT", ["Josh Conerly Jr.", "Andrew Wylie"]),
    ("TE", ["Chig Okonkwo", "Ben Sinnott"]),
    ("TE", ["John Bates", "Colson Yankoff"]),
    ("WR", ["Stefon Diggs", "Luke McCaffrey"]),
    ("WR", ["Antonio Williams"]),
    ("QB", ["Jayden Daniels", "Marcus Mariota", "Athan Kaliakmanis"]),
    ("RB", ["Rachaad White", "Austin Ekeler", "Robert Henry Jr."]),
]
WAS_DEFENSE = [
    ("DL", ["Charles Omenihu", "Jer'Zhan Newton"]),
    ("DL", ["Tim Settle", "Shy Tuttle"]),
    ("DL", ["Deatrich Wise Jr.", "Ricky Barber"]),
    ("OLB", ["Odafe Oweh", "Joshua Josephs"]),
    ("LB", ["Sonny Styles", "Kain Medrano"]),
    ("LB", ["Frankie Luvu", "Jordan Magee"]),
    ("OLB", ["K'Lavon Chaisson", "Dorance Armstrong"]),
    ("CB", ["Amik Robertson", "Rasul Douglas", "Isaac Yiadom"]),
    ("CB", ["Trey Amos", "Mike Sainristil", "Fabian Moreau"]),
    ("SS", ["Nick Cross", "Tyler Owens"]),
    ("FS", ["Jeremy Reaves", "Quan Martin", "Percy Butler"]),
]
WAS_ST = [
    ("P", ["Tress Way"]),
    ("K", ["Drew Stevens"]),
    ("H", ["Tress Way"]),
    ("LS", ["Tyler Ott"]),
    ("KR", ["Luke McCaffrey", "Austin Ekeler"]),
    ("PR", ["Antonio Williams", "Luke McCaffrey", "Treylon Burks"]),
]

DET_OFFENSE = [
    ("WR", ["Jameson Williams"]),
    ("WR", ["Amon-Ra St. Brown", "DeAndre Carter"]),
    ("LT", ["Penei Sewell"]),
    ("LG", ["Christian Mahogany", "Miles Frazier"]),
    ("C", ["Cade Mays", "Juice Scruggs"]),
    ("RG", ["Tate Ratledge", "Seth McLaughlin"]),
    ("RT", ["Blake Miller", "Larry Borom"]),
    ("TE", ["Sam LaPorta", "Brock Wright", "Tyler Conklin"]),
    ("WR", ["Isaac TeSlaa", "Tay Martin"]),
    ("QB", ["Jared Goff", "Joshua Dobbs"]),
    ("RB", ["Jahmyr Gibbs", "Sione Vaki", "Jacob Saylors"]),
]
DET_DEFENSE = [
    ("EDGE", ["Aidan Hutchinson", "Derrick Moore", "Eric O'Neill"]),
    ("DL", ["Alim McNeill", "Skyler Gill-Howard", "Mekhi Wingo"]),
    ("DL", ["Tyleik Williams", "Levi Onwuzurike"]),
    ("EDGE", ["DJ Wonnum", "Tyler Lacy", "Ahmed Hassanein", "Tyrus Wheat"]),
    ("LB", ["Derrick Barnes", "Joe Bachie"]),
    ("LB", ["Malcolm Rodriguez", "K.J. Britt"]),
    ("LB", ["Trevor Nowaske", "Amen Ogbongbemiga"]),
    ("CB", ["D.J. Reed", "Rock Ya-Sin", "Khalil Dorsey"]),
    ("CB", ["Roger McCreary", "Ennis Rakestraw Jr.", "Keith Abney II"]),
    ("S", ["Chuck Clark", "Andre Cisco"]),
    ("S", ["Brian Branch", "Christian Izien"]),
]
DET_ST = [
    ("K", ["Jake Bates"]),
    ("H", ["Jack Fox"]),
    ("P", ["Jack Fox"]),
    ("LS", ["Hogan Hatten"]),
    ("PR", ["DeAndre Carter"]),
    ("KR", ["Jacob Saylors", "DeAndre Carter"]),
]

NYG_OFFENSE = [
    ("WR", ["Malik Nabers", "Malachi Fields", "Jalin Hyatt"]),
    ("WR", ["Darnell Mooney"]),
    ("LT", ["Andrew Thomas", "J.C. Davis"]),
    ("LG", ["Jon Runyan Jr.", "Aaron Stinnie", "Josh Sills"]),
    ("C", ["Bryan Hudson", "John Michael Schmitz Jr."]),
    ("RG", ['Francis "Sisi" Mauigoa', "Aaron Stinnie"]),
    ("RT", ["Jermaine Eluemunor", "Marcus Mbow"]),
    ("TE", ["Isaiah Likely", "Theo Johnson", "Chris Manhertz", "Thomas Fidone II"]),
    ("QB", ["J.J. McCarthy", "Jameis Winston"]),
    ("FB", ["Patrick Ricard"]),
    ("RB", ["Cam Skattebo", "Devin Singletary", "Gregory Desrosiers"]),
]
NYG_DEFENSE = [
    ("DT", ["Shelby Harris", "Darius Alexander", "Bobby Jamison-Travis"]),
    ("NT", ["DJ Reader", "C.J. Okoye"]),
    ("DE", ["Darius Alexander"]),
    ("RUSH", ["Kayvon Thibodeaux", "Trace Ford"]),
    ("MLB", ["Micah McFadden", "Zaire Barnes"]),
    ("WLB", ["Arvell Reese", "Jack Kelly"]),
    ("SAM", ["Abdul Carter", "Kayvon Thibodeaux"]),
    ("CB", ["Deonte Banks", "Paulson Adebo"]),
    ("SS", ["Tyler Nubin", "Jason Pinnock"]),
    ("FS", ["Jevón Holland", "Ar'Darius Washington", "Elijah Campbell"]),
    ("CB", ["Greg Newsome II", "Colton Hood"]),
    ("NB", ["Dru Phillips", "Nic Jones"]),
]
NYG_ST = [
    ("P", ["Jordan Stout"]),
    ("K", ["Dominic Zvada"]),
    ("H", ["Jordan Stout"]),
    ("LS", ["Ben Mann"]),
    ("KOR", ["Deonte Banks", "Devin Singletary"]),
    ("PR", ["Jevón Holland"]),
]

NE_OFFENSE = [
    ("WR", ["A.J. Brown", "Efton Chism III"]),
    ("LT", ["Will Campbell", "Dametrious Crownover", "Marcus Bryant"]),
    ("LG", ["Ben Brown", "Walter Rouse"]),
    ("C", ["Jared Wilson", "Ben Brown"]),
    ("RG", ["Matt Pryor", "Walter Rouse"]),
    ("RT", ["Morgan Moses", "Caleb Lomu"]),
    ("TE", ["Hunter Henry", "Eli Raridon", "Cameron Latu"]),
    ("WR", ["DeMario Douglas", "Kyle Williams"]),
    ("WR", ["Efton Chism III", "Kyle Williams"]),
    ("RB", ["Rhamondre Stevenson", "TreVeyon Henderson", "Corey Kiner", "Lan Larison"]),
    ("QB", ["Drake Maye", "Tommy DeVito", "Behren Morton"]),
]
NE_DEFENSE = [
    ("OLB", ["Dre'Mont Jones", "Gabe Jacas"]),
    ("DT", ["Christian Barmore", "Leonard Taylor III"]),
    ("DT", ["Cory Durden", "DaQuan Jones"]),
    ("DT", ["Milton Williams", "Joshua Farmer"]),
    ("OLB", ["Elijah Ponder", "Gabe Jacas"]),
    ("LB", ["Robert Spillane", "Darius Muasau", "Erick Hunter"]),
    ("LB", ["Christian Elliss", "Namdi Obiazor"]),
    ("CB", ["Carlton Davis III", "Channing Canada"]),
    ("S", ["Craig Woodson", "Mike Brown"]),
    ("S", ["Kevin Byard III", "Jaylen Reed", "Brenden Schooler"]),
    ("CB", ["Marcus Jones", "Charles Woods"]),
    ("CB", ["Christian Gonzalez", "Karon Prunty"]),
]
NE_ST = [
    ("K", ["Andy Borregales"]),
    ("P", ["Mitch Wishnowsky"]),
    ("H", ["Mitch Wishnowsky"]),
    ("LS", ["Julian Ashby"]),
    ("PR", ["Marcus Jones", "DeMario Douglas"]),
    ("KR", ["Kyle Williams", "Corey Kiner", "Lan Larison"]),
]


def build() -> pd.DataFrame:
    rows = []
    for team, club, url, off, dfn, st in [
        ("WAS", "Commanders", WAS_URL, WAS_OFFENSE, WAS_DEFENSE, WAS_ST),
        ("DET", "Lions", DET_URL, DET_OFFENSE, DET_DEFENSE, DET_ST),
        ("NYG", "Giants", NYG_URL, NYG_OFFENSE, NYG_DEFENSE, NYG_ST),
        ("NE", "Patriots", NE_URL, NE_OFFENSE, NE_DEFENSE, NE_ST),
    ]:
        for unit, blocks in (("Offense", off), ("Defense", dfn), ("Special Teams", st)):
            for i, (pos, players) in enumerate(blocks, 1):
                rows.append(dict(
                    team=team, club=club, unit=unit, row=i, position=pos,
                    players="|".join(players), source_url=url,
                    note=f"transcribed from the official club depth-chart page on {READ_DATE}",
                ))
    return pd.DataFrame(rows)


def main() -> int:
    df = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    entries = int(df.players.str.count(r"\|").add(1).sum())
    print(f"wrote {OUT.relative_to(ROOT)}: {len(df)} slot rows, {entries} player entries")

    snap = ROOT / "data" / "availability" / "depth_charts.csv"
    if not snap.exists():
        print("no published snapshot to compare against")
        return 0
    pub = pd.read_csv(snap, dtype=str, keep_default_na=False)
    pub["depth_rank"] = pub.depth_rank.astype(int)
    published = {}
    for (team, unit), g in pub.groupby(["team", "unit"], sort=False):
        for i, (_slot, h) in enumerate(g.groupby("slot", sort=False), 1):
            published[(team, unit, i)] = [str(x) for x in h.sort_values("depth_rank").player.tolist()]
    transcribed = {(r.team, r.unit, int(r.row)): [x for x in r.players.split("|") if x]
                    for r in df.itertuples()}
    teams = set(df.team.unique())
    diff = [k for k in sorted(set(transcribed) | set(published))
            if k[0] in teams and transcribed.get(k) != published.get(k)]
    print(f"comparison against {snap.relative_to(ROOT)}: "
          f"{len(transcribed)} slots compared, {len(diff)} differ")
    for k in diff:
        print("  DIFF", k, "| page:", transcribed.get(k), "| snapshot:", published.get(k))
    return 0


if __name__ == "__main__":
    sys.exit(main())
