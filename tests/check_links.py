"""Static link/asset checker for docs/.

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
# Updated by session arena/fb363967-korea1 (2026-11-02): requirements.html and verification.html added.
# Earlier update by arena/ea02c4fb-korea1: pipeline/render_site.py replaced the
# original nine pages with its own ten; the list below is the page set that actually ships, plus the
# annex pages in lab/. Every href on these pages (including the nav entry to lab/) is resolved.
PAGES = ["index.html", "executive-summary.html", "requirements.html", "lines.html", "strategies.html",
         "validation.html", "correlations.html", "props.html", "methodology.html", "flagged.html",
         "verification.html", "sources.html",
         "lab/index.html", "lab/lines.html", "lab/strategies.html", "lab/correlation.html",
         "lab/props.html", "lab/validation.html", "lab/leaderboard.html", "lab/sources.html",
         "lab/flagged.html"]
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
                # resolve relative to the page, so sub-sites (lab/) are checked correctly
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
