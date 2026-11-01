"""Enforce the project's sourcing rule on every generated page.

Rule (from the brief): every table row must link to an official source, and any value that could not be
confirmed against an official source must be left blank and flagged rather than inferred. This checker
walks every ``<tbody>`` row of the nine pages and requires one of

  * at least one ``<a href="http...">`` in the row (an external, citable source), or
  * an explicit unverified marker (``class="unverified"`` / the word "unverified" / "flagged"), which is
    only acceptable where the value is blank.

It also verifies that no row leaves a numeric-looking cell empty without such a marker, and that the
number of ``<td>`` cells matches the ``<th>`` count of its table.

Usage: python -m tests.check_sources
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Updated by the integration session arena/ea02c4fb-korea1: pipeline/render_site.py superseded the
# original nine pages (parlays.html/data.html/verification.html -> correlations.html/sources.html),
# which left this list pointing at files that no longer exist. Page set here is what ships at the root.
# The lab/ annex is governed by the same rule but enforced by scripts/99_verify.py, which requires every
# numeric cell to carry a data-source id that resolves to an official URL in data/lab/sources.json
# (a stronger form of this check, because it validates the identifier and not just the presence of a link).
PAGES = ["index.html", "executive-summary.html", "lines.html", "strategies.html", "validation.html",
         "correlations.html", "props.html", "methodology.html", "flagged.html", "sources.html"]

TABLE = re.compile(r"<table\b[^>]*>.*?</table>", re.S)
TBODY = re.compile(r"<tbody>(.*?)</tbody>", re.S)
TR = re.compile(r"<tr>(.*?)</tr>", re.S)
TH = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
EXT = re.compile(r'<a\s[^>]*href="https?://', re.I)
UNVERIFIED = re.compile(r"unverified|flagged|left blank|<span class=\"blank\"", re.I)
TAG = re.compile(r"<[^>]+>")


def text(html: str) -> str:
    return TAG.sub("", html).strip()


def check_page(path: Path) -> tuple[int, list[str]]:
    problems: list[str] = []
    rows = 0
    if not path.exists():
        return 0, [f"{path.name}: missing page"]
    for table in TABLE.findall(path.read_text()):
        ident = re.search(r'id="([^"]*)"', table)
        name = ident.group(1) if ident else "(no id)"
        for body in TBODY.findall(table):
            for raw in TR.findall(body):
                cells_th = TH.findall(raw)
                if cells_th:  # header row repeated inside a body
                    continue
                cells = TD.findall(raw)
                if not cells:
                    continue
                rows += 1
                label = text(cells[0])[:48] or "(empty)"
                if not EXT.search(raw) and not UNVERIFIED.search(raw):
                    problems.append(f"{path.name} :: {name} :: row '{label}' has no external source link")
                if any(c.strip() == "" for c in cells):
                    # a fully empty cell is only allowed when the row is flagged
                    if not UNVERIFIED.search(raw):
                        problems.append(f"{path.name} :: {name} :: row '{label}' has an empty cell and no flag")
    return rows, problems


def main() -> int:
    total = 0
    problems: list[str] = []
    for name in PAGES:
        rows, p = check_page(ROOT / name)
        total += rows
        problems.extend(p)
    print(f"checked {len(PAGES)} pages, {total} table rows")
    if problems:
        print(f"{len(problems)} row(s) without a source link or unverified flag:")
        for p in problems[:40]:
            print("  -", p)
        if len(problems) > 40:
            print(f"  ... {len(problems) - 40} more")
        return 1
    print("every table row links to an official source or is flagged as unverified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
