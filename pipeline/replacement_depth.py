"""R7-06 — track the *depth* of the replacement, not just the fact of a replacement.

What the brief asks for
-----------------------
"Track the depth of the replacement, not just the fact of a replacement." and
"The system should be tracking injuries and know any deficiencies in defenses
such as 2nd, 3rd or 4th string backups having to replace starters due to
lineups. Also same can be said for offenses using starters or backups."

The two facts that make this measurable at all
----------------------------------------------
1. The official NFL injury report states, per player, a `game_status`
   (`Out`, `Doubtful`, `Questionable`, or blank) and a `practice_status`.
2. Each club's official depth chart states, per *slot*, an **ordered** list of
   players: depth rank 1, 2, 3, 4, 5.

Joining (1) to (2) on club + player gives, for every unavailable player, the
slot he occupies and therefore **which man is next** and **how deep he is**.
That is the whole of this module. Nothing is inferred where either side is
silent:

* A player on the injury report who is **not on his club's depth chart** is
  published as `NOT ON CHART` — the join failed, not the player. In the
  2026-11-14 snapshot there are 34 such players, including the whole Houston list
  (Houston published no parseable chart).
* A player on the chart whose slot has **nobody behind him** is published as
  `NO LISTED BACKUP`. The chart says the club lists one man at that slot; it does
  not say the club has nobody else on the roster.
* A depth *rank* is a published chart position. It is **not** proof that the man
  played, started, or took a snap. The chart carries no publication time, so a
  rank cannot be tied to a kickoff. Every row therefore records
  `role_evidence = CHART_POSITION_ONLY` and no row asserts "will start".

Severity is deliberately coarse and is a statement about the *chart*, not about
football: losing the depth-1 man in a 4-deep slot at a position where the club
lists four bodies is a different exposure from losing the depth-1 man in a
2-deep slot. The score is published with its own definition so a reader can
disagree with the weights instead of having to reverse-engineer them.

Outputs
-------
data/processed/replacement_depth.csv          one row per injured player
data/processed/replacement_slots.csv          one row per affected slot
data/processed/replacement_summary.json       counters used on the page

Run:  python pipeline/replacement_depth.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, read_json, write_json  # noqa: E402

AVAIL = ROOT / "data" / "availability"
INJURY_URL = "https://www.nfl.com/injuries/"
INJ = AVAIL / "injuries.csv"
DEP = AVAIL / "depth_charts.csv"

# Status vocabulary read verbatim from the official report. "Out" is the only
# status the NFL rulebook treats as unavailable before kickoff; Doubtful and
# Questionable are published as *risk*, never converted into a probability.
STATUS_UNAVAILABLE = {"Out"}
STATUS_RISK = {"Doubtful", "Questionable"}

# How deep the man who steps in is, expressed in chart terms.
DEPTH_LABEL = {1: "1st string", 2: "2nd string", 3: "3rd string", 4: "4th string", 5: "5th string"}


# Official club charts are not published in one consistent cell format. Measured
# on the 2026-11-14 capture: Green Bay prefixes *every* one of its 57 chart cells
# with the jersey number ("32 MarShawn Lloyd"), while the other 30 clubs do not
# prefix a single cell. A join that used the raw string would therefore fail for
# 100% of Green Bay and 0% of everyone else — a club-specific blind spot rather
# than a data gap. The number is stripped before matching and the untouched
# official string is kept in `chart_player_raw` so a reviewer can check the
# normalisation instead of trusting it.
_JERSEY = re.compile(r"^\d{1,2}\s+")


def _strip_jersey(name: str) -> str:
    return _JERSEY.sub("", str(name)).strip()


def _norm(name: str) -> str:
    """Match official-report names to chart names.

    The two official sources spell some names differently (punctuation, suffixes,
    initials). Only letters are compared, which is a documented, checkable rule;
    a name that still fails to match is reported as unmatched rather than
    fuzzy-matched, because a wrong match would mis-state a man's depth.
    """
    return re.sub(r"[^a-z]", "", _strip_jersey(name).lower())


def build() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    inj = pd.read_csv(INJ, dtype=str, keep_default_na=False)
    dep = pd.read_csv(DEP, dtype=str, keep_default_na=False)
    dep["depth_rank"] = dep.depth_rank.astype(int)

    inj["k"] = inj.player.map(_norm)
    dep["k"] = dep.player.map(_norm)

    # --- slot shape: how many men the club lists at each slot --------------
    slot_shape = (dep.groupby(["team", "unit", "slot"]).agg(
        slot_size=("depth_rank", "size"),
        deepest_rank=("depth_rank", "max"),
        position=("position", "first"),
        chart_url=("source_url", "first"),
        retrieved_utc=("retrieved_utc", "first"),
    ).reset_index())

    joined = inj.merge(
        dep[["team", "unit", "slot", "position", "depth_rank", "player", "player_url", "k",
             "source_url", "retrieved_utc"]],
        on=["team", "k"], how="left", suffixes=("", "_chart"), indicator="joined")

    rows = []
    for r in joined.itertuples(index=False):
        on_chart = r.joined == "both"
        if on_chart:
            shape = slot_shape[(slot_shape.team == r.team) & (slot_shape.unit == r.unit)
                               & (slot_shape.slot == r.slot)].iloc[0]
            rank = int(r.depth_rank)
            size = int(shape.slot_size)
            behind = size - rank
            successor_rank = rank + 1 if behind > 0 else np.nan
            if behind > 0:
                nxt = dep[(dep.team == r.team) & (dep.unit == r.unit)
                          & (dep.slot == r.slot) & (dep.depth_rank == rank + 1)]
            else:
                nxt = dep.iloc[0:0]
            successor = nxt.player.iloc[0] if len(nxt) else ""
            successor_raw = successor
            successor_url = nxt.player_url.iloc[0] if len(nxt) else ""
            replacement_status = "LISTED BELOW" if behind > 0 else "NO LISTED BACKUP"
            slot_pos = shape.position
            unit = r.unit
            chart_url = r.source_url_chart
            chart_utc = r.retrieved_utc_chart
            chart_player_raw = r.player_chart
        else:
            rank = np.nan
            size = np.nan
            behind = np.nan
            successor_rank = np.nan
            successor = ""
            successor_raw = ""
            successor_url = ""
            chart_player_raw = ""
            replacement_status = "NOT ON CHART"
            slot_pos = ""
            unit = ""
            chart_url = ""
            chart_utc = ""

        status = r.game_status
        # Exposure is defined only where both the status and the chart exist.
        if replacement_status == "NOT ON CHART":
            exposure = np.nan
            exposure_basis = "blank — player is not on the club chart the join needed"
        elif status in STATUS_UNAVAILABLE:
            exposure = float(rank) * 1.0 + (3.0 if replacement_status == "NO LISTED BACKUP" else 0.0)
            exposure_basis = ("depth rank x 1.0, plus 3.0 when the chart lists nobody behind him"
                              if replacement_status == "NO LISTED BACKUP"
                              else "depth rank x 1.0")
        elif status in STATUS_RISK:
            exposure = float(rank) * 0.5
            exposure_basis = "depth rank x 0.5 (Doubtful/Questionable, never converted to a probability)"
        else:
            exposure = 0.0
            exposure_basis = "0.0 — no game designation published at capture time"

        rows.append({
            "team": r.team, "club": r.club, "opponent": r.opponent,
            "player": r.player, "position": r.position_inj if hasattr(r, "position_inj") else r.position,
            "injury": r.injury, "practice_status": r.practice_status, "game_status": status,
            "chart_position": slot_pos,
            "chart_unit": unit,
            "chart_player_raw": chart_player_raw,
            "chart_rank": rank,
            "chart_depth_label": DEPTH_LABEL.get(int(rank), "") if pd.notna(rank) else "",
            "chart_slot_size": size,
            "chart_slot_key": f"{r.team} {unit} slot {r.slot} {slot_pos}".strip() if on_chart else "",
            "replacement_status": replacement_status,
            "replacement_rank": successor_rank,
            "replacement_depth_label": DEPTH_LABEL.get(int(successor_rank), "") if pd.notna(successor_rank) else "",
            "replacement_player": _strip_jersey(successor) if successor else "",
            "replacement_player_raw": successor_raw,
            "replacement_player_url": successor_url,
            "replacement_chart_disclosure": (
                "the chart lists an ordered name in the next position; it does not state that "
                "he played, started or took a snap" if successor else
                "no ordered name is listed behind him on this chart" if on_chart else
                "no chart entry exists for him, so no replacement can be identified"),
            "role_evidence": "CHART_POSITION_ONLY" if on_chart else "NONE",
            "exposure_score": exposure,
            "exposure_basis": exposure_basis,
            "injury_report_url": r.source_url,
            "depth_chart_url": chart_url,
            "injury_capture_utc": r.retrieved_utc,
            "depth_capture_utc": chart_utc,
        })

    depth = pd.DataFrame(rows)

    # --- per-slot exposure: defence vs offence ----------------------------
    # Built from the CHART, not from the injury list. A slot's depth structure
    # is a property of the chart; the injury report only says which of those men
    # is unavailable. Deriving "who is next" from the injured subset alone was a
    # real defect in the first cut of this module: it reported NOBODY LISTED for
    # a 3-deep slot whenever the only injured man in it was the depth-1 man, and
    # two healthy names sat behind him on the chart the whole time.
    slot_status = (inj.assign(k=inj.player.map(_norm))
                   .merge(dep[["team", "k", "unit", "slot"]], on=["team", "k"], how="inner"))
    status_by_player = {}
    for r in slot_status.itertuples(index=False):
        key = (r.team, r.unit, str(r.slot), _norm(r.player))
        # a player can be listed twice (e.g. WR and returner); keep the worst status
        prev = status_by_player.get(key, "")
        rank = {"Out": 3, "Doubtful": 2, "Questionable": 1, "": 0}
        if rank.get(r.game_status, 0) > rank.get(prev, 0):
            status_by_player[key] = r.game_status

    chart = dep.copy()
    chart["pos_key"] = [f"{t} {u} slot {sl} {pos}" for t, u, sl, pos in
                        zip(chart.team, chart.unit, chart.slot, chart.position)]
    chart["status"] = [status_by_player.get((t, u, str(sl), k), "")
                       for t, u, sl, k in zip(chart.team, chart.unit, chart.slot, chart.k)]
    chart["statused"] = chart.status.ne("") | chart.k.isin(
        set(_norm(x) for x in inj.player))

    slots = []
    # A club may chart two men at the same rank (a co-starter). That is real data,
    # not a bug: when one of them is Out the other is still listed available, so the
    # "replacement" is a co-starter and the depth label is 1st string. Counting the
    # ties keeps that visible instead of looking like a mis-parsed chart.
    ties = (chart.groupby(["team", "unit", "pos_key", "depth_rank"]).size()
            .reset_index(name="n"))
    tie_slots = set()
    for r in ties[ties.n > 1].itertuples(index=False):
        tie_slots.add((r.team, r.unit, r.pos_key))

    for (team, unit, pos_key), grp in chart.groupby(["team", "unit", "pos_key"], sort=True):
        known = grp[grp.k.isin(set(_norm(x) for x in inj.player))]
        if known.empty:
            continue
        grp = grp.sort_values("depth_rank")
        out = grp[grp.status.isin(STATUS_UNAVAILABLE)]
        risk = grp[grp.status.isin(STATUS_RISK)]
        if out.empty and risk.empty:
            continue
        available = grp[~grp.status.isin(STATUS_UNAVAILABLE)]
        top_available = int(available.depth_rank.min()) if len(available) else None
        slots.append({
            "team": team, "unit": unit,
            "chart_slot": pos_key,
            "chart_position": grp.position.iloc[0],
            "chart_slot_size": int(len(grp)),
            "out": int(len(out)), "doubtful_or_questionable": int(len(risk)),
            "top_out_rank": int(out.depth_rank.min()) if len(out) else None,
            "highest_listed_available_rank": top_available if top_available else "",
            "listed_available": int(len(available)),
            "backup_man_is_depth": (DEPTH_LABEL.get(top_available, "")
                                    if top_available else "NOBODY LISTED"),
            "next_man_listed": (_strip_jersey(available.player.iloc[0]) if len(available) else ""),
            "chart_has_rank_tie": bool((team, unit, pos_key) in tie_slots),
            "next_man_shares_top_rank": bool(
                len(available) and len(grp[grp.depth_rank == available.depth_rank.iloc[0]]) > 1),
            "depth_chart_url": grp.source_url.iloc[0],
            "injury_report_url": (grp[grp.status.ne("")].source_url.iloc[0]
                                  if grp[grp.status.ne("")].shape[0] else INJURY_URL),
        })
    slots_df = pd.DataFrame(slots).sort_values(["team", "unit", "chart_slot"]).reset_index(drop=True)

    # ---- the depth of the replacement, which is the point of the module ----
    # For every slot where the club's top listed man is unavailable, the man who
    # inherits is the highest-ranked name still listed. His chart rank *is* the
    # depth of the replacement. Two men down means a 3rd string plays; the zero
    # in that bucket below is a finding, not an omission.
    inherited = slots_df[pd.to_numeric(slots_df.out, errors="coerce").fillna(0) > 0].copy()
    inherited["replacement_chart_rank"] = pd.to_numeric(
        inherited.highest_listed_available_rank, errors="coerce")
    inherited["replacement_depth"] = inherited.replacement_chart_rank.map(
        lambda r: DEPTH_LABEL.get(int(r), "") if pd.notna(r) else "NOBODY LISTED")
    inherited["case"] = [
        (f"top-listed man (depth {int(t)}) unavailable; club lists the "
         f"{lab} next" if pd.notna(r) and pd.notna(t) else
         "top-listed man unavailable; club lists nobody else at this slot")
        for r, t, lab in zip(inherited.replacement_chart_rank, inherited.top_out_rank,
                             inherited.replacement_depth)]
    inherited.to_csv(PROC / "replacement_deep_cases.csv", index=False)
    depth_depth_counts = {lab: int((inherited.replacement_depth == lab).sum())
                          for lab in DEPTH_LABEL.values()}
    depth_depth_counts["NOBODY LISTED"] = int(
        (inherited.replacement_depth == "NOBODY LISTED").sum())

    # Losing the top man is only a *depth* problem when the man behind him is
    # himself below the top two strings.
    deep_cases = inherited[inherited.replacement_depth.isin(
        ["3rd string", "4th string", "5th string"])]

    summary = {
        "injury_rows": int(len(depth)),
        "teams_in_injury_report": int(depth.team.nunique()),
        "teams_with_chart": int(dep.team.nunique()),
        "joined_to_chart": int((depth.replacement_status != "NOT ON CHART").sum()),
        "not_on_chart": int((depth.replacement_status == "NOT ON CHART").sum()),
        "out": int(depth.game_status.eq("Out").sum()),
        "doubtful": int(depth.game_status.eq("Doubtful").sum()),
        "questionable": int(depth.game_status.eq("Questionable").sum()),
        "no_game_status": int(depth.game_status.eq("").sum()),
        "distinct_players_out": int(depth[depth.game_status.eq("Out")].player.nunique()),
        "out_with_backup_listed": int(((depth.game_status == "Out")
                                       & (depth.replacement_status == "LISTED BELOW")).sum()),
        "out_with_no_listed_backup": int(((depth.game_status == "Out")
                                          & (depth.replacement_status == "NO LISTED BACKUP")).sum()),
        "distinct_players_out_with_no_listed_backup": int(
            depth[(depth.game_status == "Out")
                  & (depth.replacement_status == "NO LISTED BACKUP")].player.nunique()),
        "out_at_depth_1": int(((depth.game_status == "Out") & (depth.chart_rank == 1)).sum()),
        "out_at_depth_2": int(((depth.game_status == "Out") & (depth.chart_rank == 2)).sum()),
        "out_at_depth_3": int(((depth.game_status == "Out") & (depth.chart_rank == 3)).sum()),
        "out_at_depth_4": int(((depth.game_status == "Out") & (depth.chart_rank == 4)).sum()),
        "affected_slots": int(len(slots_df)),
        "slots_with_top_man_out": int(len(inherited)),
        "slots_with_a_charted_rank_tie": int(slots_df.chart_has_rank_tie.sum()),
        "slots_where_the_next_man_shares_the_top_rank": int(
            slots_df.next_man_shares_top_rank.sum()),
        "replacement_depth_counts": depth_depth_counts,
        "deep_replacement_cases": int(len(deep_cases)),
        "slots_needing_a_3rd_string_or_deeper": int(len(deep_cases)),
        "teams_missing_from_chart": sorted(set(depth.team) - set(dep.team)),
        "injury_capture_utc": sorted(set(depth.injury_capture_utc))[:1],
        "depth_capture_utc": sorted(set(depth[depth.depth_capture_utc != ""].depth_capture_utc))[:1],
        "boundary": ("A chart rank is a published position, not evidence of a snap. Both sources "
                     "are undated snapshots captured at the time shown; neither states a kickoff-"
                     "relative time, so no row asserts who will start."),
    }
    return depth, slots_df, summary


def main() -> None:
    depth, slots, summary = build()
    depth.to_csv(PROC / "replacement_depth.csv", index=False)
    slots.to_csv(PROC / "replacement_slots.csv", index=False)
    write_json(PROC / "replacement_summary.json", summary)
    print(f"replacement_depth: {depth.shape}")
    for k in ["injury_rows", "joined_to_chart", "not_on_chart", "out",
              "out_at_depth_1", "out_at_depth_2", "out_at_depth_3",
              "out_with_no_listed_backup", "affected_slots",
              "slots_needing_a_3rd_string_or_deeper"]:
        print(f"  {k}: {summary[k]}")
    print(f"  distinct players Out: {summary['distinct_players_out']}")
    print(f"  replacement depth: {summary['replacement_depth_counts']}")
    print(f"  charted rank ties: {summary['slots_with_a_charted_rank_tie']} slots · "
          f"next man shares the top rank: {summary['slots_where_the_next_man_shares_the_top_rank']}")
    print(f"  deep-replacement cases: {summary['deep_replacement_cases']}")
    print(f"  teams missing from chart: {summary['teams_missing_from_chart']}")


if __name__ == "__main__":
    main()
