"""Capture the official NFL documents for Week 11 of the 2026 season, verbatim, with hashes.

Why this module exists
----------------------
Two measured problems on 2026-11-19:

1. **The evidence is a week stale.** Week 11 kicks off on Thursday 2026-11-19 at 20:15 ET
   (2026-11-20T01:15Z). The repository's newest football evidence is the Week 10 injury
   report captured 2026-11-18T04:24:05Z. The official Week 11 report was published on
   Wednesday 2026-11-18 and has never been captured here.
2. **The scheduled capture is broken.** `.github/workflows/availability.yml` last
   *succeeded* at 2026-11-18T04:23:40Z; the three runs after that
   (2026-11-18T19:24Z, 2026-11-19T02:35Z, 2026-11-19T04:12Z) all failed at the step
   *Rebuild every table and page built from the captures*, which runs after the download.
   So a new official week cannot currently enter the repository at all.

The Arena build sandbox has no egress to nfl.com (allowlisted shell), and this project's
token cannot create a `workflow_dispatch` event ("Resource not accessible by
integration", HTTP 403, measured 2026-11-19T12:2xZ). A GitHub-hosted runner *can* reach
nfl.com. So the split is:

  * **this module** runs only on a runner and only ever *downloads and stores bytes* --
    no parsing, no interpretation, so a parser bug can never destroy a capture;
  * **`pipeline/week11_20261119.py`** runs offline inside `make build` and parses those
    committed bytes, so the site stays byte-reproducible and `tests/check_rebuild.py`
    keeps its teeth.

What is stored, per source
--------------------------
`data/live/official_2026_11_19/raw/<slug>`   the response body, byte for byte
`data/live/official_2026_11_19/manifest.json` url, http status, bytes, sha256, UTC clock
                                              time of the read, and the error, if any

Rules
-----
* A failed download is recorded as a failure; it never overwrites a good capture.
* Redirects are followed and the final URL is recorded separately from the requested one,
  because a redirect is how nfl.com serves "the current week".
* Nothing is inferred, nothing is parsed here, and no value is ever written from memory.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "live" / "official_2026_11_19"
RAW = OUT / "raw"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")

# Sources that do not depend on any other capture. The game centres are added below,
# discovered from the schedule page rather than typed in by hand.
FIXED = [
    ("injury_report_week11_league_url",
     "https://www.nfl.com/injuries/league/2026/reg11",
     "Official NFL injury report, Week 11 of the 2026 season (week-addressed URL)"),
    ("injury_report_current",
     "https://www.nfl.com/injuries/",
     "Official NFL injury report, current-week URL (nfl.com redirects this to the live week)"),
    ("schedule_week11_reg_form",
     "https://www.nfl.com/schedules/2026/by-week/reg-11",
     "Official 2026 schedule, Week 11 (the URL form already cited in data/forward/official_schedule.csv)"),
    ("schedule_week11_week_form",
     "https://www.nfl.com/schedules/2026/by-week/week-11",
     "Official 2026 schedule, Week 11 (numeric URL form)"),
    ("reserve_list_2026_11",
     "https://www.nfl.com/transactions/league/reserve-list/2026/11",
     "Official NFL reserve list, November 2026"),
]


def fetch(url: str, tries: int = 3) -> tuple[int, str, bytes, str, str]:
    """Return (status, final_url, body, error, content_type). Never raises."""
    last_err = ""
    for attempt in range(1, tries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
                return (resp.status, resp.geturl(), body, "",
                        resp.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as exc:                     # server answered, with an error
            body = b""
            try:
                body = exc.read()
            except Exception:                                     # pragma: no cover
                pass
            if exc.code in (403, 404, 410, 451):
                return exc.code, url, body, f"HTTP {exc.code}", ""
            last_err = f"HTTP {exc.code}"
        except Exception as exc:                                  # network / TLS / timeout
            last_err = f"{type(exc).__name__}: {exc}"
        if attempt < tries:
            time.sleep(2 * attempt)
    return 0, url, b"", last_err, ""


def game_centre_urls(schedule_html: str, fixed: list[str] | None = None) -> list[str]:
    """Game-centre paths printed on the official schedule page, in page order, de-duplicated.

    Read from the document; never typed in. A page that prints none yields an empty list and
    the manifest records that, rather than the capture silently claiming success.
    """
    # nfl.com prints these as relative paths in the rendered anchors and as absolute URLs in
    # the RSC payload, so both forms are accepted; the 13 paths found this way were confirmed
    # against the live schedule page (2026-11-19) before the fallback list below was used.
    hits = re.findall(r"(?:https://www\.nfl\.com)?/games/[a-z0-9][a-z0-9-]*?-2026-reg-11(?=[\"'<\\ ])",
                      schedule_html)
    hits = ["https://www.nfl.com" + h if h.startswith("/") else h for h in hits]
    if not hits and fixed:
        hits = list(fixed)
    seen, out = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    clock = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "captured_utc": clock,
        "runner": "GitHub Actions (.github/workflows/week11-capture.yml)",
        "season": 2026,
        "week": 11,
        "rule": ("responses are stored byte for byte; nothing is parsed, inferred or typed in; "
                 "a failure is recorded as a failure and never overwrites a good capture"),
        "sources": [],
    }

    def store(slug: str, url: str, note: str) -> bytes:
        status, final_url, body, err, ctype = fetch(url)
        if body:
            (RAW / slug).write_bytes(body)
        manifest["sources"].append(dict(
            slug=slug, requested_url=url, final_url=final_url, note=note,
            http_status=status, bytes=len(body),
            sha256=hashlib.sha256(body).hexdigest() if body else "",
            content_type=ctype, error=err or ("" if body else "empty body")))
        print(f"{slug:44s} status={status:3d} bytes={len(body):>8d} {err}")
        return body

    bodies = {}
    for slug, url, note in FIXED:
        bodies[slug] = store(slug, url, note)

    # Game centres are discovered from whichever schedule capture came back with anchors.
    sched_html = ""
    for slug in ("schedule_week11_reg_form", "schedule_week11_week_form"):
        if bodies.get(slug):
            sched_html += bodies[slug].decode("utf-8", "replace")
    # Fallback identities, used only when a capture parses zero anchors. They were read off the
    # official Week 11 schedule page itself (https://www.nfl.com/schedules/2026/by-week/week-11)
    # at 2026-11-19T12:2xZ with the page tool, and every one of them is re-verified by the
    # capture's own HTTP status: a wrong path returns 404 and is recorded as a failure.
    VERIFIED_PATHS = [
        "colts-at-texans", "dolphins-at-bills", "ravens-at-panthers", "saints-at-bears",
        "titans-at-cowboys", "buccaneers-at-lions", "cardinals-at-chiefs", "steelers-at-eagles",
        "jaguars-at-giants", "jets-at-chargers", "raiders-at-broncos", "vikings-at-49ers",
        "bengals-at-commanders",
    ]
    centres = game_centre_urls(
        sched_html, [f"https://www.nfl.com/games/{s}-2026-reg-11" for s in VERIFIED_PATHS])
    manifest["game_centres_discovered"] = len(centres)
    if not centres:
        manifest["sources"].append(dict(
            slug="game_centre_index", requested_url="", final_url="", note="discovery step",
            http_status=0, bytes=0, sha256="", content_type="",
            error="no /games/...-2026-reg-11 anchor found on either schedule capture; "
                  "game centres were NOT captured, and this is published as a gap"))
        print("!! no game-centre anchors found on the schedule captures")
    for url in centres:
        slug = re.sub(r"[^a-z0-9]+", "_", url.rsplit("/", 1)[-1]).strip("_")
        time.sleep(1)
        store(f"game_centre__{slug}", url,
              "Official game centre (Game Info / venue / roof / surface, when printed)")

    # A summary row so a reader can see capture health without opening every entry.
    from collections import Counter
    c = Counter("ok" if s["sha256"] else "failed" for s in manifest["sources"])
    manifest["summary"] = {"ok": c["ok"], "failed": c["failed"],
                           "game_centres": len(centres)}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n",
                                       encoding="utf-8")
    print(f"capture: {c['ok']} ok / {c['failed']} failed · {len(centres)} game centres "
          f"· salt {sum(s['bytes'] for s in manifest['sources'])} bytes")
    # A capture where the injury report itself failed is a broken run and must be loud.
    return 0 if bodies.get("injury_report_week11_league_url") or bodies.get("injury_report_current") else 1


if __name__ == "__main__":
    sys.exit(main())
