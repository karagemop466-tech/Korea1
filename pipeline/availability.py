"""T15 — verified availability evidence for the injury / lineup page.

Nothing in this module is inferred. Each entry records what was actually retrieved on
`RETRIEVED` with the agent's page-fetch tool, or what our own build holds. Rows that could
not be confirmed stay BLOCKED and are rendered blank.

Two captures are transcribed exactly as published:

* `SNAPSHOT_2026` — NFL.com injury report, 2026 week 10, Thursday game WAS @ NYG
  (https://www.nfl.com/injuries/league/2026/reg10). 20 rows: 2 Out, 1 Questionable.
* `SNAPSHOT_2019` — NFL.com injury report, 2019 week 5, first game LAR @ SEA
  (https://www.nfl.com/injuries/league/2019/reg5). 11 rows: 1 Out, 1 Doubtful, 2 Questionable.

Only the games named above were transcribed. The rest of each week's report was not captured,
and the page must not imply otherwise.
"""

from __future__ import annotations

RETRIEVED = "2026-11-12"
RETRIEVED_UTC = "2026-11-12T13:30Z"

URL_INJURIES = "https://www.nfl.com/injuries/"
URL_WEEK10 = "https://www.nfl.com/injuries/league/2026/reg10"
URL_WEEK10_2019 = "https://www.nfl.com/injuries/league/2019/reg5"
URL_GAME_WAS_NYG = "https://www.nfl.com/games/commanders-at-giants-2026-reg-10"
URL_SCHEDULE_W10 = "https://www.nfl.com/schedules/2026/by-week/week-10"
URL_SCORES_W8 = "https://www.nfl.com/scores/2026/week-8"
URL_ROSTER_AZ = "https://www.nfl.com/teams/arizona-cardinals/roster"
URL_ROSTER_WAS_DEPTH = "https://www.nfl.com/teams/washington-commanders/roster?tab=depth"
URL_DEPTH_404 = "https://www.nfl.com/teams/arizona-cardinals/depth-chart"
URL_RULEBOOK = "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook"
URL_WAS_DEPTH = "https://www.commanders.com/team/depth-chart"
URL_NYG_DEPTH = "https://www.giants.com/team/depth-chart"

