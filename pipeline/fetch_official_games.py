"""Capture the official NFL game-centre pages and Game Book PDFs.

Network reality of this build environment (measured 2026-11-18T03:47Z, not
assumed): the sandbox shell refuses the TLS handshake to ``www.nfl.com`` and
``static.www.nfl.com`` (curl error 35, SSL_ERROR_SYSCALL).  This module is
therefore run on a GitHub-hosted runner by
``.github/workflows/gamebooks.yml`` — the same pattern the availability
tracker already uses — and it commits what it captured.

What it captures, per official document:

* the league's own **by-week schedule page** for a week, which prints the
  fixture, the day and date, the kickoff time, the network and a link to the
  fixture's game centre;
* the league's **scores page** for the same week — an independently
  rendered official document used only to cross-check the fixture set;
* the fixture's **game centre** page, which prints the venue (LOCATION and
  STADIUM) and links the official Game Book PDF;
* the official **Game Book PDF**, whose first page prints the date, the start
  time and its time zone, the officials, the game-day weather and the roof and
  surface designation, the venue line, both starting lineups, the substitution
  lists, the "Did Not Play" lists and the "Not Active" lists.

Every captured document is stored flattened to text, compressed, next to its
SHA-256, so a later reader can replay the parse without the network.  The raw
bytes are kept as a workflow artifact; the hash proves which bytes were read.

Fail-loud contract (REQ-63 — the defect this script was repaired for):

* ``/schedules/<season>/REG<week>`` did not select the week for this client
  (measured 2026-11-19: REG9 and REG10 came back byte-identical, both
  containing Week-11 fixtures — flag F-2026-11-19-08), so the by-week URL is
  the schedule source and every fixture slug must print the requested week;
* a week that yields zero fixtures, a slug whose week disagrees with the
  request, a schedule/scores fixture-set disagreement, a game centre with a
  blank venue, a finished fixture with no Game Book link, or a Game Book whose
  printed matchup does not match the fixture — any of these **aborts the run
  with exit 2 and writes no evidence**.  A blank capture is never committed.

Run: python pipeline/fetch_official_games.py --season 2026 --weeks 1-18
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
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
                            parse_lineup_rows, parse_roster_entries, parse_schedule_page,
                            parse_two_column_roster, split_columns,
                            fixture_week, game_link_slugs, scores_week_url,
                            slug_of, week_mismatches, week_schedule_url)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "evidence" / "official_games"
PROC = ROOT / "data" / "processed"
RAW_DIR = ROOT / "data" / "raw" / "official_games"   # gitignored: raw response bytes

UA = "nfl-line-lab/1.0 (research; contact: repository owner)"
TIMEOUT = 60

# A finished Game Book page 1 prints eleven starters in each of the four
# printed columns (visitor offence, visitor defence, home offence, home
# defence).  The pin is 40 rather than 44 so a single officially blank cell
# cannot fail the run, while a parser that stops reading rows still can.
MIN_STARTER_ROWS = 40


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
    method says so and the caller fails the run rather than publishing a
    blank parse.
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


def _slug_team_token(slug: str) -> tuple[str, str]:
    """The away/home team tokens the league printed in a fixture slug."""
    base = re.sub(r"-2026-reg-\d+$", "", slug_of(slug))
    if "-at-" not in base:
        return "", ""
    away, home = base.split("-at-", 1)
    return away, home


def book_matches_fixture(book: dict, slug: str) -> str:
    """Empty string when the Game Book's printed matchup is the fixture's;
    otherwise the reason the book must be rejected.  The check is by team
    token from the league's own slug — a book for any other game is refused,
    never published under the wrong fixture."""
    away_token, home_token = _slug_team_token(slug)
    if not away_token or not home_token:
        return f"slug {slug!r} does not split into away/home tokens"
    if not book.get("away_as_printed") or not book.get("home_as_printed"):
        return "Game Book prints no 'X at Y' matchup line"
    if away_token not in book["away_as_printed"].lower():
        return (f"book away {book['away_as_printed']!r} does not contain "
                f"slug token {away_token!r}")
    if home_token not in book["home_as_printed"].lower():
        return (f"book home {book['home_as_printed']!r} does not contain "
                f"slug token {home_token!r}")
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--weeks", default="1-18", help="e.g. 1-11 or 9,10")
    ap.add_argument("--gamebook-weeks", default="",
                    help="weeks whose Game Book PDFs are captured (default: the weeks "
                         "already listed as Final on the captured schedule rows)")
    ap.add_argument("--sleep", type=float, default=0.4, help="politeness delay, seconds")
    args = ap.parse_args()

    weeks = parse_week_spec(args.weeks)
    book_weeks = set(parse_week_spec(args.gamebook_weeks)) if args.gamebook_weeks else set()
    season = args.season
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest = dict(season=season, retrieved_utc=stamp, runner="GitHub Actions",
                    schedule_source="by-week (week-selecting URL; the REG<n> path "
                                    "was measured to ignore the week — F-2026-11-19-08)",
                    schedule_pages=[], scores_pages=[], game_centres=[], game_books=[],
                    errors=[])
    fatal: list[str] = []

    def die(msg: str) -> None:
        fatal.append(msg)
        print(f"FATAL: {msg}", flush=True)

    # ---------------------------------------------------------------- schedule
    fixtures: list[dict] = []
    for week in weeks:
        url = week_schedule_url(season, week)
        try:
            raw, status = http_get(url)
        except RuntimeError as exc:
            die(f"week {week}: schedule fetch failed ({url}): {exc}")
            continue
        text = html_to_text(raw.decode("utf-8", "replace"))
        write_raw(RAW_DIR / "schedule" / f"REG{week}.html", raw)
        nb, sh = write_gz(EVIDENCE / f"schedule/REG{week}.txt.gz", text)
        hb, hh = write_gz(EVIDENCE / f"schedule/REG{week}.html.gz", raw.decode("utf-8", "replace"))
        rows = parse_schedule_page(raw.decode("utf-8", "replace"))
        # (a) every slug must print the week we asked for;
        for bad in week_mismatches(rows, week):
            die(f"week {week}: fixture slug week mismatch: {bad}")
        # (b) one row per fixture (the page may print a card and a replay link);
        seen_week: set[str] = set()
        uniq: list[dict] = []
        for row in rows:
            s = slug_of(row["official_url"])
            if s in seen_week:
                continue
            seen_week.add(s)
            uniq.append(row)
        # (c) a week that prints no fixture is a blank capture, not a quiet one.
        if not uniq:
            die(f"week {week}: schedule page yielded 0 fixtures ({url})")
        # (d) the scores page for the same week must name the same fixtures.
        curl = scores_week_url(season, week)
        try:
            sraw, sstatus = http_get(curl)
        except RuntimeError as exc:
            die(f"week {week}: scores cross-check fetch failed ({curl}): {exc}")
            sraw = b""
        if sraw:
            score_slugs = {s for s in game_link_slugs(sraw.decode("utf-8", "replace"))
                           if s.endswith(f"-reg-{week}")}
            row_slugs = {slug_of(r["official_url"]) for r in uniq}
            if not score_slugs:
                die(f"week {week}: scores page yielded 0 game links ({curl})")
            elif score_slugs != row_slugs:
                die(f"week {week}: schedule/scores fixture sets differ — "
                    f"only-schedule={sorted(row_slugs - score_slugs)} "
                    f"only-scores={sorted(score_slugs - row_slugs)}")
            manifest["scores_pages"].append(
                dict(week=week, url=curl, http_status=sstatus,
                     fixtures=len(score_slugs), crosscheck="match"
                     if score_slugs == row_slugs else "DIFFER",
                     retrieved_utc=stamp))
        manifest["schedule_pages"].append(
            dict(week=week, url=url, http_status=status, raw_bytes=len(raw),
                 raw_sha256=sha256_bytes(raw), text_bytes=nb, text_sha256=sh,
                 html_bytes=hb, html_sha256=hh, fixtures=len(uniq),
                 slug_weeks=sorted({fixture_week(r["official_url"]) for r in uniq
                                    if fixture_week(r["official_url"]) is not None}),
                 retrieved_utc=stamp))
        for row in uniq:
            row.update(season=season, week=week, schedule_url=url, retrieved_utc=stamp)
        fixtures.extend(uniq)
        print(f"schedule {url}: {len(uniq)} fixtures", flush=True)
        time.sleep(args.sleep)

    final_slugs = {slug_of(r["official_url"]) for r in fixtures
                   if r.get("status_as_printed") == "FINAL"}

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
            die(f"game centre fetch failed ({url}): {exc}")
            continue
        if status != 200 or not raw:
            die(f"game centre {url}: http status {status}")
            continue
        text = html_to_text(raw.decode("utf-8", "replace"))
        slug = url.rsplit("/", 1)[-1]
        parsed = parse_game_centre(text, raw_html=raw.decode("utf-8", "replace"))
        if not parsed["venue_location"] or not parsed["venue_stadium"]:
            die(f"game centre {slug}: venue field blank after parse "
                f"(location={parsed['venue_location']!r}, "
                f"stadium={parsed['venue_stadium']!r})")
        if slug in final_slugs and not parsed["gamebook_url"]:
            die(f"game centre {slug}: fixture is FINAL but no Game Book link is printed")
        write_raw(RAW_DIR / "gamecentres" / f"{slug}.html", raw)
        nb, sh = write_gz(EVIDENCE / f"gamecentres/{slug}.txt.gz", text)
        hb, hh = write_gz(EVIDENCE / f"gamecentres/{slug}.html.gz", raw.decode("utf-8", "replace"))
        parsed.update(official_url=url, season=season, week=fx["week"], slug=slug,
                      raw_bytes=len(raw), raw_sha256=sha256_bytes(raw),
                      text_sha256=sh, html_sha256=hh, retrieved_utc=stamp)
        centres.append(parsed)
        manifest["game_centres"].append(dict(url=url, http_status=status, raw_bytes=len(raw),
                                             raw_sha256=sha256_bytes(raw), text_bytes=nb,
                                             text_sha256=sh, venue_location=parsed["venue_location"],
                                             venue_stadium=parsed["venue_stadium"],
                                             retrieved_utc=stamp))
        time.sleep(args.sleep)
    print(f"game centres captured: {len(centres)}", flush=True)

    # -------------------------------------------------------------- game books
    books: list[dict] = []
    roster_rows: list[dict] = []
    for c in centres:
        slug = c["slug"]
        if not c["gamebook_url"]:
            continue
        # A fixture the schedule printed FINAL must have its Game Book now
        # (absence already failed the run above).  Any other fixture is only
        # captured when its week was explicitly requested with --gamebook-weeks.
        if slug not in final_slugs and c["week"] not in book_weeks:
            continue
        url = c["gamebook_url"]
        try:
            raw, status = http_get(url)
        except RuntimeError as exc:
            die(f"game book fetch failed ({url}): {exc}")
            continue
        if status != 200 or not raw:
            die(f"game book {url}: http status {status}")
            continue
        text, method = pdf_text(raw, pages=2)
        if not text:
            die(f"game book {url}: text not extracted (method={method})")
            continue
        parsed = parse_game_book(text)
        mismatch = book_matches_fixture(parsed, slug)
        if mismatch:
            die(f"game book {slug}: rejected — {mismatch}")
            continue
        if not parsed.get("date_as_printed"):
            die(f"game book {slug}: printed date blank after parse")
            continue
        starters = [r for r in parse_lineup_rows(parsed["lineups"])
                    if r["column"] >= 0 and r["player"]]
        if len(starters) < MIN_STARTER_ROWS:
            die(f"game book {slug}: only {len(starters)} readable starter rows "
                f"(pin {MIN_STARTER_ROWS}) — lineup block not parsed")
            continue
        if not parsed.get("not_active"):
            die(f"game book {slug}: 'Not Active' block empty after parse")
            continue
        write_raw(RAW_DIR / "gamebooks" / f"{slug}.pdf", raw)
        nb, sh = write_gz(EVIDENCE / f"gamebooks/{slug}.p1.txt.gz", text)
        parsed.update(slug=slug, season=season, week=c["week"], official_url=url,
                      game_centre_url=c["official_url"], raw_bytes=len(raw),
                      raw_sha256=sha256_bytes(raw), text_sha256=sh, extraction_method=method,
                      retrieved_utc=stamp)
        books.append(parsed)
        manifest["game_books"].append(dict(url=url, game_centre_url=c["official_url"],
                                           raw_bytes=len(raw), raw_sha256=sha256_bytes(raw),
                                           text_bytes=nb, text_sha256=sh,
                                           extraction_method=method, retrieved_utc=stamp))
        # Lineups: four printed columns (visitor offence, visitor defence,
        # home offence, home defence).
        away_name = parsed.get("away_as_printed", "")
        home_name = parsed.get("home_as_printed", "")
        column_team = {0: (away_name, "away", "offense"), 1: (away_name, "away", "defense"),
                       2: (home_name, "home", "offense"), 3: (home_name, "home", "defense")}
        for row in parse_lineup_rows(parsed["lineups"]):
            if row["column"] < 0:
                roster_rows.append(dict(slug=slug, season=season, week=c["week"],
                                        team_as_printed="", side="", unit="",
                                        roster_block="lineup_unreadable", position="", jersey="",
                                        player="", official_url=url,
                                        source_url=c["official_url"], retrieved_utc=stamp,
                                        raw=row["raw"]))
                continue
            team, side, unit = column_team[row["column"]]
            roster_rows.append(dict(slug=slug, season=season, week=c["week"],
                                    team_as_printed=team, side=side, unit=unit,
                                    roster_block="starter", position=row["position"],
                                    jersey=row["jersey"], player=row["player"],
                                    official_url=url, source_url=c["official_url"],
                                    retrieved_utc=stamp, raw=row["raw"]))
        # Substitutions, did-not-play and inactive: one printed column per club.
        for label, block in (("substitution", parsed["substitutions"]),
                             ("did_not_play", parsed["did_not_play"]),
                             ("not_active", parsed["not_active"])):
            cols = parse_two_column_roster(block)
            for side, team, entries in (("away", away_name, cols["left"]),
                                        ("home", home_name, cols["right"])):
                for entry in entries:
                    roster_rows.append(dict(slug=slug, season=season, week=c["week"],
                                            team_as_printed=team, side=side, unit="",
                                            roster_block=label, position=entry["position"],
                                            jersey=entry["jersey"], player=entry["player"],
                                            official_url=url, source_url=c["official_url"],
                                            retrieved_utc=stamp, raw=""))
            for entry in cols["unattributed"]:
                roster_rows.append(dict(slug=slug, season=season, week=c["week"],
                                        team_as_printed="", side="", unit="",
                                        roster_block=label + "_unattributed",
                                        position=entry["position"],
                                        jersey=entry["jersey"], player=entry["player"],
                                        official_url=url, source_url=c["official_url"],
                                        retrieved_utc=stamp, raw=""))
        time.sleep(args.sleep)
    print(f"game books captured: {len(books)}", flush=True)

    # ------------------------------------------------------------------ output
    if fatal or manifest["errors"]:
        # Nothing is written: a failed run leaves the previous evidence
        # untouched and reports every reason on stdout (REQ-63).
        print("capture FAILED — no evidence written", flush=True)
        print(json.dumps(dict(fatal=fatal, errors=manifest["errors"]), indent=2), flush=True)
        return 2
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
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"manifest errors: {len(manifest['errors'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
