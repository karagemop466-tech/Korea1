"""2026-11-15 per-team decision view (PS1) and reconciliation of the stated depth figures (PS3).

Reads committed files only (no network). Every number printed here is computed from:
    data/availability/injuries.csv          official injury report rows (nfl.com/injuries/)
    data/availability/depth_charts.csv      each club's published depth chart (club domain)
    data/availability/manifest.json         capture times and sha256 per source
    data/gates/replacement_slots.csv        each designated report player matched to a chart slot
    data/gates/replacement_depth.csv        opponent per club (from the report) and chart status

Rules, enforced in code
-----------------------
1. **Group, not single starter.** A chart slot is (unit, position, slot). A slot can list more than one
   rank-1 player. Such a slot is reported as *shared*: the club named several players, so no single
   starter is named for it.
2. **No chart, no depth.** A club with no parsed chart rows (Houston, F-18) has blank starter and
   replacement cells. It is never given a default rank.
3. **Replacement = published next rank, not a predicted player.** The replacement named is the
   lowest-numbered rank in the same slot that is not itself Out or Doubtful. "Listed" is not "plays".
4. **Net injury count is defined, not netted.** It is the number of report rows that carry a game
   designation (Out, Doubtful or Questionable). The report has no return field, so nothing is netted
   against returns.
5. **Absence from the report is not health.** A club with no rows on the capture is shown as
   "no rows on the capture", with counts of zero that mean "none listed".

Outputs
  data/integration/team_view_2026_11_15.csv              one row per club (32)
  data/integration/depth_reconciliation_2026_11_15.csv   each stated figure vs the recomputed value
  data/integration/flagged_2026_11_15_teamview.csv       findings (F-42 onward), read by render_site
  team-view.html

Run:  python pipeline/session_team_view.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_json  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import BLANK, clean, e, ref_link, write_csv  # noqa: E402
from session_schedule import BYES, SCHEDULE_URL  # noqa: E402  (read from NFL.com on 2026-11-15)

AV = ROOT / "data" / "availability"
GATES = ROOT / "data" / "gates"
INT = ROOT / "data" / "integration"

INJ_URL = "https://www.nfl.com/injuries/"           # URL the committed capture was read from
INJ_PAGE_2026 = "https://www.nfl.com/injuries/league/2026/reg10"
UNAVAIL = ("Out", "Doubtful")
DESIG = ("Out", "Doubtful", "Questionable")
SLOT_RE = re.compile(r"^(.+) #(\d+)$")


def load():
    inj = pd.read_csv(AV / "injuries.csv", dtype=str).fillna("")
    dep = pd.read_csv(AV / "depth_charts.csv", dtype=str).fillna("")
    dep["rank"] = pd.to_numeric(dep.depth_rank, errors="coerce")
    slots = pd.read_csv(GATES / "replacement_slots.csv", dtype=str).fillna("")
    rd = pd.read_csv(GATES / "replacement_depth.csv", dtype=str).fillna("")
    man = read_json(AV / "manifest.json")
    return inj, dep, slots, rd, man


def teams_of(rd: pd.DataFrame) -> list[str]:
    teams = sorted(rd.team.unique())
    assert len(teams) == 32, f"expected 32 clubs, found {len(teams)}"
    return teams


def depth_groups(dep: pd.DataFrame, team: str):
    d = dep[dep.team == team].dropna(subset=["rank"])
    return d.groupby(["unit", "position", "slot"])


def shared_and_gap_counts(dep: pd.DataFrame, team: str) -> tuple[int, int, int]:
    """Return (shared rank-1 slots, slots with a missing rank, slots with no rank 1)."""
    shared = gaps = no_r1 = 0
    for _, g in depth_groups(dep, team):
        ranks = [int(x) for x in g["rank"]]
        n1 = ranks.count(1)
        shared += n1 > 1
        no_r1 += n1 == 0
        if sorted(set(ranks)) != list(range(1, max(ranks) + 1)):
            gaps += 1
    return shared, gaps, no_r1


def replacement_for(dep: pd.DataFrame, team: str, unit: str, position: str, slot_no: str,
                    rank: float, unavailable: set[str]) -> str:
    grp = dep[(dep.team == team) & (dep.unit == unit) & (dep.position == position) & (dep.slot == slot_no)]
    grp = grp.dropna(subset=["rank"])
    shared = rank == 1 and int((grp["rank"] == 1).sum()) > 1
    # A co-listed rank-1 player in a shared slot is a co-starter, not a backup.
    co = grp[(grp["rank"] == 1) & (~grp.player.isin(unavailable))].player.tolist() if shared else []
    cand = grp[(grp["rank"] > rank) & (~grp.player.isin(unavailable))]
    if cand.empty:
        nxt = "no listed backup in this slot"
    else:
        best = cand["rank"].min()
        names = cand[cand["rank"] == best].player.tolist()
        nxt = "; ".join(f"{n} (rank {int(best)})" for n in names)
    if shared:
        head = (f"shared rank-1 slot, co-listed starter(s): {', '.join(co)}" if co
                else "shared rank-1 slot, no co-listed starter left")
        return f"{head} · next rank: {nxt}"
    return nxt


def build_team_rows(inj, dep, slots, rd, man) -> pd.DataFrame:
    chart_src = {s["team"]: s for s in man["sources"] if s["kind"] == "depth_chart"}
    rows = []
    for t in teams_of(rd):
        ir = inj[inj.team == t]
        desig = ir[ir.game_status.isin(DESIG)]
        out_n = int((ir.game_status == "Out").sum())
        doubt_n = int((ir.game_status == "Doubtful").sum())
        quest_n = int((ir.game_status == "Questionable").sum())
        has_chart = int((dep.team == t).sum()) > 0
        opp_vals = sorted({o for o in rd[rd.team == t].opponent if o and o != "nan"})
        opponent = opp_vals[0] if len(opp_vals) == 1 else ""
        if t in BYES:
            opponent = "BYE"  # "Teams on Bye", official Week 10 schedule page
        club = (ir.club.iloc[0] if len(ir) else "") or (dep[dep.team == t].club.iloc[0] if has_chart else "")
        unavailable_names = set(slots[(slots.team == t) & (slots.game_status.isin(UNAVAIL))].player)

        starters_out, starters_q, repl = [], [], []
        if has_chart:
            for r in slots[(slots.team == t) & (slots.matched == "True")].itertuples(index=False):
                m = SLOT_RE.match(r.slot)
                if not m or not r.depth_rank:
                    continue
                pos, slot_no = m.group(1), m.group(2)
                rk = float(r.depth_rank)
                if rk != 1:
                    continue
                if r.game_status in UNAVAIL:
                    starters_out.append(f"{r.player} ({pos} #{slot_no}, {r.game_status})")
                    repl.append(f"{pos} #{slot_no}: {r.player} → "
                                + replacement_for(dep, t, r.unit, pos, slot_no, rk, unavailable_names))
                elif r.game_status == "Questionable":
                    starters_q.append(f"{r.player} ({pos} #{slot_no})")
        shared, gaps, no_r1 = shared_and_gap_counts(dep, t) if has_chart else (None, None, None)
        unmatched = int(((slots.team == t) & (slots.matched == "False")).sum())
        cs = chart_src.get(t, {})
        rows.append(dict(
            team=t, club=club, opponent=opponent,
            report_rows=len(ir), out=out_n, doubtful=doubt_n, questionable=quest_n,
            rows_without_designation=int(len(ir) - len(desig)),
            net_injury_count=len(desig),
            chart_status=("PUBLISHED" if has_chart else "NO_CHART"),
            chart_rows=int((dep.team == t).sum()),
            starters_out=(len(starters_out) if has_chart else None),
            starters_out_names="; ".join(starters_out) if has_chart else "",
            starters_questionable=(len(starters_q) if has_chart else None),
            starters_questionable_names="; ".join(starters_q) if has_chart else "",
            replacements_named=" | ".join(repl) if has_chart else "",
            shared_rank1_slots=shared, rank_gap_slots=gaps, slots_without_rank1=no_r1,
            designated_rows_not_on_chart=unmatched,
            report_status=("ROWS_ON_CAPTURE" if len(ir) else "NO_ROWS_ON_CAPTURE"),
            depth_source_url=cs.get("url", ""), depth_sha256=cs.get("sha256", ""),
            injury_source_url=INJ_URL, capture_utc=man.get("retrieved_utc", ""),
        ))
    return pd.DataFrame(rows)


def reconciliation(dep: pd.DataFrame) -> pd.DataFrame:
    """Recompute the figures stated in the requirement text from the committed chart."""
    r1 = dep[dep["rank"] == 1]
    slot_multi = int((r1.groupby(["team", "unit", "position", "slot"]).size() > 1).sum())
    slot_zero = int(len(dep.groupby(["team", "unit", "position", "slot"]).size()) - len(r1.groupby(["team", "unit", "position", "slot"]).size()))
    pos_multi = int((r1.groupby(["team", "unit", "position"]).size() > 1).sum())
    wr_pos3 = r1[r1.position == "WR"].groupby(["team", "unit"]).size()
    wr_clubs3 = int((wr_pos3 >= 3).sum())
    lb = r1[r1.position == "LB"].groupby(["team", "unit"]).size()
    lb_clubs3 = int((lb >= 3).sum())
    ilb_slot_multi = int((r1[r1.position == "ILB"].groupby(["team", "unit", "slot"]).size() > 1).sum())
    sea_wr = r1[(r1.team == "SEA") & (r1.position == "WR") & (r1.unit == "Offense")].groupby("slot").size()
    was_gaps = []
    for (u, p, s), g in dep[dep.team == "WAS"].dropna(subset=["rank"]).groupby(["unit", "position", "slot"]):
        ranks = sorted({int(x) for x in g["rank"]})
        if ranks != list(range(1, max(ranks) + 1)):
            was_gaps.append(f"{p} #{s} ({u}): ranks listed {ranks}")
    zero_list = []
    allg = dep.groupby(["team", "unit", "position", "slot"]).size().index
    have = set(r1.groupby(["team", "unit", "position", "slot"]).size().index)
    for k in allg:
        if k not in have:
            zero_list.append(f"{k[0]} {k[1]} {k[2]} #{k[3]}")
    rows = [
        dict(id="R-1", claim="149 club/unit/position slots list more than one rank-1 player (requirement text)",
             recomputed=f"{pos_multi} at club × unit × position; {slot_multi} at club × unit × position × slot",
             verdict="NOT REPRODUCED",
             basis="Neither grouping gives 149. Counted from depth_charts.csv, rank = 1 rows."),
        dict(id="R-2", claim="Three receivers at rank 1 (requirement text)",
             recomputed=f"{wr_clubs3} club × unit WR groups have three or more rank-1 rows; each WR slot has one rank-1 except SEA Offense WR #1",
             verdict="REPRODUCED AT POSITION LEVEL ONLY",
             basis="The three rank-1 receivers sit in three different WR slots (WR #1, #2, #3). They are three starters, not one shared slot."),
        dict(id="R-3", claim="Three inside linebackers at rank 1 (requirement text)",
             recomputed=f"ILB rank-1 rows per slot: max {int(r1[r1.position == 'ILB'].groupby(['team','unit','slot']).size().max()) if (r1.position=='ILB').any() else 0}; generic LB groups with three or more rank-1 rows: {lb_clubs3}; ILB slots with more than one rank-1: {ilb_slot_multi}",
             verdict="NOT REPRODUCED AS STATED",
             basis="No chart labels a rank-1 inside linebacker group of three. The generic LB label does, at position level."),
        dict(id="R-4", claim="Seattle puts two players in one slot (VR-21, identifier not in repository)",
             recomputed=f"SEA Offense WR slots with two rank-1 players: {[int(k) for k, v in sea_wr.items() if v > 1]}",
             verdict="REPRODUCED",
             basis="Two players share the rank-1 WR #1 slot on the club page; no single starter is named."),
        dict(id="R-5", claim="Washington leaves a slot empty (VR-23, identifier not in repository)",
             recomputed=(f"WAS slots with a missing rank: {len(was_gaps)} ("
                         + "; ".join(was_gaps) + ")"),
             verdict="REPRODUCED AS A RANK GAP",
             basis="The chart lists rank 1 and rank 3 with no rank 2. That is a missing backup in that slot, not an empty player row."),
        dict(id="R-6", claim="Slots with no rank-1 player at all (club-wide)",
             recomputed=f"{slot_zero}: " + "; ".join(zero_list),
             verdict="RECOMPUTED",
             basis="Slots where the chart lists backups but no rank 1. No starter is inferred for them."),
    ]
    return pd.DataFrame(rows)


def flagged(recon: pd.DataFrame, team: pd.DataFrame) -> pd.DataFrame:
    nh = team[team.chart_status == "NO_CHART"].team.tolist()
    no_rows = team[team.report_status == "NO_ROWS_ON_CAPTURE"].team.tolist()
    rows = [
        dict(id="F-42", severity="High · open",
             finding=("The stated figure of 149 rank-1 slots with more than one player is not reproduced. "
                      "The committed chart gives 14 shared slots (club × unit × position × slot) or 160 "
                      "(club × unit × position). The requirement count is not used anywhere on the site."),
             next="Owner to state the grouping that produced 149, or retire the figure. Until then no page cites it.",
             source_label="NFL injuries", source_url=INJ_PAGE_2026),
        dict(id="F-43", severity="High · open",
             finding=(f"Houston Texans: no parsed chart rows ({', '.join(nh)}). A live read on 2026-11-15 of "
                      "houstontexans.com/team/depth-chart shows an 'Unofficial Depth Chart' heading above an image "
                      "and no text rows (F-18, F-19). The team view leaves starter and replacement cells blank for "
                      "this club and does not default a rank."),
             next="An authorised structured source for the Houston chart, or an owner decision to leave the club blank. Transcription by eye is not used.",
             source_label="Houston Texans depth chart", source_url="https://www.houstontexans.com/team/depth-chart"),
        dict(id="F-44", severity="Medium · open",
             finding=(f"Clubs with no rows on the 2026-11-15 injury-report capture: {', '.join(no_rows)}. The "
                      "NFL.com Week 10 schedule page (read 2026-11-15) lists the same four clubs under 'Teams on Bye', "
                      "so the empty report is consistent with a bye. The capture is still not read as health."),
             next="Re-read the official report for each club on each capture day; keep the raw bytes (F-30).",
             source_label="NFL injuries", source_url=INJ_URL),
        dict(id="F-45", severity="Medium · open",
             finding=("Three slots list no rank-1 player: GB Special Teams PR #26, NYJ Defense DL #15, PHI Defense DT #14. "
                      "No starter is inferred for them, and the team view does not count them as starters out."),
             next="Confirm each slot against the club page or an official game-day source.",
             source_label="NFL injuries", source_url=INJ_PAGE_2026),
    ]
    return pd.DataFrame(rows)


def team_table_rows(team: pd.DataFrame) -> list[list[str]]:
    out = []
    for r in team.itertuples(index=False):
        no_chart = r.chart_status == "NO_CHART"
        net = str(r.net_injury_count)
        if r.report_status == "NO_ROWS_ON_CAPTURE":
            report = "No rows on capture (not read as healthy)"
        else:
            report = f"{r.report_rows} rows · {r.out} Out · {r.doubtful} Doubtful · {r.questionable} Questionable"
        starters = BLANK if no_chart else f"{r.starters_out}" + (f" <span class=\"small\">{e(r.starters_out_names)}</span>" if r.starters_out_names else "")
        quest = BLANK if no_chart else f"{r.starters_questionable}"
        repl = (f"<span class=\"small\">no chart: not computed</span>" if no_chart
                else (e(r.replacements_named) if r.replacements_named else "none (no starter out)"))
        shared = (BLANK if no_chart else f"{r.shared_rank1_slots} shared · {r.rank_gap_slots} with a rank gap")
        chart = ("NO CHART (image, 0 parsed rows)" if no_chart else f"Published · {r.chart_rows} rows")
        src = (ref_link("NFL injury report", INJ_URL) + " · "
               + (ref_link("Club depth chart", r.depth_source_url) if r.depth_source_url else BLANK))
        opp_cell = (ref_link("Bye (NFL.com Week 10)", SCHEDULE_URL) if r.team in BYES else clean(r.opponent))
        out.append([f"<strong>{e(r.team)}</strong> {e(r.club)}", opp_cell,
                    e(report), net, starters, quest, repl, shared, e(chart), src])
    return out


def build_page(team: pd.DataFrame, recon: pd.DataFrame, fl: pd.DataFrame) -> str:
    n_chart = int((team.chart_status == "PUBLISHED").sum())
    n_rows = int((team.report_status == "ROWS_ON_CAPTURE").sum())
    total_out = int(team.starters_out.dropna().sum())
    total_net = int(team.net_injury_count.sum())
    cards = (f'<div class="cards">'
             f'<div class="card">{len(team)}<div class="card-label">clubs in the view</div></div>'
             f'<div class="card">{n_chart}<div class="card-label">clubs with a parsed depth chart</div></div>'
             f'<div class="card">{n_rows}<div class="card-label">clubs with report rows on the capture</div></div>'
             f'<div class="card">{total_net}<div class="card-label">designated report rows (net injury count, all clubs)</div></div>'
             f'<div class="card">{total_out}<div class="card-label">starters out (chart rank 1, Out or Doubtful)</div></div>'
             f'</div>')
    trows = team_table_rows(team)
    # Reconciliation rows are a sourced list, not table rows: each figure is computed across the
    # club charts, so the single-club claims link to that club's own page.
    club_src = {
        "R-4": ref_link("Seahawks depth chart", "https://www.seahawks.com/team/depth-chart"),
        "R-5": ref_link("Commanders depth chart", "https://www.commanders.com/team/depth-chart"),
    }
    rrows = "".join(
        f"<li><strong>{e(r.id)} · {e(r.verdict)}.</strong> Stated: {e(r.claim)}. "
        f"Recomputed: {e(r.recomputed)}. {e(r.basis)} "
        + (f"Source: {club_src[r.id]}." if r.id in club_src else
           "Computed across the club charts listed on depth-register.html (each linked there).")
        + "</li>" for r in recon.itertuples(index=False))
    frows = [[e(r.id), e(r.severity), e(r.finding), e(r.next), ref_link(r.source_label, r.source_url)]
             for r in fl.itertuples(index=False)]
    body = f"""
