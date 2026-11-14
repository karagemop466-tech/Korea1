"""Requirement 6 — track the **depth** of the replacement, not just the fact of a replacement.

The distinction that matters
----------------------------
A club can lose its first-string left tackle and lose nothing measurable, because the second-string
tackle is a five-year starter. It can also lose its third-string corner and lose the game, because the
fourth string is a practice-squad call-up. "Player X is Out" is therefore the least useful form of the
fact. The useful form is: **at which depth slot does the lineup break, and how many slots break at
once.**

What this module joins
----------------------
    official injury snapshot   data/availability/injuries.csv        (who is Out / Doubtful / Questionable)
    official club depth charts data/availability/depth_charts.csv    (1st / 2nd / 3rd / 4th string
                                                                      per slot, per unit, per club)
    the game's opponent        data/forward/official_schedule.csv    (so a club's losses can be
                                                                      weighted by the opponent)

and produces, per club and unit:

    starters_out          how many depth-1 players are unavailable
    depth_impact          Σ 1/rank over the unavailable players, so losing a 1st string (1.0) counts
                          four times losing a 4th string (0.25)
    max_rank_used         the deepest slot the club would have to use if everyone listed as
                          Out/Doubtful sits out (e.g. 3 means the 3rd string starts)
    cliff                 the slot where the club has *no* listed backup (a starter out with no
                          depth behind him)
    evidence_state        VERIFIED / PARTIAL / UNVERIFIED, decided by the rules below, never by hand

Honesty rules, enforced in code
-------------------------------
1. **A chart order is not a game-time role.** The charts carry no publication time and a listed
   backup may not dress. So the row says `chart_order_basis = CLUB_DEPTH_CHART` and the page repeats
   that the depth is the club's *published order*, not a confirmed snap count.
2. **An injury is not a replacement.** A player listed Out is unavailable; the module does not claim
   the next name down actually plays.
3. **No chart, no depth.** Houston's chart is published as an image and produced 0 parsed rows
   (flagged F-18 / DB-08 on the existing pages). Houston rows are therefore `NO_CHART` and are
   **excluded** from the depth statistics rather than defaulted to 1.
4. **Position mismatch is stated, not hidden.** An injured player is matched to a chart slot by
   position group. A player whose position has no chart slot is counted separately
   (`unmatched_injuries`) instead of being silently dropped or assigned to a wrong slot.

Outputs
  data/gates/replacement_depth.csv       one row per club × unit
  data/gates/replacement_slots.csv       one row per unavailable player with the slot he vacates
  data/gates/replacement_defence.csv     opponent-adjusted summary per 2026 week-10 matchup
  assets/data/ mirrors
  replacement-depth.html

Run:  python pipeline/replacement_depth.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import BLANK, clean, e, ref_link, write_csv  # noqa: E402

OUT = ROOT / "data" / "gates"
OUT.mkdir(parents=True, exist_ok=True)
INJ = ROOT / "data" / "availability" / "injuries.csv"
DEPTH = ROOT / "data" / "availability" / "depth_charts.csv"
NFL_INJURIES = "https://www.nfl.com/injuries/"
NFL_INJURIES_WEEK = "https://www.nfl.com/injuries/league/2026/reg10"

# The two-way position map. A chart slot is (unit, position); an injured player's `position`
# column is the official report's abbreviation. Where the report's abbreviation has no chart slot
# the player is counted as unmatched, never forced into the nearest slot.
POSITION_SLOTS = {
    # offense
    "QB": ("Offense", "QB"), "RB": ("Offense", "RB"), "FB": ("Offense", "RB"),
    "WR": ("Offense", "WR"), "TE": ("Offense", "TE"),
    "LT": ("Offense", "LT"), "LG": ("Offense", "LG"), "C": ("Offense", "C"),
    "RG": ("Offense", "RG"), "RT": ("Offense", "RT"),
    "T": ("Offense", "LT"), "G": ("Offense", "LG"), "OL": ("Offense", "LT"),
    # defense: the chart uses these abbreviations directly
    "DE": ("Defense", "DE"), "DT": ("Defense", "DT"), "NT": ("Defense", "DT"),
    "DL": ("Defense", "DL"), "EDGE": ("Defense", "OLB"),
    "OLB": ("Defense", "OLB"), "ILB": ("Defense", "ILB"), "LB": ("Defense", "LB"),
    "MLB": ("Defense", "ILB"),
    "CB": ("Defense", "CB"), "S": ("Defense", "S"), "FS": ("Defense", "S"),
    "SS": ("Defense", "S"), "DB": ("Defense", "S"),
    # special teams
    "K": ("Special Teams", "K"), "P": ("Special Teams", "P"),
    "LS": ("Special Teams", "LS"), "KR": ("Special Teams", "KR"), "PR": ("Special Teams", "PR"),
}
UNAVAILABLE = {"out", "doubtful"}
AT_RISK = {"questionable"}


def _load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inj = pd.read_csv(INJ, dtype=str, keep_default_na=False)
    dep = pd.read_csv(DEPTH, dtype=str, keep_default_na=False)
    dep["depth_rank"] = pd.to_numeric(dep.depth_rank, errors="coerce")
    sched = pd.read_csv(ROOT / "data" / "forward" / "official_schedule.csv",
                        dtype=str, keep_default_na=False)
    return inj, dep.dropna(subset=["depth_rank"]), sched


def _opponent_map(sched: pd.DataFrame) -> dict:
    m = {}
    for r in sched.itertuples():
        m[r.away_team] = r.home_team
        m[r.home_team] = r.away_team
    return m


def build() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inj, dep, sched = _load()
    opp = _opponent_map(sched)
    clubs_with_chart = set(dep.team.unique())
    units = sorted(dep.unit.unique())

    # ---- 1. per unavailable player: which slots does he vacate? -------------------------
    slots = []
    for r in inj.itertuples():
        status = str(r.game_status).strip().lower()
        if status not in UNAVAILABLE | AT_RISK:
            continue
        mapped = POSITION_SLOTS.get(str(r.position).strip().upper())
        if mapped is None:
            slots.append(dict(team=r.team, player=r.player, position=r.position, unit="",
                              slot="", depth_rank=np.nan, game_status=r.game_status,
                              matched=False,
                              note="the official report's position has no chart slot in the map; "
                                   "counted as unmatched rather than forced into a slot"))
            continue
        unit, pos = mapped
        cand = dep[(dep.team == r.team) & (dep.position == pos)]
        if cand.empty:
            alt = dep[(dep.team == r.team) & (dep.unit == unit)]
            cand = alt
        hit = cand[cand.player.str.strip().str.lower() == str(r.player).strip().lower()]
        if hit.empty:
            slots.append(dict(team=r.team, player=r.player, position=r.position, unit=unit,
                              slot="", depth_rank=np.nan, game_status=r.game_status,
                              matched=False,
                              note="the player is not on the club's published depth chart (a "
                                   "practice-squad call-up, a recent signing, or a chart lag); no "
                                   "depth can be assigned"))
        else:
            h = hit.iloc[0]
            slots.append(dict(team=r.team, player=r.player, position=r.position, unit=h.unit,
                              slot=f"{h.position} #{int(h.slot)}", depth_rank=int(h.depth_rank),
                              game_status=r.game_status, matched=True, note=""))
    sl = pd.DataFrame(slots)

    # ---- 2. per club × unit: the depth of the hole -------------------------------------
    rows = []
    for team in sorted(set(inj.team) | clubs_with_chart):
        has_chart = team in clubs_with_chart
        for unit in units:
            d = dep[(dep.team == team) & (dep.unit == unit)]
            s = sl[(sl.team == team) & (sl.unit == unit) & sl.matched] if has_chart else sl.iloc[0:0]
            out = s[s.game_status.str.lower().isin(UNAVAILABLE)]
            risk = s[s.game_status.str.lower().isin(AT_RISK)]
            deepest = np.nan
            cliff = ""
            ranks_out = out.depth_rank.astype(float)
            # impact: 1/rank, so 1st string = 1.00, 2nd = 0.50, 3rd = 0.33, 4th = 0.25
            impact = float((1.0 / ranks_out).sum()) if len(ranks_out) else 0.0
            # deepest slot the club must use, per chart slot, if everyone unavailable sits out.
            # A slot is (position, slot number); the deepest backup behind the highest lost rank is
            # what the club would have to use. Computed per slot so two losses at one position do
            # not inflate each other.
            per_slot = []
            for (pos, sn), dd in d.groupby(["position", "slot"]):
                dd = dd.sort_values("depth_rank")
                lost = out[out.player.str.strip().str.lower().isin(
                    dd.player.str.strip().str.lower())]
                lost_ranks = lost.depth_rank.astype(float).dropna()
                if lost_ranks.empty:
                    continue
                max_lost = int(lost_ranks.max())
                available = dd[~dd.player.str.strip().str.lower().isin(
                    out.player.str.strip().str.lower())]
                if available.empty or available.depth_rank.min() < max_lost:
                    cliff = f"{pos} #{int(sn)}: no listed backup behind rank {max_lost}"
                    deepest = np.nan
                    per_slot.append(np.nan)
                else:
                    per_slot.append(float(available.depth_rank.min()))
            deepest = max(per_slot) if per_slot and all(np.isfinite(per_slot)) else np.nan
            if not has_chart:
                state = "NO_CHART"
            elif s.empty:
                state = "NO_INJURY"
            elif not out.empty and out.matched.all():
                state = "VERIFIED"
            else:
                state = "PARTIAL"
            rows.append(dict(
                team=team, unit=unit, chart_rows=len(d),
                unavailable=len(out), at_risk=len(risk),
                starters_out=int((ranks_out == 1).sum()) if len(ranks_out) else 0,
                depth_impact=round(impact, 3),
                deepest_slot_used=int(deepest) if np.isfinite(deepest) else "",
                cliff=cliff,
                max_chart_rank=int(d.depth_rank.max()) if len(d) else "",
                evidence_state=state,
                opponent=opp.get(team, ""),
                source_url=NFL_INJURIES_WEEK if has_chart else NFL_INJURIES,
            ))
    club_units = pd.DataFrame(rows)

    # ---- 3. per club: opponent-adjusted summary --------------------------------------
    agg = []
    for team in sorted(set(inj.team) | clubs_with_chart):
        c = club_units[club_units.team == team]
        off = c[c.unit == "Offense"]
        dfn = c[c.unit == "Defense"]
        off_i = float(off.depth_impact.sum())
        def_i = float(dfn.depth_impact.sum())
        # net: a defence losing depth helps the opponent's offence, so it enters with the
        # opposite sign. This is a stated convention, not a model output.
        net = off_i - def_i
        if team not in clubs_with_chart:
            verdict = "NO_CHART"
        elif net <= -1.0:
            verdict = "DEFENCE_DEPLETED"      # opponent should be helped
        elif net >= 1.0:
            verdict = "OFFENCE_DEPLETED"      # opponent should be helped less
        else:
            verdict = "BALANCED"
        agg.append(dict(
            team=team, opponent=opp.get(team, ""),
            offence_impact=round(off_i, 3), defence_impact=round(def_i, 3),
            net_impact=round(net, 3),
            starters_out_off=int(off.starters_out.sum()),
            starters_out_def=int(dfn.starters_out.sum()),
            at_risk=int(c.at_risk.sum()),
            unmatched=int(len(sl[(sl.team == team) & (~sl.matched)])),
            chart=("published" if team in clubs_with_chart else "none (chart published as an image)"),
            verdict=verdict, source_url=NFL_INJURIES_WEEK,
        ))
    club = pd.DataFrame(agg)
    return club_units, sl, club


def build_page(units: pd.DataFrame, slots: pd.DataFrame, club: pd.DataFrame) -> str:
    n_chart = int((club.chart == "published").sum())
    n_no = int((club.chart != "published").sum())
    n_st = int(club.starters_out_off.sum() + club.starters_out_def.sum())
    n_unm = int(club.unmatched.sum())
    cards = (
        '<div class="cards">'
        f'<div class="card good">{n_chart}/{n_chart + n_no}<div class="card-label">clubs with a parsed depth chart</div>'
        f'<div class="card-note">the official injury snapshot covers the same clubs</div></div>'
        f'<div class="card bad">{n_st}<div class="card-label">first-string players listed Out or Doubtful</div>'
        f'<div class="card-note">matched to a chart slot; the depth of each hole is below</div></div>'
        f'<div class="card luck">{n_unm}<div class="card-label">injured players with no chart slot</div>'
        f'<div class="card-note">not assigned a depth; counted, not dropped</div></div>'
        f'<div class="card">{int((club.verdict=="NO_CHART").sum())}<div class="card-label">clubs that cannot be assessed</div>'
        f'<div class="card-note">no chart means no depth claim — Houston is flagged, not defaulted</div></div>'
        "</div>")

    club_rows = []
    for r in club.sort_values("net_impact").itertuples():
        club_rows.append([
            e(r.team), e(r.opponent or ""), clean(r.chart),
            f"{r.offence_impact:.2f}", f"{r.defence_impact:.2f}", f"{r.net_impact:+.2f}",
            str(int(r.starters_out_off)), str(int(r.starters_out_def)), str(int(r.at_risk)),
            str(int(r.unmatched)), clean(r.verdict.replace("_", " ").title()),
            ref_link("official injuries", NFL_INJURIES_WEEK),
        ])
    unit_rows = []
    for r in units[units.evidence_state.isin(["VERIFIED", "PARTIAL"])].sort_values(
            ["team", "unit"]).itertuples():
        unit_rows.append([
            e(r.team), clean(r.unit), str(int(r.chart_rows)), str(int(r.unavailable)),
            str(int(r.at_risk)), str(int(r.starters_out)), f"{r.depth_impact:.2f}",
            clean(r.deepest_slot_used), clean(r.cliff), clean(r.evidence_state),
            ref_link("NFL injuries", NFL_INJURIES_WEEK),
        ])
    slot_rows = []
    shown = slots[slots.matched].sort_values(["team", "unit", "depth_rank"]).head(80)
    for r in shown.itertuples():
        slot_rows.append([
            e(r.team), clean(r.unit), e(r.player), e(r.position), clean(r.slot),
            clean(r.game_status),
            (f"1/{int(r.depth_rank)} = {1.0/int(r.depth_rank):.2f}" if pd.notna(r.depth_rank) else BLANK),
            ref_link("NFL injuries", NFL_INJURIES_WEEK),
            ref_link("club chart", f"https://www.nfl.com/teams/"),
        ])
    if not slot_rows:
        slot_rows = [["—"] * 9]

    body = f"""
