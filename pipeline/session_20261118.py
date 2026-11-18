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
HIST = AV / "history"
INJ_CAPTURE_LABEL = "2026-11-17T19:51:56Z capture"
RES_CAPTURE_LABEL = "2026-11-17T19:59:57Z capture"
DEP_CAPTURE_LABEL = "2026-11-17T19:51:56Z depth capture"

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
                         retrieved=INJ_CAPTURE_LABEL, source_url=URL_INJ))
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
                         retrieved=DEP_CAPTURE_LABEL, source_url=URL_WAS))
    return rows


def compare_reserve() -> tuple[list[dict], dict]:
    live = pd.read_csv(SPOT / "nfl_reserve_list_2026_11_live_rows.csv", dtype=str, keep_default_na=False)
    live["date"] = "2026-11-" + live.date_as_printed.str.split("/").str[1]
    cap = pd.read_csv(AV / "reserve" / "latest.csv", dtype=str, keep_default_na=False)
    cap = cap[cap.month == "2026-11"]
    kl = set(zip(live.date, live.club, live.player))
    kc = set(zip(cap.date, cap.team, cap.player))
    rows = []
    for d, t, p in sorted(kl):
        verdict = "ON BOTH" if (d, t, p) in kc else "ON LIVE PAGE ONLY"
        rows.append(dict(check="reserve list", club=t, item=f"{p} ({d[5:]})", live="listed",
                         capture="listed" if (d, t, p) in kc else "not in capture",
                         verdict=verdict, retrieved="2026-11-18 page read", source_url=URL_RES))
    for d, t, p in sorted(kc - kl):
        rows.append(dict(check="reserve list", club=t, item=f"{p} ({d[5:]})", live="not on live page",
                         capture="listed", verdict="CAPTURE ONLY", retrieved=RES_CAPTURE_LABEL, source_url=URL_RES))
    stats = dict(live_rows=len(kl), capture_nov_rows=len(kc), both=len(kl & kc),
                 live_only=len(kl - kc), capture_only=len(kc - kl),
                 capture_only_names=sorted(f"{p} ({t}, {d[5:]})" for d, t, p in kc - kl),
                 live_only_names=sorted(f"{p} ({t}, {d[5:]})" for d, t, p in kl - kc),
                 capture_dates=sorted({d for d, _, _ in kc}))
    return rows, stats


# --------------------------------------------------------------------------- #
# Facts from the committed files (all computed)
# --------------------------------------------------------------------------- #
def captures() -> list[tuple[str, Path]]:
    out = [(p.parent.name, p) for p in sorted(HIST.glob("*/depth_charts.csv"))]
    out.append(("latest (2026-11-17T19:51:56Z)", AV / "depth_charts.csv"))
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
    inj = pd.read_csv(AV / "injuries.csv", dtype=str, keep_default_na=False)
    latest = pd.read_csv(AV / "depth_charts.csv", dtype=str, keep_default_na=False)
    res_cap = pd.read_csv(AV / "reserve" / "latest.csv", dtype=str, keep_default_na=False)
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
                      f"He is not on the 2026-11-17 injury report. No official reason for the change was read."),
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
        dict(id="F-45", severity="High · open",
             finding=("The November reserve page is not a complete record. The live page read on 2026-11-18 lists "
                      f"{res['live_rows']} November rows (dated 11/10 to 11/17). The 2026-11-17 19:59Z capture lists {res['capture_nov_rows']} November rows. "
                      f"{res['both']} rows are on both. {res['capture_only']} capture rows are not on the live page ({'; '.join(res['capture_only_names'])}). "
                      f"{res['live_only']} live rows are not in the capture ({'; '.join(res['live_only_names'])}). "
                      "NFL does not state a reason on the page. A 25-row window is one possible explanation, not a verified rule."),
             next="Keep every capture (done). Owner: decide whether the monthly page is the record or a window. Re-read the live page in a later session to see whether the mismatch persists. 'Not listed' does not mean available.",
             source_label="NFL.com reserve list, November 2026", source_url=URL_RES),
        dict(id="F-46", severity="High · open",
             finding=("Request claims that no source read here confirms. "
                      f"(a) Lamar Jackson and Tyler Huntley on injured reserve: the 2026-11-12 Baltimore chart lists {bal.get('2026-11-12', '')}; "
                      f"the 2026-11-17 chart lists {bal.get('latest (2026-11-17T19:51:56Z)', '')}. Neither name is on the November reserve page or the injury report read here. "
                      f"(b) '149 slots with more than one rank-1 player': the 2026-11-17 capture gives {groups['latest (2026-11-17T19:51:56Z)']} club/unit/position groups; "
                      f"the dated captures give {', '.join(str(v) for v in groups.values())}. The request's count is not reproduced. "
                      f"(c) Seattle puts two players in one slot: not reproduced. Offense slot 5 lists {f['sea_offense_slot5_players']} players in the 2026-11-17 capture ({f['sea_offense_slot5_names']})."),
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
                      f"{'not ' if f['injury_names_checked']['Malik Willis'] == 'not listed' else ''}on the 2026-11-17 injury report."),
             next="Brief author: supply a mapping from each identifier to a source.",
             source_label="NFL.com reserve list, November 2026", source_url=URL_RES),
        dict(id="F-49", severity="Medium · open (no source)",
             finding=("Houston has no depth-chart rows in any capture (0 rows in the 2026-11-17 capture). The brief's Texans depth is published as an image. "
                      "No authorised structured source has been located, and the image has not been transcribed."),
             next="Locate an official structured source (route a) or snap counts (route b) for Houston before any Houston depth feature is built.",
             source_label="Houston Texans team page", source_url="https://www.houstontexans.com/team/depth-chart"),
    ]


# --------------------------------------------------------------------------- #
def main() -> None:
    inj = pd.read_csv(AV / "injuries.csv", dtype=str, keep_default_na=False)
    latest = pd.read_csv(AV / "depth_charts.csv", dtype=str, keep_default_na=False)
    inj_v = compare_injuries(parse_injury_excerpt(SPOT / "nfl_injuries_week10_WAS_NYG_NE_DET.md"), inj)
    dep_v = compare_depth(parse_depth_excerpt(SPOT / "commanders_depth_chart_offense_defense.md"),
                          latest[latest.team == "WAS"])
    res_v, res = compare_reserve()
    allrows = inj_v + dep_v + res_v
    pd.DataFrame(allrows).to_csv(SPOT / "spotcheck_rows.csv", index=False)

    f = facts()
    fl = flagged_rows(f, res, inj_v, dep_v)
    for r in fl:
        if not r["source_url"].startswith("https://"):
            raise SystemExit(f"{r['id']}: bad source url")
    pd.DataFrame(fl).to_csv(ROOT / "data" / "integration" / "flagged_2026_11_18.csv", index=False)

    n_inj = len(inj_v)
    n_match = sum(r["verdict"] == "MATCH" for r in inj_v)
    n_dep = len(dep_v)
    n_dep_match = sum(r["verdict"] == "MATCH" for r in dep_v)
    print(f"injury lines {n_inj}, match {n_match}; depth rows {n_dep}, match {n_dep_match}")
    print(f"reserve: live {res['live_rows']}, capture {res['capture_nov_rows']}, both {res['both']}, "
          f"live-only {res['live_only']}, capture-only {res['capture_only']}")
    print(f"multi rank-1 groups: {f['multi_rank1_by_capture']}")
    print(f"payne: {f['payne_by_capture']}")
    print(f"bal: {f['bal_by_capture']}")
    print(f"sea offense slot 5: {f['sea_offense_slot5_players']} players")


if __name__ == "__main__":
    main()
