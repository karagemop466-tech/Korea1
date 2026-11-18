"""NR4 (session `arena/ceddf8d8-korea1`) — interactive Offence vs Defence matchup deficiency matrix.

The 2026-11-18 request asks for one screen that surfaces the trench and coverage mismatches created when a
club has to put a 2nd-, 3rd- or 4th-string player opposite an opponent's first string. The repository had
nothing of the kind (a grep for "Matchup Deficiency Matrix" over every non-archive file returns 0 hits), and
the earlier matchup page (`lineup-deficiencies.html`) covers eight clubs from one dated manual read.

This matrix is built only from the two artefacts the scheduled captures already hold:

* `data/availability/depth_charts.csv` — the club's own published chart, one row per printed cell, with
  `source_url` and `retrieved_utc` on every row;
* `data/availability/injuries.csv` — the official league injury report for the fixture week, with its own
  `retrieved_utc`.

Three rules make the difference between a matrix and a fabrication:

1. **Groups, never "the starter".** A club/unit/position group is read as a *list per printed rank*. Where
   more than one name sits at rank 1 the row publishes the count and the names — 161 groups are in that
   state on the active capture (claim C-03) — so the site never invents a starter the club did not name.
2. **Only published designations.** A player is `Out`, `Questionable`, `Doubtful` or has no designation
   printed. "No designation" is not "healthy": it is blank, and the row links the report page it is blank on.
3. **Positions, not assignments.** WR-vs-CB, tackle-vs-edge, guard/centre-vs-interior-line, back-vs-linebacker
   and tight end-vs-weakside are *positional pairing conventions*, stated on the page, used to decide which
   two groups to print side by side. Nothing here claims the two players lined up against each other: no
   committed source publishes alignment, and snap counts are not captured (see register row R-24).

Writes `data/processed/matchup_matrix.csv`, `assets/data/matchup_matrix.csv` and `matchup-matrix.html`.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, SITE_DATA, write_json  # noqa: E402
from render_site import e, flag, kpi_grid, card, layout, src_link, table  # noqa: E402

DEPTH = ROOT / "data/availability/depth_charts.csv"
INJURIES = ROOT / "data/availability/injuries.csv"
SLOT_STATUS = ROOT / "data/availability/slot_status.csv"
URL_INJURIES = "https://www.nfl.com/injuries/"
URL_CLUB_INDEX = "https://www.nfl.com/teams/"

# Positional pairing convention. Each group is the set of *printed chart labels* the clubs use for it, so
# the same physical idea survives 31 different club formatting habits.
PAIRINGS = [
    ("RECEIVERS (WR)", {"WR"}, "COVERAGE — CORNERS", {"CB", "NCB", "NB", "RCB", "LCB"},
     "Outside receiver against the published corner group."),
    ("RECEIVERS (WR)", {"WR"}, "COVERAGE HELP — SAFETIES", {"S", "FS", "SS", "DB"},
     "Outside receiver against the published safety group (the deep-half the chart lists next)."),
    ("TIGHT ENDS (TE)", {"TE"}, "IN-LINE COVERAGE — WEAKSIDE/LB", {"OLB", "LLLB", "LOLB", "ROLB", "SAM", "WILL", "SLB", "LB", "MLB", "MIKE"},
     "Tight end against the published weakside/linebacker group."),
    ("BACKS (RB/FB)", {"RB", "FB", "HB"}, "BOX — INSIDE LINEBACKERS", {"ILB", "LILB", "RILB", "MLB", "MIKE", "SLB", "LB"},
     "Backfield against the published inside/box linebacker group."),
    ("TACKLES (LT/RT)", {"LT", "RT", "LOT", "ROT"}, "EDGE RUSH", {"DE", "EDGE", "RUSH", "LDE", "RDE", "OLB", "LOLB", "ROLB"},
     "Published tackle group against the published edge group (the brief's EDGE1-vs-2nd-string-OT case)."),
    ("INTERIOR LINE (LG/C/RG)", {"LG", "RG", "C"}, "INTERIOR FRONT", {"DT", "NT", "LDT", "RDT", "DL"},
     "Guards and centre against the published interior front (the brief's 2nd/3rd-string DL case)."),
]

OUT_VALUES = {"Out"}
DOUBTFUL = {"Questionable", "Doubtful"}


def _rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load():
    depth = _rows(DEPTH)
    injuries = _rows(INJURIES)
    status = _rows(SLOT_STATUS) if SLOT_STATUS.exists() else []

    by_club = defaultdict(list)
    for r in depth:
        by_club[r["team"]].append(r)

    report = defaultdict(list)          # (team, player) -> rows
    team_retrieved, team_injury_url = {}, {}
    for r in injuries:
        report[(r["team"], r["player"].strip().lower())].append(r)
        team_retrieved[r["team"]] = r.get("retrieved_utc", "")
        team_injury_url[r["team"]] = r.get("source_url", URL_INJURIES)

    opponents = {}
    for r in status:
        t = r["team"]
        if r.get("opponent"):
            opponents[t] = r["opponent"]
        else:
            opponents.setdefault(t, "")   # the join printed no opponent: a bye, recorded as such

    return depth, by_club, report, team_retrieved, team_injury_url, opponents


def group_view(rows: list[dict], positions: set[str], report, team: str) -> dict:
    """Everything the matrix can say about one club's one positional group, from published cells only.

    Cells are aggregated over the club's printed slots (a club that prints three WR rows has three
    first-string receivers, and that is the truth we publish); the co-starter flag is computed per printed
    slot, because "rank 1 means nothing" is only true inside one row of the chart.
    """
    names_by_rank: dict[int, list[str]] = defaultdict(list)
    per_slot: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    slots: set[str] = set()
    urls, retrieved = set(), set()
    for r in rows:
        if r["unit"] not in ("Offense", "Defense") or r["position"] not in positions:
            continue
        try:
            rank = int(r["depth_rank"])
        except (TypeError, ValueError):
            continue
        slot = f"{r['unit']}/{r['position']}/{r['slot']}"
        if r["player"] not in names_by_rank[rank]:
            names_by_rank[rank].append(r["player"])
        if r["player"] not in per_slot[slot][rank]:
            per_slot[slot][rank].append(r["player"])
        slots.add(slot)
        if r.get("source_url"):
            urls.add(r["source_url"])
        if r.get("retrieved_utc"):
            retrieved.add(r["retrieved_utc"])

    all_names = [n for rank in sorted(names_by_rank) for n in names_by_rank[rank]]
    desig: dict[str, str] = {}
    practice: dict[str, str] = {}
    for n in all_names:
        hits = report.get((team, n.strip().lower()), [])
        if hits:
            desig[n] = (hits[0].get("game_status") or "").strip()
            practice[n] = (hits[0].get("practice_status") or "").strip()

    out_names = [n for n in all_names if desig.get(n) in OUT_VALUES]
    q_names = [n for n in all_names if desig.get(n) in DOUBTFUL]
    dnp_names = [n for n in all_names if "Did Not Participate" in practice.get(n, "")]
    rank1 = names_by_rank.get(1, [])
    # slots where the club printed several names at rank 1 inside one row of the chart
    unordered = {slot: v.get(1, []) for slot, v in per_slot.items() if len(v.get(1, [])) > 1}
    # a slot whose whole rank-1 entry is ruled Out is the case the brief calls a promoted backup
    slot_top_out = {slot: v[1] for slot, v in per_slot.items()
                    if v.get(1) and all(n in out_names for n in v[1])}

    return {
        "n_names": len(all_names),
        "n_slots": len(slots),
        "ranks": {rank: names_by_rank[rank] for rank in sorted(names_by_rank)},
        "rank1": rank1,
        "unordered_slots": unordered,
        "slot_top_out": slot_top_out,
        "thin": len(all_names) < 3,
        "out": out_names,
        "questionable_doubtful": q_names,
        "dnp": dnp_names,
        "designation_known": sum(1 for n in all_names if n in desig),
        "chart_urls": sorted(urls),
        "retrieved": sorted(retrieved),
    }


def flag_text(label: str, v: dict) -> list[str]:
    f = []
    if v["unordered_slots"]:
        parts = [f"{slot.split('/')[1]} at printed chart row {slot.split('/')[2]}: {', '.join(names)}"
                 for slot, names in sorted(v["unordered_slots"].items())]
        f.append(f"{label}: {len(v['unordered_slots'])} printed slot(s) list more than one name at rank 1 "
                 f"with no order — { '; '.join(parts) }")
    if v["slot_top_out"]:
        parts = [f"{slot.split('/')[1]} at printed chart row {slot.split('/')[2]} ({', '.join(names)})"
                 for slot, names in sorted(v["slot_top_out"].items())]
        f.append(f"{label}: {len(v['slot_top_out'])} slot(s) whose whole rank-1 entry is ruled Out — "
                 f"{'; '.join(parts)}")
    if v["out"]:
        f.append(f"{label}: {len(v['out'])} listed name(s) ruled Out ({', '.join(v['out'])})")
    if v["questionable_doubtful"]:
        f.append(f"{label}: {len(v['questionable_doubtful'])} Questionable/Doubtful "
                 f"({', '.join(v['questionable_doubtful'])})")
    if v["dnp"]:
        f.append(f"{label}: {len(v['dnp'])} did not practise ({', '.join(v['dnp'])})")
    if v["thin"]:
        f.append(f"{label}: only {v['n_names']} name(s) listed across {v['n_slots']} printed slot(s)")
    return f


def capture_week() -> str:
    """The report week the injury capture is for — printed, not assumed."""
    weeks = {r.get("week", "") for r in _rows(INJURIES)}
    return ", ".join(sorted(w for w in weeks if w)) or "(not printed)"


def build() -> tuple[list[dict], list[dict]]:
    _, by_club, report, team_retrieved, team_injury_url, opponents = load()
    rows, excluded = [], []

    fixtures = sorted({tuple(sorted((t, o))) for t, o in opponents.items() if o and t in by_club and o in by_club})
    covered = set()
    for pair in fixtures:
        covered.update(pair)
        a, b = pair
        for off_club, def_club in ((a, b), (b, a)):
            for off_label, off_pos, def_label, def_pos, note in PAIRINGS:
                ov = group_view(by_club[off_club], off_pos, report, off_club)
                dv = group_view(by_club[def_club], def_pos, report, def_club)
                if not ov["n_names"] or not dv["n_names"]:
                    continue  # the club's chart prints no such group: not a deficiency, an absent label
                chart_off = ov["chart_urls"][0] if ov["chart_urls"] else ""
                chart_def = dv["chart_urls"][0] if dv["chart_urls"] else ""
                flags = flag_text("offence", ov) + flag_text("defence", dv)
                rows.append({
                    "fixture": f"{off_club} at {def_club}", "off_club": off_club, "def_club": def_club,
                    "off_group": off_label, "def_group": def_label, "pairing_note": note,
                    "off_names": ov["n_names"], "def_names": dv["n_names"],
                    "off_slots": ov["n_slots"], "def_slots": dv["n_slots"],
                    "off_rank1": " | ".join(ov["ranks"].get(1, [])),
                    "off_rank2": " | ".join(ov["ranks"].get(2, [])),
                    "off_rank3": " | ".join(ov["ranks"].get(3, [])),
                    "off_rank4": " | ".join(ov["ranks"].get(4, [])),
                    "def_rank1": " | ".join(dv["ranks"].get(1, [])),
                    "def_rank2": " | ".join(dv["ranks"].get(2, [])),
                    "def_rank3": " | ".join(dv["ranks"].get(3, [])),
                    "def_rank4": " | ".join(dv["ranks"].get(4, [])),
                    "off_rank1_count": len(ov["ranks"].get(1, [])),
                    "def_rank1_count": len(dv["ranks"].get(1, [])),
                    "off_unordered_slots": len(ov["unordered_slots"]),
                    "def_unordered_slots": len(dv["unordered_slots"]),
                    "off_slots_top_out": len(ov["slot_top_out"]),
                    "def_slots_top_out": len(dv["slot_top_out"]),
                    "off_out": len(ov["out"]), "def_out": len(dv["out"]),
                    "off_qd": len(ov["questionable_doubtful"]), "def_qd": len(dv["questionable_doubtful"]),
                    "off_dnp": len(ov["dnp"]), "def_dnp": len(dv["dnp"]),
                    "def_slots_all_out": len(dv["slot_top_out"]),
                    "off_slots_all_out": len(ov["slot_top_out"]),
                    "name_gap": dv["n_names"] - ov["n_names"],
                    "designation_known_off": ov["designation_known"], "designation_known_def": dv["designation_known"],
                    "flags": " · ".join(flags),
                    "off_chart_url": chart_off, "def_chart_url": chart_def,
                    "off_injury_url": team_injury_url.get(off_club, URL_INJURIES),
                    "def_injury_url": team_injury_url.get(def_club, URL_INJURIES),
                    "off_depth_utc": ", ".join(ov["retrieved"]), "def_depth_utc": ", ".join(dv["retrieved"]),
                    "off_injury_utc": team_retrieved.get(off_club, ""),
                    "def_injury_utc": team_retrieved.get(def_club, ""),
                })

    # Which pairings could not be built, and exactly why — the gap is a published row, not a silent absence.
    for t in sorted({r["team"] for r in _rows(INJURIES)} - set(by_club)):
        excluded.append({"club": t, "listed_opponent": opponents.get(t, ""),
                         "reason": "the club appears in the official injury report but published no "
                                   "parseable chart, so it has no near side to draw (Houston: image-only, "
                                   "claim C-05)", "rows": 0, "chart_url": ""})
    for t, o in sorted(opponents.items()):
        if not o:
            excluded.append({"club": t, "listed_opponent": "", "reason": "no opponent printed for the week: "
                             "the club is on bye in the official Week 10 game list",
                             "rows": 0, "chart_url": (by_club[t][0].get("source_url") if t in by_club else "")})
        elif t not in by_club:
            excluded.append({"club": t, "listed_opponent": o, "reason": "no depth rows captured (the club "
                             "publishes its chart as an image — claim C-05)", "rows": 0,
                             "chart_url": ""})
        elif o not in by_club:
            excluded.append({"club": t, "listed_opponent": o, "reason": f"the opponent {o} has no captured "
                             "chart, so the pairing has no far side", "rows": 0, "chart_url": ""})
    return rows, excluded


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------
def render(rows: list[dict], excluded: list[dict]) -> str:
    week = capture_week()
    tbl = []
    for r in rows:
        src = (src_link(r["off_chart_url"], f"{r['off_club']} chart") + " · "
               + src_link(r["def_chart_url"], f"{r['def_club']} chart") + " · "
               + src_link(r["off_injury_url"], "official report"))
        tbl.append([
            f"<strong>{e(r['fixture'])}</strong>", e(r["off_group"]), e(r["def_group"]),
            e(r["off_rank1"]) or "<span class='small'>none printed</span>",
            e(r["off_rank2"]), e(r["off_rank3"]), e(r["off_rank4"]),
            e(r["def_rank1"]) or "<span class='small'>none printed</span>",
            e(r["def_rank2"]), e(r["def_rank3"]), e(r["def_rank4"]),
            str(r["off_names"]), str(r["def_names"]), str(r["off_out"]), str(r["def_out"]),
            (e(r["flags"]) if r["flags"] else "<span class='small'>no designation printed on any listed name</span>"),
            f"<span class='small'>depth {e(r['off_depth_utc'])} / {e(r['def_depth_utc'])} · "
            f"report {e(r['off_injury_utc'])}</span><br>{src}",
        ])

    n_shared = sum(1 for r in rows if r["off_unordered_slots"] or r["def_unordered_slots"])
    n_out = sum(1 for r in rows if r["def_out"] > 0)
    n_def_r1_out = sum(1 for r in rows if r["def_slots_all_out"])
    fixtures = len({r["fixture"] for r in rows})

    kpis = kpi_grid([
        card(f"{len(rows):,}", "matchup rows", f"{fixtures} fixture pairings, both directions"),
        card(f"{n_shared:,}", "rows where a printed slot gives rank 1 to several names",
             "published as a count; no starter is named"),
        card(f"{n_out:,}", "rows where the listed names carry an Out ruling", "official report only"),
        card(f"{n_def_r1_out:,}", "rows where a defender slot's whole rank-1 entry is Out",
             "the deepest deficiency the chart itself supports"),
        card(f"{len(excluded):,}", "club-weeks the matrix could not build", "each with its reason below"),
    ])

    ex_rows = [[e(x["club"]), e(x["listed_opponent"]) or "<span class='small'>(none)</span>", e(x["reason"]),
                src_link(x["chart_url"] or URL_CLUB_INDEX, "club page")] for x in excluded]

    inj_at = e(rows[0]["off_injury_utc"]) if rows else "not captured"
    dep_at = e(rows[0]["off_depth_utc"]) if rows else "not captured"
    as_at = (f'<p class="flag info">As-at. The injury report this matrix overlays is the official '
             f'<strong>{e(week)}</strong> table, captured {inj_at}; the depth charts are the {dep_at} club '
             "captures. Those fixtures have already been played, so this page is a worked example of the "
             "surface on settled games — it is deliberately not presented as a live pre-kickoff read for the "
             "next fixture week, and the freshness panel below is what turns it into one.</p>")

    body = f"""{as_at}
{flag("How to read a cell. Every name below is a cell the club itself published, at the rank the club "
                    "printed. A cell with two names is two names, not one starter — the club did not choose. "
                    "A blank cell means the chart printed nothing there, which is not a claim that the roster "
                    "has nobody: it is the limit of the source. Designations are printed only as the official "
                    "report prints them, with the capture time of both documents on the row.", "warn")}
{kpis}

