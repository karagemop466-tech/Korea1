"""Fail-closed verifier for the `review/` sub-site (session `arena/d58198fc-korea1`).

Checks, per page:
  R1  every table row carries an official or primary reference
  R2  every table is captioned
  R3  every internal link, anchor and asset resolves (relative to review/)
  R4  no leaked NaN / None / inf tokens
  R5  the canonical snapshot is printed in the footer
  R6  no external script/style dependency
  R7  every page listed in NAV exists and every page present is in NAV
plus cross-page:
  R8  every capture file referenced on official-sources.html exists on disk
  R9  the claim count printed on index.html equals the number of claim rows
  R10 every DRIFT claim appears on flagged.html
  R11 narrative numbers on the sub-site agree with the artifacts they cite

Exit code is non-zero on any failure.
"""
from __future__ import annotations

import html as html_mod
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_site import Collector, official_refs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "review"
DATA = ROOT / "data" / "repo_audit"
NAV = ["index.html", "claims.html", "my-lines.html", "injuries.html", "suggestions.html",
       "questions.html", "official-sources.html", "flagged.html"]
BAD = re.compile(r"(?<![\w/])(nan|NaN|None|inf|-inf)(?![\w/-])")


def main() -> int:
    sha = json.loads((ROOT / "data/sources.json").read_text())["upstream"]["commit_sha"]
    failures: list[str] = []
    results = []

    present = sorted(p.name for p in REVIEW.glob("*.html"))
    if set(present) != set(NAV):
        failures.append(f"page set mismatch: present={present} nav={NAV}")

    for name in NAV:
        page = REVIEW / name
        if not page.exists():
            failures.append(f"{name}: missing")
            continue
        raw = page.read_text()
        c = Collector()
        c.feed(raw)

        nosrc = [i for i, row in enumerate(c.rows, 1)
                 if not official_refs([h for _, hrefs in row for h in hrefs])]
        if nosrc:
            failures.append(f"{name}: {len(nosrc)} table rows without an official/primary reference")
        if c.captions != c.tables:
            failures.append(f"{name}: {c.tables} tables but {c.captions} captions")

        broken = []
        for href in c.links:
            u = urlsplit(href)
            if u.scheme or href.startswith("//"):
                continue
            target = unquote(u.path)
            path = (page.parent / target).resolve() if target else page
            if not path.exists():
                broken.append(href)
                continue
            if u.fragment and path.suffix == ".html":
                tc = Collector()
                tc.feed(path.read_text())
                if unquote(u.fragment) not in tc.ids:
                    broken.append(href)
        if broken:
            failures.append(f"{name}: broken internal links {broken[:5]}")

        leaked = BAD.findall(" ".join(t for row in c.rows for t, _ in row))
        if leaked:
            failures.append(f"{name}: leaked missing-value tokens {leaked[:3]}")
        if sha[:12] not in raw:
            failures.append(f"{name}: canonical snapshot missing from footer")
        ext = [a for a in c.assets if urlsplit(a).scheme or a.startswith("//")]
        if ext:
            failures.append(f"{name}: external asset dependency {ext[:3]}")
        missing_assets = [a for a in c.assets
                          if not (page.parent / unquote(urlsplit(a).path)).exists()]
        if missing_assets:
            failures.append(f"{name}: missing assets {missing_assets[:3]}")

        results.append((name, len(c.rows), c.tables, len(nosrc), len(broken)))
        print(f"[{'PASS' if not broken and not nosrc else 'FAIL'}] review/{name} "
              f"rows={len(c.rows)} tables={c.tables} official_missing={len(nosrc)} broken={len(broken)}")

    # R8: capture files referenced exist
    src = __import__("pandas").read_csv(DATA / "official_sources.csv")
    captured = src[src["http_status"].astype(str).str.len() > 0]["id"].tolist()
    for cid in captured:
        if not (DATA / "captures" / f"{cid}.json").exists():
            failures.append(f"capture {cid} claimed but data/repo_audit/captures/{cid}.json is missing")

    # R9: claim count on the index equals the claims file
    claims = __import__("pandas").read_csv(DATA / "claims.csv")
    idx_text = (REVIEW / "index.html").read_text()
    if f">{len(claims)}<" not in idx_text:
        failures.append(f"index.html does not print the claim count {len(claims)}")

    # R10: every DRIFT row is on flagged.html
    flagged = (REVIEW / "flagged.html").read_text()
    drift = claims[claims["verdict"] == "DRIFT"]
    for _, r in drift.iterrows():
        if html_mod.escape(str(r["claim"])) not in flagged:
            failures.append(f"flagged.html omits DRIFT claim {r['id']}")

    # R11: narrative numbers agree with the artifacts
    manifest = json.loads((ROOT / "data/availability/manifest.json").read_text())
    n_charts = len([s for s in manifest["sources"]
                    if s["kind"] == "depth_chart" and s.get("rows", 0) > 0])
    inj = (REVIEW / "injuries.html").read_text()
    if f"{n_charts}/32" not in inj:
        failures.append(f"injuries.html does not print the parsed-chart count {n_charts}/32")
    digest = __import__("pandas").read_csv(DATA / "digest_baseline.csv")
    n_bad = int((digest["state"] != "MATCH").sum())
    if f"{n_bad} of {len(digest)}" not in (REVIEW / "flagged.html").read_text():
        failures.append("flagged.html does not print the stale-digest count")

    # R13: rebuild determinism — rendering twice must produce identical bytes
    import subprocess
    before = {n: (REVIEW / n).read_bytes() for n in NAV}
    subprocess.run([sys.executable, str(ROOT / "pipeline/render_audit_site.py")],
                   cwd=ROOT, capture_output=True, check=True)
    changed = [n for n in NAV if (REVIEW / n).read_bytes() != before[n]]
    if changed:
        failures.append(f"render is not deterministic: {changed}")

    # R12: HTML structure + every class used is defined in assets/style.css
    from html.parser import HTMLParser
    css = (ROOT / "assets" / "style.css").read_text()
    defined = set(re.findall(r"\.([a-zA-Z][\w-]*)", css))
    VOID = {"meta", "link", "br", "img", "hr", "input", "source", "area", "base",
            "col", "embed", "param", "track", "wbr"}

    class _P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack, self.errs = [], []

        def handle_starttag(self, tag, attrs):
            if tag not in VOID:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if tag in VOID:
                return
            if not self.stack:
                self.errs.append(f"stray </{tag}>")
            elif self.stack[-1] == tag:
                self.stack.pop()
            else:
                self.errs.append(f"mismatch </{tag}> vs open <{self.stack[-1]}>")

    for name in NAV:
        raw = (REVIEW / name).read_text()
        parser = _P()
        parser.feed(raw)
        if parser.errs or parser.stack:
            failures.append(f"{name}: HTML structure {parser.errs[:3]} {parser.stack[:3]}")
        classes = set()
        for m in re.finditer(r'class="([^"]+)"', raw):
            classes |= set(m.group(1).split())
        undef = classes - defined
        if undef:
            failures.append(f"{name}: classes not defined in assets/style.css {sorted(undef)}")

    print()
    for f in failures:
        print("FAIL:", f)
    print(f"\n{len(failures)} failing checks")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
