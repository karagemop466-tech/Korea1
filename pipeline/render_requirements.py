"""F2 — render REQUIREMENTS.md from requirements/requirements.csv.

One source of truth (`requirements/requirements.csv`) feeds both this markdown file and the
`requirements.html` page, so the two cannot drift. Nothing here is summarised by hand: the counts,
the per-area roll-up and the status vocabulary are computed.

Run: python pipeline/render_requirements.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402

SRC = ROOT / "requirements" / "requirements.csv"
OUT = ROOT / "REQUIREMENTS.md"
ORDER = ["MET", "PARTIAL", "FLAGGED", "NOT MET"]


def main() -> None:
    req = pd.read_csv(SRC)
    unknown = set(req.status) - set(ORDER)
    if unknown:
        raise SystemExit(f"unknown status value(s): {sorted(unknown)}")
    counts = req.status.value_counts().to_dict()

    lines = [
        "# Requirements traceability — NFL Line Lab",
        "",
        "Every requirement in the brief, one row each, with the artefact that satisfies it and a source",
        "link. Generated from [`requirements/requirements.csv`](requirements/requirements.csv) by",
        "`pipeline/render_requirements.py`; the same data renders as",
        "[`requirements.html`](https://karagemop466-tech.github.io/Korea1/requirements.html).",
        "",
        "**Status vocabulary** — `MET`: a published artefact proves it. `PARTIAL`: the work exists but a",
        "stated limitation applies. `FLAGGED`: blocked or unverified, published on the",
        "[Flagged for review](https://karagemop466-tech.github.io/Korea1/flagged.html) page.",
        "`NOT MET`: nothing was delivered and nothing was invented to cover the gap.",
        "",
        f"**{len(req)} requirements** — "
        + " · ".join(f"{int(counts.get(k, 0))} {k}" for k in ORDER),
        "",
        "## Coverage by area",
        "",
        "| Area | Requirements | MET | PARTIAL | FLAGGED / NOT MET |",
        "|---|---|---|---|---|",
    ]
    for area in req.area.drop_duplicates():
        sub = req[req.area == area]
        lines.append(f"| {area} | {len(sub)} | {int((sub.status == 'MET').sum())} | "
                     f"{int((sub.status == 'PARTIAL').sum())} | "
                     f"{int(sub.status.isin(['FLAGGED', 'NOT MET']).sum())} |")

    lines += ["", "## The list", ""]
    for area in req.area.drop_duplicates():
        lines += [f"### {area}", "",
                  "| # | Requirement | Status | How it is met | Evidence | Source |",
                  "|---|---|---|---|---|---|"]
        for r in req[req.area == area].itertuples():
            how = str(r.how_met).replace("|", "\\|")
            lines.append(f"| {r.id} | {str(r.requirement).replace('|', chr(92) + '|')} | "
                         f"**{r.status}** | {how} | [{r.evidence}]({r.evidence_href}) | "
                         f"[source]({r.source_url}) |")
        lines.append("")

    lines += [
        "## What is not satisfied",
        "",
        "| # | Requirement | Status | Why |",
        "|---|---|---|---|",
    ]
    for r in req[req.status.isin(["PARTIAL", "FLAGGED", "NOT MET"])].itertuples():
        lines.append(f"| {r.id} | {str(r.requirement).replace('|', chr(92) + '|')} | {r.status} | "
                     f"{str(r.how_met).replace('|', chr(92) + '|')} |")
    lines += [
        "",
        "None of these block publication: each is disclosed on the site, with the reason and what",
        "would unblock it, on the [Flagged for review](flagged.html) page.",
        "",
    ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.name}: {len(req)} requirements, "
          + ", ".join(f"{int(counts.get(k, 0))} {k}" for k in ORDER))


if __name__ == "__main__":
    main()
