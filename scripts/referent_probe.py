#!/usr/bin/env python3
"""Resolve every external citation printed on the published site.

Why this exists
---------------
The site verifier (``pipeline/verify_site.py`` and ``tests/check_sources.py``)
checks that every published table row carries a reference whose *domain* is on
an allow-list.  That is a **presence** check: it proves a reference was printed,
not that the referenced page exists or says what the row attributes to it.  A
citation that resolves to a 404 is worse than no citation, because it looks
like evidence.

This script closes that gap.  For each distinct external URL printed anywhere in
the published HTML it records:

    status        HTTP status of the final response (0 = transport failure)
    final_url     URL after redirects (empty when the fetch failed)
    redirected    1 when the final URL path differs from the requested path
    title         HTML <title> of the response, when parseable
    bytes         response body length
    sha256        sha256 of the response body
    expect_hit    1/0/'' - whether the expected substring (if any) was found
    result        RESOLVED / REDIRECT / UNRESOLVED / UNCHECKED / EXPECTED-MISS

Honesty rules (these matter more than the counts):

* A transport failure is recorded as ``UNCHECKED``, never as success and never
  as failure.  "We could not reach it" is not the same as "it is not there".
* A 4xx/5xx is ``UNRESOLVED``.  It is published, not silently deleted.
* ``expect_hit=0`` is ``EXPECTED-MISS``: the page loaded but did not contain the
  text the site attributes to it.  That is a claim-support failure, which is a
  different and more serious defect than a dead link.
* Nothing here rewrites a URL.  Repairs are decided by a human and recorded in
  ``data/audit/referent_register.csv``.

Usage
-----
    python3 scripts/referent_probe.py                # probe every URL
    python3 scripts/referent_probe.py --limit 20     # first 20 (smoke test)
    python3 scripts/referent_probe.py --host nfl.com # one host only

The sandbox that renders the site cannot open arbitrary outbound connections,
so this probe is normally executed by ``.github/workflows/referent-audit.yml``
on a GitHub-hosted runner, which commits the result back to the branch.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse, urlunparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JSON = os.path.join(ROOT, "data", "audit", "referent_probe.json")
OUT_CSV = os.path.join(ROOT, "data", "audit", "referent_register.csv")
EXPECT_CSV = os.path.join(ROOT, "data", "audit", "referent_expectations.csv")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 Korea1-referent-audit/1.0"
)

# Pages that are published to GitHub Pages.  archive/** is deliberately excluded:
# it is a frozen record of superseded builds and its links are history, not claims.
PAGE_GLOBS = ["*.html", "lab/*.html"]


def published_pages() -> list[str]:
    out = []
    for g in PAGE_GLOBS:
        out.extend(sorted(glob.glob(os.path.join(ROOT, g))))
    return [p for p in out if os.path.basename(p) != "index.html" or True]


def extract_urls(pages: list[str]) -> dict[str, dict]:
    """Return {url: {'pages': [...], 'texts': [...]}} for external http(s) links."""
    link_re = re.compile(r'<a\s+[^>]*href="(https?://[^"#]+)(?:#[^"]*)?"[^>]*>(.*?)</a>', re.S)
    found: dict[str, dict] = {}
    for path in pages:
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        try:
            html = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in link_re.finditer(html):
            url = m.group(1).strip()
            if not url.startswith(("http://", "https://")):
                continue
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
            rec = found.setdefault(url, {"pages": [], "texts": []})
            if rel not in rec["pages"]:
                rec["pages"].append(rel)
            if text and text not in rec["texts"] and len(rec["texts"]) < 6:
                rec["texts"].append(text)
    return found


def load_expectations() -> dict[str, dict]:
    """Optional claim-support checks: url -> {ref_id, claim, expect}."""
    out: dict[str, dict] = {}
    if not os.path.exists(EXPECT_CSV):
        return out
    with open(EXPECT_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            url = (row.get("url") or "").strip()
            if url:
                out[url] = {
                    "ref_id": (row.get("ref_id") or "").strip(),
                    "claim": (row.get("claim") or "").strip(),
                    "expect": (row.get("expect") or "").strip(),
                    "manual_status": (row.get("manual_status") or "").strip(),
                    "manual_checked_at": (row.get("manual_checked_at") or "").strip(),
                    "manual_note": (row.get("manual_note") or "").strip(),
                }
    return out


def normalise(u: str) -> str:
    p = urlparse(u)
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme, p.netloc.lower(), path, "", "", ""))


def fetch(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return {
                "status": int(resp.status),
                "final_url": resp.geturl(),
                "content_type": (resp.headers.get("Content-Type") or "").split(";")[0].strip(),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "body": body,
                "error": "",
            }
    except urllib.error.HTTPError as exc:  # 4xx / 5xx still have a status
        body = b""
        try:
            body = exc.read()
        except Exception:
            pass
        return {
            "status": int(exc.code),
            "final_url": getattr(exc, "url", url) or url,
            "content_type": "",
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest() if body else "",
            "body": body,
            "error": f"HTTPError {exc.code}",
        }
    except Exception as exc:  # DNS, TLS, timeout, proxy block - NOT a failure verdict
        return {
            "status": 0,
            "final_url": "",
            "content_type": "",
            "bytes": 0,
            "sha256": "",
            "body": b"",
            "error": type(exc).__name__ + ": " + str(exc)[:200],
        }


TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
# NFL Football Operations serves its own 404 as a 200 with this marker.
FLAG_ON_THE_PLAY = "FLAG ON THE PLAY"


def classify(rec: dict) -> str:
    if rec["status"] == 0:
        return "UNCHECKED"
    if rec["error"].startswith("HTTPError") or rec["status"] >= 400:
        # A soft-404 still counts as unresolved.
        return "UNRESOLVED"
    if rec["soft404"]:
        return "UNRESOLVED"
    if rec["redirected"]:
        return "REDIRECT"
    if rec["expect"] and not rec["expect_hit"]:
        return "EXPECTED-MISS"
    return "RESOLVED"


def probe(url: str, timeout: int) -> dict:
    res = fetch(url, timeout=timeout)
    body = res.pop("body")
    text = ""
    if body:
        text = body.decode("utf-8", errors="replace")
    m = TITLE_RE.search(text)
    title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    low = text.lower()
    soft404 = FLAG_ON_THE_PLAY.lower() in low and len(text) < 5000
    rec = {
        "url": url,
        "status": res["status"],
        "final_url": res["final_url"],
        "redirected": 1 if (res["final_url"] and normalise(res["final_url"]) != normalise(url)) else 0,
        "content_type": res["content_type"],
        "bytes": res["bytes"],
        "sha256": res["sha256"],
        "title": title[:300],
        "soft404": soft404,
        "error": res["error"],
        "expect": "",
        "expect_hit": "",
        "result": "",
        "_text": low,  # kept only for the expectation test; stripped before output
    }
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="probe only the first N URLs")
    ap.add_argument("--host", default="", help="only probe URLs whose host contains this string")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--sleep", type=float, default=0.4, help="politeness delay between requests")
    args = ap.parse_args()

    pages = published_pages()
    urls = extract_urls(pages)
    expectations = load_expectations()
    if not urls:
        print("no external URLs found", file=sys.stderr)
        return 1

    keys = sorted(urls)
    if args.host:
        keys = [u for u in keys if args.host in urlparse(u).netloc]
    if args.limit:
        keys = keys[: args.limit]

    started = _dt.datetime.now(_dt.timezone.utc)
    rows = []
    checked = 0
    for url in keys:
        rec = probe(url, args.timeout)
        exp = expectations.get(url) or expectations.get(url.rstrip("/") + "/") or {}
        if exp.get("expect"):
            rec["expect"] = exp["expect"]
            rec["expect_hit"] = 1 if exp["expect"].lower() in rec["_text"] else 0
        rec["ref_id"] = exp.get("ref_id", "")
        rec["claim"] = exp.get("claim", "")
        rec["manual_status"] = exp.get("manual_status", "")
        rec["manual_checked_at"] = exp.get("manual_checked_at", "")
        rec["manual_note"] = exp.get("manual_note", "")
        rec["pages"] = ";".join(urls[url]["pages"])
        rec["n_pages"] = len(urls[url]["pages"])
        rec["link_text"] = " | ".join(urls[url]["texts"])[:300]
        rec["result"] = classify(rec)
        rec.pop("soft404", None)
        rec.pop("_text", None)
        rows.append(rec)
        checked += 1
        print(
            f"[{checked}/{len(keys)}] {rec['result']:<14} {rec['status']:<4} {url}",
            flush=True,
        )
        if args.sleep and checked < len(keys):
            time.sleep(args.sleep)

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    summary: dict[str, int] = {}
    for r in rows:
        summary[r["result"]] = summary.get(r["result"], 0) + 1
    payload = {
        "generated_utc": started.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "finished_utc": _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "pages_scanned": [os.path.relpath(p, ROOT).replace(os.sep, "/") for p in pages],
        "urls_total": len(keys),
        "summary": summary,
        "rows": rows,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=False)

    fields = [
        "url", "result", "status", "final_url", "redirected", "content_type",
        "bytes", "sha256", "title", "error", "ref_id", "claim", "expect",
        "expect_hit", "manual_status", "manual_checked_at", "manual_note",
        "n_pages", "pages", "link_text",
    ]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print("\n--- summary ---")
    for k in sorted(summary):
        print(f"{summary[k]:5d}  {k}")
    print(f"{len(rows):5d}  total probed ({len(urls)} distinct on site)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
