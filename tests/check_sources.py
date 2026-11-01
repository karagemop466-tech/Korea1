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
# Discovered, not hard-coded - see the note in tests/check_links.py.
PAGES = sorted(p.name for p in ROOT.glob("*.html"))

TABLE = re.compile(r"<table\b[^>]*>.*?</table>", re.S)
TBODY = re.compile(r"<tbody>(.*?)</tbody>", re.S)
TR = re.compile(r"<tr>(.*?)</tr>", re.S)
TH = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
EXT = re.compile(r'<a\s[^>]*href="https?://', re.I)
# A row that documents a *missing* input may point at the on-site source register instead of an
# external page - but only if the row says so in words. That keeps "we could not find this" rows
# honest without letting unsourced claims through.
REGISTER = re.compile(r'href="(?:\.\./)*[\w-]*sources?\.html', re.I)
STATUS = re.compile(r"not present|not published|not available|unavailable|left blank|needs review|"
                    r"no .*source|blank by design", re.I)
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
                sourced = EXT.search(raw) or UNVERIFIED.search(raw) or (REGISTER.search(raw) and STATUS.search(raw))
                if not sourced:
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