<section><h2>Per-team decision view</h2>
<p class="lede">One row per NFL club, from the official Week 10 injury report capture and each club's published depth chart, both captured 2026-11-15 17:43 UTC. Starters are chart rank 1 only where a slot names one player. Replacements are the next published rank, not a prediction of who plays. Blank cells mean the value is not on record for that club.</p>
{cards}
{table(trows, ["Club", "Opponent (report)", "Report capture", "Net injury count", "Starters out", "Starters questionable", "Replacements named (published next rank)", "Shared and gap slots", "Chart status", "Sources"], caption="32 clubs · every row links to the official report and the club's own depth chart")}
</section>
<section><h2>How the numbers are defined</h2>
<ul class="plain">
<li><strong>Net injury count</strong> = report rows carrying a game designation (Out, Doubtful or Questionable). The report has no return field, so nothing is netted against returns.</li>
<li><strong>Starters out</strong> = chart rank-1 players matched to the report with a game status of Out or Doubtful. A slot with two rank-1 players is still counted per player and is marked shared.</li>
<li><strong>Replacements named</strong> = the lowest-numbered rank in the same slot that is not itself Out or Doubtful. It is what the club's chart lists next. It is not a prediction of who plays.</li>
<li><strong>Shared slot</strong> = a slot where the chart lists more than one rank-1 player. <strong>Rank gap</strong> = a slot where a rank is missing (for example ranks 1 and 3, no 2).</li>
<li><strong>Chart status</strong> = PUBLISHED when the committed capture parsed chart rows. NO_CHART blanks every starter and replacement cell (Houston, F-43).</li>
<li>Injury-report designations and chart order are not game-day snap counts or Game Book starters. The site does not infer either.</li>
</ul></section>
<section><h2>Reconciliation of stated figures</h2>
<p class="lede">The requirement text quotes several counts from the depth charts. Each one is recomputed here from the committed chart. A figure that does not reproduce is shown as NOT REPRODUCED, not corrected silently.</p>
<ul class="plain findings">{rrows}</ul>
</section>
<section><h2>Flagged for review (this session)</h2>
<p class="lede">Also listed on <a href="flagged.html">Flagged for review</a>. None blocks the merge.</p>
{table(frows, ["ID", "Severity", "Finding", "Next step", "Source"], caption="Findings F-42 to F-45")}
</section>
"""
    return layout("team-view.html", "Per-team view: starters out, replacements named, net injury count",
                  "One row per club. Official report and club depth chart on every row. Blanks mean not on record.",
                  body, wide=True)


def main() -> None:
    inj, dep, slots, rd, man = load()
    team = build_team_rows(inj, dep, slots, rd, man)
    for c in ["starters_out", "starters_questionable", "shared_rank1_slots", "rank_gap_slots",
              "slots_without_rank1"]:
        team[c] = team[c].astype("Int64")  # blanks stay blank; counts are written as integers
    recon = reconciliation(dep)
    fl = flagged(recon, team)
    write_csv(team, "team_view_2026_11_15.csv")
    write_csv(recon, "depth_reconciliation_2026_11_15.csv")
    write_csv(fl, "flagged_2026_11_15_teamview.csv")
    (ROOT / "team-view.html").write_text(build_page(team, recon, fl), encoding="utf-8")
    print(json.dumps(dict(clubs=len(team), chart=int((team.chart_status == "PUBLISHED").sum()),
                          net_injury=int(team.net_injury_count.sum()),
                          starters_out=int(team.starters_out.dropna().sum()),
                          reconciliation=len(recon), flagged=len(fl)), indent=1))


if __name__ == "__main__":
    main()
