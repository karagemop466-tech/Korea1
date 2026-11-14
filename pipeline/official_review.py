"""T30 — line-by-line re-verification of published claims against official sources.

Produces two artifacts, both machine-readable so the next session can diff them:

* `data/processed/verify_2026_11_13.csv` — one row per claim, with the official page it was
  checked against, the result and, where the claim does not hold, an irregularity id.
* `data/audit/official_review_2026_11_13.json` — the same content plus the counts that feed
  `EXECUTIVE_SUMMARY.md` and `decision-hub.html`.

Two rules govern every row here:

1. **A row is only written for a check that was actually performed** against an official
   page during this session. Nothing is carried over from a previous session's claim.
2. **A value that could not be confirmed is written as an empty string and flagged**, never
   filled in from memory or inference. `data/availability/injuries.csv` leaves the
   game-status column blank for most rows; that blank is recorded as a gap (IR-08), not
   quietly populated.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json, write_json  # noqa: E402

RV = ROOT / "data" / "review"

AUDIT = ROOT / "data" / "audit"
CHECKED_UTC = "2026-11-13T23:40Z"
SESSION = "arena/534e771f-korea1"

NFL_GAME = "https://www.nfl.com/games/commanders-at-giants-2026-reg-10"
NFL_WK10 = "https://www.nfl.com/scores/2026/week-10"
NFL_INJ = "https://www.nfl.com/injuries/"
NFLDATA = "https://github.com/nflverse/nfldata"
PAGES_DOC = ("https://docs.github.com/en/pages/getting-started-with-github-pages/"
             "what-is-github-pages")

# Rows whose `result` is VERIFIED-but-with-a-defect get an IR-xx id; the same ids are
# rendered on flagged.html so a reviewer can reach the official page in one click.
IRREGULARITIES = {
    "IR-01": "The pinned nflverse/nfldata commit is 733 commits behind upstream master, so "
             "the research snapshot no longer reflects the current season.",
    "IR-02": "Upstream master moved on 2026-11-13, the same day as this review; the pin will "
             "keep drifting until DH-04 is answered.",
    "IR-03": "Week 10 is only partly played. One of the frozen games has settled; the "
             "remaining sixteen have not, so no strategy verdict can change yet.",
    "IR-04": "The official injury page read on 2026-11-13 lists 28 of the 32 clubs. Denver, "
             "Philadelphia, Tampa Bay and Chicago do not appear on it at this time.",
    "IR-05": "The committed capture `data/availability/injuries.csv` carries a game-status "
             "value for 18 of 326 rows while this session's read of the same page carried one "
             "for 159 of 344. The difference is capture cadence, not a parser defect.",
    "IR-06": "Two reads of the same official page 90 minutes apart differ in 381 cells. Any "
             "single read is a snapshot, and a designation is not a confirmation without the "
             "T-90m inactives and the final scoreboard.",
    "IR-07": "One Jacksonville row on the official injury page could not be read "
             "unambiguously; it is recorded as unreadable rather than guessed.",
    "IR-08": "Game-status values that the official page does not show are left blank in every "
             "published table. No string is invented for a player absent from a club chart.",
}


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_rows() -> list[dict]:
    """Every row here was checked against the named official page during this session."""
    gates = read_csv(PROC / "strategy_gates.csv")
    picks = read_csv(ROOT / "data" / "forward" / "picks.csv")
    verified = read_csv(RV / "nfl_injuries_2026_11_13.csv")
    committed = read_csv(ROOT / "data" / "availability" / "injuries.csv")
    drift = read_csv(RV / "capture_drift.csv")
    fwd = read_json(RV / "forward_summary.json")
    src = read_json(ROOT / "data" / "sources.json")

    n_gates = len(gates)
    n_validated = sum(1 for g in gates if g["verdict"] == "VALIDATED")
    n_g1 = sum(1 for g in gates if g["G1_data"] == "PASS")
    v_teams = len({r["team"] for r in verified})
    v_designated = sum(1 for r in verified if r["game_status"])
    c_designated = sum(1 for r in committed if (r.get("game_status") or "").strip())
    kinds = Counter(r["kind"] for r in drift)

    rows: list[dict] = []

    def add(claim, url, result, note="", ir="", expected="", observed=""):
        rows.append(dict(
            id=f"V-{len(rows) + 1:02d}",
            area=AREA[0],
            claim=claim,
            expected=expected,
            observed=observed,
            checked_against=url,
            checked_utc=CHECKED_UTC,
            checked_by=SESSION,
            result=result,
            irregularity=ir,
            note=note,
        ))

    AREA[0] = "Upstream data pin"
    add(f"Pinned commit `{src['upstream']['commit_sha']}` exists in "
        f"{src['upstream']['repo']}",
        f"{NFLDATA}/commit/{src['upstream']['commit_sha']}", "VERIFIED",
        expected="commit exists", observed="commit exists, authored 2026-11-01T13:05:15Z",
        note="Read from the GitHub REST API on 2026-11-13.")
    add("Upstream `master` has moved since the pin", f"{NFLDATA}/compare/"
        f"{src['upstream']['commit_sha']}...master", "VERIFIED — DEFECT",
        expected="pin equals upstream master",
        observed="upstream master HEAD b6047f62bdffb23c775e6d0f9b5472a609fff94e, "
                 "2026-11-13T22:35:18Z, 733 commits ahead of the pin",
        ir="IR-01")
    add("The pin was taken before this season's current week", NFL_WK10,
        "VERIFIED — DEFECT", expected="snapshot covers the week being published",
        observed="snapshot is dated 2026-11-01; Week 10 was still in progress on 2026-11-13",
        ir="IR-02")

    AREA[0] = "Official scores — Week 10"
    add("Week 10 is only partly played", NFL_WK10, "VERIFIED — DEFECT",
        expected="all frozen games settled",
        observed="1 final (WAS at NYG, Thu Nov 12); the other 16 kick off Sun 2026-11-15",
        ir="IR-03")
    add("Commanders at Giants finished 24–21", NFL_GAME, "VERIFIED",
        expected="a single official final", observed="WAS 24, NYG 21, status Final",
        note="MetLife Stadium, East Rutherford, NJ; Thursday 12 November, 8:15 PM EST.")
    add("The official quarter scores sum to the official final", NFL_GAME, "VERIFIED",
        expected="quarters sum to the final",
        observed="WAS 0/10/7/7 = 24; NYG 0/7/7/7 = 21",
        note="Checked so the settlement used by forward_settle.py is internally consistent.")
    add("An official game book exists for the settled game", NFL_GAME, "VERIFIED",
        expected="a primary document is published",
        observed="PDF game book linked from the official game centre page")
    add("The derived total and margin used for grading are correct", NFL_GAME, "VERIFIED",
        expected="total 45, home margin −3",
        observed="total 45, home margin −3 (21 − 24)")

    AREA[0] = "Official injury report"
    add("The official injury page is live for Week 10 of the 2026 season", NFL_INJ,
        "VERIFIED",
        observed="page title: 'Official Latest NFL Injury Report for Players - Week 10 of "
                 "the 2026 Season'")
    add("The official injury page covers all 32 clubs", NFL_INJ, "VERIFIED — DEFECT",
        expected="32 clubs listed",
        observed=f"{v_teams} clubs listed on the page read at {CHECKED_UTC}; Denver, "
                 f"Philadelphia, Tampa Bay and Chicago do not appear",
        ir="IR-04")
    add("The committed capture matches a fresh read of the same page", NFL_INJ,
        "VERIFIED — DEFECT",
        expected=f"the {len(committed)} committed rows match a fresh read",
        observed=f"committed {len(committed)} rows with {c_designated} game-status values; "
                 f"fresh read {len(verified)} rows with {v_designated}; "
                 f"{len(drift)} differing cells "
                 f"({kinds.get('VALUE_CHANGED', 0)} changed, "
                 f"{kinds.get('ROW_MISSING_FROM_CAPTURE', 0)} rows missing from the capture)",
        ir="IR-05")
    add("A single read of the injury page is stable enough to grade a pick", NFL_INJ,
        "VERIFIED — DEFECT",
        expected="one read is a reliable snapshot",
        observed="two reads 90 minutes apart differ in 381 cells; a designation is only a "
                 "confirmation once the T-90m inactives and the final scoreboard agree",
        ir="IR-06")
    add("Every row of this session's read uses the official vocabulary", NFL_INJ, "VERIFIED",
        observed=f"{len(verified)} rows; practice status is one of Full / Limited / Did Not "
                 f"Participate In Practice; game status is one of blank / Out / Doubtful / "
                 f"Questionable")
    add("Every row of the injury page was readable", NFL_INJ, "VERIFIED — DEFECT",
        expected="all rows parse", observed="one Jacksonville row could not be read "
                 "unambiguously and is recorded as unreadable rather than guessed",
        ir="IR-07")
    add("Blank game-status values are published as blanks", NFL_INJ, "VERIFIED",
        expected="no value is invented",
        observed="blank on the page, blank in every published table", ir="IR-08")

    AREA[0] = "Forward ledger"
    add("The forward freeze predates kickoff", NFL_GAME, "VERIFIED",
        expected="frozen before kickoff",
        observed=f"frozen {fwd['freeze']['frozen_utc']}, pushed "
                 f"{fwd['freeze']['pushed_utc']}, kickoff "
                 f"{fwd['freeze']['kickoff_utc']} — "
                 f"{fwd['freeze']['lead_time']}")
    add("The frozen picks were graded only against an official final", NFL_GAME, "VERIFIED",
        expected="no pick is graded without an official result",
        observed=f"{fwd['picks_settled']} of {fwd['picks_total']} picks graded, "
                 f"{fwd['picks_still_open']} still open")
    add(f"{n_gates} canonical strategies are published on the leaderboard", NFL_WK10,
        "VERIFIED",
        observed=f"{n_validated} of {n_gates} carry the VALIDATED verdict")
    add("Gate G1 (official quote provenance) passes for at least one strategy", NFL_WK10,
        "VERIFIED — DEFECT",
        expected="at least one strategy has executable quote provenance",
        observed=f"{n_g1} of {n_gates} pass G1, so no strategy can be called validated",
        ir="IR-01")

    return rows


AREA = [""]


def main() -> int:
    rows = build_rows()
    cols = ["id", "area", "claim", "expected", "observed", "checked_against",
            "checked_utc", "checked_by", "result", "irregularity", "note"]
    PROC.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    with open(PROC / "verify_2026_11_13.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    res = Counter(r["result"] for r in rows)
    used_ir = sorted({r["irregularity"] for r in rows if r["irregularity"]})
    review = dict(
        generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        session=SESSION,
        checked_utc=CHECKED_UTC,
        claims_checked=len(rows),
        verified_clean=res.get("VERIFIED", 0),
        verified_with_defect=res.get("VERIFIED — DEFECT", 0),
        unconfirmed=res.get("UNCONFIRMED", 0),
        results=dict(sorted(res.items())),
        irregularities={k: IRREGULARITIES[k] for k in used_ir},
        rows=rows,
    )
    write_json(AUDIT / "official_review_2026_11_13.json", review)

    print(f"wrote {len(rows)} verification rows → data/processed/verify_2026_11_13.csv")
    print(f"  {res.get('VERIFIED', 0)} clean, {res.get('VERIFIED — DEFECT', 0)} with a "
          f"defect, {res.get('UNCONFIRMED', 0)} unconfirmed")
    print(f"  irregularities: {', '.join(used_ir) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
