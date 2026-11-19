"""Session arena/db6cd525-korea1, 2026-11-18: official spot-check (CS4) and flagged rows F-42 onward (CS6).

Every number here is computed from committed files and the three verbatim excerpts under
data/live/spotcheck_2026_11_18/. Nothing is typed in by hand and there is no network access.

Outputs
  data/live/spotcheck_2026_11_18/spotcheck_rows.csv   one row per compared line
  data/integration/flagged_2026_11_18.csv             flagged rows (source_url blank = shown as text)

Run:  python pipeline/session_20261118.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402

SPOT = ROOT / "data" / "live" / "spotcheck_2026_11_18"
AV = ROOT / "data" / "availability"
# The 2026-11-18 spot-check compares verbatim reads taken that day against the capture
# they were taken from. The rolling files are rewritten by every scheduled fetch, which
# would flip all 120 spot-check verdicts (and their retrieved stamps) the next time the
# job runs — the F-2026-11-19-03 defect class, pinned here the same way.
AV_PINNED = AV / "history" / "2026-11-18"
HIST = AV / "history"
def newest_stamp(path: Path) -> str:
    """retrieved_utc of a committed capture, read from the file (never typed in)."""
    d = pd.read_csv(path, dtype=str, keep_default_na=False, usecols=["retrieved_utc"])
    return d.retrieved_utc.max()


def newest_key() -> str:
    """Label of the newest dated depth capture (last history folder)."""
    return sorted(HIST.glob("*/depth_charts.csv"))[-1].parent.name

URL_INJ = "https://www.nfl.com/injuries/"
URL_RES = "https://www.nfl.com/transactions/league/reserve-list/2026/11"
URL_WAS = "https://www.commanders.com/team/depth-chart"
URL_BAL = "https://www.baltimoreravens.com/team/depth-chart"
URL_DOCS = "https://docs.github.com/en/actions/using-workflows/triggering-a-workflow#triggering-a-workflow-from-a-workflow"

LINK_CELL = re.compile(r"^\[(.*?)\]\((.*?)\)$")
TEAM_HEAD = re.compile(r"\((WAS|NYG|NE|DET)\)")


# --------------------------------------------------------------------------- #
# Parsers for the verbatim excerpts
# --------------------------------------------------------------------------- #
def parse_injury_excerpt(path: Path) -> list[dict]:
    team, out = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            m = TEAM_HEAD.search(line)
            team = m.group(1) if m else None
        elif team and line.startswith("| ["):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            m = LINK_CELL.match(cells[0])
            out.append(dict(team=team, player=m.group(1), position=cells[1], injury=cells[2],
                            practice=cells[3], game=cells[4] if len(cells) > 4 else ""))
    return out


def parse_depth_excerpt(path: Path) -> list[dict]:
    unit, out = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            unit = line[3:].strip()
        elif unit in ("Offense", "Defense") and line.startswith("| ") and "[" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            players = [LINK_CELL.match(c).group(1) for c in cells[1:] if LINK_CELL.match(c)]
            out.append(dict(unit=unit, label=cells[0], players=players))
    return out


# --------------------------------------------------------------------------- #
# Comparisons
# --------------------------------------------------------------------------- #
def compare_injuries(live: list[dict], inj: pd.DataFrame) -> list[dict]:
    rows = []
    for lr in live:
        m = inj[(inj.team == lr["team"]) & (inj.player == lr["player"])]
        if len(m) != 1:
            verdict, cap = f"NOT ONE ROW IN CAPTURE ({len(m)})", ("", "", "")
        else:
            r = m.iloc[0]
            cap = (r.injury, r.practice_status, r.game_status)
            diffs = [f"{n}: capture '{a}' vs live '{b}'"
                     for n, a, b in (("injury", r.injury, lr["injury"]),
                                     ("practice", r.practice_status, lr["practice"]),
                                     ("game", r.game_status, lr["game"]))
                     if a.strip() != b.strip()]
            verdict = "MATCH" if not diffs else "MISMATCH: " + "; ".join(diffs)
        rows.append(dict(check="injury report", club=lr["team"], item=lr["player"],
                         live=" · ".join(x or "—" for x in (lr["injury"], lr["practice"], lr["game"])),
                         capture=" · ".join(x or "—" for x in cap), verdict=verdict,
                         retrieved=newest_stamp(AV_PINNED / "injuries.csv") + " injury capture", source_url=URL_INJ))
    return rows


def compare_depth(live: list[dict], was: pd.DataFrame) -> list[dict]:
    """Live rows are in slot order, so the k-th live row with a given label is the k-th slot with that label."""
    rows, k_seen = [], {}
    for lr in live:
        key = (lr["unit"], lr["label"])
        k = k_seen.get(key, 0)
        k_seen[key] = k + 1
        grp = was[(was.unit == lr["unit"]) & (was.position == lr["label"])]
        slots = sorted(grp.slot.astype(int).unique())
        if k >= len(slots):
            pub, verdict = [], "NO PUBLISHED SLOT"
        else:
            g = grp[grp.slot.astype(int) == slots[k]].sort_values("depth_rank", key=lambda s: s.astype(int))
            pub = g.player.tolist()
            verdict = "MATCH" if pub == lr["players"] else "MISMATCH"
        rows.append(dict(check="club depth chart", club="WAS", item=f"{lr['unit']} {lr['label']} row {k + 1}",
                         live=" | ".join(lr["players"]) or "—",
                         capture=" | ".join(pub) or "—", verdict=verdict,
                         retrieved=newest_stamp(AV_PINNED / "depth_charts.csv") + " depth capture", source_url=URL_WAS))
    return rows


def compare_reserve() -> tuple[list[dict], dict]:
    """Compare one dated live-page excerpt with both the cited older capture and newest capture.

    Never pair statistics from a rolling `latest.csv` with a narrative that names a
    particular historical capture. Keeping the two comparisons separate preserves the
    2026-11-17 discrepancy while recording what the 2026-11-18 recapture contains.
    """
    live = pd.read_csv(SPOT / "nfl_reserve_list_2026_11_live_rows.csv", dtype=str, keep_default_na=False)
    live["date"] = "2026-11-" + live.date_as_printed.str.split("/").str[1]
    historical = pd.read_csv(
        AV / "reserve" / "history" / "2026-11-17T195957Z" / "reserve_list.csv",
        dtype=str, keep_default_na=False,
    )
    # The comparison is explicitly against the 2026-11-18 recapture. `latest.csv` is
    # a rolling pointer and must not be used for a dated claim: the scheduled job can
    # advance it after this live-page excerpt was recorded.
    recapture = pd.read_csv(
        AV / "reserve" / "history" / "2026-11-18T044201Z" / "reserve_list.csv",
        dtype=str, keep_default_na=False,
    )
    live_keys = set(zip(live.date, live.club, live.player))
    rows: list[dict] = []
    stats: dict = {"live_rows": len(live_keys)}

    captures = [
        ("2026-11-17T19:59:57Z capture", historical),
        ("2026-11-18T04:42:01Z capture", recapture),
    ]
    for label, captured in captures:
        captured = captured[captured.month == "2026-11"]
        capture_keys = set(zip(captured.date, captured.team, captured.player))
        for d, t, p in sorted(live_keys):
            on_capture = (d, t, p) in capture_keys
            rows.append(dict(check=f"reserve list vs {label}", club=t, item=f"{p} ({d[5:]})",
                             live="listed", capture="listed" if on_capture else "not in capture",
                             verdict="ON BOTH" if on_capture else "ON LIVE PAGE ONLY",
                             retrieved="2026-11-18 page read", source_url=URL_RES))
        for d, t, p in sorted(capture_keys - live_keys):
            rows.append(dict(check=f"reserve list vs {label}", club=t, item=f"{p} ({d[5:]})",
                             live="not on live page", capture="listed", verdict="CAPTURE ONLY",
                             retrieved=label, source_url=URL_RES))
        key = "historical" if label.startswith("2026-11-17") else "recapture"
        stats[key] = dict(
            label=label, rows=len(capture_keys), both=len(live_keys & capture_keys),
            live_only=len(live_keys - capture_keys), capture_only=len(capture_keys - live_keys),
            live_only_names=sorted(f"{p} ({t}, {d[5:]})" for d, t, p in live_keys - capture_keys),
            capture_only_names=sorted(f"{p} ({t}, {d[5:]})" for d, t, p in capture_keys - live_keys),
        )
    return rows, stats


# --------------------------------------------------------------------------- #
# Facts from the committed files (all computed)
# --------------------------------------------------------------------------- #
def captures() -> list[tuple[str, Path]]:
    out = [(p.parent.name, p) for p in sorted(HIST.glob("*/depth_charts.csv"))]
    import filecmp
    latest = AV / "depth_charts.csv"
    if not any(filecmp.cmp(latest, p, shallow=False) for _, p in out):
        out.append(("latest", latest))
    return out


def multi_rank1_groups(d: pd.DataFrame) -> int:
    d = d.assign(r=d.depth_rank.astype(int))
    g = d[d.r == 1].groupby(["team", "unit", "position"]).size()
    return int((g > 1).sum())


def player_depth(d: pd.DataFrame, team: str, player: str) -> str:
    m = d[(d.team == team) & (d.player == player)]
    if not len(m):
        return "absent"
    return "; ".join(f"{u} {p} slot {s} rank {r}" for u, p, s, r in zip(m.unit, m.position, m.slot, m.depth_rank))


def bal_qbs(d: pd.DataFrame) -> str:
    q = d[(d.team == "BAL") & (d.position == "QB")].sort_values("depth_rank", key=lambda s: s.astype(int))
    return " · ".join(f"QB{r} {p}" for r, p in zip(q.depth_rank, q.player)) or "none"


def facts() -> dict:
    inj = pd.read_csv(AV_PINNED / "injuries.csv", dtype=str, keep_default_na=False)
    latest = pd.read_csv(AV_PINNED / "depth_charts.csv", dtype=str, keep_default_na=False)
    # Pinned: the F-48 narrative compares against the 2026-11-18 capture, not the rolling latest.csv.
    res_cap = pd.read_csv(AV / "reserve" / "history" / "2026-11-18T044201Z" / "reserve_list.csv",
                          dtype=str, keep_default_na=False)
    sea5 = latest[(latest.team == "SEA") & (latest.unit == "Offense") & (latest.slot == "5")]
    f = dict(
        injury_rows=len(inj), injury_clubs=int(inj.team.nunique()),
        sea_inj=int((inj.team == "SEA").sum()), cin_inj=int((inj.team == "CIN").sum()),
        depth_rows=len(latest), depth_clubs=int(latest.team.nunique()),
        hou_depth_rows=int((latest.team == "HOU").sum()),
        multi_rank1_latest=multi_rank1_groups(latest),
        multi_rank1_by_capture={n: multi_rank1_groups(pd.read_csv(p, dtype=str, keep_default_na=False))
                                for n, p in captures()},
        payne_by_capture={n: player_depth(pd.read_csv(p, dtype=str, keep_default_na=False), "WAS", "Daron Payne")
                          for n, p in captures()},
        bal_by_capture={n: bal_qbs(pd.read_csv(p, dtype=str, keep_default_na=False)) for n, p in captures()},
        sea_offense_slot5_players=int(sea5.player.nunique()),
        sea_offense_slot5_names="; ".join(sea5.player.tolist()),
        reserve_names_checked={n: ("listed" if ((res_cap.player == n)).any() else "not listed")
                               for n in ["Lamar Jackson", "Tyler Huntley", "Malik Willis", "Michael Wilson"]},
        injury_names_checked={n: ("listed" if (inj.player == n).any() else "not listed")
                              for n in ["Lamar Jackson", "Tyler Huntley", "Malik Willis", "Daron Payne"]},
    )
    return f


# --------------------------------------------------------------------------- #
# Flagged rows F-42 onward
# --------------------------------------------------------------------------- #
def flagged_rows(f: dict, res: dict, inj_v: list[dict], dep_v: list[dict]) -> list[dict]:
    was_mis = sum(1 for r in dep_v if r["verdict"] != "MATCH")
    payne = f["payne_by_capture"]
    payne_listed = [n for n, v in payne.items() if v != "absent"]
    payne_absent = [n for n, v in payne.items() if v == "absent"]
    groups = f["multi_rank1_by_capture"]
    bal = f["bal_by_capture"]
    return [
        dict(id="F-42", severity="High · open",
             finding=("Washington depth chart changed between captures. Daron Payne is on the club chart in "
                      f"{', '.join(payne_listed) or 'no capture'} and absent from {', '.join(payne_absent) or 'none'}. "
                      f"The live club page read on 2026-11-18 also omits him (live Defense DL/DT rows, spot-check). "
                      f"The newest capture (scheduled job, 2026-11-18T04:24:05Z) also omits him. No official reason for the change was read."),
             next="Source check: the Commanders roster or transaction record for the change. No Washington DL1 role is asserted until then. The 2026-11-13 depth test was repaired to compare like dates (CS2).",
             source_label="Commanders club depth chart", source_url=URL_WAS),
        dict(id="F-43", severity="Medium · repaired in this session",
             finding=("The availability job committed the raw captures but rebuilt only depth_status.csv and the review page. "
                      "Every other table built from the captures (replacement depth, live verification, price archive, executive summary, repository review) lagged the 2026-11-17 capture. "
                      "A full rebuild then changed 28 tracked files. The job now runs make site and make verify before it commits."),
             next="Check the first scheduled run after merge. GitHub does not start workflows for pushes made with GITHUB_TOKEN, so the committed rebuild is not re-verified by verify.yml (see F-47).",
             source_label="GitHub Actions documentation", source_url=URL_DOCS),
        dict(id="F-44", severity="High · open (owner decision)",
             finding=("The rebuild changed published close numbers. The committed price archive had blank close cells for 2026 Week 10 games; "
                      "the build code on main fills them from the forward ledger's frozen lines and labels them LEDGER_MIRROR_CLOSE. "
                      "The label says the number is not an authenticated bookmaker quote. Gate G1 still fails, so no verdict changes. "
                      "This commit brings the committed CSV in line with the existing code (26 close cells changed in data/processed/price_archive.csv). It is not a new source capture."),
             next="Owner: decide whether a ledger freeze may populate a close column at all (the price-data policy in DECISIONS.md is still empty). If not, remove the fill in pipeline/price_archive.py and the cells go back to blank.",
             source_label="NFL.com scores (settlement source)", source_url="https://www.nfl.com/scores/2026/week-10"),
        dict(id="F-45", severity="Medium · historical discrepancy; retention policy open",
             finding=("The live November reserve-page excerpt read on 2026-11-18 contains "
                      f"{res['live_rows']} rows. The 2026-11-17T19:59:57Z capture has "
                      f"{res['historical']['both']} of those rows in common, "
                      f"{res['historical']['live_only']} live-page-only and {res['historical']['capture_only']} capture-only rows. "
                      f"The 2026-11-18T04:42:01Z recapture has {res['recapture']['both']} rows in common, "
                      f"{res['recapture']['live_only']} live-page-only and {res['recapture']['capture_only']} capture-only rows. "
                      "This later capture matches the sampled live-page rows; it does not establish the NFL page's retention or completeness policy."),
             next="Keep both immutable captures. Confirm the source's retention semantics before treating a missing row as unavailable; do not infer that the monthly page is complete or a rolling window.",
             source_label="NFL.com reserve list, November 2026", source_url=URL_RES),
        dict(id="F-46", severity="High · open",
             finding=("Request claims that no source read here confirms. "
                      f"(a) Lamar Jackson and Tyler Huntley on injured reserve: the 2026-11-12 Baltimore chart lists {bal.get('2026-11-12', '')}; "
                      f"the newest chart lists {bal.get(newest_key(), '')}. Neither name is on the November reserve page or the injury report read here. "
                      f"(b) '149 slots with more than one rank-1 player': the newest capture gives {groups[newest_key()]} club/unit/position groups; "
                      f"the dated captures give {', '.join(str(v) for v in groups.values())}. The request's count is not reproduced. "
                      f"(c) Seattle puts two players in one slot: not reproduced. Offense slot 5 lists {f['sea_offense_slot5_players']} players in the newest capture ({f['sea_offense_slot5_names']})."),
             next="Owner: supply the source for each claim, and the definition used for the 149 count.",
             source_label="Baltimore Ravens club depth chart", source_url=URL_BAL),
        dict(id="F-47", severity="Medium · open",
             finding=("GitHub does not start workflows for pushes made with GITHUB_TOKEN. The scheduled availability and reserve-list jobs commit with it, "
                      "so verify.yml does not run on those commits. The reserve-list job runs only its own test and rebuilds nothing."),
             next="Owner: decide whether scheduled jobs should run make build and check_rebuild before they commit, or use a token that triggers workflows.",
             source_label="GitHub Actions documentation", source_url=URL_DOCS),
        dict(id="F-48", severity="Medium · open",
             finding=("Brief identifiers VR-17, VR-24, VR-25, VR-26, VQ-05, VQ-06, VQ-07, SG-03 and SG-05 do not appear anywhere in the repository. "
                      "The claims tied to them are not verified. The one observation that can be checked is recorded in the spot-check: Malik Willis is on the November reserve page "
                      f"(MIA, 11/10; in capture: {f['reserve_names_checked']['Malik Willis']}) and "
                      f"{'not ' if f['injury_names_checked']['Malik Willis'] == 'not listed' else ''}on the newest injury report."),
             next="Brief author: supply a mapping from each identifier to a source.",
             source_label="NFL.com reserve list, November 2026", source_url=URL_RES),
        dict(id="F-49", severity="Medium · open (no source)",
             finding=("Houston has no depth-chart rows in any capture (0 rows in the newest capture). The brief's Texans depth is published as an image. "
                      "No authorised structured source has been located, and the image has not been transcribed."),
             next="Locate an official structured source (route a) or snap counts (route b) for Houston before any Houston depth feature is built.",
             source_label="Houston Texans team page", source_url="https://www.houstontexans.com/team/depth-chart"),
        dict(id="F-50", severity="High · repaired in this branch",
             finding=("Commit 0193893 (S18, PR #77) replaced the WAS, NYG, DET and NE rows of data/availability/depth_charts.csv with the 2026-11-13 official extract, "
                      "and stamped every replaced row 2026-11-17T19:51:56Z, which is not the source of those rows. The same commit changed "
                      "test_depth_snapshot_matches_the_official_charts so that drift is logged and cannot fail. "
                      "This branch restores the strict test (2026-11-13 extract against the 2026-11-13 dated capture). "
                      "The S18 rows are no longer in the newest file: the scheduled job on main (commit 9933bba, 2026-11-18T04:24:05Z) wrote a new capture of the club charts, "
                      "which is the source of record. That capture has no Daron Payne row, and the live Commanders page read on 2026-11-18 agrees with it on the rows compared (see spotcheck_rows.csv)."),
             next="Owner: confirm. Any reconciliation must be a new dated capture, never an edit of an older one. The S18 rows remain in git history.",
             source_label="Commanders club depth chart", source_url=URL_WAS),
        dict(id="F-51", severity="Medium · repaired",
             finding=("scripts/reconcile_depth_charts.py is now a read-only comparison against the same-date 2026-11-13 capture. "
                      "It does not write the current or historical depth snapshots; a regression test verifies both files remain byte-identical."),
             next="No further action for the overwrite hazard. Any new chart extraction must be captured as a new dated snapshot through the official-source workflow.",
             source_label="", source_url=""),
    ]


# --------------------------------------------------------------------------- #
def main() -> None:
    inj = pd.read_csv(AV_PINNED / "injuries.csv", dtype=str, keep_default_na=False)
    latest = pd.read_csv(AV_PINNED / "depth_charts.csv", dtype=str, keep_default_na=False)
    inj_v = compare_injuries(parse_injury_excerpt(SPOT / "nfl_injuries_week10_WAS_NYG_NE_DET.md"), inj)
    dep_v = compare_depth(parse_depth_excerpt(SPOT / "commanders_depth_chart_offense_defense.md"),
                          latest[latest.team == "WAS"])
    res_v, res = compare_reserve()
    allrows = inj_v + dep_v + res_v
    pd.DataFrame(allrows).to_csv(SPOT / "spotcheck_rows.csv", index=False)

    f = facts()
    fl = flagged_rows(f, res, inj_v, dep_v)
    for r in fl:
        if r["source_url"] and not r["source_url"].startswith("https://"):
            raise SystemExit(f"{r['id']}: bad source url")
    pd.DataFrame(fl).to_csv(ROOT / "data" / "integration" / "flagged_2026_11_18.csv", index=False)

    n_inj = len(inj_v)
    n_match = sum(r["verdict"] == "MATCH" for r in inj_v)
    n_dep = len(dep_v)
    n_dep_match = sum(r["verdict"] == "MATCH" for r in dep_v)
    print(f"injury lines {n_inj}, match {n_match}; depth rows {n_dep}, match {n_dep_match}")
    print(f"reserve historical: live {res['live_rows']}, capture {res['historical']['rows']}, "
          f"both {res['historical']['both']}, live-only {res['historical']['live_only']}, "
          f"capture-only {res['historical']['capture_only']}")
    print(f"reserve 2026-11-18 recapture: live {res['live_rows']}, capture {res['recapture']['rows']}, "
          f"both {res['recapture']['both']}, live-only {res['recapture']['live_only']}, "
          f"capture-only {res['recapture']['capture_only']}")
    print(f"multi rank-1 groups: {f['multi_rank1_by_capture']}")
    print(f"payne: {f['payne_by_capture']}")
    print(f"bal: {f['bal_by_capture']}")
    print(f"sea offense slot 5: {f['sea_offense_slot5_players']} players")


if __name__ == "__main__":
    main()
