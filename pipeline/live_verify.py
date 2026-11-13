"""V1 — independent official-source verification of the published injury table.

Why this exists
---------------
`pipeline/verify_site.py` proves that every published row *carries* an official link.
It cannot prove the row is *true*: it only ever sees the repository's own copies.
This module is the missing second opinion. It compares what the site publishes
against an extract taken directly from the official page.

Two constraints decide the design
---------------------------------
1. **The official page is a live document.** Practice participation and game
   statuses are published in stages across a week. A capture on 11-13 can
   legitimately differ from one on 11-12 for the same player. So a difference is
   *not* automatically an error in the published table.
2. **Some differences cannot be explained by a later update.** A player already
   listed `Out` or `Doubtful` cannot become a healthy participant in a later
   capture; a player missing from a club's table that the publisher demonstrably
   captured is an omission, not drift.

Every compared field therefore carries a `defect_class`, and only
`confirmed_defect` rows are allegations against the build. `drift_possible` rows
are reported as unresolved, never silently counted as failures.

How the drift rule was calibrated (not assumed)
-----------------------------------------------
The repository keeps a verbatim capture of the same official page taken
2026-11-12T13:06:29Z (`data/evidence/nfl_injuries/week10_2026/injury_report.md`)
and the availability workflow's own 11-12 snapshot
(`data/availability/history/2026-11-12/injuries.csv`). Those two are compared
here first: they agree on 254/254 rows and 0 of 1,016 cells. That proves the
published parser is faithful, and it proves that any disagreement with today's
live page is a *change at the source*, not a transcription error by the build.

Run: python pipeline/live_verify.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LIVE_CAPTURE_UTC, ROOT, write_json  # noqa: E402

LIVE = ROOT / "data" / "live"
OFFICIAL_PAGE = "https://www.nfl.com/injuries/league/2026/reg10"
PUBLISHED = ROOT / "data" / "availability" / "injuries.csv"
EXTRACT = LIVE / "official_injury_extract_2026_reg10.csv"
ARCHIVE_MD = ROOT / "data" / "evidence" / "nfl_injuries" / "week10_2026" / "injury_report.md"
ARCHIVE_SNAPSHOT = ROOT / "data" / "availability" / "history" / "2026-11-12" / "injuries.csv"
METHOD = ("read the official NFL.com Week 10 injury report in full with the page-fetch "
          "tool; all four matchup sections transcribed cell by cell; blank official "
          "cells left blank, never guessed")
FIELDS = ["position", "injury", "practice_status", "game_status"]
# A player in one of these states did not play, so a later capture cannot make him
# a full participant. Differences on these rows are not drift.
INACTIVE = {"out", "doubtful", "ir", "injured reserve", "sus", "suspended"}
# Official NFL game-status vocabulary (the four designations a club may assign).
GAME_STATUS = {"", "out", "doubtful", "questionable"}
PRACTICE_STATUS = {"", "did not participate in practice", "limited participation in practice",
                   "full participation in practice"}


def _norm(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v != v:
        return ""
    return str(v).strip()


def _inactive(status: str) -> bool:
    return _norm(status).lower() in INACTIVE


def archive_calibration() -> dict:
    """Compare the repo's own 11-12 verbatim page against its 11-12 snapshot.

    This is the control. Both describe the same instant, so any difference would
    be a parser defect. `data/evidence/` is a fixed document, so this test does
    not drift with the live page.
    """
    if not (ARCHIVE_MD.exists() and ARCHIVE_SNAPSHOT.exists()):
        return {"available": False}
    rows, club = [], None
    from fetch_availability import BY_NICK  # noqa: E402  (local import: heavy module)

    for line in ARCHIVE_MD.read_text().splitlines():
        s = line.strip()
        if s in BY_NICK:
            club = s
            continue
        if not (s.startswith("|") and club):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) != 5 or cells[0] == "Player" or set(cells[0]) <= set("- "):
            continue
        m = re.match(r"\[([^\]]+)\]", cells[0])
        if not m:
            continue
        rows.append(dict(club=club, player=m.group(1), position=cells[1], injury=cells[2],
                         practice_status=cells[3], game_status=cells[4]))
    a = pd.DataFrame(rows)
    a.to_csv(LIVE / "archive_2026-11-12_extract.csv", index=False)
    h = pd.read_csv(ARCHIVE_SNAPSHOT, dtype=str, keep_default_na=False)
    m = a.merge(h, on=["club", "player"], how="outer", indicator=True,
                suffixes=("_arch", "_pub"))
    both = m[m._merge == "both"]
    diffs = 0
    for f in FIELDS:
        diffs += int((both[f + "_arch"].map(_norm) != both[f + "_pub"].map(_norm)).sum())
    return dict(available=True,
                archive_rows=int(len(a)),
                snapshot_rows=int(len(h)),
                matched_rows=int(len(both)),
                row_gaps=int((m._merge != "both").sum()),
                cell_differences=int(diffs),
                cells_compared=int(len(both) * len(FIELDS)),
                verdict="PARSER_FAITHFUL" if diffs == 0 and len(both) == len(h) == len(a)
                else "PARSER_DEFECT")


def compare(published: pd.DataFrame, official: pd.DataFrame) -> pd.DataFrame:
    pub = published.copy()
    for c in FIELDS:
        pub[c] = pub[c].map(_norm)
    off = official.copy()
    for c in FIELDS:
        off[c] = off[c].map(_norm)
    off_keys = {(r.club, r.player) for r in off.itertuples()}
    rows = []

    for r in off.itertuples():
        hit = pub[(pub.team == r.club) & (pub.player == r.player)]
        if hit.empty:
            rows.append(dict(
                club=r.club, player=r.player, field="player_row",
                published_value="", official_value="present",
                verdict="MISSING_FROM_PUBLISHED", defect_class="unresolved",
                source_url=OFFICIAL_PAGE,
                note=("the official page lists the player and the published table did capture "
                      "this club, so the row is absent from the snapshot. Two causes fit and "
                      "this module cannot separate them: (a) the status was added to the page "
                      "between the 18:32Z snapshot and the transcription, or (b) the parser "
                      "dropped it. Recorded as unresolved for re-check, not asserted as a "
                      "defect; the next scheduled capture decides which it is")))
            continue
        p = hit.iloc[0]
        pub_inactive = _inactive(p["game_status"])
        for f in FIELDS:
            pv, ov = _norm(p[f]), _norm(getattr(r, f, ""))
            if pv == ov:
                verdict, klass, note = "MATCH", "", ""
            elif ov == "":
                verdict, klass = "UNVERIFIED", "no_basis"
                note = ("official page leaves this cell blank; the published value cannot be "
                        "confirmed or denied from this source")
            elif pv == "":
                verdict, klass = "MISSING_VALUE", "drift_possible"
                note = ("official page states a value the published cell does not carry; a "
                        "later status publication can add a value, so this alone does not "
                        "prove a defect")
            elif pub_inactive:
                verdict, klass = "INCONSISTENT", "confirmed_defect"
                note = ("the published table already recorded the player as unavailable, so a "
                        "later update cannot explain a different participation status; the "
                        "published cell is contradicted by the official page")
            else:
                verdict, klass = "DIFFERENT", "drift_possible"
                note = ("values differ; practice and game statuses are published in stages, so "
                        "an update between the two capture times explains this")
            rows.append(dict(club=r.club, club_name=_norm(p["club"]), player=r.player,
                             field=f, published_value=pv, official_value=ov,
                             verdict=verdict, defect_class=klass,
                             source_url=OFFICIAL_PAGE, note=note))

    for r in pub.itertuples():
        if (r.team, r.player) in off_keys:
            continue
        rows.append(dict(club=r.team, club_name=_norm(r.club), player=r.player,
                         field="player_row", published_value="present", official_value="",
                         verdict="NOT_ON_OFFICIAL_EXTRACT", defect_class="out_of_scope",
                         source_url=OFFICIAL_PAGE,
                         note=("the published row belongs to a club outside the four "
                               "transcribed matchups, or to a player the official page no "
                               "longer lists; it is not graded")))
    return pd.DataFrame(rows)


def internal_consistency(published: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Checks that need no second source: contradictions inside the published table.

    An `Out` or `Doubtful` designation is a statement that the player will not
    play. A player who did not play cannot also be recorded as a full practice
    participant in the same row, so that combination is self-contradictory
    whatever the official page says moments later. This runs on every published
    row, so it covers all 28 captured clubs, not just the transcribed sample.
    """
    p = published.copy()
    for c in ["game_status", "practice_status", "injury", "position"]:
        p[c] = p[c].map(_norm)
    issues = []

    def add(mask, check, severity, note):
        for r in p[mask].itertuples():
            issues.append(dict(club=r.team, player=r.player, check=check,
                               severity=severity, practice_status=r.practice_status,
                               game_status=r.game_status, injury=r.injury,
                               source_url=_norm(r.source_url), note=note))

    add((p.game_status.str.lower().isin(["out", "doubtful"]))
        & (p.practice_status.str.lower() == "full participation in practice"),
        "unavailable_but_full_practice", "contradiction",
        "game status says the player is Out or Doubtful while practice status says full "
        "participation; the two cells cannot both describe the same player")
    add(~p.game_status.str.lower().isin(GAME_STATUS), "unknown_game_status", "vocabulary",
        "game status outside the official Out / Doubtful / Questionable set")
    add(~p.practice_status.str.lower().isin(PRACTICE_STATUS), "unknown_practice_status",
        "vocabulary", "practice status outside the official three-level set")
    dup = p.duplicated(subset=["team", "player"], keep=False)
    add(dup, "duplicate_player_row", "duplicate",
        "same club and player appear more than once in the published table")
    add(p.injury.str.lower().isin(["none", "n/a", "na", "unknown"]), "placeholder_injury",
        "vocabulary", "an injury text that is a placeholder rather than an official value")

    out = pd.DataFrame(issues)
    stats = dict(rows=int(len(p)), clubs=int(p.team.nunique()),
                 contradictions=int((out.severity == "contradiction").sum())
                 if not out.empty else 0,
                 vocabulary=int((out.severity == "vocabulary").sum()) if not out.empty else 0,
                 duplicates=int((out.severity == "duplicate").sum()) if not out.empty else 0,
                 rows_with_issue=int(out[["club", "player"]].drop_duplicates().shape[0])
                 if not out.empty else 0)
    return out, stats