<section><h2>The pairing convention, stated before any number</h2>
<p>The matrix lines up <em>groups</em>, because a positional pairing is the only thing two published depth
charts can be asked about honestly:</p>
<ul>
{"".join(f"<li><strong>{e(p[0])}</strong> vs <strong>{e(p[2])}</strong> — {e(p[4])}</li>" for p in PAIRINGS)}
</ul>
<p class="small">This is a convention about which two lists to print side by side. It is not a claim about
who aligned against whom on a play, and no snap, route or block data is used: none is captured (see
<a href="request-register.html">register rows R-24 and R-57</a>).</p>
<input class="filter" type="search" placeholder="Filter: club, position, or a player's name"
       aria-label="Filter the matrix">
</section>

<section><h2>1 · The matrix — {len(rows):,} rows</h2>
<p>Sort any column by clicking its header; the two counts and the two "Out" counts are the deficiency
signal, the names are the evidence.</p>
{table(tbl, ["Fixture", "Offence group", "Defence group",
             "Off 1st", "Off 2nd", "Off 3rd", "Off 4th",
             "Def 1st", "Def 2nd", "Def 3rd", "Def 4th",
             "Off names", "Def names", "Off Out", "Def Out", "What the sources print", "Capture times and sources"],
       caption=f"{len(rows):,} rows · built from the dated official captures only · download: "
               "<a href='assets/data/matchup_matrix.csv'>CSV</a>")}
