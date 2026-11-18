"""Capture the official NFL game-centre pages and Game Book PDFs.

Network reality of this build environment (measured 2026-11-18T03:47Z, not
assumed): the sandbox shell refuses the TLS handshake to ``www.nfl.com`` and
``static.www.nfl.com`` (curl error 35, SSL_ERROR_SYSCALL).  This module is
therefore run on a GitHub-hosted runner by
``.github/workflows/gamebooks.yml`` — the same pattern the availability
tracker already uses — and it commits what it captured.

What it captures, per official document:

* the league's own **schedule page** for a week, which prints the fixture,
  the day and date, the kickoff time, the network and a link to the fixture's
  game centre;
* the fixture's **game centre** page, which prints the venue (LOCATION and
  STADIUM) and links the official Game Book PDF;
* the official **Game Book PDF**, whose first page prints the date, the start
  time and its time zone, the officials, the game-day weather and the roof and
  surface designation, the venue line, both starting lineups, the substitution
  lists, the "Did Not Play" lists and the "Not Active" lists.

Every captured document is stored flattened to text, compressed, next to its
SHA-256, so a later reader can replay the parse without the network.  The raw
bytes are kept as a workflow artifact; the hash proves which bytes were read.

Run: python pipeline/fetch_official_games.py --season 2026 --weeks 1-11
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from official_games import (html_to_text, parse_game_book, parse_game_centre,  # noqa: E402
                            parse_roster_entries, parse_schedule_page)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "evidence" / "official_games"
PROC = ROOT / "data" / "processed"
RAW_DIR = ROOT / "data" / "raw" / "official_games"   # gitignored: raw response bytes

UA = "nfl-line-lab/1.0 (research; contact: repository owner)"
TIMEOUT = 60


def http_get(url: str, tries: int = 3) -> tuple[bytes, int]:
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read(), resp.status
        except urllib.error.HTTPError as exc:          # pragma: no cover - network
            if exc.code in (404, 403):
                return b"", exc.code
            last = exc
        except Exception as exc:                        # pragma: no cover - network
            last = exc
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"could not fetch {url}: {last}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_gz(path: Path, text: str) -> tuple[int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = text.encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as fh:
        fh.write(raw)
    path.write_bytes(buf.getvalue())
    return len(raw), sha256_bytes(raw)


def write_raw(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def pdf_text(data: bytes, pages: int = 2) -> tuple[str, str]:
    """Extract the first pages of a PDF.  Returns (text, method).

    ``pdftotext -layout`` is preferred because the Game Book is a table and the
    column gaps survive; ``pypdf`` is the fallback when poppler is absent.
    Neither method invents content: if the text cannot be extracted the
    method says so and the caller leaves the fields blank.
    """
    tmp = RAW_DIR / "tmp_gamebook.pdf"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(data)
    try:
        proc = subprocess.run(["pdftotext", "-layout", "-f", "1", "-l", str(pages), str(tmp), "-"],
                              capture_output=True, text=True, timeout=180)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout, "pdftotext -layout"
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(tmp))
        text = "\n".join((reader.pages[i].extract_text() or "") for i in range(min(pages, len(reader.pages))))
        if text.strip():
            return text, "pypdf"
    except Exception:
        pass
    return "", "unavailable"


def week_paths(season: int, week: int) -> str:
    return f"https://www.nfl.com/schedules/{season}/REG{week}"


def parse_week_spec(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--weeks", default="1-18", help="e.g. 1-11 or 9,10")
    ap.add_argument("--gamebook-weeks", default="",
                    help="weeks whose Game Book PDFs are captured (default: the weeks "
                         "already listed as Final on the captured game-centre pages)")
    ap.add_argument("--sleep", type=float, default=0.4, help="politeness delay, seconds")
    args = ap.parse_args()

    weeks = parse_week_spec(args.weeks)
    book_weeks = set(parse_week_spec(args.gamebook_weeks)) if args.gamebook_weeks else set()
    season = args.season
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest = dict(season=season, retrieved_utc=stamp, runner="GitHub Actions",
                    schedule_pages=[], game_centres=[], game_books=[], errors=[])

    # ---------------------------------------------------------------- schedule
    fixtures: list[dict] = []
    for week in weeks:
        url = week_paths(season, week)
        try:
            raw, status = http_get(url)
        except RuntimeError as exc:
            manifest["errors"].append(dict(url=url, stage="schedule", error=str(exc)))
            continue
        text = html_to_text(raw.decode("utf-8", "replace"))
        write_raw(RAW_DIR / "schedule" / f"REG{week}.html", raw)
        nb, sh = write_gz(EVIDENCE / f"schedule/REG{week}.txt.gz", text)
        manifest["schedule_pages"].append(dict(week=week, url=url, http_status=status,
                                               raw_bytes=len(raw), raw_sha256=sha256_bytes(raw),
                                               text_bytes=nb, text_sha256=sh,
                                               retrieved_utc=stamp))
        rows = parse_schedule_page(text)
        for row in rows:
            row.update(season=season, week=week, schedule_url=url, retrieved_utc=stamp)
        fixtures.extend(rows)
        print(f"schedule REG{week}: {len(rows)} fixtures", flush=True)
        time.sleep(args.sleep)

    # ------------------------------------------------------------ game centres
    centres: list[dict] = []
    seen: set[str] = set()
    for fx in fixtures:
        url = fx["official_url"]
        if url in seen:
            continue
        seen.add(url)
        try:
            raw, status = http_get(url)
        except RuntimeError as exc:
            manifest["errors"].append(dict(url=url, stage="game_centre", error=str(exc)))
            continue
        if status != 200 or not raw:
            manifest["errors"].append(dict(url=url, stage="game_centre",
                                           error=f"http status {status}"))
            continue
        text = html_to_text(raw.decode("utf-8", "replace"))
        slug = url.rsplit("/", 1)[-1]
        write_raw(RAW_DIR / "gamecentres" / f"{slug}.html", raw)
        nb, sh = write_gz(EVIDENCE / f"gamecentres/{slug}.txt.gz", text)
        parsed = parse_game_centre(text)
        parsed.update(official_url=url, season=season, week=fx["week"], slug=slug,
                      raw_bytes=len(raw), raw_sha256=sha256_bytes(raw),
                      text_sha256=sh, retrieved_utc=stamp)
        centres.append(parsed)
        manifest["game_centres"].append(dict(url=url, http_status=status, raw_bytes=len(raw),
                                             raw_sha256=sha256_bytes(raw), text_bytes=nb,
                                             text_sha256=sh, retrieved_utc=stamp))
        time.sleep(args.sleep)
    print(f"game centres captured: {len(centres)}", flush=True)

    # -------------------------------------------------------------- game books
    books: list[dict] = []
    roster_rows: list[dict] = []
    for c in centres:
        if c["status_as_printed"] != "Final" or not c["gamebook_url"]:
            continue
        if book_weeks and c["week"] not in book_weeks:
            continue
        url = c["gamebook_url"]
        try:
            raw, status = http_get(url)
        except RuntimeError as exc:
            manifest["errors"].append(dict(url=url, stage="game_book", error=str(exc)))
            continue
        if status != 200 or not raw:
            manifest["errors"].append(dict(url=url, stage="game_book",
                                           error=f"http status {status}"))
            continue
        slug = c["slug"]
        write_raw(RAW_DIR / "gamebooks" / f"{slug}.pdf", raw)
        text, method = pdf_text(raw, pages=2)
        if not text:
            manifest["errors"].append(dict(url=url, stage="game_book", error="text not extracted"))
            continue
        nb, sh = write_gz(EVIDENCE / f"gamebooks/{slug}.p1.txt.gz", text)
        parsed = parse_game_book(text)
        parsed.update(slug=slug, season=season, week=c["week"], official_url=url,
                      game_centre_url=c["official_url"], raw_bytes=len(raw),
                      raw_sha256=sha256_bytes(raw), text_sha256=sh, extraction_method=method,
                      retrieved_utc=stamp)
        books.append(parsed)
        manifest["game_books"].append(dict(url=url, game_centre_url=c["official_url"],
                                           raw_bytes=len(raw), raw_sha256=sha256_bytes(raw),
                                           text_bytes=nb, text_sha256=sh,
                                           extraction_method=method, retrieved_utc=stamp))
        for side, key in (("away", "away_as_printed"), ("home", "home_as_printed")):
            team = parsed.get(key, "")
            for label, block in (("starter", parsed["lineups"]),
                                 ("substitution", parsed["substitutions"]),
                                 ("did_not_play", parsed["did_not_play"]),
                                 ("not_active", parsed["not_active"])):
                for entry in parse_roster_entries(block):
                    roster_rows.append(dict(slug=slug, season=season, week=c["week"],
                                            team_as_printed=team, side=side, roster_block=label,
                                            position=entry["position"], jersey=entry["jersey"],
                                            player=entry["player"], official_url=url,
                                            source_url=c["official_url"], retrieved_utc=stamp))
        time.sleep(args.sleep)
    print(f"game books captured: {len(books)}", flush=True)

    # ------------------------------------------------------------------ output
    PROC.mkdir(parents=True, exist_ok=True)
    fx = pd.DataFrame(fixtures)
    if not fx.empty:
        fx.to_csv(PROC / "official_fixtures.csv", index=False)
    if centres:
        pd.DataFrame(centres).to_csv(PROC / "official_gamecentres.csv", index=False)
    if books:
        pd.DataFrame(books).to_csv(PROC / "official_gamebooks.csv", index=False)
    if roster_rows:
        pd.DataFrame(roster_rows).to_csv(PROC / "official_gamebook_rosters.csv", index=False)
    (EVIDENCE).mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"manifest errors: {len(manifest['errors'])}")
    for e in manifest["errors"][:10]:
        print("  ", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
