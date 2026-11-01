#!/usr/bin/env python3
"""
98_linkcheck.py - the site cannot ship with a broken link or an unknown source id.

Checks, for every page in docs/:
  L01 every internal .html link resolves to a file
  L02 every asset (css/js) reference resolves
  L03 every data-source attribute resolves to an entry in data/sources.json
  L04 every page is reachable from the navigation rendered on every page
  L05 well-formedness: table / div / tbody tag counts balance
  L06 every page declares a title, a lang and the stylesheet

Writes data/linkcheck.json and exits non-zero on any failure.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "lab")
NAV = ["index.html", "lines.html", "strategies.html", "correlation.html", "props.html",
       "validation.html", "leaderboard.html", "sources.html", "flagged.html"]

with open(os.path.join(ROOT, "data", "sources.json")) as f:
    SOURCES = {s["id"] for s in json.load(f)["sources"]}

pages = sorted(f for f in os.listdir(DOCS) if f.endswith(".html"))
problems: list[dict] = []
counts = {"internal_links": 0, "assets": 0, "source_refs": 0, "external_links": 0}


def bad(check, page, detail):
    problems.append({"check": check, "page": page, "detail": detail})


for page in pages:
    with open(os.path.join(DOCS, page), encoding="utf-8") as f:
        text = f.read()

    hrefs = re.findall(r'href="([^"]+)"', text)
    for href in hrefs:
        if href.startswith(("http://", "https://", "mailto:")):
            counts["external_links"] += 1
            if not re.match(r"^https?://[^\s]+$", href):
                bad("L07 external url malformed", page, href)
            continue
        if href.endswith(".html"):
            counts["internal_links"] += 1
            if not os.path.exists(os.path.join(DOCS, href)):
                bad("L01 broken internal link", page, href)
        elif href.startswith("assets/"):
            counts["assets"] += 1
            if not os.path.exists(os.path.join(DOCS, href)):
                bad("L02 missing asset", page, href)

    for sid in set(re.findall(r'data-source="([^"]+)"', text)):
        counts["source_refs"] += 1
        if sid not in SOURCES:
            bad("L03 unknown source id", page, sid)

    for target in NAV:
        if f'href="{target}"' not in text:
            bad("L04 page missing from navigation", page, target)

    for tag in ("table", "div", "tbody", "thead", "tr"):
        if text.count(f"<{tag}") != text.count(f"</{tag}>"):
            bad("L05 unbalanced tag", page,
                f"<{tag}> {text.count('<' + tag)} vs </{tag}> {text.count('</' + tag + '>')}")

    if "<title>" not in text:
        bad("L06 missing title", page, "")
    if 'lang="en"' not in text:
        bad("L06 missing lang attribute", page, "")
    if 'assets/style.css' not in text:
        bad("L06 missing stylesheet", page, "")

payload = {
    "pages_checked": len(pages),
    "counts": counts,
    "problems": problems,
    "passed": not problems,
}
with open(os.path.join(ROOT, "data", "lab", "linkcheck.json"), "w") as f:
    json.dump(payload, f, indent=2)

print(f"{len(pages)} pages, {counts['internal_links']} internal links, "
      f"{counts['assets']} assets, {counts['source_refs']} source references, "
      f"{counts['external_links']} external links")
if problems:
    for p in problems[:20]:
        print("FAIL", p)
    sys.exit(1)
print("LINK CHECK PASSED")
