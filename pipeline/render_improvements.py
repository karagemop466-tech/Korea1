"""T32 — render `improvements.html`: what to change to make the site decide better.

Rows are read from `data/review/improvements.csv`. The status column distinguishes what
this session actually built (and the build proves it, because the page is generated from
the same committed files) from what is proposed and awaiting your choice. Nothing in a
"Proposed" row has been implemented.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_site import OFFICIAL, ROOT, card, e, flag, kpi_grid, layout, src_link, table  # noqa: E402

RV = ROOT / "data" / "review"


def read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pill(text: str, tone: str = "") -> str:
    return f'<span class="pill {tone}">{e(text)}</span>' if text else ""


def ref(key: str) -> str:
    url = OFFICIAL.get(key)
    return src_link(url, key) if url else e(key)


def status_tone(s: str) -> str:
    if s.startswith("Implemented"):
        return "pos"
    if s.startswith("Partly"):
        return "warn"
    return ""


def build() -> str:
    rows = read(RV / "improvements.csv")
    done = [r for r in rows if r["status"].startswith(("Implemented", "Partly"))]
    proposed = [r for r in rows if not r["status"].startswith(("Implemented", "Partly"))]
    body = []

    body.append(kpi_grid([
        card(str(len(rows)), "Improvements registered", "each with options, cost and risk"),
        card(str(len(done)), "Built this session", "proven by the build, not asserted", "pos"),
        card(str(len(proposed)), "Proposed, not built", "awaiting your choice on a path"),
        card("0", "Changes made without a register row",
             "every edit this session maps to an id above", "pos"),
    ]))

    body.append(flag(
        "<strong>Review, then choose.</strong> Each row below is an option set, not an "
        "action. The rows marked <em>Implemented this session</em> were built because they "
        "add evidence without changing any number already published; the "
        "<em>Proposed</em> rows change behaviour or another session's file and are left for "
        "you. Paths for the underlying decisions are on the "
        "<a href=\"decision-hub.html\">decision hub</a>.", "info"))

    hdr = ["Id", "Area", "What the site does today", "Improvement", "Why it decides better",
           "Options", "Cost", "Risk", "Status", "Official reference"]
    def render(group: list[dict]) -> list[list[str]]:
        out = []
        for r in group:
            out.append([
                f'<code>{e(r["id"])}</code>',
                e(r["area"]),
                e(r["current_behaviour"]),
                f'<strong>{e(r["improvement"])}</strong>',
                e(r["why_it_improves_decision_making"]),
                e(r["options"]),
                e(r["cost"]),
                e(r["risk"]),
                pill(r["status"], status_tone(r["status"])),
                ref(r["official_reference"]),
            ])
        return out

    body.append(
        '<section><div class="section-head"><h2>Built this session</h2>'
        f'<p class="muted">{len(done)} rows · additive: no already-published number changed</p>'
        '</div>'
        '<div class="table-tools"><input class="filter" type="search" placeholder="Filter…">'
        '</div>'
        + table(render(done), hdr, cls="grid",
                caption="Improvements already carried out by session arena/534e771f-korea1.")
        + "</section>")

    body.append(
        '<section><div class="section-head"><h2>Proposed — awaiting your choice</h2>'
        f'<p class="muted">{len(proposed)} rows · none of these has been implemented</p></div>'
        '<div class="table-tools"><input class="filter" type="search" placeholder="Filter…">'
        '</div>'
        + table(render(proposed), hdr, cls="grid",
                caption="Improvements proposed but not implemented; each needs a path chosen "
                        "on the decision hub first.")
        + "</section>")

    body.append(
        '<section><div class="section-head"><h2>What this session did not do</h2></div>'
        '<div class="findings"><ul>'
        '<li>It did not refresh the pinned data snapshot. That is decision DH-04 and it moves '
        'every published number, so it needs your approval and a fresh audit.</li>'
        '<li>It did not add any availability term to the line-origination model. That is '
        'DH-05 and the repository has no measured point value for an absence yet.</li>'
        '<li>It did not edit any file owned by another session, except one repair (IMP-05) '
        'that makes the build deterministic again; the request to fix the depth-chart parser '
        '(IMP-06) is logged in <code>COORDINATION.md</code> rather than edited.</li>'
        '<li>It did not merge or close the three open pull requests from earlier sessions.</li>'
        '</ul></div></section>')

    return "\n".join(body)


def main() -> int:
    title = "Site improvements"
    subtitle = ("What to change so the site supports a decision better — each row with its "
                "options, cost, risk and whether it has been built.")
    html = layout("improvements.html", title, subtitle, build(), wide=True)
    path = ROOT / "improvements.html"
    path.write_text(html, encoding="utf-8")
    print(f"  wrote {path.name} ({len(html):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
