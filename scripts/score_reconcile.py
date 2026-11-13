#!/usr/bin/env python3
"""Re-check the published NFL.com score census against the live official game pages.

`data/governance/post_pin_nfl_scores_2026_11_12.csv` is a 28-row census of Week 8-9
2026 final scores that the pinned community archive still listed as UPCOMING.  Each row
was transcribed by an earlier session from nfl.com on 2026-11-12.  This script opens the
official game page for every one of those 28 rows, re-reads the final score from the
page, and records whether the two agree.

It is a *reconciliation*, not a re-transcription:

    MATCH     the live official page agrees with the published row
    MISMATCH  they disagree - the published row is wrong and is flagged
    UNPARSED  the page loaded but the score could not be read from it; no verdict
    UNCHECKED the fetch failed at the transport layer; no verdict
    UNRESOLVED the game page returned 4xx/5xx; the row's citation is dead

Nothing here edits the census.  Mismatches are published on the Flagged-for-Review page
for a human to resolve.

Runs on a GitHub-hosted runner (the build sandbox has no egress to nfl.com) via
`.github/workflows/referent-audit.yml`.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "governance", "post_pin_nfl_scores_2026_11_12.csv")
OUT_CSV = os.path.join(ROOT, "data", "audit", "score_reconciliation.csv")
OUT_JSON = os.path.join(ROOT, "data", "audit", "score_reconciliation.json")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 Korea1-score-reconcile/1.0"
)

# "ARI 33 – 30 DAL (Final)"  ->  away ARI 33, home DAL 30
CLAIM = re.compile(r"^([A-Z]{2,4})\s+(\d{1,2})\s*[–-]\s*(\d{1,2})\s+([A-Z]{2,4})\b", re.U)
# NFL.com game centre prints "<n>\n\n<n> points" for the away total, then the home total.
POINTS = re.compile(r"(\d{1,2})\n\n\1 points")
FLAG_ON_THE_PLAY = "FLAG ON THE PLAY"


def fetch(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "text/html,*/*;q=0.8",
                                               "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return {"status": int(resp.status), "body": body, "final_url": resp.geturl(), "error": ""}
    except urllib.error.HTTPError as exc:
        return {"status": int(exc.code), "body": b"", "final_url": url, "error": f"HTTPError {exc.code}"}
    except Exception as exc:
        return {"status": 0, "body": b"", "final_url": "", "error": type(exc).__name__ + ": " + str(exc)[:160]}


def live_scores(text: str):
    """Return (away, home, blocks_agree) or None when the page does not yield them.

    An NFL.com game-centre page prints the two totals twice: once in the header
    summary and once in the quarter-by-quarter table.  `blocks_agree` is 1 only
    when both blocks read the same two numbers, which is what makes the parse
    trustworthy rather than merely successful.
    """
    if FLAG_ON_THE_PLAY in text and len(text) < 20000:
        return None
    vals = [int(m.group(1)) for m in POINTS.finditer(text)]
    if len(vals) < 2:
        return None
    away, home = vals[0], vals[1]
    agree = 1 if len(vals) >= 4 and (vals[2], vals[3]) == (away, home) else 0
    return away, home, agree


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args()

    with open(SRC, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if args.limit:
        rows = rows[: args.limit]

    started = _dt.datetime.now(_dt.timezone.utc)
    out = []
    for i, r in enumerate(rows, 1):
        url = (r.get("nfl_com_url") or "").strip()
        claim = (r.get("nfl_com_final") or "").strip()
        m = CLAIM.match(claim)
        c_away = c_home = None
        if m:
            c_away, c_home = int(m.group(2)), int(m.group(3))
        rec = {
            "game_id": r.get("game_id", ""),
            "season": r.get("season", ""),
            "week": r.get("week", ""),
            "gameday": r.get("gameday", ""),
            "matchup": r.get("matchup", ""),
            "published_claim": claim,
            "published_away": "" if c_away is None else c_away,
            "published_home": "" if c_home is None else c_home,
            "nfl_com_url": url,
            "http_status": 0,
            "live_away": "",
            "live_home": "",
            "blocks_agree": "",
            "result": "",
            "sha256": "",
            "error": "",
            "checked_utc": "",
        }
        if not url:
            rec["result"] = "UNCHECKED"
            rec["error"] = "row carries no game URL"
            out.append(rec)
            continue
        res = fetch(url, timeout=args.timeout)
        rec["http_status"] = res["status"]
        rec["sha256"] = hashlib.sha256(res["body"]).hexdigest()[:16] if res["body"] else ""
        rec["error"] = res["error"]
        rec["checked_utc"] = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        if res["status"] == 0:
            rec["result"] = "UNCHECKED"
        elif res["status"] >= 400:
            rec["result"] = "UNRESOLVED"
        else:
            text = res["body"].decode("utf-8", errors="replace")
            if FLAG_ON_THE_PLAY in text and len(text) < 20000:
                rec["result"] = "UNRESOLVED"
                rec["error"] = "nfl.com soft-404 (FLAG ON THE PLAY)"
            else:
                got = live_scores(text)
                if got is None:
                    rec["result"] = "UNPARSED"
                    rec["error"] = "could not read the final score from the page"
                else:
                    la, lh, agree = got
                    rec["live_away"], rec["live_home"] = la, lh
                    rec["blocks_agree"] = agree
                    if not agree:
                        rec["result"] = "UNPARSED"
                        rec["error"] = ("header and quarter table on the official page disagree; "
                                        "no verdict recorded")
                    if c_away is None:
                        rec["result"] = "UNPARSED"
                        rec["error"] = "published claim could not be parsed"
                    elif (la, lh) == (c_away, c_home):
                        rec["result"] = "MATCH"
                    else:
                        rec["result"] = "MISMATCH"
        out.append(rec)
        print(f"[{i}/{len(rows)}] {rec['result']:<10} {rec['matchup']:<14} "
              f"published {rec['published_away']}-{rec['published_home']} "
              f"live {rec['live_away']}-{rec['live_home']} {url}", flush=True)
        if args.sleep and i < len(rows):
            time.sleep(args.sleep)

    summary: dict[str, int] = {}
    for r in out:
        summary[r["result"]] = summary.get(r["result"], 0) + 1

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    fields = list(out[0].keys()) if out else []
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(out)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        import json
        json.dump({"generated_utc": started.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                   "source_csv": os.path.relpath(SRC, ROOT), "rows": len(out),
                   "summary": summary, "results": out}, fh, indent=1)
    print("\n--- summary ---")
    for k in sorted(summary):
        print(f"{summary[k]:5d}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
