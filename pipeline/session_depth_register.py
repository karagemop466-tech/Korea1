"""2026-11-15 depth-chart register: one row per club with capture time, source and row check (PS2).

Reads committed files only (no network). Source of every value:
    data/availability/manifest.json       capture time, sha256, HTTP status, parsed-row count per club
    data/availability/depth_charts.csv    the parsed chart rows (each row carries its source URL and time)

The register is a drift alarm as well as a register. For each club it compares the row count the
scraper wrote in the manifest with the number of rows actually present in depth_charts.csv. A mismatch
or a zero-row parse is written as a failure, never as a blank that looks like a clean chart.

Live labels: two club pages were read on 2026-11-15 (Packers, Texans). Their printed label is recorded
exactly. Every other club's label is left blank, because it was not read in this session.

Outputs
  data/integration/depth_register_2026_11_15.csv   one row per club (32)
  depth-register.html

Run:  python pipeline/session_depth_register.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_json  # noqa: E402
from render_site import layout, table  # noqa: E402
from session_common import BLANK, clean, e, ref_link, write_csv  # noqa: E402

AV = ROOT / "data" / "availability"

# Label printed on the club page, read live on 2026-11-15 (verbatim). Other clubs: not read.
LIVE_LABEL = {
    "GB": ("Unofficial, Nov. 10, 2026", "https://www.packers.com/team/depth-chart"),
    "HOU": ("Unofficial Depth Chart (heading above an image; no text rows)", "https://www.houstontexans.com/team/depth-chart"),
}


def build() -> pd.DataFrame:
    man = read_json(AV / "manifest.json")
    dep = pd.read_csv(AV / "depth_charts.csv", dtype=str).fillna("")
    dep["rank"] = pd.to_numeric(dep.depth_rank, errors="coerce")
    srcs = [s for s in man["sources"] if s["kind"] == "depth_chart"]
    assert len(srcs) == 32, f"expected 32 depth-chart sources in the manifest, found {len(srcs)}"
    rows = []
    for s in sorted(srcs, key=lambda x: x["team"]):
        t = s["team"]
        d = dep[dep.team == t]
        parsed = int(len(d))
        manifest_rows = int(s.get("rows", 0))
        if parsed == 0:
            check = "PARSE_FAILED"
        elif parsed == manifest_rows:
            check = "MATCH"
        else:
            check = "MISMATCH"
        grp = d.dropna(subset=["rank"]).groupby(["unit", "position", "slot"])
        shared = gaps = no_r1 = 0
        for _, g in grp:
            ranks = [int(x) for x in g["rank"]]
            shared += ranks.count(1) > 1
            no_r1 += ranks.count(1) == 0
            gaps += sorted(set(ranks)) != list(range(1, max(ranks) + 1))
        units = d.unit.value_counts().to_dict()
        label, label_url = LIVE_LABEL.get(t, ("", ""))
        rows.append(dict(
            team=t, club=(d.club.iloc[0] if parsed else ""),
            depth_source_url=s["url"], capture_utc=man["retrieved_utc"], sha256=s["sha256"],
            http_status=s["http_status"], bytes=s["bytes"],
            manifest_rows=manifest_rows, parsed_rows=parsed, row_check=check,
            offense_rows=int(units.get("Offense", 0)), defense_rows=int(units.get("Defense", 0)),
            special_teams_rows=int(units.get("Special Teams", 0)),
            slots=int(len(grp)), shared_rank1_slots=int(shared), rank_gap_slots=int(gaps),
            slots_without_rank1=int(no_r1),
            live_label_2026_11_15=label, live_label_source=label_url,
            previous_snapshot_kept=bool(s.get("previous_snapshot_kept", False)),
            error=s.get("error", ""),
        ))
    return pd.DataFrame(rows)


def page(reg: pd.DataFrame) -> str:
    n_match = int((reg.row_check == "MATCH").sum())
    n_fail = int((reg.row_check != "MATCH").sum())
    cards = (f'<div class="cards">'
             f'<div class="card">{len(reg)}<div class="card-label">club charts in the register</div></div>'
             f'<div class="card">{n_match}<div class="card-label">rows match the manifest (drift check passed)</div></div>'
             f'<div class="card">{n_fail}<div class="card-label">failed the drift check (shown, not hidden)</div></div>'
             f'<div class="card">{int(reg.parsed_rows.sum())}<div class="card-label">parsed chart rows in total</div></div>'
             f'</div>')
    rows = []
    for r in reg.itertuples(index=False):
        flag = {"MATCH": "MATCH", "PARSE_FAILED": "PARSE FAILED", "MISMATCH": "MISMATCH"}[r.row_check]
        label = e(r.live_label_2026_11_15) if r.live_label_2026_11_15 else BLANK
        label_src = ref_link("club page", r.live_label_source) if r.live_label_source else ""
        rows.append([
            f"<strong>{e(r.team)}</strong> {e(r.club)}",
            e(r.capture_utc),
            f"<code>{e(r.sha256[:12])}…</code>",
            f"{r.manifest_rows} / {r.parsed_rows}",
            e(flag),
            f"{r.offense_rows} / {r.defense_rows} / {r.special_teams_rows}",
            f"{r.shared_rank1_slots} / {r.rank_gap_slots} / {r.slots_without_rank1}",
            (label + (" " + label_src if label_src else "")) if r.live_label_2026_11_15 else BLANK,
            ref_link("Club depth chart", r.depth_source_url),
        ])
    body = f"""