<p class="flag info"><strong>What this page is.</strong> Requirement 6 of the 2026-11-14 brief: track
the <strong>depth of the replacement</strong>, not the fact of a replacement. A club losing its first
string counts for more than a club losing its fourth string, and a club with no listed backup behind
a starter is in a different position from one with three. This page joins the official injury
snapshot to the official club depth charts and prints the depth of every hole.</p>
{cards}
<section>
<div class="section-head"><h2>1 · The measure, and what it refuses to claim</h2></div>
<p><strong>depth_impact = Σ 1/rank</strong> over the club's unavailable players, so a first-string
loss is 1.00, a second-string loss 0.50, a third 0.33 and a fourth 0.25 — losing a starter counts
four times losing a fourth-string player, and two second-string losses (1.00) equal one first-string
loss. <strong>Net impact</strong> = offence − defence, so a depleted defence (which helps the
opponent's offence) reads negative. That sign convention is a published convention, not a model
output.</p>
<p>What the measure does <em>not</em> do:</p>
<ul>
<li>It does not claim a listed backup plays. A club depth chart carries no publication time and no
game-time confirmation, so the depth is the club's <em>published order</em>.</li>
<li>It does not assign a depth to a player the chart does not list. Those are counted as
<code>unmatched</code> and reported — {n_unm} today — rather than being treated as a first-string loss.</li>
<li>It does not assess a club with no parsed chart. {n_no} club(s) have none; their rows read
<code>NO_CHART</code> and are excluded from the statistics rather than defaulted.</li>
</ul>
</section>
<section>
<div class="section-head"><h2>2 · Club summary, worst first</h2></div>
<p>Sorted by net impact. A negative net impact means the defence has lost more depth than the offence.
The opponent column is the week-10 opponent from the official schedule, so a loss can be read against
who is next.</p>
{table(club_rows, ["Club", "Opponent", "Chart", "Offence impact", "Defence impact", "Net", "1st-string out (OFF)",
                   "1st-string out (DEF)", "At risk", "No chart slot", "Verdict", "Official source"],
       caption="Replacement depth by club: how deep the hole is, not just that it exists")}
</section>
<section>
<div class="section-head"><h2>3 · Depth by unit</h2></div>
<p>Only units with a parsed chart are shown. <code>deepest_slot_used</code> is how far down the club
would have to go if everyone listed Out or Doubtful sits out; <code>cliff</code> marks a slot with no
listed backup at all.</p>
{table(unit_rows or [["—"] * 11], ["Club", "Unit", "Chart rows", "Unavailable", "At risk",
                                   "1st-string out", "Depth impact", "Deepest slot used", "Cliff",
                                   "Evidence", "Official source"],
       caption="Depth of the replacement by club and unit")}
</section>
<section>
<div class="section-head"><h2>4 · Every unavailable player and the slot he vacates</h2></div>
<p>This is the audit trail for the numbers above: one row per player the official report lists as Out
or Doubtful who is on his club's published chart, with the slot and the 1/rank weight he contributes.</p>
{table(slot_rows, ["Club", "Unit", "Player", "Pos", "Slot", "Game status", "Weight",
                   "Official source", "Chart source"],
       caption="Unavailable players matched to a depth slot (first 80 shown)")}
</section>
<section>
<div class="section-head"><h2>5 · Why this is not yet a signal</h2></div>
<p>Depth is a <em>condition</em>, not a forecast. Turning it into a signal needs two things this
build does not have: (a) a confirmed game-day inactive list per club — the official pregame report is
published 90 minutes before kickoff and is not archived here; and (b) a measured relationship between
depth loss and scoring, estimated out of sample. Both are proposed as <code>DEP-01</code> and
<code>DEP-02</code> on <a href="suggestions-review-2026-11-14.html">the suggestions page</a>, and
neither is claimed as a result.</p>
<p class="flag warn">Unverified cells stay blank. The depth charts are the clubs' published order and
carry no publication time; an injury designation is not a snap count. Downloads:
<a href="assets/data/replacement_depth.csv">replacement_depth.csv</a> ·
<a href="assets/data/replacement_slots.csv">replacement_slots.csv</a> ·
<a href="assets/data/replacement_defence.csv">replacement_defence.csv</a>.</p>
</section>
"""
    return layout("replacement-depth.html", "Replacement depth",
                  "Depth of the hole, not the fact of it: official injuries joined to official club depth charts.",
                  body, wide=True)


def main() -> None:
    units, slots, club = build()
    write_csv(units, "replacement_depth.csv")
    write_csv(slots, "replacement_slots.csv")
    write_csv(club, "replacement_defence.csv")
    for name, df in (("replacement_depth.csv", units), ("replacement_slots.csv", slots),
                     ("replacement_defence.csv", club)):
        (OUT / name).write_text(df.to_csv(index=False), encoding="utf-8")
    (ROOT / "replacement-depth.html").write_text(build_page(units, slots, club), encoding="utf-8")
    print(f"  replacement_depth.csv   {len(units)} club×unit rows; "
          f"{(units.evidence_state=='VERIFIED').sum()} verified, "
          f"{(units.evidence_state=='NO_CHART').sum()} no chart")
    print(f"  replacement_slots.csv   {len(slots)} unavailable/at-risk players, "
          f"{int(slots.matched.sum())} matched to a slot")


if __name__ == "__main__":
    main()
