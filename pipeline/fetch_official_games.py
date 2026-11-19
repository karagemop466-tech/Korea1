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
                            parse_lineup_rows, parse_roster_entries, parse_schedule_page,
                            parse_two_column_roster, split_columns)
from official_payload import (parse_game_centre_info, parse_schedule_payload,  # noqa: E402
                              parse_week_selector, published_week)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "evidence" / "official_games"
PROC = ROOT / "data" / "processed"
RAW_DIR = ROOT / "data" / "raw" / "official_games"   # gitignored: raw response bytes

UA = "nfl-line-lab/1.0 (research; contact: repository owner)"
TIMEOUT = 60


# ---------------------------------------------------------------------------
# Fail-loud pins (REQ-63).  Every one of these is a condition the official
# documents themselves establish; nothing here infers a value.  A failed pin
# aborts the run with exit 2 before any CSV or manifest is written, so the
# workflow goes red instead of committing a silent blank.
# ---------------------------------------------------------------------------

def _norm(s: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def book_matches_fixture(book: dict, slug: str) -> str:
    """The Game Book's printed matchup must belong to this fixture's slug.

    Returns ``""`` when the printed club names carry every club token of the
    slug, otherwise the reason the book must be rejected.  The slug is the
    league's own stable identity for the fixture, so the check does not
    depend on how the club names are styled in the PDF.
    """
    away = _norm(book.get("away_as_printed"))
    home = _norm(book.get("home_as_printed"))
    if not away or not home:
        return f"Game Book prints no matchup (away={away!r}, home={home!r})"
    structural = {"at", "reg", "pre", "post", "pro", "bowl"}
    club_tokens = {t for t in _norm(slug).split()
                   if t not in structural and not t.isdigit()}
    if not club_tokens:
        return f"slug {slug!r} carries no club tokens to check against"
    printed = set(away.split()) | set(home.split())
    if not club_tokens <= printed:
        return (f"Game Book prints {away} at {home} but the fixture slug is "
                f"{slug} — a document for another game")
    return ""


def book_week_slug(slug: str, week: object) -> bool:
    """A ``-reg-<n>`` slug must name the week that was requested."""
    m = re.search(r"-reg-(\d+)$", str(slug or ""))
    return not m or str(int(m.group(1))) == str(week)


def date_fragment_printed(value: str) -> bool:
    """The printed date line carries the league's own M/D/YYYY date."""
    return bool(re.search(r"\d{1,2}/\d{1,2}/\d{4}", str(value or "")))


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
    """The league's own URL for one week's schedule (the ``reg-<week>`` form).

    The form is the one the league's own game-centre records cite
    (``data/forward/official_schedule.csv`` → ``source_page``):
    ``/schedules/<season>/by-week/reg-<week>``.

    The earlier form, ``/schedules/<season>/REG<week>``, returns the league's
    *current* week whatever week the path names: the 2026-11-19 capture of
    ``REG9`` and ``REG10`` returned byte-identical documents (SHA-256
    ``6ad52b57…``) that both published Week 11.  That is why the capture has
    to read the published week out of the page instead of trusting the URL.
    """
    return f"https://www.nfl.com/schedules/{season}/by-week/reg-{week}"


def week_path_forms(season: int, week: int) -> list[str]:
    """The URL forms the league serves a week under.

    Two forms are in use and both are cited by official records in this
    repository: ``by-week/reg-<week>`` (the ``source_page`` column of
    ``data/forward/official_schedule.csv``) and ``by-week/week-<week>`` (the
    form read live by the session ``arena/831c3566-korea1`` on 2026-11-19,
    which confirmed the Week 10 schedule with all fourteen games final).

    The capture tries them in order and keeps the one whose page publishes the
    week that was asked for.  It never assumes: the week is read out of the
    page, and if no form publishes the requested week the capture records the
    mismatch rather than labelling one week's fixtures with another week's
    number.
    """
    return [f"https://www.nfl.com/schedules/{season}/by-week/reg-{week}",
            f"https://www.nfl.com/schedules/{season}/by-week/week-{week}"]


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
                    schedule_pages=[], scores_pages=[], game_centres=[], game_books=[], errors=[])
    fatal: list[str] = []

    def die(reason: str) -> None:
        """Record a reason the run must stop before anything is published."""
        fatal.append(reason)

    # ---------------------------------------------------------------- schedule
    fixtures: list[dict] = []
    weeks_meta: list[dict] = []
    final_slugs: set[str] = set()
    for week in weeks:
        # Try each URL form the league serves a week under and keep the one
        # whose page publishes the week that was asked for.  A form that
        # fails is remembered only until a later form succeeds — a working
        # second form is not an error.
        raw = b""
        status = 0
        url = ""
        html = ""
        published = ""
        forms_tried: list[str] = []
        form_errors: list[str] = []
        for candidate in week_path_forms(season, week):
            forms_tried.append(candidate)
            try:
                body, code = http_get(candidate)
            except RuntimeError as exc:
                form_errors.append(f"{candidate}: {exc}")
                continue
            if code != 200 or not body:
                form_errors.append(f"{candidate}: http status {code}")
                continue
            candidate_html = body.decode("utf-8", "replace")
            candidate_week = published_week(candidate_html)
            raw, status, url, html = body, code, candidate, candidate_html
            published = candidate_week
            if str(candidate_week) == str(week):
                break
        if not html:
            die(f"week {week}: no schedule page readable ({'; '.join(form_errors)})")
            continue
        if str(published) != str(week):
            die(f"week {week}: the page at {url} publishes week {published!r}, "
                f"not the requested week — refusing to label one week's fixtures "
                f"with another week's number")
        text = html_to_text(html)
        write_raw(RAW_DIR / "schedule" / f"reg{week}.html", raw)
        nb, sh = write_gz(EVIDENCE / f"schedule/reg{week}.txt.gz", text)
        hb, hh = write_gz(EVIDENCE / f"schedule/reg{week}.html.gz", html)
        # The week the page publishes is read out of the page, not assumed
        # from the URL: the league's schedule application does not always
        # serve the week the path names.
        manifest["schedule_pages"].append(dict(week=week, url=url, http_status=status,
                                               url_forms_tried=";".join(forms_tried),
                                               published_week=published,
                                               week_matches_url=(str(week) == str(published)),
                                               raw_bytes=len(raw), raw_sha256=sha256_bytes(raw),
                                               text_bytes=nb, text_sha256=sh,
                                               html_bytes=hb, html_sha256=hh,
                                               retrieved_utc=stamp))
        rows = parse_schedule_payload(html)
        if not rows:
            # Fall back to the anchor form, for a page served as plain markup.
            rows = parse_schedule_page(html)
        if not rows:
            die(f"week {week}: 0 fixtures parsed from {url} — the page shape "
                f"changed or the week did not render; refusing to write an "
                f"empty week")
        for row in rows:
            row.update(schedule_url=url, retrieved_utc=stamp,
                       week_requested=week, week_published=published,
                       week_matches_url=(str(week) == str(published)))
            # A slug the league prints as ``...-reg-<n>`` must name the week
            # that was requested; the REG9/REG10 defect (F-2026-11-19-08) was
            # exactly this disagreement going unnoticed.
            if not book_week_slug(str(row.get("official_url", "")).rstrip("/").rsplit("/", 1)[-1], week):
                die(f"week {week}: slug {row.get('official_url')!r} does not "
                    f"name week {week} — the schedule page served a fixture "
                    f"from another week")
        fixtures.extend(rows)
        print(f"schedule reg{week}: {len(rows)} fixtures (page publishes week {published})",
              flush=True)
        # The anchor form of the SAME captured page also prints ``FINAL`` beside
        # a finished game; those slugs form the finished set the Game Book must
        # cover.  The word is the league's own, transcribed, never derived from
        # a clock.
        for row in parse_schedule_page(html):
            if str(row.get("status_as_printed", "")).upper() == "FINAL":
                final_slugs.add(str(row.get("official_url", "")).rstrip("/").rsplit("/", 1)[-1])
        # Independent fixture-set cross-check against the league's scores page
        # for the same week (F-2026-11-19-08's lesson: one page can disagree
        # with another about which fixtures exist).
        scores_url = f"https://www.nfl.com/scores/{season}/week-{week}"
        try:
            sraw, scode = http_get(scores_url)
        except RuntimeError as exc:
            die(f"week {week}: scores cross-check unreachable ({scores_url}: {exc})")
            sraw, scode = b"", 0
        if sraw and scode == 200:
            score_slugs = set(re.findall(
                r'href="(?:https://www\.nfl\.com)?/games/([^"?#]+)"',
                sraw.decode("utf-8", "replace")))
            sched_slugs = {str(r.get("official_url", "")).rstrip("/").rsplit("/", 1)[-1]
                           for r in rows}
            if score_slugs != sched_slugs:
                only_sched = sorted(sched_slugs - score_slugs)
                only_scores = sorted(score_slugs - sched_slugs)
                die(f"week {week}: schedule page and scores page disagree on "
                    f"the fixture set (only schedule: {only_sched}; only "
                    f"scores: {only_scores})")
            manifest["scores_pages"].append(dict(
                week=week, url=scores_url, http_status=scode,
                fixtures=len(score_slugs),
                raw_sha256=sha256_bytes(sraw), retrieved_utc=stamp))
        elif scode:
            die(f"week {week}: scores cross-check http status {scode} ({scores_url})")
        # The same page publishes the season's week windows and the clubs on a
        # bye in each week; they are read from the page that was captured.
        for window in parse_week_selector(html):
            window.update(schedule_url=url, retrieved_utc=stamp)
            weeks_meta.append(window)
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
        html = raw.decode("utf-8", "replace")
        text = html_to_text(html)
        slug = url.rsplit("/", 1)[-1]
        write_raw(RAW_DIR / "gamecentres" / f"{slug}.html", raw)
        nb, sh = write_gz(EVIDENCE / f"gamecentres/{slug}.txt.gz", text)
        hb, hh = write_gz(EVIDENCE / f"gamecentres/{slug}.html.gz", html)
        parsed = parse_game_centre(text, raw_html=html)
        # The league renders the venue in the Game Info block and links the
        # Game Book in its own "Download Game Book (PDF)" module; both are read
        # from the page as the league serves it.
        info = parse_game_centre_info(html)
        parsed.update(official_url=url, season=season, week=fx.get("week", ""), slug=slug,
                      away_team=fx.get("away_team", ""), home_team=fx.get("home_team", ""),
                      fixture_id=fx.get("fixture_id", ""),
                      raw_bytes=len(raw), raw_sha256=sha256_bytes(raw),
                      text_sha256=sh, html_sha256=hh, retrieved_utc=stamp)
        if info["venue_location"] and not parsed.get("venue_location"):
            parsed["venue_location"] = info["venue_location"]
        if info["venue_stadium"] and not parsed.get("venue_stadium"):
            parsed["venue_stadium"] = info["venue_stadium"]
        # Only the league's ``/gamecenter/`` links are Game Books.  The
        # payload's looser PDF match once returned the Record & Fact Book for
        # every unplayed fixture (2026-11-19); a non-conforming URL is
        # recorded as rejected and never fetched as a Game Book.
        if info["gamebook_url"] and "/gamecenter/" in info["gamebook_url"]:
            parsed["gamebook_url"] = info["gamebook_url"]
        elif info["gamebook_url"]:
            parsed["gamebook_url"] = ""
            parsed["gamebook_url_rejected"] = info["gamebook_url"]
        parsed["page_title"] = info["page_title"]
        # REQ-23: the venue comes from the game centre's own Game Info block.
        # A centre that prints no venue at all is a parse failure or a page
        # change — either way the fixture cannot be published venue-blank.
        if not (parsed.get("venue_location") or parsed.get("venue_stadium")):
            die(f"game centre {url} printed no venue (LOCATION and STADIUM "
                f"both blank) — refusing to publish a fixture without its "
                f"venue")
        centres.append(parsed)
        manifest["game_centres"].append(dict(url=url, http_status=status, raw_bytes=len(raw),
                                             raw_sha256=sha256_bytes(raw), text_bytes=nb,
                                             text_sha256=sh, retrieved_utc=stamp,
                                             gamebook_url=parsed.get("gamebook_url", ""),
                                             venue_location=parsed.get("venue_location", ""),
                                             venue_stadium=parsed.get("venue_stadium", "")))
        time.sleep(args.sleep)
    print(f"game centres captured: {len(centres)}", flush=True)

    # -------------------------------------------------------------- game books
    books: list[dict] = []
    roster_rows: list[dict] = []
    for c in centres:
        if not c["gamebook_url"]:
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
        # --- fail-loud pins on the document just read (REQ-63) -------------
        mismatch = book_matches_fixture(parsed, slug)
        if mismatch:
            die(f"Game Book {url}: {mismatch} — a document that does not "
                f"name this fixture will not be published as its book")
        if not book_week_slug(slug, c["week"]):
            die(f"Game Book slug {slug} does not name week {c['week']}")
        if not date_fragment_printed(parsed.get("date_as_printed", "")):
            die(f"Game Book {url} printed no M/D/YYYY date line — the "
                f"identification strip did not parse")
        readable_starters = sum(
            1 for r in parse_lineup_rows(parsed.get("lineups", ""))
            if r["column"] >= 0 and r["player"])
        if readable_starters < 40:
            die(f"Game Book {slug} yielded {readable_starters} readable "
                f"starting-lineup cells (the printed grid holds 44; 40 is the "
                f"floor) — the lineup table did not parse")
        if not parsed.get("not_active"):
            die(f"Game Book {slug} printed no Not Active list — the game-day "
                f"inactive list is required for every captured book")
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
                                        position=entry["position"], jersey=entry["jersey"],
                                        player=entry["player"], official_url=url,
                                        source_url=c["official_url"], retrieved_utc=stamp, raw=""))
        time.sleep(args.sleep)
    print(f"game books captured: {len(books)}", flush=True)

    # Every fixture the schedule page marks FINAL must have had a Game Book
    # link on its centre; a finished game whose centre offers no book is the
    # league not publishing yet — the run goes red and the next scheduled
    # attempt retries, rather than the site publishing a finished fixture
    # with no document behind it.  When --gamebook-weeks narrows the capture,
    # only the FINAL fixtures in those weeks are held to this rule.
    week_by_slug = {str(f.get("official_url", "")).rstrip("/").rsplit("/", 1)[-1]:
                    str(f.get("week_requested", "")) for f in fixtures}
    captured_book_slugs = {str(b.get("slug", "")) for b in books}
    for slug in sorted(final_slugs):
        wk = week_by_slug.get(slug, "")
        if book_weeks and wk and str(wk) not in {str(x) for x in book_weeks}:
            continue
        if slug not in captured_book_slugs:
            die(f"fixture {slug} is FINAL on the schedule page but its game "
                f"centre offered no Game Book link — a finished fixture "
                f"without its official book will not be published")

    # ------------------------------------------------------------------ output
    ok = not fatal and not manifest["errors"]
    if not ok:
        # Nothing is published: the committed CSVs, evidence and manifest stay
        # exactly as they are, and the run exits 2 so the workflow stops
        # before its commit step.  The reasons are printed three ways so they
        # are actually visible from CI: stderr for the log, GitHub
        # ``::error::`` annotations (the check-runs API returns them even when
        # the log download is blocked), and a rejected manifest next to the
        # raw bytes that the always-run artifact step uploads.
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        rejected = dict(manifest, fatal=fatal)
        (EVIDENCE / "manifest-rejected.json").write_text(
            json.dumps(rejected, indent=2), encoding="utf-8")
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / "manifest-rejected.json").write_text(
            json.dumps(rejected, indent=2), encoding="utf-8")
        print("FATAL — capture rejected; no CSV or manifest was written "
              "(the workflow stops before its commit step):", file=sys.stderr)
        for reason in fatal:
            print(f"  - {reason}", file=sys.stderr)
            print(f"::error title=gamebooks capture rejected::{reason}")
        for err in manifest["errors"]:
            print(f"  - error: {err}", file=sys.stderr)
            print(f"::error title=gamebooks capture error::{err}")
        return 2
    PROC.mkdir(parents=True, exist_ok=True)
    fx = pd.DataFrame(fixtures)
    if not fx.empty:
        fx.to_csv(PROC / "official_fixtures.csv", index=False)
    if weeks_meta:
        # Every captured page carries the season's full week list, so the
        # windows are de-duplicated by the league's own week and week type.
        seen_windows: dict[tuple[str, str], dict] = {}
        for window in weeks_meta:
            seen_windows.setdefault((str(window.get("week", "")),
                                     str(window.get("week_type", ""))), window)
        pd.DataFrame(list(seen_windows.values())).to_csv(
            PROC / "official_week_windows.csv", index=False)
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