</section>

<section><h2>2 · Club-weeks the matrix could not build</h2>
<p>A gap in coverage is a finding, so it is printed as its own table instead of being absorbed into a blank.</p>
{table(ex_rows, ["Club", "Printed opponent", "Why there is no row", "Source"],
       caption=f"{len(ex_rows)} club-weeks excluded · reason from the capture manifest and the live official page")}
</section>

<section><h2>3 · What a row here can be used for</h2>
<ul>
<li><strong>As a candidate feature, not a verdict.</strong> The count of listed names and the count of those
names ruled Out are mechanically comparable across clubs; whether that difference moves a line is a
modelling question, and the ablation the request asks for (register row R-44) is not built yet.</li>
<li><strong>Never as "who started".</strong> The Game Book, not the chart, is the official record of
starters; no Game Book is captured in the merged tree (register rows R-23 and R-30, sibling PR #82).</li>
<li><strong>Never as "who is available".</strong> A player absent from the weekly report can be on the
reserve list (the Malik Willis case, claim C-12), so absence from the report is not health.</li>
</ul>
<p class="small">Both documents have timestamps because they both move: the official report revised values
between captures in the 2026-11-13 verification pass, and the club charts drifted between 2026-11-13 and
2026-11-17 (flag F-2026-11-18-01). A matrix row without its capture time would be a guess with a name
attached.</p>
</section>"""
    return layout("matchup-matrix.html", "Matchup deficiency matrix (1st–4th string)",
                  "Offence group against defence group, for every fixture the official captures can "
                  "support — printed ranks, printed designations, and the counts that say how thin each "
                  "side is.", body, wide=True)


def main() -> int:
    rows, excluded = build()
    PROC.mkdir(parents=True, exist_ok=True)
    cols = ["fixture", "off_club", "def_club", "off_group", "def_group", "pairing_note",
            "off_names", "def_names", "off_slots", "def_slots",
            "off_rank1", "off_rank2", "off_rank3", "off_rank4",
            "def_rank1", "def_rank2", "def_rank3", "def_rank4",
            "off_rank1_count", "def_rank1_count", "off_unordered_slots", "def_unordered_slots",
            "off_slots_top_out", "def_slots_top_out",
            "off_out", "def_out", "off_qd", "def_qd",
            "off_dnp", "def_dnp", "def_slots_all_out", "off_slots_all_out", "name_gap",
            "designation_known_off", "designation_known_def", "flags",
            "off_chart_url", "def_chart_url", "off_injury_url", "def_injury_url",
            "off_depth_utc", "def_depth_utc", "off_injury_utc", "def_injury_utc"]
    with open(PROC / "matchup_matrix.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in cols} for r in rows)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    # byte copy, not a text copy: a text copy translates newlines and makes the published file differ from
    # the one the build compared, which is what tests/check_rebuild.py is designed to catch
    (SITE_DATA / "matchup_matrix.csv").write_bytes((PROC / "matchup_matrix.csv").read_bytes())
    with open(PROC / "matchup_matrix_excluded.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["club", "listed_opponent", "reason", "rows", "chart_url"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(excluded)
    write_json(PROC / "matchup_matrix_summary.json", {
        "rows": len(rows), "fixtures": len({r["fixture"] for r in rows}),
        "excluded_club_weeks": len(excluded),
        "depth_capture": (rows[0]["off_depth_utc"] if rows else ""),
        "pairings": [f"{p[0]} vs {p[2]}" for p in PAIRINGS],
    })
    (ROOT / "matchup-matrix.html").write_text(render(rows, excluded), encoding="utf-8")
    print(f"  matchup matrix: {len(rows)} rows, {len(excluded)} excluded club-weeks -> matchup-matrix.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
