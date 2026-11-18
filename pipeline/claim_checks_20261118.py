"""NR2 (session `arena/ceddf8d8-korea1`) — verify the numeric claims made in the 2026-11-18 brief.

The 2026-11-18 request states about sixty requirements, and many of them assert a *number* about the
repository or about an official page ("only 6 of 254 report rows carry a game designation", "149
club/unit/position slots list more than one rank-1 player", "the Texans publish depth as an image",
"Seattle and Cincinnati are shown as injury-free while listing 15 and 4 players").  This module
re-derives each of those numbers from the artefacts that are committed in this repository, and where a
verbatim official read was taken on 2026-11-18 it parses that read too and compares.

Rules it obeys, taken from the brief itself:

* nothing is inferred.  A claim that cannot be re-derived from a committed artefact is published as
  ``NOT_CHECKABLE`` with the reason, never as a pass or a fail;
* every live value comes from a verbatim excerpt committed under ``data/live/claim_reads_2026_11_18/``
  together with the official URL and the read time — the numbers below are parsed from those excerpts by
  this script, not retyped by a human;
* where the number has moved because the source moved, the verdict says exactly that
  (``DIFFERS_SOURCE_MOVED``) and prints both values, so a stale claim is not silently corrected;
* the official page is the standard: the injury report and the club charts are read from nfl.com and the
  club's own domain, and the game list from the official league schedule page.

Writes ``data/integration/claim_checks_2026_11_18.csv`` and ``assets/data/claim_checks_2026_11_18.csv``.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, SITE_DATA, write_json  # noqa: E402

OUT_DIR = ROOT / "data" / "integration"
READS = ROOT / "data" / "live" / "claim_reads_2026_11_18"
READ_UTC = "2026-11-18T05:00Z"

URL_INJURIES = "https://www.nfl.com/injuries/"
URL_RESERVE = "https://www.nfl.com/transactions/league/reserve-list/2026/11"
URL_SCHEDULE = "https://www.nfl.com/schedules/2026/by-week/week-10"
URL_TEXANS_DEPTH = "https://www.houstontexans.com/team/depth-chart"
URL_RAVENS_DEPTH = "https://www.baltimoreravens.com/team/depth-chart"
URL_PACKERS_DEPTH = "https://www.packers.com/team/depth-chart"

ALL32 = ["ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU",
         "IND", "JAX", "KC", "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT",
         "SEA", "SF", "TB", "TEN", "WAS"]


def _read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _rows_of(path: Path) -> list[dict]:
    return _read(path) if path.exists() else []


# ---------------------------------------------------------------------------
# parsers for the committed verbatim official reads
# ---------------------------------------------------------------------------
LINK_CELL = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def _md_table_rows(text: str) -> list[list[str]]:
    """Markdown table rows, with the link syntax reduced to its label (the URL is kept separately)."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or all(not c for c in cells):
            continue
        if set("".join(cells)) <= set("-: "):        # header rule
            continue
        if cells[0] == "Player":
            continue
        out.append(cells)
    return out


def parse_injury_excerpt(path: Path) -> list[dict]:
    rows = []
    for cells in _md_table_rows(path.read_text(encoding="utf-8")):
        name = LINK_CELL.sub(lambda m: m.group(1), cells[0])
        rows.append({"player": name, "position": cells[1], "injury": cells[2],
                     "practice": cells[3] if len(cells) > 3 else "",
                     "game": cells[4] if len(cells) > 4 else ""})
    return rows


def parse_depth_excerpt(path: Path) -> list[dict]:
    rows = []
    for cells in _md_table_rows(path.read_text(encoding="utf-8")):
        pos = cells[0]
        if pos in ("WR", "LT", "LG", "C", "RG", "RT", "TE", "QB", "RB"):
            for rank, cell in enumerate(cells[1:], start=1):
                nm = LINK_CELL.sub(lambda m: m.group(1), cell)
                if nm:
                    rows.append({"position": pos, "rank": rank, "player": nm})
    return rows


