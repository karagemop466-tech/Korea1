"""Static link/asset checker across all canonical root pages and lab/ annex.

Verifies
  * every internal href resolves to a file that exists
  * every in-page anchor (#id) exists in the target document
  * no external CDN dependencies (the site must work offline / on Pages)
  * no empty table bodies and no leaked 'None'/'nan' cells

Usage: python -m tests.check_links
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    "index.html", "executive-summary.html", "lines.html", "injuries.html", "lineups.html",
    "strategies.html", "validation.html", "correlations.html", "props.html",
    "questions.html", "suggestions.html", "decisions.html", "methodology.html",
    "requirements.html", "verification.html", "flagged.html", "sources.html", "audit.html",
    "lab/index.html", "lab/lines.html", "lab/strategies.html", "lab/correlation.html",
    "lab/props.html", "lab/validation.html", "lab/leaderboard.html", "lab/sources.html",
    "lab/flagged.html",
]
HREF = re.compile(r'href="([^"]+)"')
ID = re.compile(r'id="([^"]+)"')
SRC = re.compile(r'src="([^"]+)"')


def main() -> int:
    pages = [ROOT / p for p in PAGES if (ROOT / p).exists()]
    missing = [p for p in PAGES if not (ROOT / p).exists()]
    errors: list[str] = [f"missing page {m}" for m in missing]
    for page in pages:
        text = page.read_text()
        local_ids = set(ID.findall(text))
        for href in HREF.findall(text):
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            target, _, anchor = href.partition("#")
            if target:
                path = (page.parent / target).resolve()
                if not path.exists():
                    errors.append(f"{page.name}: missing file for href {href}")
                    continue
                if anchor and anchor not in set(ID.findall(path.read_text())):
                    errors.append(f"{page.name}: missing anchor #{anchor} in {target}")
            elif anchor and anchor not in local_ids:
                errors.append(f"{page.name}: missing local anchor #{anchor}")
        for s in SRC.findall(text):
            if s.startswith(("http://", "https://")):
                errors.append(f"{page.name}: external script/style dependency {s}")
            elif not (page.parent / s).exists():
                errors.append(f"{page.name}: missing asset {s}")
        if ">None<" in text:
            errors.append(f"{page.name}: leaked None cell")
        if re.search(r">\s*nan\s*<", text):
            errors.append(f"{page.name}: leaked nan cell")
        if "<tbody></tbody>" in text:
            errors.append(f"{page.name}: empty table body")
    print(f"checked {len(pages)} pages")
    if errors:
        print("\n".join(errors))
        return 1
    print("all internal links, anchors and assets resolve; no external dependencies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
