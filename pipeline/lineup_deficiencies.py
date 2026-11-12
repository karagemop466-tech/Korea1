"""G4 — Official NFL injury + 1st/2nd/3rd/4th-string offensive & defensive lineup deficiency tracker.

Evidence separation
-------------------
1. Official Week 10 (2026-11-12) injury designations and practice participation are verified
   line by line against https://www.nfl.com/injuries/ and individual https://www.nfl.com/players/.../
   pages read on 2026-11-12.
2. Positional string order (1st, 2nd, 3rd, 4th string) across Offense and Defense for four complete
   Week 10 matchups (8 NFL clubs: WAS@NYG, NE@DET, KC@ATL, MIN@GB) is verified line by line against
   each club's official domain depth chart read on 2026-11-12. Where a club labels its depth chart
   "Unofficial" or omits a newly traded / injured player, that discrepancy is recorded verbatim and
   never inferred or filled in.
3. Historical starter-vs-backup impact diagnostics (2019–2022 regular season) are computed strictly
   walk-forward (prior-games usage only, zero lookahead) from the pinned community play-by-play
   table (`prop_player_games.csv`) and `originated_lines.csv`. Because community play-by-play is not
   an official NFL snap/inactive census, numeric model-residual cells remain blank in strict public
   HTML tables and are published in `data/lineups/pbp_backup_impact.csv` as labelled research data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, write_json  # noqa: E402

OUT_DIR = ROOT / "data" / "lineups"
VERIFIED_DATE = "2026-11-12"

URL_NFL_INJURIES = "https://www.nfl.com/injuries/"
URL_NFL_INACTIVES = "https://www.nfl.com/inactives/"
URL_NFL_GAME_PREP = "https://operations.nfl.com/game-operations-logistics/preparation-safety/game-and-stadium-prep"
URL_NFL_HEALTH = "https://operations.nfl.com/inside-football-ops/players-legends/player-health-safety"
URL_NFL_VIKINGS_QB = "https://www.nfl.com/news/vikings-wont-commit-to-kirk-cousins-starting-packers"

CLUB_DEPTH_URLS = {
    "WAS": ("https://www.commanders.com/team/depth-chart", "Club depth chart (Commanders.com; no explicit 'unofficial' banner on table)"),
    "NYG": ("https://www.giants.com/team/depth-chart", "Club depth chart (Giants.com)"),
    "NE": ("https://www.patriots.com/team/depth-chart", "Labelled 'Patriots Unofficial Depth Chart — published by the writers of Patriots.com'"),
    "DET": ("https://www.detroitlions.com/team/depth-chart", "Labelled '2026 Unofficial Depth Chart Compiled by Lions Football Communications'"),
    "KC": ("https://www.chiefs.com/team/depth-chart", "Labelled 'Kansas City Chiefs Unofficial Depth Chart'"),
    "ATL": ("https://www.atlantafalcons.com/team/depth-chart", "Club depth chart (AtlantaFalcons.com)"),
    "MIN": ("https://www.vikings.com/team/depth-chart", "Labelled '2026 Unofficial Depth Chart' (Vikings.com)"),
    "GB": ("https://www.packers.com/team/depth-chart", "Labelled 'Unofficial, Nov. 10, 2026' (Packers.com)"),
}

# Every entry below was read directly from https://www.nfl.com/injuries/ and the 8 official club
# depth charts on 2026-11-12. Empty string "" denotes a field left blank on the official page
# (never inferred or filled in).
WEEK10_ENTRIES = [
    # --- Matchup 1: WAS @ NYG (Thu Nov 12, 2026, 8:15 PM EST) ---
    dict(matchup="WAS @ NYG", kickoff="2026-11-12 20:15 EST", club="WAS", opponent="NYG", unit="Offense",
         pos_injury="C", pos_depth="C", player="Lucas Patrick", player_url="https://www.nfl.com/players/lucas-patrick/",
         injury="Concussion", practice_status="Did Not Participate In Practice", game_status="Out",
         player_string="UNLISTED_ON_DEPTH_CHART",
         string_1="Nick Allegretti", string_2="Matt Gulbin (Full)", string_3="", string_4="",
         active_replacement="Nick Allegretti (1st) / Matt Gulbin (2nd)",
         deficiency_tier="DEPTH_DISCREPANCY",
         deficiency_note="Ruled Out at C on NFL.com injury report, but omitted from Commanders.com 2-deep C row (Nick Allegretti / Matt Gulbin). 2nd-string Matt Gulbin practiced Full."),
    dict(matchup="WAS @ NYG", kickoff="2026-11-12 20:15 EST", club="WAS", opponent="NYG", unit="Offense",
         pos_injury="TE", pos_depth="TE (row 2)", player="Colson Yankoff", player_url="https://www.nfl.com/players/colson-yankoff/",
         injury="Knee", practice_status="Did Not Participate In Practice", game_status="Out",
         player_string="2nd string",
         string_1="John Bates (Full)", string_2="Colson Yankoff (Out)", string_3="", string_4="",
         active_replacement="Ben Sinnott (2nd string in TE row 1 behind Chig Okonkwo)",
         deficiency_tier="2ND_STRING_OUT",
         deficiency_note="2nd-string TE behind John Bates ruled Out; no 3rd/4th string listed in TE row 2. Parallel TE row has 1st Chig Okonkwo (Full) and 2nd Ben Sinnott."),
    dict(matchup="WAS @ NYG", kickoff="2026-11-12 20:15 EST", club="WAS", opponent="NYG", unit="Offense",
         pos_injury="WR", pos_depth="WR (row 1)", player="Treylon Burks", player_url="https://www.nfl.com/players/treylon-burks/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="2nd string",
         string_1="Terry McLaurin", string_2="Treylon Burks (DNP)", string_3="", string_4="",
         active_replacement="Jaylin Lane / Antonio Williams / Luke McCaffrey (other WR rows)",
         deficiency_tier="2ND_STRING_DNP",
         deficiency_note="2nd-string WR behind Terry McLaurin (and 3rd-string PR) DNP; no 3rd string listed in WR row 1; injury/game status blank on NFL.com."),
    dict(matchup="WAS @ NYG", kickoff="2026-11-12 20:15 EST", club="WAS", opponent="NYG", unit="Defense",
         pos_injury="CB", pos_depth="CB (row 1)", player="Amik Robertson", player_url="https://www.nfl.com/players/amik-robertson/",
         injury="", practice_status="Limited Participation in Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Amik Robertson (Limited)", string_2="Rasul Douglas", string_3="", string_4="",
         active_replacement="Rasul Douglas (2nd string)",
         deficiency_tier="STARTER_LIMITED_2ND_READY",
         deficiency_note="1st-string starting CB limited in practice; 2nd-string Rasul Douglas is direct replacement if snap-limited or inactive."),
    dict(matchup="WAS @ NYG", kickoff="2026-11-12 20:15 EST", club="WAS", opponent="NYG", unit="Offense",
         pos_injury="QB", pos_depth="QB", player="Jayden Daniels", player_url="https://www.nfl.com/players/jayden-daniels/",
         injury="", practice_status="Full Participation in Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Jayden Daniels (Full)", string_2="Marcus Mariota", string_3="Athan Kaliakmanis", string_4="",
         active_replacement="Starter full participant",
         deficiency_tier="STARTER_FULL",
         deficiency_note="1st-string QB practiced in full; 2nd Marcus Mariota and 3rd Athan Kaliakmanis remain in reserve."),
    dict(matchup="WAS @ NYG", kickoff="2026-11-12 20:15 EST", club="WAS", opponent="NYG", unit="Defense",
         pos_injury="DT", pos_depth="DL (row 2)", player="Shy Tuttle", player_url="https://www.nfl.com/players/shy-tuttle/",
         injury="", practice_status="Full Participation in Practice", game_status="",
         player_string="2nd string",
         string_1="Tim Settle", string_2="Shy Tuttle (Full)", string_3="", string_4="",
         active_replacement="2nd-string rotational DL full participant",
         deficiency_tier="STARTER_FULL",
         deficiency_note="2nd-string interior DL behind Tim Settle practiced in full."),
    dict(matchup="WAS @ NYG", kickoff="2026-11-12 20:15 EST", club="NYG", opponent="WAS", unit="Defense",
         pos_injury="LB", pos_depth="LB (MLB/WLB/SAM)", player="Malik Harrison", player_url="https://www.nfl.com/players/malik-harrison/",
         injury="Groin", practice_status="Limited Participation in Practice", game_status="Questionable",
         player_string="UNLISTED_ON_DEPTH_CHART (3rd+ / subpackage)",
         string_1="Micah McFadden (MLB) / Arvell Reese (WLB)", string_2="Zaire Barnes (MLB) / Jack Kelly (WLB)", string_3="", string_4="",
         active_replacement="Zaire Barnes / Jack Kelly (2nd string LBs)",
         deficiency_tier="ROTATIONAL_QUESTIONABLE",
         deficiency_note="Questionable (Groin) for TNF; unlisted on Giants.com 2-deep LB rows, indicating rotational/special-teams LB role."),
    dict(matchup="WAS @ NYG", kickoff="2026-11-12 20:15 EST", club="NYG", opponent="WAS", unit="Offense",
         pos_injury="QB", pos_depth="QB", player="J.J. McCarthy", player_url="https://www.nfl.com/players/j-j-mccarthy/",
         injury="", practice_status="Full Participation in Practice", game_status="",
         player_string="1st string (starter)",
         string_1="J.J. McCarthy (Full)", string_2="Jameis Winston", string_3="", string_4="",
         active_replacement="Starter full participant",
         deficiency_tier="STARTER_FULL",
         deficiency_note="1st-string QB practiced in full (alongside 1st-string LT Andrew Thomas, RT Jermaine Eluemunor, WR Malik Nabers, WR Darnell Mooney, RB Cam Skattebo, SAM Abdul Carter — all Full)."),

    # --- Matchup 2: NE vs DET (Sun Nov 15, 2026, 9:30 AM EST, Munich) ---
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="NE", opponent="DET", unit="Defense",
         pos_injury="CB", pos_depth="CB (row 1)", player="Carlton Davis III", player_url="https://www.nfl.com/players/carlton-davis/",
         injury="Knee", practice_status="Did Not Participate In Practice", game_status="Out",
         player_string="1st string (starter)",
         string_1="Carlton Davis III (Out)", string_2="Channing Canada", string_3="", string_4="",
         active_replacement="Channing Canada (2nd string CB)",
         deficiency_tier="STARTER_OUT_2ND_STRING",
         deficiency_note="1st-string starting boundary CB ruled Out (Knee); 2nd-string Channing Canada forced into starter role with no 3rd/4th string listed in CB row 1, while CB row 2 backup Charles Woods is also Limited."),
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="NE", opponent="DET", unit="Defense",
         pos_injury="S", pos_depth="S (row 2)", player="Kevin Byard", player_url="https://www.nfl.com/players/kevin-byard/",
         injury="", practice_status="Limited Participation in Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Kevin Byard III (Limited)", string_2="Jaylen Reed", string_3="Brenden Schooler (DNP)", string_4="",
         active_replacement="Jaylen Reed (2nd string S; 3rd string Brenden Schooler DNP)",
         deficiency_tier="MULTI_STRING_DEFICIENCY",
         deficiency_note="1st-string starting S Kevin Byard Limited while 3rd-string S Brenden Schooler DNP — leaves 2nd-string Jaylen Reed as sole healthy backup in S row 2."),
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="NE", opponent="DET", unit="Defense",
         pos_injury="CB", pos_depth="CB (row 2)", player="Charles Woods", player_url="https://www.nfl.com/players/charles-woods/",
         injury="", practice_status="Limited Participation in Practice", game_status="",
         player_string="2nd string",
         string_1="Marcus Jones", string_2="Charles Woods (Limited)", string_3="", string_4="",
         active_replacement="Karon Prunty (2nd string in CB row 3)",
         deficiency_tier="2ND_STRING_LIMITED",
         deficiency_note="2nd-string CB behind Marcus Jones Limited in the same week CB1 Carlton Davis III is Out — compounds secondary thinness."),
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="NE", opponent="DET", unit="Offense",
         pos_injury="C", pos_depth="LG (1st) / C (2nd)", player="Ben Brown", player_url="https://www.nfl.com/players/ben-brown-2/",
         injury="Knee", practice_status="Did Not Participate In Practice", game_status="Out",
         player_string="1st string LG / 2nd string C",
         string_1="Ben Brown (Out at LG; Jared Wilson 1st at C)", string_2="Walter Rouse (DNP at LG/RG)", string_3="", string_4="",
         active_replacement="Unlisted / cross-position G (Greg Van Roten also Limited)",
         deficiency_tier="STARTER_AND_2ND_DEPLETED",
         deficiency_note="1st-string LG (and 2nd-string C) Ben Brown ruled Out (Knee), AND 2nd-string LG/RG Walter Rouse DNP, AND G Greg Van Roten Limited — interior OL pushed to 3rd+ emergency combination."),
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="NE", opponent="DET", unit="Offense",
         pos_injury="RB", pos_depth="RB", player="TreVeyon Henderson", player_url="https://www.nfl.com/players/treveyon-henderson/",
         injury="Illness", practice_status="Did Not Participate In Practice", game_status="Out",
         player_string="2nd string",
         string_1="Rhamondre Stevenson (DNP)", string_2="TreVeyon Henderson (Out)", string_3="Corey Kiner", string_4="Lan Larison",
         active_replacement="Corey Kiner (3rd string) & Lan Larison (4th string)",
         deficiency_tier="3RD_4TH_STRING_EXPOSED",
         deficiency_note="2nd-string RB TreVeyon Henderson ruled Out (Illness) AND 1st-string RB Rhamondre Stevenson DNP — directly exposes 3rd-string Corey Kiner and 4th-string Lan Larison."),
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="NE", opponent="DET", unit="Offense",
         pos_injury="WR", pos_depth="WR (row 1)", player="A.J. Brown", player_url="https://www.nfl.com/players/a-j-brown/",
         injury="", practice_status="Limited Participation in Practice", game_status="",
         player_string="1st string (starter)",
         string_1="A.J. Brown (Limited)", string_2="Efton Chism III", string_3="", string_4="",
         active_replacement="Efton Chism III (2nd string) / Kyle Williams",
         deficiency_tier="STARTER_LIMITED_2ND_READY",
         deficiency_note="1st-string X-WR Limited; 2nd-string Efton Chism III is also listed as 1st-string WR in row 3, so absence pulls 2nd-string Kyle Williams into 3-WR sets."),
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="NE", opponent="DET", unit="Offense",
         pos_injury="T", pos_depth="RT", player="Morgan Moses", player_url="https://www.nfl.com/players/morgan-moses/",
         injury="", practice_status="Limited Participation in Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Morgan Moses (Limited)", string_2="Caleb Lomu", string_3="", string_4="",
         active_replacement="Caleb Lomu (2nd string RT)",
         deficiency_tier="STARTER_LIMITED_2ND_READY",
         deficiency_note="1st-string RT Morgan Moses Limited while backup swing T Walter Rouse DNP; 2nd-string Caleb Lomu next up."),
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="NE", opponent="DET", unit="Offense",
         pos_injury="TE", pos_depth="TE", player="Hunter Henry", player_url="https://www.nfl.com/players/hunter-henry/",
         injury="", practice_status="Limited Participation in Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Hunter Henry (Limited)", string_2="Eli Raridon", string_3="Cameron Latu (DNP)", string_4="",
         active_replacement="Eli Raridon (2nd string TE; 3rd string Cameron Latu DNP)",
         deficiency_tier="MULTI_STRING_DEFICIENCY",
         deficiency_note="1st-string TE Hunter Henry Limited and 3rd-string TE Cameron Latu DNP — leaves 2nd-string Eli Raridon as sole healthy tight end on depth chart."),
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="DET", opponent="NE", unit="Defense",
         pos_injury="CB", pos_depth="CB (row 1)", player="D.J. Reed", player_url="https://www.nfl.com/players/d-j-reed/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter)",
         string_1="D.J. Reed (DNP)", string_2="Rock Ya-Sin", string_3="Khalil Dorsey", string_4="Nick Whiteside",
         active_replacement="Rock Ya-Sin (2nd) -> Khalil Dorsey (3rd) -> Nick Whiteside (4th)",
         deficiency_tier="STARTER_DNP_2ND_3RD_4TH_CHAIN",
         deficiency_note="1st-string starting CB D.J. Reed DNP; full 4-string Lions CB replacement chain verified (2nd Rock Ya-Sin, 3rd Khalil Dorsey, 4th Nick Whiteside)."),
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="DET", opponent="NE", unit="Defense",
         pos_injury="S", pos_depth="S (row 2)", player="Brian Branch", player_url="https://www.nfl.com/players/brian-branch/",
         injury="", practice_status="Limited Participation in Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Brian Branch (Limited)", string_2="Christian Izien", string_3="", string_4="",
         active_replacement="Christian Izien (2nd string S)",
         deficiency_tier="MULTI_STRING_DEFICIENCY",
         deficiency_note="1st-string S Brian Branch Limited AND safety Kerby Joseph also Limited (unlisted on Lions Nov 2026 unofficial depth chart; S row 1 Chuck Clark has no backup listed)."),
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="DET", opponent="NE", unit="Offense",
         pos_injury="C", pos_depth="C", player="Cade Mays", player_url="https://www.nfl.com/players/cade-mays/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Cade Mays (DNP)", string_2="Juice Scruggs", string_3="", string_4="",
         active_replacement="Juice Scruggs (2nd string C)",
         deficiency_tier="STARTER_DNP_2ND_STRING",
         deficiency_note="1st-string starting C Cade Mays DNP; 2nd-string Juice Scruggs is direct replacement with no 3rd string listed at C."),
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="DET", opponent="NE", unit="Offense",
         pos_injury="RB", pos_depth="RB", player="Sione Vaki", player_url="https://www.nfl.com/players/sione-vaki/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="2nd string",
         string_1="Jahmyr Gibbs", string_2="Sione Vaki (DNP)", string_3="Jacob Saylors (Full)", string_4="",
         active_replacement="Jacob Saylors (3rd string RB elevated to RB2)",
         deficiency_tier="3RD_STRING_ELEVATED",
         deficiency_note="2nd-string RB Sione Vaki DNP; 3rd-string Jacob Saylors (Full Participation) moves into primary backup RB role behind 1st-string Jahmyr Gibbs."),
    dict(matchup="NE vs DET", kickoff="2026-11-15 09:30 EST", club="DET", opponent="NE", unit="Offense",
         pos_injury="QB", pos_depth="QB", player="Jared Goff", player_url="https://www.nfl.com/players/jared-goff/",
         injury="", practice_status="Limited Participation in Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Jared Goff (Limited)", string_2="Joshua Dobbs", string_3="", string_4="",
         active_replacement="Joshua Dobbs (2nd string QB)",
         deficiency_tier="STARTER_LIMITED_2ND_READY",
         deficiency_note="1st-string QB Jared Goff Limited in practice (alongside 1st-string WR Amon-Ra St. Brown Limited -> 2nd DeAndre Carter); 2nd-string QB is Joshua Dobbs."),

    # --- Matchup 3: KC @ ATL (Sun Nov 15, 2026, 1:00 PM EST) ---
    dict(matchup="KC @ ATL", kickoff="2026-11-15 13:00 EST", club="KC", opponent="ATL", unit="Offense",
         pos_injury="T", pos_depth="RT", player="Jaylon Moore", player_url="https://www.nfl.com/players/jaylon-moore-2/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Jaylon Moore (DNP)", string_2="Joshua Ezeudu", string_3="", string_4="",
         active_replacement="Joshua Ezeudu (2nd string RT & 2nd string LG)",
         deficiency_tier="STARTER_DNP_2ND_STRING",
         deficiency_note="1st-string starting RT Jaylon Moore DNP; 2nd-string Joshua Ezeudu is listed as backup at BOTH RT and LG, thinning cross-line protection."),
    dict(matchup="KC @ ATL", kickoff="2026-11-15 13:00 EST", club="KC", opponent="ATL", unit="Defense",
         pos_injury="DT", pos_depth="DT (row 1)", player="Peter Woods", player_url="https://www.nfl.com/players/peter-woods/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="2nd string",
         string_1="Chris Jones", string_2="Peter Woods (DNP)", string_3="Omarr Norman-Lott (Limited, unlisted)", string_4="",
         active_replacement="Bryson Eason (2nd string in DT row 2) / Omarr Norman-Lott (Limited)",
         deficiency_tier="MULTI_STRING_DEFICIENCY",
         deficiency_note="2nd-string DT Peter Woods behind Chris Jones DNP, while rotational DT Omarr Norman-Lott is also Limited — interior pass-rush rotation behind Chris Jones depleted."),
    dict(matchup="KC @ ATL", kickoff="2026-11-15 13:00 EST", club="KC", opponent="ATL", unit="Offense",
         pos_injury="QB", pos_depth="QB", player="Patrick Mahomes", player_url="https://www.nfl.com/players/patrick-mahomes/",
         injury="", practice_status="Full Participation in Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Patrick Mahomes (Full)", string_2="Justin Fields (Full)", string_3="Garrett Nussmeier", string_4="",
         active_replacement="Starter full participant",
         deficiency_tier="STARTER_FULL",
         deficiency_note="1st-string QB Patrick Mahomes, 2nd-string QB Justin Fields, 1st-string TE Travis Kelce, 1st-string WRs Rashee Rice & Xavier Worthy, and 1st-string CB Mansoor Delane all practiced Full."),
    dict(matchup="KC @ ATL", kickoff="2026-11-15 13:00 EST", club="ATL", opponent="KC", unit="Defense",
         pos_injury="LB", pos_depth="ILB (row 1)", player="Divine Deablo", player_url="https://www.nfl.com/players/divine-deablo/",
         injury="", practice_status="Limited Participation in Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Divine Deablo (Limited)", string_2="Christian Harris", string_3="Josh Woods (DNP)", string_4="",
         active_replacement="Christian Harris (2nd string ILB; 3rd string Josh Woods DNP)",
         deficiency_tier="MULTI_STRING_DEFICIENCY",
         deficiency_note="1st-string ILB Divine Deablo Limited while 3rd-string ILB Josh Woods DNP — leaves 2nd-string Christian Harris without healthy 3rd-string cover."),
    dict(matchup="KC @ ATL", kickoff="2026-11-15 13:00 EST", club="ATL", opponent="KC", unit="Defense",
         pos_injury="DE", pos_depth="DE (row 1 & row 2)", player="Za'Darius Smith", player_url="https://www.nfl.com/players/za-darius-smith/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="2nd string",
         string_1="Cameron Thomas (DE1) / Brandon Dorlus (DE2)", string_2="Za'Darius Smith (DNP) / Yasir Abdullah", string_3="Charles Snowden / James Pearce Jr. (DNP)", string_4="",
         active_replacement="Charles Snowden (3rd string DE1) & Yasir Abdullah (2nd string DE2)",
         deficiency_tier="3RD_STRING_ELEVATED",
         deficiency_note="2nd-string DE Za'Darius Smith DNP AND 3rd-string DE James Pearce Jr. (row 2) DNP, plus 2nd-string DL Gervon Dexter Sr. DNP — three defensive-front rotational backups missed practice against Mahomes."),
    dict(matchup="KC @ ATL", kickoff="2026-11-15 13:00 EST", club="ATL", opponent="KC", unit="Offense",
         pos_injury="WR", pos_depth="WR (row 2) / PR (1st)", player="Zachariah Branch", player_url="https://www.nfl.com/players/zachariah-branch/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="2nd string WR / 1st string PR",
         string_1="Olamide Zaccheaus (WR; 2nd PR)", string_2="Zachariah Branch (DNP)", string_3="Jahan Dotson (3rd PR)", string_4="",
         active_replacement="Olamide Zaccheaus (moves to 1st PR) / Beaux Collins (WR depth)",
         deficiency_tier="2ND_STRING_DNP",
         deficiency_note="2nd-string slot WR and 1st-string Punt Returner Zachariah Branch DNP; Olamide Zaccheaus absorbs punt-return role."),

    # --- Matchup 4: MIN @ GB (Sun Nov 15, 2026, 1:00 PM EST) ---
    dict(matchup="MIN @ GB", kickoff="2026-11-15 13:00 EST", club="MIN", opponent="GB", unit="Offense",
         pos_injury="QB", pos_depth="QB", player="Kyler Murray", player_url="https://www.nfl.com/players/kyler-murray/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Kyler Murray (DNP)", string_2="Carson Wentz (Limited)", string_3="Max Brosmer", string_4="",
         active_replacement="Carson Wentz (2nd, Limited) / Max Brosmer (3rd) / Kirk Cousins (unlisted trade acquisition)",
         deficiency_tier="3RD_4TH_STRING_EXPOSED",
         deficiency_note="1st-string QB Kyler Murray DNP and 2nd-string QB Carson Wentz Limited, exposing 3rd-string Max Brosmer; NFL.com also reports newly acquired Kirk Cousins is not yet committed to start and is omitted from Vikings.com unofficial depth chart."),
    dict(matchup="MIN @ GB", kickoff="2026-11-15 13:00 EST", club="MIN", opponent="GB", unit="Offense",
         pos_injury="TE", pos_depth="TE", player="T.J. Hockenson", player_url="https://www.nfl.com/players/t-j-hockenson/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter)",
         string_1="T.J. Hockenson (DNP)", string_2="Gavin Bartholomew", string_3="", string_4="",
         active_replacement="Gavin Bartholomew (2nd string TE)",
         deficiency_tier="STARTER_DNP_2ND_STRING",
         deficiency_note="1st-string starting TE T.J. Hockenson DNP; 2nd-string Gavin Bartholomew is sole remaining TE listed on Vikings depth chart."),
    dict(matchup="MIN @ GB", kickoff="2026-11-15 13:00 EST", club="MIN", opponent="GB", unit="Offense",
         pos_injury="WR", pos_depth="WR (row 3)", player="Jauan Jennings", player_url="https://www.nfl.com/players/jauan-jennings/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter, WR3 slot)",
         string_1="Jauan Jennings (DNP)", string_2="Myles Price", string_3="", string_4="",
         active_replacement="Myles Price (2nd string WR) / Tai Felton",
         deficiency_tier="STARTER_DNP_2ND_STRING",
         deficiency_note="Starting WR Jauan Jennings DNP alongside TE1 T.J. Hockenson and QB1 Kyler Murray; 2nd-string Myles Price steps into 11-personnel WR role."),
    dict(matchup="MIN @ GB", kickoff="2026-11-15 13:00 EST", club="MIN", opponent="GB", unit="Defense",
         pos_injury="LB", pos_depth="LB (row 1)", player="Blake Cashman", player_url="https://www.nfl.com/players/blake-cashman/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Blake Cashman (DNP)", string_2="Ivan Pace Jr.", string_3="", string_4="",
         active_replacement="Ivan Pace Jr. (2nd string LB)",
         deficiency_tier="STARTER_DNP_2ND_STRING",
         deficiency_note="1st-string starting off-ball LB Blake Cashman DNP; 2nd-string Ivan Pace Jr. replaces him with no 3rd string listed in LB row 1."),
    dict(matchup="MIN @ GB", kickoff="2026-11-15 13:00 EST", club="MIN", opponent="GB", unit="Defense",
         pos_injury="DT", pos_depth="DL (row 3)", player="Tyrion Ingram-Dawkins", player_url="https://www.nfl.com/players/tyrion-ingram-dawkins/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Tyrion Ingram-Dawkins (DNP)", string_2="Elijah Williams", string_3="", string_4="",
         active_replacement="Elijah Williams (2nd string DL)",
         deficiency_tier="STARTER_DNP_2ND_STRING",
         deficiency_note="1st-string DL Tyrion Ingram-Dawkins DNP; 2nd-string Elijah Williams is direct replacement."),
    dict(matchup="MIN @ GB", kickoff="2026-11-15 13:00 EST", club="MIN", opponent="GB", unit="Defense",
         pos_injury="LB", pos_depth="OLB (row 1)", player="Kyle Van Noy", player_url="https://www.nfl.com/players/kyle-van-noy/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="2nd string",
         string_1="Dallas Turner", string_2="Kyle Van Noy (DNP)", string_3="Chaz Chambliss", string_4="",
         active_replacement="Chaz Chambliss (3rd string OLB elevated to OLB2)",
         deficiency_tier="3RD_STRING_ELEVATED",
         deficiency_note="2nd-string OLB Kyle Van Noy DNP behind Dallas Turner, elevating 3rd-string Chaz Chambliss to primary edge rotation; S2 Jay Ward also Limited (-> 3rd Jakobe Thomas)."),
    dict(matchup="MIN @ GB", kickoff="2026-11-15 13:00 EST", club="GB", opponent="MIN", unit="Offense",
         pos_injury="RB", pos_depth="RB", player="Josh Jacobs", player_url="https://www.nfl.com/players/josh-jacobs-x3315/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Josh Jacobs (DNP)", string_2="MarShawn Lloyd", string_3="Pierre Strong Jr.", string_4="Kaleb Johnson",
         active_replacement="MarShawn Lloyd (2nd) -> Pierre Strong Jr. (3rd) -> Kaleb Johnson (4th)",
         deficiency_tier="STARTER_DNP_2ND_3RD_4TH_CHAIN",
         deficiency_note="1st-string RB Josh Jacobs DNP (and unlisted RB Chris Brooks Limited); full 4-string RB chain verified on Packers Nov 10 depth chart (2nd MarShawn Lloyd, 3rd Pierre Strong Jr., 4th Kaleb Johnson)."),
    dict(matchup="MIN @ GB", kickoff="2026-11-15 13:00 EST", club="GB", opponent="MIN", unit="Offense",
         pos_injury="C", pos_depth="C & LG", player="Sean Rhyan", player_url="https://www.nfl.com/players/sean-rhyan/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Sean Rhyan (DNP at C); Aaron Banks (Limited at LG)", string_2="Jager Burton (2nd C); Travis Glover (Limited, 2nd LG)", string_3="Donovan Jennings (3rd LG)", string_4="",
         active_replacement="Jager Burton (2nd C) & Donovan Jennings (3rd LG behind two Limited LGs)",
         deficiency_tier="MULTI_STRING_DEFICIENCY",
         deficiency_note="1st-string C Sean Rhyan DNP (-> 2nd Jager Burton), while 1st-string LG Aaron Banks AND 2nd-string LG Travis Glover are both Limited (-> 3rd Donovan Jennings) and 2nd-string RG Kevin Zeitler is Limited."),
    dict(matchup="MIN @ GB", kickoff="2026-11-15 13:00 EST", club="GB", opponent="MIN", unit="Offense",
         pos_injury="TE", pos_depth="TE", player="Josh Whyle", player_url="https://www.nfl.com/players/josh-whyle/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="4th string",
         string_1="Tucker Kraft", string_2="Jonnu Smith", string_3="Mark Redman", string_4="Josh Whyle (DNP)",
         active_replacement="1st Tucker Kraft, 2nd Jonnu Smith, 3rd Mark Redman all active ahead",
         deficiency_tier="4TH_STRING_DNP",
         deficiency_note="4th-string TE Josh Whyle DNP; verified 1st–4th TE ladder shows top three TEs unaffected."),
    dict(matchup="MIN @ GB", kickoff="2026-11-15 13:00 EST", club="GB", opponent="MIN", unit="Defense",
         pos_injury="LB", pos_depth="LB (row 1)", player="Zaire Franklin", player_url="https://www.nfl.com/players/zaire-franklin/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Zaire Franklin (DNP)", string_2="Ty'Ron Hopper (Limited)", string_3="Kristian Welch", string_4="",
         active_replacement="Ty'Ron Hopper (2nd, Limited) -> Kristian Welch (3rd string LB)",
         deficiency_tier="3RD_4TH_STRING_EXPOSED",
         deficiency_note="1st-string LB Zaire Franklin DNP AND 2nd-string LB Ty'Ron Hopper Limited — directly exposes 3rd-string LB Kristian Welch (plus LB Micah Parsons Limited on NFL.com but omitted from Packers Nov 10 unofficial depth chart)."),
    dict(matchup="MIN @ GB", kickoff="2026-11-15 13:00 EST", club="GB", opponent="MIN", unit="Defense",
         pos_injury="LB", pos_depth="EDGE (row 1)", player="Lukas Van Ness", player_url="https://www.nfl.com/players/lukas-van-ness/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Lukas Van Ness (DNP)", string_2="Brenton Cox Jr", string_3="", string_4="",
         active_replacement="Brenton Cox Jr (2nd string EDGE)",
         deficiency_tier="STARTER_DNP_2ND_STRING",
         deficiency_note="1st-string starting EDGE Lukas Van Ness DNP; 2nd-string Brenton Cox Jr replaces him with no 3rd string listed in EDGE row 1."),
    dict(matchup="MIN @ GB", kickoff="2026-11-15 13:00 EST", club="GB", opponent="MIN", unit="Defense",
         pos_injury="S", pos_depth="NB (Nickel DB)", player="Javon Bullard", player_url="https://www.nfl.com/players/javon-bullard/",
         injury="", practice_status="Did Not Participate In Practice", game_status="",
         player_string="1st string (starter)",
         string_1="Javon Bullard (DNP)", string_2="Kamal Hadden", string_3="", string_4="",
         active_replacement="Kamal Hadden (2nd string Nickel DB)",
         deficiency_tier="STARTER_DNP_2ND_STRING",
         deficiency_note="1st-string starting Nickel DB Javon Bullard DNP; 2nd-string Kamal Hadden replaces him in slot coverage."),
]


def build_week10_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for i, item in enumerate(WEEK10_ENTRIES, 1):
        club = item["club"]
        depth_url, depth_disclaimer = CLUB_DEPTH_URLS[club]
        rows.append({
            "entry_id": f"LD-{i:02d}",
            "verified_date": VERIFIED_DATE,
            **item,
            "official_injury_url": URL_NFL_INJURIES,
            "club_depth_url": depth_url,
            "club_depth_disclaimer": depth_disclaimer,
        })
    df = pd.DataFrame(rows)

    matchup_rows = [
        dict(
            matchup="WAS @ NYG",
            kickoff="2026-11-12 20:15 EST",
            away_offense_state="QB1 Jayden Daniels Full; TE2 Colson Yankoff Out; WR2 Treylon Burks DNP; C Lucas Patrick Out (unlisted on 2-deep)",
            home_defense_state="All 1st-string NYG defenders off report or Full (SAM1 Abdul Carter Full; CB2 Colton Hood Full); rotational LB Malik Harrison Questionable",
            home_offense_state="QB1 J.J. McCarthy, LT1 Andrew Thomas, RT1 Jermaine Eluemunor, WR1 Malik Nabers, WR1 Darnell Mooney, RB1 Cam Skattebo all Full",
            away_defense_state="CB1 Amik Robertson Limited (-> 2nd Rasul Douglas); DL2 Shy Tuttle Full",
            net_lineup_flags="WAS secondary CB1 Limited & reserve TE2/C Out vs near-full-strength NYG starters",
            official_source=URL_NFL_INJURIES,
        ),
        dict(
            matchup="NE vs DET",
            kickoff="2026-11-15 09:30 EST",
            away_offense_state="SEVERE: LG1 Ben Brown Out + LG2 Walter Rouse DNP (3rd+ OL); RB1 Stevenson DNP + RB2 Henderson Out (-> 3rd Corey Kiner & 4th Lan Larison); WR1 A.J. Brown, RT1 Moses, TE1 Henry Limited + TE3 Latu DNP; QB1 Drake Maye Full",
            home_defense_state="CB1 D.J. Reed DNP (-> 2nd Rock Ya-Sin / 3rd Khalil Dorsey / 4th Nick Whiteside); S1 Brian Branch & S Kerby Joseph Limited",
            home_offense_state="C1 Cade Mays DNP (-> 2nd Juice Scruggs); RB2 Sione Vaki DNP (-> 3rd Jacob Saylors behind RB1 Gibbs); QB1 Goff & WR1 St. Brown Limited",
            away_defense_state="SEVERE: CB1 Carlton Davis III Out (-> 2nd Channing Canada) + CB2 Charles Woods Limited; S1 Kevin Byard Limited + S3 Brenden Schooler DNP",
            net_lineup_flags="Both secondaries compromised (NE CB1 Out, DET CB1 DNP); NE offense faces compounded RB3/RB4 and LG3+ depth depletion",
            official_source=URL_NFL_INJURIES,
        ),
        dict(
            matchup="KC @ ATL",
            kickoff="2026-11-15 13:00 EST",
            away_offense_state="RT1 Jaylon Moore DNP (-> 2nd Joshua Ezeudu, dual LG2/RT2 backup); QB1 Mahomes, TE1 Kelce, WR1 Rice, WR1 Worthy all Full",
            home_defense_state="PASS-RUSH & LB DEPTH DEPLETED: ILB1 Divine Deablo Limited + ILB3 Josh Woods DNP (-> 2nd Christian Harris); DE2 Za'Darius Smith DNP (-> 3rd Charles Snowden); DE3 James Pearce Jr. DNP; DL2 Gervon Dexter Sr. DNP",
            home_offense_state="WR2 / PR1 Zachariah Branch DNP; QB1 Michael Penix Jr., RB1 Bijan Robinson, WR1 Drake London, TE1 Kyle Pitts off injury report",
            away_defense_state="DT2 Peter Woods DNP + DT Omarr Norman-Lott Limited behind DT1 Chris Jones; CB1 Mansoor Delane, LB2 Jeffrey Bassa, S2 Jaden Hicks Full",
            net_lineup_flags="KC skill starters Full (only RT1 DNP) against ATL defense missing 4 front-seven rotational/starter pieces in practice",
            official_source=URL_NFL_INJURIES,
        ),
        dict(
            matchup="MIN @ GB",
            kickoff="2026-11-15 13:00 EST",
            away_offense_state="CRITICAL: QB1 Kyler Murray DNP + QB2 Carson Wentz Limited (-> 3rd Max Brosmer / uncommitted Kirk Cousins); TE1 T.J. Hockenson DNP (-> 2nd Gavin Bartholomew); WR Jauan Jennings DNP (-> 2nd Myles Price)",
            home_defense_state="SEVERE: LB1 Zaire Franklin DNP + LB2 Ty'Ron Hopper Limited (-> 3rd Kristian Welch) + LB Micah Parsons Limited; EDGE1 Lukas Van Ness DNP (-> 2nd Brenton Cox Jr); NB1 Javon Bullard DNP (-> 2nd Kamal Hadden)",
            home_offense_state="RB1 Josh Jacobs DNP (-> 2nd MarShawn Lloyd / 3rd Pierre Strong Jr. / 4th Kaleb Johnson); C1 Sean Rhyan DNP (-> 2nd Jager Burton); LG1 Banks & LG2 Glover Limited (-> 3rd Donovan Jennings); TE4 Josh Whyle DNP",
            away_defense_state="LB1 Blake Cashman DNP (-> 2nd Ivan Pace Jr.); DL1 Tyrion Ingram-Dawkins DNP (-> 2nd Elijah Williams); OLB2 Kyle Van Noy DNP (-> 3rd Chaz Chambliss); S2 Jay Ward Limited",
            net_lineup_flags="Highest two-sided starter attrition on Week 10 slate: MIN QB1/QB2/TE1/WR/LB1/DL1 vs GB RB1/C1/LG1-2/LB1-2/EDGE1/NB1",
            official_source=URL_NFL_INJURIES,
        ),
    ]
    return df, pd.DataFrame(matchup_rows)


def compute_pbp_backup_impact(pg: pd.DataFrame, lines: pd.DataFrame, *, min_team_games: int = 3) -> pd.DataFrame:
    """Strictly prefix-safe (no-lookahead) classification of 1st vs 2nd vs 3rd/4th-string games.

    For each (season, team) ordered strictly by `(game_date, game_id)`, players seen in strictly
    earlier games of that season (`game_date < current_date`) are ranked by cumulative prior usage:
      - QB role: `pass_att` (min 5 cumulative prior attempts)
      - RB role: `rush_att` (min 8 cumulative prior rushes)
      - WR/TE primary receiver role: `targets` (min 8 cumulative prior targets)

    Then in the current game `g`, BEFORE updating cumulative histories:
      - `1ST_STRING_ACTIVE`: pregame rank-1 starter records >0 usage in `g`
      - `2ND_STRING_REPLACES_1ST`: pregame rank-1 starter is absent (0 usage), pregame rank-2 active
      - `3RD_4TH_STRING_OR_EMERGENCY`: both pregame rank-1 and rank-2 are absent, forcing 3rd/4th+ string
    """
    pg = pg.copy()
    pg["game_date_str"] = pg["game_date"].astype(str).str.slice(0, 10)
    team_games = (
        pg[["season", "week", "game_date_str", "game_id", "team"]]
        .drop_duplicates()
        .sort_values(["season", "game_date_str", "game_id", "team"])
        .reset_index(drop=True)
    )
    by_gt = {
        (r_gid, r_team): sub
        for (r_gid, r_team), sub in pg.groupby(["game_id", "team"], sort=False)
    }

    specs = [
        ("QB", "pass_att", 5.0),
        ("RB", "rush_att", 8.0),
        ("WR_TE_PRIMARY", "targets", 8.0),
    ]

    records = []
    for (season, team), sched in team_games.groupby(["season", "team"], sort=True):
        cum_usage: dict[str, dict[str, float]] = {role: {} for role, _, _ in specs}
        prior_dates: list[str] = []
        # Group by date just in case (though a team plays at most once per date)
        for row in sched.itertuples(index=False):
            g_sub = by_gt.get((row.game_id, team), pd.DataFrame())
            if len(prior_dates) >= min_team_games:
                for role, col, min_prior in specs:
                    hist = {pid: u for pid, u in cum_usage[role].items() if u >= min_prior}
                    ranked = sorted(hist.items(), key=lambda kv: (-kv[1], kv[0]))
                    if len(ranked) >= 2:
                        p1 = ranked[0][0]
                        p2 = ranked[1][0]
                        active_ids = set(g_sub.loc[g_sub[col] > 0, "player_id"]) if len(g_sub) else set()
                        if p1 in active_ids:
                            state = "1ST_STRING_ACTIVE"
                        elif p2 in active_ids:
                            state = "2ND_STRING_REPLACES_1ST"
                        else:
                            state = "3RD_4TH_STRING_OR_EMERGENCY"
                        records.append({
                            "game_id": row.game_id,
                            "season": int(season),
                            "week": int(row.week),
                            "gameday": row.game_date_str,
                            "team": team,
                            "role": role,
                            "lineup_state": state,
                            "pregame_1st_id": p1,
                            "pregame_2nd_id": p2,
                            "n_ranked_depth": len(ranked),
                        })
            # Update state AFTER emitting predictions/classifications (strictly causal)
            for r_pl in g_sub.itertuples(index=False):
                for role, col, _ in specs:
                    val = float(getattr(r_pl, col))
                    if val > 0:
                        cum_usage[role][r_pl.player_id] = cum_usage[role].get(r_pl.player_id, 0.0) + val
            prior_dates.append(row.game_date_str)

    states_df = pd.DataFrame(records)
    if states_df.empty or lines.empty:
        return states_df

    # Join pregame team scoring expectations from walk-forward originated_lines.csv
    ln = lines[["game_id", "home_team", "away_team", "home_score", "away_score",
                "pred_margin_ensemble", "pred_total_ensemble"]].copy()
    ln["exp_home_pts"] = 0.5 * (ln["pred_total_ensemble"] + ln["pred_margin_ensemble"])
    ln["exp_away_pts"] = 0.5 * (ln["pred_total_ensemble"] - ln["pred_margin_ensemble"])

    home_view = ln.rename(columns={
        "home_team": "team", "home_score": "team_pts", "away_score": "opp_pts",
        "exp_home_pts": "exp_team_pts", "exp_away_pts": "exp_opp_pts",
    })[["game_id", "team", "team_pts", "opp_pts", "exp_team_pts", "exp_opp_pts"]]
    away_view = ln.rename(columns={
        "away_team": "team", "away_score": "team_pts", "home_score": "opp_pts",
        "exp_away_pts": "exp_team_pts", "exp_home_pts": "exp_opp_pts",
    })[["game_id", "team", "team_pts", "opp_pts", "exp_team_pts", "exp_opp_pts"]]
    scores_team = pd.concat([home_view, away_view], ignore_index=True)

    merged = states_df.merge(scores_team, on=["game_id", "team"], how="inner")
    merged["pts_minus_starter_blind_model"] = merged["team_pts"] - merged["exp_team_pts"]
    merged["margin_minus_starter_blind_model"] = (
        (merged["team_pts"] - merged["opp_pts"]) - (merged["exp_team_pts"] - merged["exp_opp_pts"])
    )
    return merged


def summarize_pbp_backup_impact(merged: pd.DataFrame) -> pd.DataFrame:
    order = ["1ST_STRING_ACTIVE", "2ND_STRING_REPLACES_1ST", "3RD_4TH_STRING_OR_EMERGENCY"]
    rows = []
    for role in ["QB", "RB", "WR_TE_PRIMARY"]:
        sub_r = merged[merged.role == role]
        for st_name in order:
            g = sub_r[sub_r.lineup_state == st_name]
            rows.append({
                "role": role,
                "lineup_state": st_name,
                "n_team_games": int(len(g)),
                "mean_team_pts": float(g["team_pts"].mean()) if len(g) else np.nan,
                "mean_opp_pts": float(g["opp_pts"].mean()) if len(g) else np.nan,
                "mean_pts_vs_starter_blind_model": float(g["pts_minus_starter_blind_model"].mean()) if len(g) else np.nan,
                "mean_margin_vs_starter_blind_model": float(g["margin_minus_starter_blind_model"].mean()) if len(g) else np.nan,
                "evidence_status": "UNVERIFIED — community play-by-play proxy; official 90-minute inactive/snap census absent",
                "official_context_url": URL_NFL_INJURIES,
            })
    return pd.DataFrame(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wk10_df, matchups_df = build_week10_tables()
    wk10_df.to_csv(OUT_DIR / "week10_2026_injuries_depth.csv", index=False)
    matchups_df.to_csv(OUT_DIR / "week10_2026_matchup_deficiencies.csv", index=False)

    pg_path = PROC / "prop_player_games.csv"
    ln_path = PROC / "originated_lines.csv"
    if pg_path.exists() and ln_path.exists():
        pg = pd.read_csv(pg_path)
        ln = pd.read_csv(ln_path)
        game_level = compute_pbp_backup_impact(pg, ln)
        summary = summarize_pbp_backup_impact(game_level)
        summary.to_csv(OUT_DIR / "pbp_backup_impact.csv", index=False)
    else:
        summary = pd.DataFrame()

    write_json(OUT_DIR / "sources_lineups.json", {
        "verified_date_utc": VERIFIED_DATE,
        "week_audited": "2026 Regular Season Week 10",
        "clubs_audited": list(CLUB_DEPTH_URLS.keys()),
        "entries_count": int(len(wk10_df)),
        "offense_entries": int((wk10_df.unit == "Offense").sum()),
        "defense_entries": int((wk10_df.unit == "Defense").sum()),
        "official_sources": {
            "nfl_injuries": URL_NFL_INJURIES,
            "nfl_inactives_checked_blank": URL_NFL_INACTIVES,
            "nfl_game_prep_90min_rule": URL_NFL_GAME_PREP,
            "nfl_player_health_safety": URL_NFL_HEALTH,
            "nfl_vikings_qb_news": URL_NFL_VIKINGS_QB,
            "club_depth_charts": {k: {"url": v[0], "disclaimer": v[1]} for k, v in CLUB_DEPTH_URLS.items()},
        },
        "pbp_research_note": (
            "pbp_backup_impact.csv is derived walk-forward from hash-pinned community play-by-play "
            "(2019-2022) and originated_lines.csv. Public HTML tables keep community-derived numeric "
            "metrics blank and flagged UNVERIFIED."
        ),
    })
    print(f"wrote {len(wk10_df)} official Week 10 injury/depth-chart rows and {len(summary)} PBP summary rows to {OUT_DIR}")


if __name__ == "__main__":
    main()