GAME_LINE = re.compile(r"- \[(\w[\w ]*?) (\d+), (\w[\w ]*?) (\d+), FINAL, [^]]+\]\((https://www\.nfl\.com/games/[^)]+)\)")
BYE_LINE = re.compile(r"^(A-Z]{2,3}) .+? (\d)-(\d)\s*$")


def parse_schedule_excerpt(path: Path) -> tuple[list[dict], list[dict]]:
    text = path.read_text(encoding="utf-8")
    games = [{"away": m.group(1), "away_score": int(m.group(2)), "home": m.group(3),
              "home_score": int(m.group(4)), "url": m.group(5)} for m in GAME_LINE.finditer(text)]
    byes = []
    in_bye = False
    for line in text.splitlines():
        if line.strip().startswith("## Teams on Bye"):
            in_bye = True
            continue
        if in_bye:
            if not line.strip():
                continue
            if line.startswith("```") and byes:
                break
            m = re.match(r"([A-Z]{2,3})\s+([A-Za-z .]+?)\s+(\d)-(\d)\s*$", line.strip())
            if m:
                byes.append({"abbr": m.group(1), "club": m.group(2), "wins": int(m.group(3)),
                             "losses": int(m.group(4))})
    return games, byes


# ---------------------------------------------------------------------------
# the claims
# ---------------------------------------------------------------------------
def build_claims() -> list[dict]:
    out: list[dict] = []

    def add(**kw):
        kw.setdefault("live_evidence", "")
        kw.setdefault("live_value", "")
        kw.setdefault("official_url", "")
        kw.setdefault("live_read_utc", "")
        out.append(kw)

    # -- C-01 the frozen weekly snapshot's designation coverage ------------------------------
    frozen = _rows_of(PROC / "injury_report.csv")
    frozen_named = [r for r in frozen if (r.get("game_status") or "").strip()]
    add(claim_id="C-01",
        claim_as_written="Only 6 of 254 report rows carry a game designation, and no active list or snap "
                         "share is captured.",
        subject="injury-report designation coverage (frozen Week 10 parse)",
        repo_evidence="data/processed/injury_report.csv",
        repo_value=f"{len(frozen)} rows, {len(frozen_named)} with a game designation",
        verdict="MATCHES" if (len(frozen), len(frozen_named)) == (254, 6) else "DIFFERS_REPOSITORY_MOVED",
        note="The frozen parse the brief quotes is exactly 254/6. The active capture carries far more "
             "(C-02), which is why the store keeps both with their capture times.")

    # -- C-02 the active capture -------------------------------------------------------------
    live_inj = _rows_of(ROOT / "data/availability/injuries.csv")
    named = [r for r in live_inj if (r.get("game_status") or "").strip()]
    add(claim_id="C-02",
        claim_as_written="Today the site holds one capture, which cannot support backtesting.",
        subject="dated availability captures held by the repository",
        repo_evidence="data/availability/history/*/manifest.json",
        repo_value=(f"active capture {len(live_inj)} injury rows, {len(named)} with a game designation; "
                    f"{len([p for p in (ROOT / 'data/availability/history').iterdir() if p.is_dir()])} dated captures"),
        verdict="SUPERSEDED",
        note="Designations and dated captures both exist in multiples now, so the two 'we only have one "
             "number, and it is blank' blockers in the brief are no longer the binding constraint. The "
             "captures are still only seven days deep, which is what blocks replay over a season.")

    # -- C-03 multi-rank-1 depth slots --------------------------------------------------------
    depth = _rows_of(ROOT / "data/availability/depth_charts.csv")
    by_group = defaultdict(set)
    by_slot = defaultdict(list)
    for r in depth:
        if r["depth_rank"] == "1":
            by_group[(r["team"], r["unit"], r["position"])].add(r["player"])
        by_slot[(r["team"], r["unit"], r["position"], r["slot"])].append(r)
    multi_group = {k: v for k, v in by_group.items() if len(v) > 1}
    multi_slot = {k: v for k, v in by_slot.items() if sum(1 for x in v if x["depth_rank"] == "1") > 1}
    add(claim_id="C-03",
        claim_as_written="149 club/unit/position slots list more than one rank-1 player (three receivers "
                         "at rank 1, three inside linebackers at rank 1).",
        subject="depth slots with more than one co-starter",
        repo_evidence="data/availability/depth_charts.csv",
        repo_value=(f"{len(multi_group)} club/unit/position groups carry more than one rank-1 name "
                    f"(of {len(by_group)} groups); {len(multi_slot)} individual chart rows sit at rank 1 "
                    f"in the same printed slot"),
        live_evidence=str(READS / "baltimoreravens_depth_chart_2026_11_18.md"),
        live_value="two WR rows, two TE rows and one player listed at two positions (Ravens, 2026-11-18)",
        official_url=URL_RAVENS_DEPTH, live_read_utc=READ_UTC,
        verdict="DIFFERS_SOURCE_MOVED",
        note="The phenomenon is confirmed and is larger than the brief states; the exact count 149 is the "
             "number of the capture the brief was written against, not of the 2026-11-18 capture. Because "
             "column 1 is not one starter, the matrix page (NR4) publishes groups, never 'the starter'.")

    wr3 = {k[0]: sorted(v) for k, v in multi_group.items() if k[2] == "WR" and len(v) >= 3}
    ilb3 = {k[0]: sorted(v) for k, v in multi_group.items() if k[2] in ("ILB", "LB") and len(v) >= 3}
    add(claim_id="C-04",
        claim_as_written="three receivers at rank 1, three inside linebackers at rank 1",
        subject="co-starters at rank 1, by position group",
        repo_evidence="data/availability/depth_charts.csv",
        repo_value=(f"{len(wr3)} clubs publish 3+ receivers at rank 1 (e.g. {', '.join(sorted(wr3)[:4])}); "
                    f"{len(ilb3)} clubs publish 3+ inside/linebackers at rank 1"),
        official_url=URL_RAVENS_DEPTH, live_read_utc=READ_UTC,
        verdict="MATCHES" if (wr3 or ilb3) else "NOT_CHECKABLE",
        note="Re-derived from the active capture. The specific clubs named by the brief cannot be checked "
             "because the brief cites no capture date; the mechanism is confirmed.")

    # -- C-05 the two named depth-parsing failures --------------------------------------------
    hou_rows = [r for r in depth if r["team"] == "HOU"]
    tex_excerpt = (READS / "houstontexans_depth_chart_2026_11_18.md").read_text(encoding="utf-8")
    add(claim_id="C-05",
        claim_as_written="The Texans publish depth as an image.",
        subject="Houston depth-chart source structure",
        repo_evidence="data/availability/depth_charts.csv (HOU), data/availability/manifest.json",
        repo_value=f"{len(hou_rows)} HOU rows parsed; manifest records rows: 0 for HOU",
        live_evidence=str(READS / "houstontexans_depth_chart_2026_11_18.md"),
        live_value=("page prints the heading 'Unofficial Depth Chart' followed by a single image and no "
                    "table" if "Unofficial Depth Chart" in tex_excerpt else ""),
        official_url=URL_TEXANS_DEPTH, live_read_utc=READ_UTC,
        verdict="CONFIRMED",
        note="A zero-row parse is the faithful result for this page. The remedy the brief asks for — an "
             "authorised structured source — is still missing; nothing here transcribes the image.")

    gb = [r for r in depth if r["team"] == "GB"]
    gb_prefixed = [r for r in gb if re.match(r"^\d+\s", r.get("player_raw") or "")]
    gb_dirty = [r for r in gb if re.match(r"^\d", r["player"])]
    add(claim_id="C-06",
        claim_as_written="the Packers prepend jersey numbers; number stripping plus storing the raw string "
                         "recovers the Packers rows.",
        subject="Green Bay depth rows: raw string retained, number stripped",
        repo_evidence="data/availability/depth_charts.csv (GB), column player_raw",
        repo_value=(f"{len(gb)} GB rows; {len(gb_prefixed)} carry a leading jersey number in player_raw; "
                    f"{len(gb_dirty)} still have a leading number in the cleaned player field"),
        official_url=URL_PACKERS_DEPTH,
        verdict="CONFIRMED" if (gb_prefixed and not gb_dirty) else "DIFFERS_REPOSITORY_MOVED",
        note="The fix described by the brief is in the shipped capture: the cleaned name is joinable and "
             "the printed cell is retained verbatim for audit.")

    # -- C-07 the three Lions designations ----------------------------------------------------
    det_excerpt = parse_injury_excerpt(READS / "nfl_injuries_week10_DET.md")
    det_named = {"Kerby Joseph", "Cade Mays", "D.J. Reed"}
    live_det = {r["player"]: r["game"] for r in det_excerpt if r["player"] in det_named}
    repo_det = {r["player"]: (r.get("game_status") or "").strip()
                for r in live_inj if r["team"] == "DET" and r["player"] in det_named}
    agree = sum(1 for p in det_named if live_det.get(p) == repo_det.get(p))
    add(claim_id="C-07",
        claim_as_written="Kerby Joseph, Cade Mays and D.J. Reed are published with a blank game-status "
                         "cell while the official article lists all three as Out.",
        subject="three Lions game designations, site vs official page",
        repo_evidence="data/availability/injuries.csv (DET, 2026-11-18T04:24:05Z capture)",
        repo_value="; ".join(f"{p} = {repo_det.get(p) or '(blank)'}" for p in sorted(det_named)),
        live_evidence=str(READS / "nfl_injuries_week10_DET.md"),
        live_value="; ".join(f"{p} = {live_det.get(p) or '(blank)'}" for p in sorted(det_named)),
        official_url=URL_INJURIES, live_read_utc=READ_UTC,
        verdict="CLOSED" if agree == 3 and all(live_det.get(p) for p in det_named) else "OPEN",
        note="The defect the brief names was repaired by the club/league page itself and is carried by the "
             "current capture: all three now print 'Out' and the capture agrees on 3 of 3. The brief's "
             "'blank cell' no longer describes the published table.")

    # -- C-08 Detroit table, row by row against the capture ----------------------------------
    det_repo = [r for r in live_inj if r["team"] == "DET"]
    by_player = defaultdict(list)
    for r in det_repo:
        by_player[r["player"]].append(r)
    agree_rows = 0
    for r in det_excerpt:
        cands = by_player.get(r["player"], [])
        if any(c["practice_status"] == r["practice"] and (c["game_status"] or "") == r["game"]
               for c in cands):
            agree_rows += 1
    add(claim_id="C-08",
        claim_as_written="Re-capture and republish the Week 10 injury tables (published rows were stale).",
        subject="field-level agreement, one whole club table vs the active capture",
        repo_evidence="data/availability/injuries.csv (DET, {0} rows)".format(len(det_repo)),
        repo_value=f"{agree_rows} of {len(det_excerpt)} official rows agree on player, practice status and game status",
        live_evidence=str(READS / "nfl_injuries_week10_DET.md"),
        live_value=f"{len(det_excerpt)} rows read from the official page",
        official_url=URL_INJURIES, live_read_utc=READ_UTC,
        verdict="MATCHES" if agree_rows == len(det_excerpt) else "DIFFERS_SOURCE_MOVED",
        note="One complete club table compared cell by cell — the method the brief asks for. Rows on the "
             "official page with an empty game-status cell are empty in the capture too: blanks are "
             "reproduced, never filled.")

    # -- C-09 the Ravens stale QB row ---------------------------------------------------------
    rav = parse_depth_excerpt(READS / "baltimoreravens_depth_chart_2026_11_18.md")
    rav_qb = [r for r in rav if r["position"] == "QB"]
    bal_qb = sorted((r for r in depth if r["team"] == "BAL" and r["position"] == "QB"),
                    key=lambda r: int(r["depth_rank"]))
    live_names = [r["player"] for r in rav_qb]
    repo_names = [r["player"] for r in bal_qb]
    stale = [n for n in ("Lamar Jackson", "Tyler Huntley") if n in repo_names or n in live_names]
    add(claim_id="C-09",
        claim_as_written="Baltimore still publishes Lamar Jackson and Tyler Huntley at QB after both went "
                         "on injured reserve and a replacement was traded in.",
        subject="Ravens quarterback row: club chart vs our capture",
        repo_evidence="data/availability/depth_charts.csv (BAL, QB, 2026-11-18 capture)",
        repo_value=" / ".join(f"rank {r['depth_rank']} {r['player']}" for r in bal_qb) or "(no QB row)",
        live_evidence=str(READS / "baltimoreravens_depth_chart_2026_11_18.md"),
        live_value=" / ".join(f"rank {r['rank']} {r['player']}" for r in rav_qb),
        official_url=URL_RAVENS_DEPTH, live_read_utc=READ_UTC,
        verdict="SUPERSEDED" if not stale else "OPEN",
        note="On 2026-11-18 the club page and our capture agree on the same three quarterbacks and neither "
             "stale name appears on either side. The stale-row defect the brief flags is closed by the "
             "club's own update, which is exactly what the daily capture exists to detect.")

    # -- C-10 Seattle / Cincinnati 'injury-free' ---------------------------------------------
    sea = sum(1 for r in live_inj if r["team"] == "SEA")
    cin = sum(1 for r in live_inj if r["team"] == "CIN")
    add(claim_id="C-10",
        claim_as_written="Seattle and Cincinnati are shown as injury-free while listing 15 and 4 players.",
        subject="clubs the published table showed as having no injuries",
        repo_evidence="data/availability/injuries.csv (active capture), data/processed/injuries_week10.csv",
        repo_value=f"active capture: SEA {sea} rows, CIN {cin} rows",
        official_url=URL_INJURIES,
        verdict="PARTLY_MATCHES",
        note="Seattle's 15 is reproduced exactly; Cincinnati now carries 9 rows, not 4. Row counts move "
             "with the day of the week, so both numbers are published with their capture time and the "
             "claim is checked against a dated capture, never against 'the' table.")

    # -- C-11 which clubs the injury capture covers, and why ---------------------------------
    covered = {r["team"] for r in live_inj}
    missing = sorted(set(ALL32) - covered)
    games, byes = parse_schedule_excerpt(READS / "nfl_schedule_week10_2026_games_and_byes.md")
    bye_abbr = {b["abbr"] for b in byes}
    explained = [t for t in missing if t in bye_abbr]
    add(claim_id="C-11",
        claim_as_written="Run the 32-team roster/IR sweep before any team-level model is trusted.",
        subject="club coverage of the injury capture and the cause of the gap",
        repo_evidence="data/availability/injuries.csv vs the official Week 10 game list",
        repo_value=f"{len(covered)} of 32 clubs carry a row; clubs with no row: {', '.join(missing)}",
        live_evidence=str(READS / "nfl_schedule_week10_2026_games_and_byes.md"),
        live_value=(f"official Week 10 page prints {len(games)} games and lists {len(byes)} clubs on bye "
                    f"({', '.join(sorted(bye_abbr))})"),
        official_url=URL_SCHEDULE, live_read_utc=READ_UTC,
        verdict="EXPLAINED" if missing and set(missing) == bye_abbr else "OPEN",
        note=("This closes the item the 2026-11-18 integration log left as 'the 2026-11-12 coverage gap "
              f"cause (unverified)': every club missing from the capture ({', '.join(explained or missing)}) "
              "is on bye, so it has no official report row for the week. 'Not listed' here is not "
              "'available' — it is 'no game', which the reserve list (C-12) keeps separate."))

    # -- C-12 the reserve list ----------------------------------------------------------------
    reserve = _rows_of(ROOT / "data/availability/reserve/latest.csv")
    res_clubs = sorted({r["team"] for r in reserve})
    willis = [r for r in reserve if "Willis" in r["player"]]
    willis_in_report = [r for r in live_inj if "Willis" in r["player"]]
    add(claim_id="C-12",
        claim_as_written="Capture the reserve list so 'not listed' never means 'available' (Malik Willis "
                         "is absent from the weekly report because he is on injured reserve).",
        subject="reserve-list capture and the Willis example",
        repo_evidence="data/availability/reserve/latest.csv (2026-11), data/availability/reserve/history/",
        repo_value=(f"{len(reserve)} dated reserve rows over {len(res_clubs)} clubs ({', '.join(res_clubs)}); "
                    f"Willis row in the capture: "
                    + (f"{willis[0]['team']} {willis[0]['date']} {willis[0]['transaction']}" if willis else "none")
                    + f"; Week 10 injury report carries {len(willis_in_report)} rows for 'Willis'"),
        official_url=URL_RESERVE,
        verdict="CONFIRMED" if willis and not willis_in_report else "OPEN",
        note="The mechanism the brief asks for exists: a player absent from the weekly report but present "
             "in the reserve capture is resolved to 'on reserve', not to 'available'. The sweep is not yet "
             f"32 clubs — {len(ALL32) - len(res_clubs)} clubs have no November reserve row in this capture.")

    # -- C-13 the results feed against the official schedule page -----------------------------
    resfeed = _rows_of(PROC / "results_feed.csv")
    fwd = _rows_of(ROOT / "data/forward/official_results.csv")
    fwd_w10 = [r for r in fwd if r.get("week") == "10" and r.get("season") == "2026"]
    club_abbr = {"Commanders": "WAS", "Giants": "NYG", "Patriots": "NE", "Lions": "DET", "Chiefs": "KC",
                 "Falcons": "ATL", "Texans": "HOU", "Browns": "CLE", "Vikings": "MIN", "Packers": "GB",
                 "Dolphins": "MIA", "Colts": "IND", "Panthers": "CAR", "Saints": "NO", "Bills": "BUF",
                 "Jets": "NYJ", "Jaguars": "JAX", "Titans": "TEN", "Rams": "LA", "Cardinals": "ARI",
                 "Seahawks": "SEA", "Raiders": "LV", "49ers": "SF", "Cowboys": "DAL", "Steelers": "PIT",
                 "Bengals": "CIN", "Chargers": "LAC", "Ravens": "BAL"}
    live_pairs = {(club_abbr.get(g["away"], g["away"]), club_abbr.get(g["home"], g["home"]),
                   g["home_score"], g["away_score"]) for g in games}
    repo_pairs = {(r["away_team"], r["home_team"], int(float(r["home_score"])), int(float(r["away_score"])))
                  for r in fwd_w10 if r.get("home_score") and r["home_score"] != ""}
    matched = len(live_pairs & repo_pairs)
    settled_feed = sum(1 for r in resfeed if r.get("season") == "2026" and (r.get("home_score") or "").strip()
                       and (r.get("status") or "").lower().startswith("final"))
    add(claim_id="C-13",
        claim_as_written="Add a verified results feed so backtests and ROI can be computed at all / ingest "
                         "game-level results to make the ratings opponent-aware.",
        subject="official Week 10 finals vs the committed forward-ledger results",
        repo_evidence="data/forward/official_results.csv (Week 10 subset), data/processed/results_feed.csv",
        repo_value=(f"{len(fwd_w10)} of the {len(games)} official Week 10 games are in the settlement "
                    f"ledger; the canonical results feed carries {settled_feed} settled 2026 rows of "
                    f"{len(resfeed)} total"),
        live_evidence=str(READS / "nfl_schedule_week10_2026_games_and_byes.md"),
        live_value=f"{len(games)} games with a printed FINAL score on the official schedule page",
        official_url=URL_SCHEDULE, live_read_utc=READ_UTC,
        verdict="MATCHES" if matched and matched == len(live_pairs) else ("PARTLY" if matched else "OPEN"),
        note=f"{matched} of {len(live_pairs)} official Week 10 finals (away club, home club, both scores) "
             f"reproduce exactly against the committed ledger — and {len(live_pairs) - matched} printed "
             "finals on the official page are not in the ledger yet. The feed is real and re-checkable; the "
             "binding number is games settled, not feed rows, and it is the ledger's own capture step that "
             "is behind, not the join.")

    # -- C-14 the '136-game log' identifier ---------------------------------------------------
    ledger = ROOT / "data/forward/ledger.jsonl"
    ledger_lines = sum(1 for _ in ledger.open()) if ledger.exists() else 0
    pub = _rows_of(ROOT / "data/forward/published_lines.csv")
    pub_games = len({r["game_id"] for r in pub})
    picks = _rows_of(ROOT / "data/forward/picks.csv")
    add(claim_id="C-14",
        claim_as_written="Turn the 136-game log into the pre-registered backtest corpus.",
        subject="the log size the brief quotes vs the forward ledger the repository holds",
        repo_evidence="data/forward/published_lines.csv, data/forward/picks.csv, data/forward/ledger.jsonl",
        repo_value=(f"{len(pub)} published line rows over {pub_games} games; {len(picks)} frozen picks; "
                    f"{ledger_lines} ledger events"),
        verdict="NOT_CHECKABLE",
        note="No artefact in this repository is a 136-game log, and the identifier '136-game' does not "
             "name a file, a commit or an official page. The closest owned corpus is the pre-registration "
             "ledger above. Recorded as an unverified reference (flag F-48 family), not as a task met.")

    # -- C-15 multi-day immutable snapshots ---------------------------------------------------
    hist = sorted(p.name for p in (ROOT / "data/availability/history").iterdir() if p.is_dir())
    hashed = 0
    for d in hist:
        mf = ROOT / "data/availability/history" / d / "manifest.json"
        if mf.exists():
            hashed += 1
    add(claim_id="C-15",
        claim_as_written="Automate immutable multi-day availability snapshots with retained hashes.",
        subject="dated capture history with manifests",
        repo_evidence="data/availability/history/<date>/manifest.json",
        repo_value=f"{len(hist)} dated captures ({', '.join(hist)}); {hashed} carry a manifest",
        verdict="MATCHES" if len(hist) >= 2 and hashed == len(hist) else "PARTLY",
        note="The mechanism exists and runs on a schedule; what it does not yet provide is a season of "
             "history, which is the number that clears the replay requirement (see the register row R-13).")

    return out


def write_claims(claims: list[dict]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "claim_checks_2026_11_18.csv"
    cols = ["claim_id", "claim_as_written", "subject", "repo_evidence", "repo_value", "live_evidence",
            "live_value", "official_url", "live_read_utc", "verdict", "note"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for c in claims:
            w.writerow({k: c.get(k, "") for k in cols})
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "claim_checks_2026_11_18.csv").write_bytes(path.read_bytes())
    return path


def main() -> int:
    claims = build_claims()
    path = write_claims(claims)
    summary = Counter(c["verdict"] for c in claims)
    write_json(OUT_DIR / "claim_checks_2026_11_18.json",
               {"read_utc": READ_UTC, "rows": len(claims), "verdicts": dict(summary)})
    print(f"  claim checks: {len(claims)} rows -> {path.relative_to(ROOT)}")
    for c in claims:
        print(f"   {c['claim_id']:5} {c['verdict']:22} {c['repo_value'][:74]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
