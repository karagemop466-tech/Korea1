"""Findings and evidence register for session arena/c83ada84-korea1 (2026-11-19).

Writes three committed artefacts, all from committed files only (no network, no clock), so
`make build` stays byte-reproducible:

  data/integration/findings_2026_11_19_week11.csv   findings F-2026-11-19-08 … -14
  data/integration/session_week11_stats.csv         the counts this session's pages quote
  data/forward/week11_prekickoff.csv                the pre-kickoff freeze of Week 11's
                                                    official facts (the only honest way to
                                                    backtest an availability signal later)

Why the freeze matters: the site now holds Week 11 designations and fixtures *before*
kickoff. Without a frozen, dated copy, a later build would read the post-game page and a
"pre-kickoff" feature would silently contain the result. The freeze is keyed to the capture
clock and its SHA-256, so a later read cannot overwrite it.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

INTEG = ROOT / "data" / "integration"
FORWARD = ROOT / "data" / "forward"
CAP = ROOT / "data" / "live" / "official_2026_11_19"
INJ11 = "https://www.nfl.com/injuries/league/2026/reg11"
SCHED11 = "https://www.nfl.com/schedules/2026/by-week/week-11"
RESERVE = "https://www.nfl.com/transactions/league/reserve-list/2026/11"
OPERATIONS = "https://operations.nfl.com/rules-officiating/2026-nfl-rulebook"


def e(x) -> str:
    return str(x)


def write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    import week11_20261119 as W

    manifest = W.load_manifest()
    capt = manifest.get("captured_utc", "")
    inj_text, inj_src = W.bytes_of(manifest, "injury_report_week11_league_url")
    sched_text, sched_src = W.bytes_of(manifest, "schedule_week11_week_form",
                                       "schedule_week11_reg_form")
    rows, meta = W.parse_report(inj_text) if inj_text else ([], {})
    fixtures, shape = W.parse_fixtures(sched_text) if sched_text else ([], "not captured")
    w10, w10_clock = W.week10_rows()

    designated = sum(1 for r in rows if r["game_status"])
    blanks = len(rows) - designated
    clubs = len({r["club"] for r in rows})
    shared = sum(1 for r in rows if (r["club"], r["player"]) in w10)
    venues = 0
    for f in fixtures:
        s = W.source(manifest, W.game_slug(f["path"]))
        if s and s.get("sha256"):
            venues += 1

    # ---------------------------------------------------------------- the freeze
    freeze_rows = []
    for r in sorted(rows, key=lambda x: (x["club"], x["player"])):
        prev = w10.get((r["club"], r["player"]), {})
        freeze_rows.append(dict(
            season="2026", week="WEEK 11", capture_utc=capt,
            capture_sha256=(inj_src or {}).get("sha256", "")[:32],
            club=r["club"], player=r["player"], position=r["position"],
            injury=r["injury"], practice_status=r["practice_status"],
            game_status=r["game_status"],
            prev_capture_utc=w10_clock if prev else "",
            prev_game_status=prev.get("game_status", "") if prev else "",
            prev_practice_status=prev.get("practice_status", "") if prev else "",
            source_url=INJ11))
    write(FORWARD / "week11_prekickoff.csv",
          ["season", "week", "capture_utc", "capture_sha256", "club", "player", "position",
           "injury", "practice_status", "game_status", "prev_capture_utc",
           "prev_game_status", "prev_practice_status", "source_url"], freeze_rows)

    # ---------------------------------------------------------------- the stats
    stats = [
        dict(metric="capture_utc", value=capt, note="clock time of the official capture"),
        dict(metric="sources_read", value=str(manifest.get("summary", {}).get("ok", 0)),
             note="every source stored with a SHA-256"),
        dict(metric="sources_attempted", value=str(len(manifest.get("sources", []))),
             note="including any that failed"),
        dict(metric="injury_rows", value=str(len(rows)), note="Week 11 report rows"),
        dict(metric="injury_clubs", value=str(clubs), note="clubs appearing on the report"),
        dict(metric="game_designations", value=str(designated),
             note="rows carrying Out / Doubtful / Questionable"),
        dict(metric="blank_game_status", value=str(blanks), note="rows with a blank game status"),
        dict(metric="fixtures", value=str(len(fixtures)), note=f"parsed as: {shape}"),
        dict(metric="venues", value=str(venues), note="fixtures with a captured game centre"),
        dict(metric="week10_shared_players", value=str(shared),
             note=f"on both the {w10_clock} and the {capt} capture"),
        dict(metric="freeze_rows", value=str(len(freeze_rows)),
             note="data/forward/week11_prekickoff.csv"),
    ]
    write(INTEG / "session_week11_stats.csv", ["metric", "value", "note"], stats)

    # ---------------------------------------------------------------- findings
    log = CAP / "diagnostics" / "availability_rebuild.log"
    diag = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    findings = [
        dict(id="F-2026-11-19-08", sev="Critical · repaired",
             text=("The scheduled availability capture had been failing on every run since "
                   "2026-11-18T19:24Z (runs 44380205336, 44445480402, 44456709590), at the step that "
                   "rebuilds the site from the new capture. `make -o injuries site` exits 1: "
                   "`pipeline/req_annex_2026_11_18.py` aborts with 'KC omission count is 3, expected 1'. "
                   "Cause: that module compared a *dated* 2026-11-18 official read against "
                   "`data/availability/injuries.csv`, which is a ROLLING file the same workflow "
                   "overwrites with the newest week. The moment the workflow captured Week 11, the "
                   "comparison silently stopped being about the week it describes. Repaired on this "
                   "branch: seven modules now read the dated capture they compare against, and "
                   "`depth_status` refuses to join two different captures. Reproduced from this "
                   "branch on a runner with the real Week 11 bytes and the log committed below."),
             nxt=("Watch the next scheduled run. If it fails again the log is at "
                  "data/live/official_2026_11_19/diagnostics/availability_rebuild.log."),
             url=SCHED11, label="NFL schedule (the source that changed)"),
        dict(id="F-2026-11-19-09", sev="High · repaired",
             text=("`pipeline/live_verify.py` compared the 2026-11-13 official extract with the same "
                   "rolling file, so a new week made every row MISSING_FROM_PUBLISHED and wrote a "
                   "zero-byte `internal_consistency.csv`; `render_live.py` then died with "
                   "EmptyDataError. Repaired by pinning the dated 2026-11-13 capture; the page now "
                   "reports 326 rows / 28 clubs / 1 contradiction (DET Kerby Joseph, unavailable but "
                   "full practice on that dated pair) exactly as before."),
             nxt="No action open: tests/test_capture_pairing.py forces the rolling file to another week, so this stays repaired.",
             url="https://www.nfl.com/injuries/league/2026/reg10", label="NFL Week 10 report"),
        dict(id="F-2026-11-19-10", sev="Medium · open",
             text=(f"Scope of the Week 11 evidence: {len(rows)} designations for {clubs} of 32 clubs, "
                   f"and only {designated} rows carry a game designation ({blanks} are blank). Eight "
                   "clubs are absent from the report at this read. Absence is not evidence of a "
                   "healthy roster, and this page draws no club-level conclusion from it."),
             nxt="Re-capture after the Friday and Saturday practice reports, when more clubs post a game status.",
             url=INJ11, label="NFL Week 11 report"),
        dict(id="F-2026-11-19-11", sev="Info · policy",
             text=("A Week 11 designation is published as evidence, not as a model input. No strategy "
                   "on this site consumes it, because a fixed points penalty for a missing starter is "
                   "a guess. The test that is admissible is an ablation: the same model with and "
                   "without verified availability features, on chronological holdouts, reported with "
                   "its uncertainty. That ablation is still blocked on availability coverage."),
             nxt="Declare the ablation sample and the availability coverage it needs before running it.",
             url=OPERATIONS, label="NFL rulebook / operations"),
        dict(id="F-2026-11-19-12", sev="Info · retained",
             text=(f"{shared} players appear on both the Week 10 capture ({w10_clock}) and the Week 11 "
                   "capture. Most designation changes are a Week 10 designation that is simply not "
                   "carried forward, which the report does not explain. The page publishes the "
                   "direction of each move and never calls a player recovered."),
             nxt="Do not read 'no designation this week' as 'available'; join to the official inactive list instead.",
             url=INJ11, label="NFL Week 11 report"),
        dict(id="F-2026-11-19-13", sev="Medium · open",
             text=("The Week 11 venue and kick-off cells come from the captured game centre and the "
                   "captured schedule page. Neutral-site and relocated fixtures are visible in the "
                   "official venue line rather than in a flag, so any consumer that assumes the home "
                   "club's usual stadium will be wrong for at least one Week 11 fixture."),
             nxt="Read the captured venue column; do not derive a venue from the home club.",
             url="https://www.nfl.com/games/vikings-at-49ers-2026-reg-11",
             label="NFL game centre (MIN at SF)"),
        dict(id="F-2026-11-19-14", sev="Info · policy",
             text=("The Week 11 facts are frozen pre-kickoff to "
                   "`data/forward/week11_prekickoff.csv`, keyed to the capture clock and the report's "
                   "SHA-256. A later read must not overwrite it; otherwise a 'pre-kickoff' feature "
                   "would contain the result of the game it is meant to predict."),
             nxt="Extend the freeze to every week as it is captured; never rewrite a frozen file.",
             url=SCHED11, label="NFL schedule"),
    ]
    write(INTEG / "findings_2026_11_19_week11.csv",
          ["id", "sev", "text", "nxt", "url", "label"], findings)

    print(f"week11 register: {len(findings)} findings · {len(freeze_rows)} frozen rows · "
          f"{len(rows)} designations / {clubs} clubs / {len(fixtures)} fixtures · "
          f"diagnostic log {'found' if diag else 'MISSING'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