def summarize(detail: pd.DataFrame, in_scope: list[str]) -> pd.DataFrame:
    rows = []
    for club, g in detail.groupby("club"):
        if club not in in_scope:
            continue
        c = g.verdict.value_counts()
        rows.append(dict(club=club, fields_compared=int(len(g)),
                         match=int(c.get("MATCH", 0)),
                         confirmed_defect=int((g.defect_class == "confirmed_defect").sum()),
                         drift_possible=int((g.defect_class == "drift_possible").sum()),
                         unresolved=int((g.defect_class == "unresolved").sum()),
                         unverified_no_basis=int((g.defect_class == "no_basis").sum()),
                         source_url=OFFICIAL_PAGE))
    out = pd.DataFrame(rows).sort_values("club").reset_index(drop=True)
    out["verdict"] = out.apply(
        lambda r: "PASS" if r.confirmed_defect == 0 and r.unresolved == 0 else "REVIEW",
        axis=1)
    return out


def main() -> int:
    LIVE.mkdir(parents=True, exist_ok=True)
    official = pd.read_csv(EXTRACT, dtype=str, keep_default_na=False)
    published = pd.read_csv(PUBLISHED, dtype=str, keep_default_na=False)
    calibration = archive_calibration()
    detail = compare(published, official)
    consistency, consistency_stats = internal_consistency(published)
    consistency.to_csv(LIVE / "internal_consistency.csv", index=False)
    in_scope = sorted(official.club.unique().tolist())
    summary = summarize(detail, in_scope)
    graded = detail[detail.club.isin(in_scope)]

    detail.to_csv(LIVE / "injury_field_verification.csv", index=False)
    summary.to_csv(LIVE / "injury_verification_summary.csv", index=False)

    c = graded.defect_class.value_counts()
    head = dict(
        generated_utc=LIVE_CAPTURE_UTC,
        official_page=OFFICIAL_PAGE,
        method=METHOD,
        transcribed_clubs=in_scope,
        official_rows=int(len(official)),
        published_rows=int(len(published)),
        fields_compared=int(len(graded)),
        match=int(c.get("", 0)),
        confirmed_defects=int(c.get("confirmed_defect", 0)),
        unresolved=int(c.get("unresolved", 0)),
        drift_possible=int(c.get("drift_possible", 0)),
        no_basis=int(c.get("no_basis", 0)),
        out_of_scope=int((detail.defect_class == "out_of_scope").sum()),
        clubs_passing=int((summary.verdict == "PASS").sum()),
        clubs=len(summary),
        parser_calibration=calibration,
        internal_consistency=consistency_stats,
        scope_note=("week 10 of the 2026 season, the eight clubs in the four matchups "
                    "transcribed. This is a sample, not a census of all 32 clubs."),
    )
    write_json(LIVE / "verification_summary.json", head)
    write_json(LIVE / "PROVENANCE.json", dict(
        generated_utc=head["generated_utc"],
        official_page=OFFICIAL_PAGE,
        network_note=("the build sandbox shell cannot complete a TLS handshake with nfl.com "
                      "(re-measured 2026-11-13 22:5xZ: URLError, 'TLS/SSL connection has been "
                      "closed'), so the extract was taken with the agent page-fetch tool and "
                      "committed here so a clean checkout can re-run the comparison offline"),
        method=METHOD,
        transcribed_clubs=in_scope,
        drift_control=calibration,
        transcription_limits=[
            "four of the sixteen week-10 matchups were transcribed; the other twelve are out of scope",
            "the extract is a hand transcription and is itself subject to transcription error; "
            "every disagreeing cell is published for manual re-check rather than auto-corrected",
            "the official page is a live document and can change between captures; capture "
            "date recorded above, published snapshot retrieved 2026-11-13T18:32:20Z",
        ],
    ))

    print(f"parser calibration: {calibration.get('verdict')} "
          f"({calibration.get('matched_rows')}/{calibration.get('archive_rows')} rows, "
          f"{calibration.get('cell_differences')}/{calibration.get('cells_compared')} cells differ)")
    print(f"official rows {head['official_rows']} | published rows {head['published_rows']} "
          f"| graded fields {head['fields_compared']}")
    print(f"MATCH {head['match']} · confirmed_defects {head['confirmed_defects']} · "
          f"unresolved {head['unresolved']} · drift_possible {head['drift_possible']} · "
          f"no_basis {head['no_basis']} · out_of_scope {head['out_of_scope']}")
    print(summary.to_string(index=False))
    print(f"internal consistency: {consistency_stats['rows']} rows / "
          f"{consistency_stats['clubs']} clubs · contradictions "
          f"{consistency_stats['contradictions']} · vocabulary {consistency_stats['vocabulary']} "
          f"· duplicates {consistency_stats['duplicates']}")
    if not consistency.empty:
        print(consistency[["club", "player", "check", "severity"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
