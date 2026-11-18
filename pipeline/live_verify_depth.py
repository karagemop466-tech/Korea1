"""V1b — point-in-time verification of the archived 2026-11-13 depth snapshot.

Compares the immutable `data/availability/history/2026-11-13/depth_charts.csv`
with `data/live/official_depth_extract_2026_11_13.csv`, transcribed directly
from four official club charts read on 2026-11-13. The snapshot and transcription
have separate capture timestamps, both published in the verification summary.

The current daily snapshot is deliberately not compared with this older extract:
changes between dates are temporal deltas, not parser errors. Current availability
and its history are published separately in `availability.html` and
`injury-deltas.html`; without a time-matched official extract, current depth rows
are not described as independently re-verified.

Two rules follow from that and are enforced here and by
`tests/test_live_verify.py`:

* The published snapshot is never rewritten to match an older transcription. A
  capture's rows are the parse of that capture and keep that capture's timestamp;
  editing them to agree with another date breaks the row-count and timestamp
  invariants that `pipeline/current_snapshot_audit.py` checks against
  `data/availability/manifest.json`.
* The gap between the verified date and the published date is still shown, not
  hidden: `data/live/depth_capture_divergence.csv` lists every slot whose ordered
  player list differs between the two dates, labelled as capture movement.

The unit of comparison is a *slot*: one position row of one club, identified by
(team, unit, position, occurrence). The ordered player list is compared element
by element, because the site's "1st / 2nd / 3rd / 4th string" claim rests on it.

Verdicts per slot
-----------------
MATCH      the ordered player list is identical in these dated captures
MISMATCH   the ordered player list differs in order, membership or length
MISSING    the official extract has a slot absent from the dated snapshot
EXTRA      the dated snapshot has a slot absent from the official extract

Club disclaimers found on the official pages are recorded as irregularity rows;
two of the four charts are explicitly *unofficial*.

Run: python pipeline/live_verify_depth.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LIVE_CAPTURE_UTC, ROOT, read_json, write_json  # noqa: E402

LIVE = ROOT / "data" / "live"
SNAPSHOT = ROOT / "data" / "availability" / "history" / "2026-11-13" / "depth_charts.csv"
SNAPSHOT_MANIFEST = SNAPSHOT.parent / "manifest.json"
CURRENT_SNAPSHOT = ROOT / "data" / "availability" / "depth_charts.csv"
CURRENT_MANIFEST = CURRENT_SNAPSHOT.parent / "manifest.json"
EXTRACT = LIVE / "official_depth_extract_2026_11_13.csv"

# The verified sample: the four clubs whose official charts were transcribed by hand.
CLUBS = ("DET", "NE", "NYG", "WAS")

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
    snapshot_manifest = read_json(SNAPSHOT_MANIFEST)
    current_manifest = read_json(CURRENT_MANIFEST)

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
            verdict, note = "EXTRA", "dated snapshot slot not present in the official extract"
        elif pv is None:
            verdict, note = "MISSING", "official extract has this slot; the dated snapshot has none"
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

    # Informational only: how far the current daily capture has moved since the
    # dated official transcription. This is not a defect list and it is not
    # verification of the current capture — it exists so a reader can see the
    # size of the gap between what was checked and what is being published.
    cur = pd.read_csv(CURRENT_SNAPSHOT, dtype=str, keep_default_na=False)
    cur["depth_rank"] = cur["depth_rank"].astype(int)
    cur_rows = _pub_rows(cur)
    current_manifest_rows = len(cur)
    drift = []
    for key in sorted(set(official) | set(cur_rows)):
        if key[0] not in teams:
            continue
        ov, cv = official.get(key), cur_rows.get(key)
        if ov == cv:
            continue
        if ov is None:
            verdict, note = "ONLY_IN_LATEST_CAPTURE", "the slot exists in the latest capture, not in the dated official transcription"
        elif cv is None:
            verdict, note = "MISSING_FROM_LATEST_CAPTURE", "the slot exists in the dated official transcription, not in the latest capture"
        else:
            verdict, note = "CAPTURE_MOVEMENT", "ordered player list differs between the two capture dates; not a parser defect"
        drift.append(dict(team=key[0], unit=key[1], row=key[2],
                          official_2026_11_13=" | ".join(ov or []),
                          latest_capture=" | ".join(cv or []),
                          verdict=verdict, note=note,
                          source_url=ext[ext.team == key[0]].source_url.iloc[0]))
    pd.DataFrame(drift).to_csv(LIVE / "depth_capture_divergence.csv", index=False)

    counts = detail.verdict.value_counts().to_dict()
    head = dict(
        generated_utc=LIVE_CAPTURE_UTC,
        official_source_read_utc=LIVE_CAPTURE_UTC,
        comparison_snapshot_utc=snapshot_manifest.get("retrieved_utc", ""),
        latest_snapshot_utc=current_manifest.get("retrieved_utc", ""),
        latest_snapshot_independently_verified=False,
        latest_snapshot_note=("The latest daily chart snapshot is not compared with this older "
                              "2026-11-13 official extract; differences between dates are not "
                              "classified as parser errors. The latest capture is never rewritten "
                              "to match the older transcription: its rows are the parse of its own "
                              "fetch and must keep their own capture timestamp."),
        current_capture_rows=current_manifest_rows,
        current_capture_divergent_slots=len(drift),
        current_capture_divergence_note=("Slots whose ordered player list differs between the dated "
                                         "official transcription and the latest capture, listed in "
                                         "data/live/depth_capture_divergence.csv. Capture movement, "
                                         "not a defect, and not a claim about who starts."),
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
