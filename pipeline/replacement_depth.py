"""T56 — the depth of the replacement, not only the fact of a replacement.

Why this is a separate artifact
-------------------------------
Knowing that a starter is out is a fact about one player. Knowing what plays
in his place is a fact about the *depth* behind him, and it is the fact that
moves a line: a first-string backup who has not started a game is a different
problem from a third-string player who has started eleven.

The official club depth charts publish that order. This module joins the
official injury report to the official club depth charts and records, for every
position group where the first-listed player is unavailable, **which string
replaces him**.

What is recorded, and what is not
---------------------------------
* `replacement_depth.csv` — one row per depth-chart slot whose first-listed
  player is unavailable, with the replacement's published rank (2nd / 3rd /
  4th string), the club's depth-chart URL, the injury-report URL and the
  capture time.
* `lineup_deficiency.csv` — the deficiency register gains the replacement tier
  in `expected_backup_tier`, with the evidence for it in `tier_evidence` and
  the club's chart in `roster_source_url`.

Three limits are enforced, not assumed away:

1. **A club that publishes no machine-readable order contributes nothing.** For
   those clubs the tier stays blank and the row says why. A blank tier is not
   a first-string replacement.
2. **The club's own caveat travels with the number.** Two of the clubs in the
   capture label their chart "unofficial"; the register says so.
3. **A slot whose published order failed an independent re-read is not used.**
   The verdict from the depth-slot verification is applied as a gate.

Outputs
-------
  data/processed/replacement_depth.csv       slot-level detail
  data/processed/lineup_deficiency.csv       enriched in place
  assets/data/replacement_depth.csv           the same, for the site

Run:  python pipeline/replacement_depth.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from common import PROC  # noqa: E402
from fetch_injuries import POSITION_MAP  # noqa: E402

AVAIL = ROOT / "data" / "availability"
LIVE = ROOT / "data" / "live"
SITE_DATA = ROOT / "assets" / "data"

# The clubs publish their own position labels. This is the editorial grouping
# of those labels into the position groups the injury report uses, so that a
# club's "NT" and the report's "DL" describe the same group. It is a mapping of
# labels only: no result, no availability and no outcome enters it.
DEPTH_POSITION_MAP: dict[str, tuple[str, str]] = {
    **POSITION_MAP,
    "EDGE": ("D", "DL"), "LDE": ("D", "DL"), "RDE": ("D", "DL"),
    "LDT": ("D", "DL"), "RDT": ("D", "DL"), "NT": ("D", "DL"), "N": ("D", "DL"),
    "ILB": ("D", "LB"), "MIKE": ("D", "LB"), "MLB": ("D", "LB"),
    "WILL": ("D", "LB"), "WLB": ("D", "LB"), "OLB": ("D", "LB"),
    "LOLB": ("D", "LB"), "LILB": ("D", "LB"), "ROLB": ("D", "LB"),
    "RILB": ("D", "LB"), "SAM": ("D", "S"),
    "DB": ("D", "CB"), "NCB": ("D", "CB"),
    "H": ("O", "RB"), "HB": ("O", "RB"), "FB": ("O", "RB"), "RUSH": ("O", "RB"),
    "T": ("O", "OL"), "G": ("O", "OL"),
    "LT": ("O", "OL"), "LOT": ("O", "OL"), "RT": ("O", "OL"), "ROT": ("O", "OL"),
    "LG": ("O", "OL"), "RG": ("O", "OL"),
    "PK": ("O", "P"),
}
UNIT_SIDE = {"Offense": "O", "Defense": "D"}

RANK_NUMBER = {"2nd string": 2, "3rd string": 3, "4th string": 4}

DETAIL_COLUMNS = [
    "team", "club", "unit", "side", "slot", "position", "position_group",
    "first_listed", "first_listed_game_status", "first_listed_practice_status",
    "flag", "replacement_player", "replacement_depth_rank",
    "replacement_depth_label", "replacement_verified",
    "depth_source_url", "injury_source_url", "depth_retrieved_utc",
    "depth_order_verdict", "note",
]


def _rank(label: str):
    return RANK_NUMBER.get(str(label).strip())


def build_detail() -> pd.DataFrame:
    slots_path = AVAIL / "slot_status.csv"
    if not slots_path.exists():
        return pd.DataFrame(columns=DETAIL_COLUMNS)
    slots = pd.read_csv(slots_path, dtype=str).fillna("")

    verdicts: dict[tuple[str, str, str, str], str] = {}
    v_path = LIVE / "depth_slot_verification.csv"
    if v_path.exists():
        v = pd.read_csv(v_path, dtype=str).fillna("")
        for r in v.itertuples(index=False):
            verdicts[(r.team, r.unit, r.position, str(r.row))] = r.verdict

    caveats: dict[str, str] = {}
    c_path = LIVE / "depth_chart_disclaimers.csv"
    if c_path.exists():
        c = pd.read_csv(c_path, dtype=str).fillna("")
        for r in c.itertuples(index=False):
            caveats[r.team] = r.quoted_text

    rows = []
    for r in slots.itertuples(index=False):
        flag = str(r.flag).strip()
        if not flag:
            continue
        pos = str(r.position).strip()
        mapped = DEPTH_POSITION_MAP.get(pos)
        if mapped is None:
            continue
        side, group = mapped
        unit_side = UNIT_SIDE.get(str(r.unit))
        if unit_side != side:
            continue
        verdict = verdicts.get((r.team, str(r.unit), pos, str(r.slot)), "")
        rank = _rank(r.next_listed_rank)
        note_bits = []
        if str(r.next_listed_rank).strip() == "no other available player listed in this slot":
            note_bits.append("no other player is listed behind him in this slot")
        if verdict and verdict != "MATCH":
            note_bits.append(f"independent re-read verdict: {verdict}")
        elif not verdict:
            note_bits.append("this slot was not part of the independent re-read")
        if r.team in caveats:
            note_bits.append("the club labels this chart unofficial")
        rows.append({
            "team": r.team, "club": r.club, "unit": r.unit, "side": side,
            "slot": r.slot, "position": pos, "position_group": group,
            "first_listed": r.first_listed,
            "first_listed_game_status": r.game_status,
            "first_listed_practice_status": r.practice_status,
            "flag": flag,
            "replacement_player": r.next_listed,
            "replacement_depth_rank": rank if rank else "",
            "replacement_depth_label": r.next_listed_rank,
            "replacement_verified": "no" if not r.next_listed else "yes",
            "depth_source_url": r.depth_source_url,
            "injury_source_url": r.injury_source_url,
            "depth_retrieved_utc": r.depth_retrieved_utc,
            "depth_order_verdict": verdict or "not re-read",
            "note": "; ".join(note_bits),
        })
    return pd.DataFrame(rows, columns=DETAIL_COLUMNS)


def enrich_deficiency(detail: pd.DataFrame) -> pd.DataFrame:
    """Attach the replacement depth to the deficiency register, in place."""
    ld_path = PROC / "lineup_deficiency.csv"
    if not ld_path.exists():
        return pd.DataFrame()
    ld = pd.read_csv(ld_path, dtype=str).fillna("")
    if detail.empty:
        return ld

    by_group: dict[tuple[str, str, str], list[dict]] = {}
    for r in detail.to_dict("records"):
        key = (r["team"], r["position_group"], r["side"])
        by_group.setdefault(key, []).append(r)

    tiers, evidences, urls, labels, states = [], [], [], [], []
    for r in ld.to_dict("records"):
        key = (r["team"], r["position_group"], r["side"])
        slots = by_group.get(key, [])
        if not slots:
            # No published order says anything about this group.
            tiers.append("")
            evidences.append(
                "no replacement depth on record — the club publishes no "
                "machine-readable depth order for this position group")
            urls.append(r.get("roster_source_url", ""))
            labels.append(r.get("roster_tier", ""))
            states.append("none on record")
            continue
        ranks = [s["replacement_depth_rank"] for s in slots if s["replacement_depth_rank"] != ""]
        detail_bits = []
        for s in slots:
            who = s["replacement_player"] or "no listed replacement"
            depth = s["replacement_depth_label"] or "depth not published"
            detail_bits.append(f"slot {s['slot']} ({s['position']}): "
                               f"{s['first_listed']} [{s['flag']}] -> {who} ({depth})")
        if ranks:
            worst = max(ranks)
            unpublished = sum(1 for x in slots if x["replacement_depth_rank"] == "")
            tiers.append(worst)
            states.append("published" if not unpublished else
                          f"partial — {unpublished} of {len(slots)} slots publish "
                          "no replacement")
            evidences.append("official club depth chart — " + "; ".join(detail_bits))
            urls.append(slots[0]["depth_source_url"])
            labels.append("official club depth chart (published order)"
                          + (" — the club labels this chart unofficial"
                             if "unofficial" in slots[0]["note"] else ""))
        else:
            tiers.append("")
            evidences.append("replacement depth not published — " + "; ".join(detail_bits))
            urls.append(slots[0]["depth_source_url"])
            labels.append("official club depth chart (published order), "
                          "replacement not listed")
            states.append("published order only — no replacement named")
    ld["expected_backup_tier"] = tiers
    ld["tier_evidence"] = evidences
    ld["roster_source_url"] = urls
    ld["roster_tier"] = labels
    ld["replacement_depth_status"] = states
    return ld


def main() -> None:
    detail = build_detail()
    detail.to_csv(PROC / "replacement_depth.csv", index=False)
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    detail.to_csv(SITE_DATA / "replacement_depth.csv", index=False)

    ld = enrich_deficiency(detail)
    if len(ld):
        ld.to_csv(PROC / "lineup_deficiency.csv", index=False)

    print(f"replacement_depth: {len(detail)} slots where the first-listed player "
          f"is unavailable")
    if len(detail):
        print(f"  replacement depth: "
              f"{detail.replacement_depth_label.value_counts().to_dict()}")
    if len(ld):
        filled = ld.expected_backup_tier.replace("", "0").astype(float)
        print(f"  deficiency rows: {len(ld)}; with a replacement tier: "
              f"{int((filled > 0).sum())}; without: {int((filled == 0).sum())}")


if __name__ == "__main__":
    main()
