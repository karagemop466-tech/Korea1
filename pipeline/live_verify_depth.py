"""V1b — independent verification of the published depth-chart snapshot.

Compares `data/availability/depth_charts.csv` (written by the scheduled
availability workflow from each club's `/team/depth-chart` page) against
`data/live/official_depth_extract_2026_11_13.csv`, transcribed directly from
four official club charts while reading them in full on 2026-11-13.

The unit of comparison is a *slot*: one published position row of one club,
identified by (team, unit, position, occurrence). The ordered list of players in
that row is compared element by element, because the depth order is exactly what
the site's "1st / 2nd / 3rd / 4th string" claim rests on.

Verdicts per slot
-----------------
MATCH      the ordered player list is identical
MISMATCH   the ordered player list differs in order, membership or length
MISSING    the club publishes the slot; the snapshot has no such slot
EXTRA      the snapshot has a slot the club page (as transcribed) does not

Club disclaimers found on the official pages are recorded as irregularity rows,
because they change what the site is allowed to claim: two of the four charts
are explicitly *unofficial*.

Run: python pipeline/live_verify_depth.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, write_json  # noqa: E402

LIVE = ROOT / "data" / "live"
SNAPSHOT = ROOT / "data" / "availability" / "depth_charts.csv"
EXTRACT = LIVE / "official_depth_extract_2026_11_13.csv"

# Disclaimers read on the official pages themselves, quoted, with their source.
DISCLAIMERS = [
    dict(team="DET", source_url="https://www.detroitlions.com/team/depth-chart",
         quoted_text="2026 Unofficial Depth Chart Compiled by Lions Football Communications",
         consequence=("the chart the site treats as the club's published order is labelled "
                      "unofficial by the club itself; a 2nd-string cell is an ordering, not a "
                      "depth-chart fact the club commits to")),
    dict(team="NE", source_url="https://www.patriots.com/team/depth-chart",
         quoted_text=("The 2026 depth chart is unofficial and is published by the writers of "
                      "Patriots.com. The depth chart reflects the opinions of the Patriots.com "
                      "writers and don't necessarily reflect those of the organization."),
         consequence=("the Patriots chart is the writers' opinion, not a club statement; any "
                      "1st/2nd/3rd-string claim for NE inherits that limit")),
    dict(team="WAS", source_url="https://www.commanders.com/team/depth-chart",
         quoted_text="(no unofficial disclaimer displayed; page titled 'Team Depth Chart')",
         consequence="ordering is published by the club; no publication timestamp is shown"),
    dict(team="NYG", source_url="https://www.giants.com/team/depth-chart",
         quoted_text="(no unofficial disclaimer displayed; page titled 'Team Depth Chart')",
         consequence="ordering is published by the club; no publication timestamp is shown"),
]


def _pub_rows(pub: pd.DataFrame) -> dict:
    """(team, unit, row-within-unit) -> ordered player list, from the snapshot.

    `slot` is continuous across a club's whole chart, so it is re-ranked inside
    each unit to line up with the official extract, which numbers rows per unit.
    """
    out = {}
    for (team, unit), g in pub.groupby(["team", "unit"], sort=False):
        for i, (slot, h) in enumerate(g.groupby("slot", sort=False), 1):
            out[(team, unit, i)] = [str(x) for x in h.sort_values("depth_rank").player.tolist()]
    return out


def _off_rows(ext: pd.DataFrame) -> dict:
    return {(r.team, r.unit, int(r.row)): [x for x in r.players.split("|") if x]
            for r in ext.itertuples()}


def main() -> int:
    LIVE.mkdir(parents=True, exist_ok=True)
    ext = pd.read_csv(EXTRACT, dtype=str, keep_default_na=False)
    pub = pd.read_csv(SNAPSHOT, dtype=str, keep_default_na=False)
    pub["depth_rank"] = pub["depth_rank"].astype(int)

    official = _off_rows(ext)
    published = _pub_rows(pub)
    pos_of = {(r.team, r.unit, int(r.row)): r.position for r in ext.itertuples()}

    rows = []
    teams = sorted(ext.team.unique())
    for key in sorted(set(official) | set(published)):
        if key[0] not in teams:
            continue
        ov, pv = official.get(key), published.get(key)
        url = ext[ext.team == key[0]].source_url.iloc[0]
        if ov is None:
            verdict, note = "EXTRA", "published slot not present on the official page as transcribed"
        elif pv is None:
            verdict, note = "MISSING", "official page publishes this slot; the snapshot has none"
        elif ov == pv:
            verdict, note = "MATCH", ""
        else:
            verdict = "MISMATCH"
            note = "ordered player list differs"
        rows.append(dict(team=key[0], unit=key[1], position=pos_of.get(key, ""), row=key[2],
                         published_order=" | ".join(pv or []),
                         official_order=" | ".join(ov or []),
                         verdict=verdict, source_url=url, note=note))
    detail = pd.DataFrame(rows)
    detail.to_csv(LIVE / "depth_slot_verification.csv", index=False)

    summary = (detail.groupby("team").verdict.value_counts().unstack(fill_value=0)
               .reindex(columns=["MATCH", "MISMATCH", "MISSING", "EXTRA"], fill_value=0)
               .reset_index())
    summary["slots"] = summary[["MATCH", "MISMATCH", "MISSING", "EXTRA"]].sum(axis=1)
    summary["verdict"] = summary.apply(
        lambda r: "PASS" if r.MISMATCH == 0 and r.MISSING == 0 and r.EXTRA == 0 else "REVIEW", axis=1)
    summary["source_url"] = summary.team.map(
        {t: ext[ext.team == t].source_url.iloc[0] for t in teams})
    summary.to_csv(LIVE / "depth_verification_summary.csv", index=False)

    disc = pd.DataFrame(DISCLAIMERS)
    disc.to_csv(LIVE / "depth_chart_disclaimers.csv", index=False)

    counts = detail.verdict.value_counts().to_dict()
    head = dict(
        generated_utc=pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        clubs=teams,
        slots_compared=int(len(detail)),
        match=int(counts.get("MATCH", 0)),
        mismatch=int(counts.get("MISMATCH", 0)),
        missing=int(counts.get("MISSING", 0)),
        extra=int(counts.get("EXTRA", 0)),
        players_compared=int(len(pub[pub.team.isin(teams)])),
        clubs_passing=int((summary.verdict == "PASS").sum()),
        unofficial_charts=int((disc.quoted_text.str.contains("Unofficial|unofficial")).sum()),
        scope_note=("four of 32 clubs (WAS, NYG, DET, NE), the two week-10 matchups used by "
                    "the lineup-deficiency page. A sample, not a census."),
    )
    write_json(LIVE / "depth_verification_summary.json", head)
    print(f"slots compared {head['slots_compared']} | players {head['players_compared']} "
          f"| MATCH {head['match']} MISMATCH {head['mismatch']} MISSING {head['missing']} "
          f"EXTRA {head['extra']}")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
