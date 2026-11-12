"""T14 — official injury + depth-chart impact register (2026 Week 10 pilot).

Inputs are *official observations*, not model estimates:

  data/official/injuries_2026_w10.csv      NFL.com official injury report (Week 10, 2026)
  data/official/depth_charts_2026_w10.csv  club-published depth charts, 6 clubs
  data/official/provenance_2026_w10.json   URL, fetch time and SHA-256 for each file

Rules enforced here (fail closed):

1. Every row must name an official source URL on an allowlisted official host.
   A row without one is dropped *and reported*, never silently kept.
2. Depth rank is joined strictly by normalised player name. No fuzzy matching:
   an unmatched player is written as ``UNRANKED`` with ``depth_rank`` blank, and
   the row is counted as an unverified-rank row. We never guess a role.
3. A blank game status in the source stays blank (``NO DESIGNATION``). A blank is
   not read as "healthy"; practice participation is reported separately.
4. Counts published by this module are recomputed from the joined rows; the
   site prints them from the CSV, so a changed snapshot changes every number.

Out (all under data/processed/):

  injury_report.csv        every transcribed row + supplied depth context
  injury_replacements.csv  one row per reported player listed on a club chart,
                           naming the next man up at that slot
  injury_team_summary.csv  per-club availability and depth-deficiency counts
  injury_coverage.csv      club-by-club coverage ledger (6 of 32 verified)
  injury_checks.csv        the machine-checked invariants this module asserts
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROC, ROOT, sha256_of, write_json  # noqa: E402

OFFICIAL_DIR = ROOT / "data" / "official"
INJ = OFFICIAL_DIR / "injuries_2026_w10.csv"
DEPTH = OFFICIAL_DIR / "depth_charts_2026_w10.csv"
PROV = OFFICIAL_DIR / "provenance_2026_w10.json"

# Official hosts: NFL.com league site and the club-owned sites the league links to.
OFFICIAL_HOSTS = {
    "www.nfl.com", "nfl.com", "www.commanders.com", "www.giants.com",
    "www.patriots.com", "www.detroitlions.com", "www.chiefs.com",
    "www.atlantafalcons.com",
}
SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b", re.I)
NONWORD = re.compile(r"[^a-z0-9 ]+")
BLANK = ""


def norm(name: str) -> str:
    """Normalise a player name for an exact, suffix-insensitive join."""
    s = str(name).lower().replace("'", "").replace(".", " ")
    s = NONWORD.sub(" ", s)
    s = SUFFIX.sub(" ", s)
    return " ".join(s.split())


def host_ok(url: str) -> bool:
    return urlsplit(str(url)).scheme == "https" and urlsplit(str(url)).hostname in OFFICIAL_HOSTS


def add_slot_groups(depth: pd.DataFrame) -> pd.DataFrame:
    """Number repeated slot labels in file order.

    A chart can list two WR columns, two CB columns, or two TE columns. The
    (team, unit, slot, slot_group) tuple identifies one physical column, so a
    replacement is looked up in the *same* column and never across columns.
    A new column starts at the first row of the group and at every row whose
    rank is 1 (a column whose top slot is blank, e.g. KC KR/PR, therefore keeps
    the same group as its neighbours).
    """
    depth = depth.reset_index(drop=True).copy()
    depth["depth_rank_int"] = depth.depth_rank.astype(int)
    groups = []
    counter: dict[tuple, int] = {}
    for i, r in depth.iterrows():
        key = (r.team, r.unit, r.slot)
        first = i == 0 or (depth.loc[i - 1, "team"], depth.loc[i - 1, "unit"],
                           depth.loc[i - 1, "slot"]) != key
        if first or r.depth_rank_int == 1:
            counter[key] = counter.get(key, 0) + 1
        groups.append(counter[key])
    depth["slot_group"] = groups
    return depth.drop(columns=["depth_rank_int"])


def load_inputs():
    missing = [p.name for p in (INJ, DEPTH, PROV) if not p.exists()]
    if missing:
        raise SystemExit(f"missing official snapshot file(s): {missing}")
    inj = pd.read_csv(INJ, dtype=str).fillna(BLANK)
    depth = add_slot_groups(pd.read_csv(DEPTH, dtype=str).fillna(BLANK))
    prov = json.loads(PROV.read_text())
    return inj, depth, prov


def integrity(inj: pd.DataFrame, depth: pd.DataFrame, prov: dict) -> pd.DataFrame:
    checks = []

    def add(name, passed, detail):
        checks.append(dict(check=name, passed=bool(passed), detail=detail))

    add("injury rows present", len(inj) > 0, f"{len(inj)} rows")
    add("depth rows present", len(depth) > 0, f"{len(depth)} rows")
    add("every injury row has an official source",
        inj.source_url.map(host_ok).all(),
        f"{int(inj.source_url.map(host_ok).sum())}/{len(inj)} official")
    add("every depth row has an official source",
        depth.source_url.map(host_ok).all(),
        f"{int(depth.source_url.map(host_ok).sum())}/{len(depth)} official")
    add("injury file hash matches provenance",
        sha256_of(INJ) == prov["sources"][0]["sha256"], prov["sources"][0]["sha256"][:16])
    add("depth file hash matches provenance",
        sha256_of(DEPTH) == prov["depth_file"]["sha256"], prov["depth_file"]["sha256"][:16])
    add("depth rank is an integer >= 1",
        depth.depth_rank.astype(int).ge(1).all(), "all ranks >= 1")
    add("no duplicate (team, slot column, rank)",
        not depth.duplicated(["team", "unit", "slot", "slot_group", "depth_rank"]).any(),
        f"{depth[['team','unit','slot','slot_group']].drop_duplicates().shape[0]} slot columns")
    add("every club in the injury file has a depth chart",
        set(inj.team) <= set(depth.team), f"{sorted(set(inj.team))}")
    return pd.DataFrame(checks)


def enrich(inj: pd.DataFrame, depth: pd.DataFrame) -> pd.DataFrame:
    depth = depth.copy()
    depth["key"] = depth.player.map(norm)
    depth["depth_rank"] = depth.depth_rank.astype(int)

    # A player can appear at more than one slot (e.g. NE Ben Brown: LG1 and C2).
    # Take the *best* (lowest) rank as the role, and keep that slot as the context.
    best = (depth.sort_values("depth_rank")
                 .drop_duplicates("key", keep="first")[
                     ["key", "unit", "slot", "slot_group", "depth_rank"]])
    best = best.rename(columns={"unit": "chart_unit", "slot": "chart_slot", "depth_rank": "depth_rank"})
    slots = depth.groupby("key").slot.nunique().rename("slots_listed")

    out = inj.copy()
    out["key"] = out.player.map(norm)
    out = out.merge(best, on="key", how="left").merge(slots, on="key", how="left")

    out["depth_rank"] = out.depth_rank.astype("Int64")
    out["slots_listed"] = out.slots_listed.astype("Int64")
    out["chart_slot"] = out.chart_slot.fillna(BLANK)
    out["chart_unit"] = out.chart_unit.fillna(BLANK)
    out["slot_group"] = out.slot_group.astype("Int64")
    out["role"] = out.depth_rank.map(
        lambda r: "UNRANKED" if pd.isna(r) else ("STARTER" if int(r) == 1 else f"{int(r)}-STRING"))
    out["role_rank"] = out.depth_rank.map(
        lambda r: "unverified" if pd.isna(r) else ("starter" if int(r) == 1 else f"depth {int(r)}"))
    out["game_status"] = out.game_status.replace(BLANK, "NO DESIGNATION")
    out["injury"] = out.injury.replace(BLANK, BLANK)

    # Next man up: the next listed player at the same slot, strictly deeper.
    nxt, nxt_rank = [], []
    for r in out.itertuples():
        if pd.isna(r.depth_rank):
            nxt.append(BLANK); nxt_rank.append(pd.NA); continue
        pool = depth[(depth.team == r.team) & (depth.slot == r.chart_slot)
                     & (depth.slot_group == int(r.slot_group))
                     & (depth.depth_rank > int(r.depth_rank))].sort_values("depth_rank")
        if pool.empty:
            nxt.append(BLANK); nxt_rank.append(pd.NA)
        else:
            nxt.append(pool.iloc[0].player); nxt_rank.append(int(pool.iloc[0].depth_rank))
    out["next_man_up"] = nxt
    out["next_man_up_rank"] = pd.array(nxt_rank, dtype="Int64")
    return out


def summaries(rep: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for team, g in rep.groupby("team"):
        out_g = g[g.game_status.eq("Out")]
        q_g = g[g.game_status.isin(["Questionable", "Doubtful"])]
        starters_out = out_g[out_g.depth_rank.eq(1)]
        rows.append(dict(
            team=team,
            club=g.team_name.iloc[0],
            record=g.record.iloc[0] if "record" in g else BLANK,
            reported=int(len(g)),
            practice_only=int(g.game_status.eq("NO DESIGNATION").sum()),
            ruled_out=int(len(out_g)),
            doubtful=int(g.game_status.eq("Doubtful").sum()),
            questionable=int(g.game_status.eq("Questionable").sum()),
            starters_ruled_out=int(len(starters_out)),
            starters_flagged=int(q_g.depth_rank.eq(1).sum()),
            backups_ruled_out=int(len(out_g[out_g.depth_rank.gt(1)])),
            unranked_reported=int(g.depth_rank.isna().sum()),
            off_ruled_out=int(out_g.chart_unit.eq("Offense").sum()),
            def_ruled_out=int(out_g.chart_unit.eq("Defense").sum()),
            deepest_replacement_rank=(int(starters_out.next_man_up_rank.max())
                                      if starters_out.next_man_up_rank.notna().any() else pd.NA),
            source_url=g.source_url.iloc[0],
            chart_url=g.chart_url.iloc[0] if "chart_url" in g else BLANK,
        ))
    team = pd.DataFrame(rows).sort_values(["starters_ruled_out", "ruled_out", "reported"],
                                          ascending=[False, False, False])

    repl = rep[rep.depth_rank.notna() & rep.game_status.isin(["Out", "Doubtful", "Questionable"])].copy()
    repl = repl.sort_values(["team", "depth_rank"])
    return team, repl


def coverage(inj: pd.DataFrame, depth: pd.DataFrame) -> pd.DataFrame:
    clubs = sorted(depth.team.unique())
    rows = [dict(team=c, club=depth[depth.team.eq(c)].team_name.iloc[0],
                 depth_chart_verified="YES", chart_url=depth[depth.team.eq(c)].source_url.iloc[0],
                 chart_label=depth[depth.team.eq(c)].chart_label.iloc[0],
                 injury_rows=int(inj.team.eq(c).sum()))
            for c in clubs]
    excluded = sorted(set(inj.team) - set(clubs))
    rows.append(dict(team="(other clubs)", club="Not covered by this pilot", depth_chart_verified="NO",
                     chart_url="https://www.nfl.com/injuries/",
                     chart_label="26 of 32 clubs are outside the declared pilot scope",
                     injury_rows=0))
    if excluded:
        raise SystemExit(f"injury rows for a club without a verified chart: {excluded}")
    return pd.DataFrame(rows)


def main() -> None:
    inj, depth, prov = load_inputs()
    checks = integrity(inj, depth, prov)
    PROC.mkdir(parents=True, exist_ok=True)
    checks.to_csv(PROC / "injury_checks.csv", index=False)
    if not checks.passed.all():
        print(checks[~checks.passed].to_string(index=False))
        raise SystemExit("injury snapshot failed an integrity check")

    rep = enrich(inj, depth)
    # club record + chart URL are official observations copied from the snapshot
    meta = depth.drop_duplicates("team")[["team", "team_name", "record", "source_url"]].rename(
        columns={"source_url": "chart_url"})
    rep = rep.merge(meta, on="team", how="left", suffixes=("", "_chart"))
    rep["record"] = rep.record.fillna(BLANK)
    rep["chart_url"] = rep.chart_url.fillna(BLANK)

    team, repl = summaries(rep)
    cov = coverage(inj, depth)

    rep.to_csv(PROC / "injury_report.csv", index=False)
    team.to_csv(PROC / "injury_team_summary.csv", index=False)
    repl.to_csv(PROC / "injury_replacements.csv", index=False)
    cov.to_csv(PROC / "injury_coverage.csv", index=False)

    write_json(PROC / "injury_snapshot.json", {
        "snapshot": prov["snapshot"],
        "fetched_utc": prov["fetched_utc"],
        "injury_source": "https://www.nfl.com/injuries/",
        "injury_rows": int(len(rep)),
        "depth_rows": int(len(depth)),
        "clubs_covered": int(len(cov[cov.depth_chart_verified.eq("YES")])),
        "clubs_total": 32,
        "ruled_out": int(team.ruled_out.sum()),
        "starters_ruled_out": int(team.starters_ruled_out.sum()),
        "unranked_rows": int(rep.depth_rank.isna().sum()),
        "no_game_designation": int(rep.game_status.eq("NO DESIGNATION").sum()),
        "limitations": prov["limitations"],
    })
    print(f"  injury rows {len(rep)} · depth rows {len(depth)} · clubs covered {len(cov)-1}/32")
    print(f"  ruled out {int(team.ruled_out.sum())} · starters ruled out {int(team.starters_ruled_out.sum())}"
          f" · unranked {int(rep.depth_rank.isna().sum())}")
    print(f"  wrote injury_report.csv, injury_team_summary.csv, injury_replacements.csv, injury_coverage.csv, injury_checks.csv")


if __name__ == "__main__":
    main()