# id, source, url, what it provides, checked, result, status, enables
SOURCE_CHECKS = [
    dict(id="AV-01", source="NFL injury report hub",
         url=URL_INJURIES,
         provides="Current-week injury report: player, position, injury, practice status, game status",
         checked=RETRIEVED,
         result="HTTP 200 · “2026 NFL Injury Report — WEEK 10”, season selector 1965–2026, week selector 1–10",
         status="VERIFIED",
         enables="The availability fields the deficit register needs, for the current week only"),
    dict(id="AV-02", source="Week-specific injury report (2026 week 10)",
         url=URL_WEEK10,
         provides="Stable URL per season and week, so a capture can be re-checked or cited",
         checked=RETRIEVED,
         result="HTTP 200 · same 14-game week; every game rendered with per-club tables",
         status="VERIFIED",
         enables="A citable, reproducible link for each weekly capture"),
    dict(id="AV-03", source="Historical injury report (2019 week 5)",
         url=URL_WEEK10_2019,
         provides="Past-season reports, page by page",
         checked=RETRIEVED,
         result="HTTP 200 · heading “Injuries — WEEK 5”; the HTML <title> wrongly says “Week 10 of the "
                "2019 Season” (same defect as 2026), so the heading and URL are authoritative",
         status="VERIFIED",
         enables="A multi-season availability study, subject to manual capture"),
    dict(id="AV-04", source="NFL Game Center (WAS at NYG, 2026 week 10)",
         url=URL_GAME_WAS_NYG,
         provides="Game-level status letters (A / Q / O as observed) and practice participation for a subset "
                  "of players per club",
         checked=RETRIEVED,
         result="HTTP 200 · lists 4 players per club, not the full report; one position and one practice "
                "status disagree with the report (see conflicts)",
         status="VERIFIED",
         enables="Cross-checking a game's availability snapshot; not a complete source"),
    dict(id="AV-05", source="Week 10 2026 schedule",
         url=URL_SCHEDULE_W10,
         provides="Fixture list, kickoff times and byes",
         checked=RETRIEVED,
         result="HTTP 200 · 14 games (Thu 1, Munich 1, Sun 1:00 seven, Sun 4:05 two, Sun 4:25 one, SNF 1, "
                "MNF 1); byes CHI, DEN, PHI, TB",
         status="VERIFIED",
         enables="Denominator for capture coverage (1 of 14 games transcribed)"),
    dict(id="AV-06", source="2026 week 8 scores",
         url=URL_SCORES_W8,
         provides="Official final scores",
         checked=RETRIEVED,
         result="HTTP 200 · e.g. Panthers 19–27 Packers, Cardinals 33–30 Cowboys. The variant "
                "/scores/2026/REG8 returned HTTP 502 before redirecting on retry as /scores/2026/week-8",
         status="VERIFIED",
         enables="Proving that board rows for week 8 are already settled"),
    dict(id="AV-07", source="Team roster (Arizona Cardinals)",
         url=URL_ROSTER_AZ,
         provides="Player, jersey, position, roster status (ACT / RES / DEV), height, weight, experience",
         checked=RETRIEVED,
         result="HTTP 200 · alphabetical roster; no depth rank in the table",
         status="VERIFIED · NOT A DEPTH CHART",
         enables="Roster membership and position; explicitly not starter/backup ordering"),
    dict(id="AV-08", source="Roster with depth tab (Washington Commanders, ?tab=depth)",
         url=URL_ROSTER_WAS_DEPTH,
         provides="Test of whether a depth view is served by a query parameter",
         checked=RETRIEVED,
         result="HTTP 200 · identical alphabetical roster table; no depth ordering in the payload",
         status="VERIFIED · NEGATIVE",
         enables="Rules out the tab-parameter route as a depth-chart source"),
    dict(id="AV-09", source="Team depth-chart path (Arizona Cardinals)",
         url=URL_DEPTH_404,
         provides="Test of the conventional depth-chart URL under nfl.com/teams",
         checked=RETRIEVED,
         result="HTTP 404 · “Flag on the Play” error page. Club sites publish charts (AV-11, AV-12); the league site does not",
         status="VERIFIED · NEGATIVE",
         enables="Establishes that the league site has no depth-chart page; the club route is the one that works"),
    dict(id="AV-10", source="2026 NFL rulebook",
         url=URL_RULEBOOK,
         provides="Rule text, including Rule 5 (players, substitutes and withdrawn players) and injury "
                  "timeouts",
         checked=RETRIEVED,
         result="HTTP 200 · rulebook with 2026 rule changes and a downloadable PDF",
         status="VERIFIED",
         enables="The rule basis for substitution and participation, not a depth ordering"),
    dict(id="AV-11", source="Club depth chart (Washington Commanders)",
         url=URL_WAS_DEPTH,
         provides="Ordered cells per position: offence, defence and special teams",
         checked=RETRIEVED,
         result="HTTP 200 · tables present with published order, e.g. QB Jayden Daniels | Marcus Mariota | "
                "Athan Kaliakmanis and C Nick Allegretti | Matt Gulbin. No publication timestamp is shown",
         status="VERIFIED",
         enables="Starter/backup ordering for this club; not a confirmed game-day lineup"),
    dict(id="AV-12", source="Club depth chart (New York Giants)",
         url=URL_NYG_DEPTH,
         provides="Ordered cells per position: offence, defence and special teams",
         checked=RETRIEVED,
         result="HTTP 200 · tables present with published order, e.g. QB J.J. McCarthy | Jameis Winston and "
                "C Bryan Hudson | John Michael Schmitz Jr. No publication timestamp is shown",
         status="VERIFIED",
         enables="Starter/backup ordering for this club; not a confirmed game-day lineup"),
]

SNAPSHOT_2026 = [
    # player, club, position, injury, practice status, game status
    ("John Bates", "WAS", "TE", "", "Full Participation in Practice", ""),
    ("Treylon Burks", "WAS", "WR", "", "Did Not Participate In Practice", ""),
    ("Jayden Daniels", "WAS", "QB", "", "Full Participation in Practice", ""),
    ("Matt Gulbin", "WAS", "C", "", "Full Participation in Practice", ""),
    ("Chig Okonkwo", "WAS", "TE", "", "Full Participation in Practice", ""),
    ("Lucas Patrick", "WAS", "C", "Concussion", "Did Not Participate In Practice", "Out"),
    ("Amik Robertson", "WAS", "CB", "", "Limited Participation in Practice", ""),
    ("Shy Tuttle", "WAS", "DT", "", "Full Participation in Practice", ""),
    ("Colson Yankoff", "WAS", "TE", "Knee", "Did Not Participate In Practice", "Out"),
    ("Abdul Carter", "NYG", "LB", "", "Full Participation in Practice", ""),
    ("Jermaine Eluemunor", "NYG", "T", "", "Full Participation in Practice", ""),
    ("Malik Harrison", "NYG", "LB", "Groin", "Limited Participation in Practice", "Questionable"),
    ("Colton Hood", "NYG", "CB", "", "Full Participation in Practice", ""),
    ("Theo Johnson", "NYG", "TE", "", "Full Participation in Practice", ""),
    ("Charlie Jones", "NYG", "WR", "", "Full Participation in Practice", ""),
    ("J.J. McCarthy", "NYG", "QB", "", "Full Participation in Practice", ""),
    ("Darnell Mooney", "NYG", "WR", "", "Full Participation in Practice", ""),
    ("Malik Nabers", "NYG", "WR", "", "Full Participation in Practice", ""),
    ("Cam Skattebo", "NYG", "RB", "", "Full Participation in Practice", ""),
    ("Andrew Thomas", "NYG", "T", "", "Full Participation in Practice", ""),
]

