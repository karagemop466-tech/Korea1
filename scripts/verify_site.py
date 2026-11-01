#!/usr/bin/env python3
"""Offline structural checks: every published data row has an evidence reference."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/strategy-data.json"
errors: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)

try:
    data = json.loads(DATA.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"FAIL: cannot parse {DATA.relative_to(ROOT)}: {exc}")
    sys.exit(1)

source_ids = {s.get("id") for s in data.get("sources", [])}
for source in data.get("sources", []):
    parsed = urlparse(source.get("url", ""))
    check(bool(source.get("title") and source.get("publisher") and source.get("supports")),
          f"Source {source.get('id')} is missing metadata")
    check(parsed.scheme == "https" and bool(parsed.netloc),
          f"Source {source.get('id')} does not have an HTTPS URL")
    check(bool(source.get("checked")), f"Source {source.get('id')} has no review date")

record_groups = ("strategies", "correlations", "gates", "leaderboard", "awards", "irregularities")
for group in record_groups:
    records = data.get(group, [])
    check(bool(records), f"{group} has no records")
    for i, record in enumerate(records, 1):
        refs = record.get("sources", [])
        check(bool(refs), f"{group}[{i}] has no source links")
        for ref in refs:
            check(ref in source_ids, f"{group}[{i}] references unknown source {ref}")
for corr in data.get("correlations", []):
    check(corr.get("value", "") == "", f"Correlation {corr.get('pair')} has an unsubstantiated value")
for strategy in data.get("strategies", []):
    check(bool(strategy.get("status")), f"Strategy {strategy.get('id')} has no status")
    check(strategy.get("empirical", "") == "", f"Strategy {strategy.get('id')} has an invented empirical result")

# All static local links and script/style references in published root-level HTML.
html_files = list(ROOT.glob("*.html"))
for html_path in html_files:
    text = html_path.read_text(encoding="utf-8")
    for href in re.findall(r'''(?:href|src)=["']([^"']+)["']''', text):
        if href.startswith(("https://", "http://", "mailto:", "#", "data:")):
            continue
        target = (html_path.parent / href.split("#", 1)[0].split("?", 1)[0]).resolve()
        check(target.exists(), f"Broken local link in {html_path.name}: {href}")

required_pages = ["index.html", "singles.html", "props.html", "parlays.html", "correlations.html",
                  "validation.html", "flagged.html", "sources.html"]
for page in required_pages:
    check((ROOT / page).is_file(), f"Required page missing: {page}")

# Every generated table uses sourceLinks() on its row, with source references validated above.
app = (ROOT / "assets/app.js").read_text(encoding="utf-8")
check("function sourceLinks" in app, "Source link renderer missing")
check("data.sources.find" in app, "Renderer does not resolve row citations from source register")

if errors:
    print("Site verification FAILED:")
    for error in errors:
        print(f" - {error}")
    sys.exit(1)

print(f"Site verification passed: {len(html_files)} root HTML pages; "
      f"{len(data['sources'])} source records; " + ", ".join(f"{len(data[k])} {k}" for k in record_groups) + ".")
print("Checks were structural/offline; external links must be reviewed from the source register.")
