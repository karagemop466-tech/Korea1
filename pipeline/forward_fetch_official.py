"""Capture official NFL.com game pages for frozen games that have no official final yet.

Why this is a *candidate* extractor and not a settlement writer
---------------------------------------------------------------
`pipeline/forward_grade.py` settles a ticket only from a row in
`data/forward/official_results.csv` whose `official_url` is an nfl.com page. That file is
evidence, so nothing may be appended to it by a parser that has not been validated against
real NFL.com HTML.

This sandbox cannot reach nfl.com at all (`TLS/SSL connection has been closed (EOF)`; the
same limitation is documented in `pipeline/fetch_availability.py`), so the extraction rules
below have **never been run against a real page**. Writing evidence from rules that were
never validated would be worse than the manual capture it replaces. Therefore:

* this module **archives** the official page verbatim (bytes + SHA-256 + HTTP status);
* it **proposes** a score in `data/forward/official_candidates.csv`;
* it **never** writes `official_results.csv`.

Promoting a candidate is a separate, reviewed step: a session checks it against the archived
page, then appends the row. That keeps the evidence file's provenance honest while removing
the "nobody knows which games are ready to settle" problem.

Run it on a GitHub-hosted runner (`.github/workflows/forward-ledger.yml`), never in `make build`.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FWD = ROOT / "data" / "forward"
RAW = FWD / "raw_captures"
CANDIDATES = FWD / "official_candidates.csv"
UA = "Mozilla/5.0 (compatible; korea1-forward-ledger/1.0; +https://github.com/karagemop466-tech/Korea1)"

CAND_COLS = ["game_id", "away_team", "home_team", "candidate_away_score", "candidate_home_score",
             "final_marker_found", "source_url", "http_status", "bytes", "sha256",
             "archived_path", "captured_utc", "extraction_status"]


def http_get(url: str, tries: int = 3) -> tuple[int, bytes, str]:
    err = ""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read(), ""
        except urllib.error.HTTPError as ex:
            err = f"HTTP {ex.code}"
            if ex.code in (403, 404):
                return ex.code, b"", err
        except Exception as ex:  # noqa: BLE001 - recorded, never swallowed
            err = f"{type(ex).__name__}: {ex}"
    return 0, b"", err


def _ints_near(html: str, abbr: str) -> list[int]:
    """Scores printed in the same markup block as a team abbreviation.

    Deliberately conservative: only bare integers that sit in their own element next to the
    abbreviation are returned. It is a *proposal* helper, never a settlement decision.
    """
    out: list[int] = []
    for m in re.finditer(re.escape(abbr), html):
        window = html[m.end():m.end() + 600]
        for n in re.findall(r">\s*(\d{1,3})\s*<", window)[:3]:
            out.append(int(n))
    return out


def propose(game: dict, html: str) -> dict:
    """Propose a score from an archived page, or say why it could not."""
    status = "UNPARSED"
    away = home = ""
    final_marker = bool(re.search(r"\bFinal\b", html))
    if final_marker:
        aw, hm = _ints_near(html, game["away_team"]), _ints_near(html, game["home_team"])
        if aw and hm and aw[0] <= 100 and hm[0] <= 100:
            away, home = aw[0], hm[0]
            status = "PROPOSED"
    if not final_marker:
        status = "NOT_FINAL"
    elif status != "PROPOSED":
        status = "UNPARSED"
    return {"candidate_away_score": away, "candidate_home_score": home,
            "final_marker_found": int(final_marker), "extraction_status": status}


def games_needing_official() -> list[dict]:
    """Frozen games with no official row yet."""
    sched = FWD / "official_schedule.csv"
    off = FWD / "official_results.csv"
    if not sched.exists():
        return []
    with sched.open() as fh:
        sched_rows = list(csv.DictReader(fh))
    have = set()
    if off.exists():
        with off.open() as fh:
            have = {r["game_id"] for r in csv.DictReader(fh)
                    if r["status_on_page"].strip().lower() == "final"
                    and r["official_url"].startswith("https://www.nfl.com/")}
    return [g for g in sched_rows if g["game_id"] not in have]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=20, help="max games to fetch this run")
    args = ap.parse_args()

    # Hold ourselves to the promise made in the docstring: capture the evidence file's digest
    # before doing anything, and fail loudly if this run changes it. A printed claim is not a check.
    off = FWD / "official_results.csv"
    before = hashlib.sha256(off.read_bytes()).hexdigest() if off.exists() else ""

    todo = games_needing_official()[: args.limit]
    if not todo:
        print("every frozen game already has an official final; nothing to fetch")
        return 0
    RAW.mkdir(parents=True, exist_ok=True)
    existing = {}
    if CANDIDATES.exists():
        with CANDIDATES.open() as fh:
            for r in csv.DictReader(fh):
                existing[r["game_id"]] = r

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for g in todo:
        url = g["official_url"]
        code, body, err = http_get(url, tries=2)
        row = {c: "" for c in CAND_COLS}
        row.update({"game_id": g["game_id"], "away_team": g["away_team"], "home_team": g["home_team"],
                    "source_url": url, "http_status": code, "bytes": len(body), "captured_utc": now})
        if not body:
            row["extraction_status"] = f"FETCH_FAILED: {err}"[:200]
            print(f"  {g['game_id']}: fetch failed ({err[:80]})")
        else:
            digest = hashlib.sha256(body).hexdigest()
            dest = RAW / f"{g['game_id']}_{digest[:12]}.html"
            dest.write_bytes(body)
            try:
                archived = str(dest.relative_to(ROOT))
            except ValueError:          # e.g. a test scratch directory outside the repo
                archived = str(dest)
            row.update({"sha256": digest, "archived_path": archived,
                        **propose(g, body.decode("utf-8", "replace"))})
            print(f"  {g['game_id']}: {code} {len(body):,}B {row['extraction_status']}")
        existing[g["game_id"]] = row       # a later capture supersedes an earlier one

    with CANDIDATES.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CAND_COLS, lineterminator="\n")
        w.writeheader()
        for gid in sorted(existing):
            w.writerow({c: existing[gid].get(c, "") for c in CAND_COLS})
    after = hashlib.sha256(off.read_bytes()).hexdigest() if off.exists() else ""
    if before != after:
        raise RuntimeError("this module must never modify official_results.csv; restore it and fix the code")
    print(f"wrote {CANDIDATES} ({len(existing)} games); "
          f"official_results.csv unchanged (sha256 {after[:12] or 'absent'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