SNAPSHOT_2019 = [
    ("Bryce Hager", "LAR", "LB", "Shoulder", "Did Not Participate In Practice", "Out"),
    ("Marcus Peters", "LAR", "CB", "", "Full Participation in Practice", ""),
    ("Taylor Rapp", "LAR", "S", "Ankle", "Did Not Participate In Practice", "Doubtful"),
    ("Andrew Whitworth", "LAR", "T", "", "Full Participation in Practice", ""),
    ("Ezekiel Ansah", "SEA", "DE", "", "Full Participation in Practice", ""),
    ("Duane Brown", "SEA", "T", "Biceps", "Full Participation in Practice", "Questionable"),
    ("Mike Iupati", "SEA", "G", "", "Full Participation in Practice", ""),
    ("Quinton Jefferson", "SEA", "DT", "", "Full Participation in Practice", ""),
    ("Rashaad Penny", "SEA", "RB", "", "Full Participation in Practice", ""),
    ("Ethan Pocic", "SEA", "C", "Back", "Full Participation in Practice", "Questionable"),
    ("Neiko Thorpe", "SEA", "CB", "", "Full Participation in Practice", ""),
]

CONFLICTS = [
    dict(id="AV-C1", item="Lucas Patrick — listed position",
         report="C (injury report)", other="OL (Game Center); C (team roster)",
         disposition="Published as C. Game Center uses a generic offensive-line label; no downgrade of "
                     "the row and no inference about which linemate would replace him.",
         ref_url=URL_WEEK10, other_url=URL_GAME_WAS_NYG),
    dict(id="AV-C2", item="Malik Harrison — practice participation",
         report="Limited Participation in Practice",
         other="“Did participate” (Game Center)",
         disposition="Published as Limited. The report table is the specific source; the discrepancy is "
                     "recorded rather than reconciled by guesswork.",
         ref_url=URL_WEEK10, other_url=URL_GAME_WAS_NYG),
    dict(id="AV-C3", item="HTML page title vs heading (2019 and 2026)",
         report="Heading: “Injuries — WEEK 5” (2019) / “WEEK 10” (2026)",
         other="Page <title>: “Week 10 of the 2019 Season” on both pages",
         disposition="Heading and URL treated as authoritative; the title is a template defect. This is "
                     "why no capture keys off the page title.",
         ref_url=URL_WEEK10_2019, other_url=URL_WEEK10),
    dict(id="AV-C4", item="Game Center coverage vs full report",
         report="20 rows for the Thursday game (9 WAS, 11 NYG)",
         other="Game Center shows 4 players per club",
         disposition="Report used for the capture; Game Center used only as a cross-check. Neither is a "
                     "complete injury census: clubs list only players with a report entry.",
         ref_url=URL_WEEK10, other_url=URL_GAME_WAS_NYG),
    dict(id="AV-C5", item="“Depth chart order” in roster metadata",
         report="Search metadata describes the roster as including “depth chart order”",
         other="Rendered roster is alphabetical; ?tab=depth serves the same table",
         disposition="Metadata is boilerplate, not evidence. No depth ordering is claimed.",
         ref_url=URL_ROSTER_AZ, other_url=URL_ROSTER_WAS_DEPTH),
]