<section><h2>Depth-chart register</h2>
<p class="lede">One row per club: when the chart was captured, which club page it came from, the sha256 of the bytes that were read, and whether the parsed rows match the count the scraper wrote. Every row links to the club's own depth-chart page. The row-level chart lines are in the committed file <code>data/availability/depth_charts.csv</code>, each with its own source URL and time.</p>
{cards}
{table(rows, ["Club", "Captured (UTC)", "sha256 (first 12)", "Rows: manifest / parsed", "Drift check", "Offense / Defense / Special teams rows", "Shared · gap · no-rank-1 slots", "Label printed on the page (read live 2026-11-15)", "Source"], caption="32 clubs · capture time, hash and row check on every row")}
</section>
<section><h2>How to read it</h2>
<ul class="plain">
<li><strong>Drift check.</strong> MATCH means the parsed row count equals the count the scraper wrote. PARSE FAILED means zero rows were parsed (Houston, F-43); the chart is not used, and its cells are blank everywhere on this site.</li>
<li><strong>Shared · gap · no-rank-1 slots.</strong> A shared slot names more than one rank-1 player. A gap is a missing rank in a slot. A no-rank-1 slot has backups listed but no starter. None of them is resolved by guessing.</li>
<li><strong>Labels.</strong> The Packers page carries "Unofficial, Nov. 10, 2026" (F-33) and the Houston page "Unofficial Depth Chart" (F-18). The labels are shown, not used to rank sources. Blank labels mean the page was not read in this session.</li>
<li><strong>Dates.</strong> The capture time is the scraper run time recorded in the manifest. The page's own printed date is not captured, and the register does not treat the run time as the chart's publication date.</li>
<li><strong>Raw bytes.</strong> Only the sha256 is kept. Raw bytes are not retained on the site (F-30), so a hash cannot be re-checked here without re-reading the page.</li>
</ul></section>
"""
    return layout("depth-register.html", "Depth-chart register: date, source and row check per club",
                  "One row per club. Capture time, source page, sha256 and drift check on every row.",
                  body, wide=True)


def main() -> None:
    reg = build()
    write_csv(reg, "depth_register_2026_11_15.csv")
    (ROOT / "depth-register.html").write_text(page(reg), encoding="utf-8")
    print(json.dumps(dict(clubs=len(reg), match=int((reg.row_check == "MATCH").sum()),
                          not_match=int((reg.row_check != "MATCH").sum()),
                          parsed_rows=int(reg.parsed_rows.sum())), indent=1))


if __name__ == "__main__":
    main()