# id, signal, definition, required inputs, available today, status, leak risk, gate
SIGNALS = [
    dict(id="AV-S1", signal="QB1 unavailable",
         definition="The club's first-string quarterback is listed Out or Doubtful before kickoff.",
         inputs="Depth rank for QB at the capture time + official game status",
         available="Report yes; club chart for 2 of 32 clubs", status="PILOT ONLY",
         leak="High if the depth rank is taken from post-game participation",
         gate="G1 data + timestamp rule + all eight gates"),
    dict(id="AV-S2", signal="Starting interior line out",
         definition="A first-string C or G is listed Out, changing protection and run scheme.",
         inputs="Depth rank for C/G + official game status",
         available="Report yes; club chart for 2 of 32 clubs", status="PILOT ONLY",
         leak="High: line combinations are often only public after the game",
         gate="G1 data + timestamp rule + all eight gates"),
    dict(id="AV-S3", signal="Starting corner out",
         definition="A first-string CB is Out or Doubtful, shifting coverage assignments.",
         inputs="Depth rank for CB + official game status",
         available="Report yes; club chart for 2 of 32 clubs", status="PILOT ONLY",
         leak="High: shadow/coverage assignment is a post-game observation",
         gate="G1 data + timestamp rule + all eight gates"),
    dict(id="AV-S4", signal="Second/third/fourth-string replacement",
         definition="The player who takes the most snaps at a position is not the first-string player.",
         inputs="Depth chart or participation/snap counts",
         available="Charts list 2–4 names; 2 of 32 clubs captured; no 2023–2026 participation",
         status="OPEN",
         leak="Very high: snap counts are published after the game",
         gate="G1 data + timestamp rule + all eight gates"),
    dict(id="AV-S5", signal="Practice-status trend within the week",
         definition="Change from Did Not Participate to Limited/Full across the week's reports.",
         inputs="Every daily report for the week, timestamped",
         available="Only one snapshot captured", status="OPEN",
         leak="Medium: only safe if each report is captured before the next is superseded",
         gate="G1 data + timestamp rule + all eight gates"),
    dict(id="AV-S6", signal="Short-week / rest differential",
         definition="Days between games, computed from the official schedule.",
         inputs="Official schedule and kickoff times",
         available="YES — already used as REST_ADV_ATS (no availability data)",
         status="AVAILABLE",
         leak="Low", gate="All eight gates"),
    dict(id="AV-S7", signal="Inactive list at kickoff",
         definition="Players declared inactive before kickoff; the exact deadline still needs an official "
                    "source.",
         inputs="Official inactives list with a timestamp",
         available="No machine-readable official inactives source verified",
         status="BLOCKED",
         leak="Low if captured before kickoff, but the source is unverified",
         gate="G1 data + timestamp rule + all eight gates"),
    dict(id="AV-S8", signal="Participation-based depth proxy (2019–2022)",
         definition="Rank players within position by prior-week play share and use that as the depth "
                    "ordering.",
         inputs="Play-by-play with player IDs (held for 2019–2022 only)",
         available="Data yes; 2023–2026 NO", status="PILOT ONLY",
         leak="Medium: requires strict prior-week windows",
         gate="All eight gates"),
]

PROBES = [
    ("Shell egress to www.nfl.com", "TLS handshake refused — the automated build cannot read NFL pages"),
    ("Agent page-fetch tool to www.nfl.com", "200 for the injury hub, week pages, game centre, schedule, "
                                             "scores and roster pages"),
    ("www.nfl.com/teams/<club>/depth-chart", "404 (verified on the Arizona Cardinals path)"),
    ("www.nfl.com/teams/<club>/roster?tab=depth", "200 but the same alphabetical roster"),
    ("www.nfl.com/scores/2026/REG8", "502 on the first request; the canonical /scores/2026/week-8 returned 200"),
]

BOARD_EVIDENCE = [
    ("2026_08_ARI_DAL", "Board listed as an open week-8 line (no score joined)",
     "NFL.com: Cardinals 33 – Cowboys 30, Final", URL_SCORES_W8),
    ("2026_08_CAR_GB", "Board listed as an open week-8 line (no score joined)",
     "NFL.com: Panthers 19 – Packers 27, Final", URL_SCORES_W8),
]

METHOD_NOTES = [
    "A capture is only usable if it is timestamped before the kickoff of the game it describes. The "
    "2026 week-10 capture was taken on 2026-11-12, before the 20:15 ET kickoff, and the report itself "
    "is the league's pre-game publication.",
    "A club chart publishes an order; it does not publish a game-day role. This site therefore quotes the "
    "chart cells and does not call anyone a confirmed starter or replacement (Q30, Q32, S17).",
    "Absence of a player from the report is not evidence that he is healthy, and presence is not "
    "evidence that he will play: clubs list only players with a report entry, and game status may be "
    "blank.",
    "League-wide rates cannot be computed from these captures: 1 of 14 week-10 games is transcribed, "
    "and 1 of 16 for 2019 week 5 (the first game on that page).",
]
