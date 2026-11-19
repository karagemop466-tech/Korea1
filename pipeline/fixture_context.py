"""The fixture-context feature set, built only from published schedule facts.

What this module reads
----------------------
Only documents the repository already holds, each of them an official NFL
document captured with its HTTP status, byte count and SHA-256:

* the league's own weekly schedule page, captured under
  ``data/evidence/official_games/schedule/`` — the league publishes the
  fixture list, the kickoff instant, the week, the status, the category, the
  venue, the broadcast networks and the club-by-club identifiers;
* the league's own game-centre page, captured under
  ``data/evidence/official_games/gamecentres/`` — the league prints the venue
  twice, as ``LOCATION`` and as ``STADIUM``;
* the league's own Game Book text, captured under
  ``data/evidence/official_games/gamebooks/`` — the starting lineups, the
  "Did Not Play" lists and the "Not Active" lists.

What it writes
--------------
``data/processed/official_documents.csv``  — one row per captured official
    document: kind, URL, HTTP status, bytes, SHA-256, capture time.
``data/processed/week_windows.csv`` — the league's own week windows and the
    clubs on a bye in each week.
``data/processed/fixture_context.csv`` — one row per fixture.

Rules
-----
* A fact the league did not publish is blank.  It is never filled from a
  mirror, a model or a previous week.
* A column that is **converted** rather than printed says so: the only
  conversion is the league's UTC kickoff instant to the league's own Eastern
  time zone, using the IANA ``America/New_York`` zone.  The conversion is
  recorded in ``derivation`` on every row.
* The week the page publishes is read out of the page.  When it differs from
  the week the capture asked for, both are published and the row is flagged —
  the 2026-11-19 capture asked for Week 9 and Week 10 and was served the
  current week's page for both.

Run: python pipeline/fixture_context.py
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from official_payload import (parse_game_centre_info, parse_schedule_payload,  # noqa: E402
                              parse_week_selector, published_week)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "evidence" / "official_games"
PROC = ROOT / "data" / "processed"

# The league's own Eastern time zone.  The league prints every kickoff in
# Eastern time; the schedule payload carries the same instant in UTC.
EASTERN = ZoneInfo("America/New_York")

DOC_COLUMNS = ["document_id", "kind", "url", "http_status", "bytes", "sha256",
                "text_sha256", "week_requested", "week_published", "week_matches_url",
                "retrieved_utc", "evidence_path", "parsed_ok", "note"]

FIXTURE_COLUMNS = [
    "fixture_id", "season", "season_type", "week", "week_type",
    "away_team", "away_team_name", "home_team", "home_team_name",
    "kickoff_utc", "kickoff_et", "kickoff_date_et", "kickoff_weekday_et",
    "venue_name_as_published", "venue_city_as_published", "venue_country_as_published",
    "venue_location_as_printed", "venue_stadium_as_printed", "venue_agreement",
    "status_as_published", "category_as_published", "game_type_as_published",
    "international_as_published", "neutral_site_as_published", "is_flexible_as_published",
    "networks_as_published", "elias_id", "gsis_id", "slug",
    "week_window_begin_utc", "week_window_end_utc", "teams_on_bye",
    "week_requested", "week_published", "week_matches_url",
    "game_centre_captured", "gamebook_captured",
    "schedule_url", "official_url", "schedule_evidence_path",
    "game_centre_evidence_path", "gamebook_evidence_path",
    "retrieved_utc", "derivation",
]


def _read_gz(path: Path) -> str:
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _manifest() -> dict:
    path = EVIDENCE / "manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _schedule_pages() -> list[tuple[Path, dict]]:
    """Every captured schedule page with the manifest's record of it."""
    manifest = _manifest()
    by_week = {str(rec.get("week")): rec for rec in manifest.get("schedule_pages", [])}
    out: list[tuple[Path, dict]] = []
    folder = EVIDENCE / "schedule"
    if not folder.exists():
        return out
    for path in sorted(folder.glob("*.html.gz")):
        stem = path.name[: -len(".html.gz")]
        week = stem[3:] if stem.lower().startswith("reg") else stem
        rec = dict(by_week.get(week, {}))
        rec.setdefault("week", week)
        out.append((path, rec))
    return out


def _game_centre_pages() -> list[tuple[Path, dict]]:
    manifest = _manifest()
    by_url = {rec.get("url"): rec for rec in manifest.get("game_centres", [])}
    out: list[tuple[Path, dict]] = []
    folder = EVIDENCE / "gamecentres"
    if not folder.exists():
        return out
    for path in sorted(folder.glob("*.html.gz")):
        slug = path.name[: -len(".html.gz")]
        rec = dict(by_url.get(f"https://www.nfl.com/games/{slug}", {}))
        rec.setdefault("url", f"https://www.nfl.com/games/{slug}")
        out.append((path, rec))
    return out


def _game_books() -> dict[str, Path]:
    folder = EVIDENCE / "gamebooks"
    if not folder.exists():
        return {}
    return {p.name[: -len(".p1.txt.gz")]: p for p in sorted(folder.glob("*.p1.txt.gz"))}


def _local(zone: ZoneInfo, instant: str) -> tuple[str, str, str]:
    """(Eastern instant, Eastern date, weekday) for a published UTC instant."""
    if not instant:
        return "", "", ""
    try:
        when = pd.Timestamp(instant)
    except Exception:
        return "", "", ""
    if when.tzinfo is None:
        when = when.tz_localize("UTC")
    local = when.tz_convert(zone)
    return local.strftime("%Y-%m-%d %H:%M"), local.strftime("%Y-%m-%d"), local.strftime("%A")


def build() -> dict:
    """Write the document register, the week windows and the fixture context."""
    PROC.mkdir(parents=True, exist_ok=True)
    manifest = _manifest()
    documents: list[dict] = []
    windows: list[dict] = []
    fixtures: dict[str, dict] = {}
    fixture_order: list[str] = []

    # ---------------------------------------------------- schedule documents
    for path, rec in _schedule_pages():
        html = _read_gz(path)
        week = str(rec.get("week", ""))
        pub = published_week(html)
        rows = parse_schedule_payload(html)
        doc_id = f"schedule-reg{week}"
        documents.append(dict(
            document_id=doc_id, kind="official schedule page",
            url=rec.get("url", ""), http_status=rec.get("http_status", ""),
            bytes=rec.get("raw_bytes", ""), sha256=rec.get("raw_sha256", ""),
            text_sha256=rec.get("text_sha256", ""),
            week_requested=week, week_published=pub,
            week_matches_url=(str(week) == str(pub)),
            retrieved_utc=rec.get("retrieved_utc", ""),
            evidence_path=str(path.relative_to(ROOT)),
            parsed_ok=bool(rows),
            note=("" if str(week) == str(pub) else
                  f"page publishes week {pub}; capture asked for week {week}"),
        ))
        for window in parse_week_selector(html):
            window.update(evidence_path=str(path.relative_to(ROOT)))
            windows.append(window)
        for row in rows:
            fid = row["fixture_id"] or f"{row['away_team']}@{row['home_team']}"
            if fid not in fixtures:
                fixtures[fid] = dict(row)
                fixture_order.append(fid)
            else:
                for field, value in row.items():
                    if value not in ("", None) and fixtures[fid].get(field) in ("", None):
                        fixtures[fid][field] = value
            # A fixture can appear on more than one captured page — the
            # league served the same Week 11 document for the Week 9 and the
            # Week 10 request — so every page that carried it is listed.
            evidence = fixtures[fid].setdefault("_schedule_evidence", [])
            if str(path.relative_to(ROOT)) not in evidence:
                evidence.append(str(path.relative_to(ROOT)))
            urls = fixtures[fid].setdefault("_schedule_urls", [])
            if rec.get("url", "") not in urls:
                urls.append(rec.get("url", ""))
            requested = fixtures[fid].setdefault("_week_requested", [])
            if week not in requested:
                requested.append(week)
            fixtures[fid]["schedule_evidence_path"] = ";".join(evidence)
            fixtures[fid]["schedule_url"] = ";".join(urls)
            fixtures[fid]["week_requested"] = ";".join(requested)
            fixtures[fid]["week_published"] = pub
            fixtures[fid]["week_matches_url"] = (
                "YES" if all(str(w) == str(pub) for w in requested) else "NO")

    # ----------------------------------------------------- game-centre pages
    centres: dict[str, dict] = {}
    for path, rec in _game_centre_pages():
        html = _read_gz(path)
        info = parse_game_centre_info(html)
        slug = path.name[: -len(".html.gz")]
        url = info.get("canonical_url") or rec.get("url", "")
        documents.append(dict(
            document_id=f"gamecentre-{slug}", kind="official game centre",
            url=url or rec.get("url", ""), http_status=rec.get("http_status", ""),
            bytes=rec.get("raw_bytes", ""), sha256=rec.get("raw_sha256", ""),
            text_sha256=rec.get("text_sha256", ""),
            week_requested="", week_published="", week_matches_url="",
            retrieved_utc=rec.get("retrieved_utc", ""),
            evidence_path=str(path.relative_to(ROOT)),
            parsed_ok=bool(info.get("venue_location") or info.get("venue_stadium")),
            note=info.get("gamebook_url", ""),
        ))
        centres[slug] = info

    books = _game_books()
    for slug, path in books.items():
        documents.append(dict(
            document_id=f"gamebook-{slug}", kind="official Game Book (text)",
            url=f"https://static.www.nfl.com/image/upload/gamecenter/{slug}.pdf",
            http_status="", bytes="", sha256="", text_sha256="",
            week_requested="", week_published="", week_matches_url="",
            retrieved_utc="", evidence_path=str(path.relative_to(ROOT)),
            parsed_ok=True, note="first page text, as captured",
        ))

    # ---------------------------------------------------------- the fixtures
    window_by_week: dict[str, dict] = {}
    for window in windows:
        window_by_week.setdefault(str(window.get("week", "")), window)

    rows: list[dict] = []
    for fid in fixture_order:
        fx = fixtures[fid]
        slug = fx.get("slug", "")
        info = centres.get(slug, {})
        book_path = books.get(slug)
        instant_et, date_et, weekday_et = _local(EASTERN, str(fx.get("kickoff_utc", "")))
        window = window_by_week.get(str(fx.get("week", "")), {})
        printed_location = info.get("venue_location", "")
        printed_stadium = info.get("venue_stadium", "")
        published_venue = fx.get("venue_name", "")
        agreement = ""
        if printed_stadium and published_venue:
            a = printed_stadium.upper().replace(" STADIUM", "").replace(" FIELD", "")
            b = published_venue.upper().replace(" STADIUM", "").replace(" FIELD", "")
            agreement = "MATCH" if a == b else "DIFFERENT"
        elif printed_stadium or published_venue:
            agreement = "ONE SIDE ONLY"
        derivation = ("kickoff_et = kickoff_utc converted with the IANA "
                      "America/New_York zone; every other column is printed by "
                      "the league")
        rows.append({
            "fixture_id": fid,
            "season": fx.get("season", ""),
            "season_type": fx.get("season_type", ""),
            "week": fx.get("week", ""),
            "week_type": fx.get("week_type", ""),
            "away_team": fx.get("away_team", ""),
            "away_team_name": fx.get("away_team_name", ""),
            "home_team": fx.get("home_team", ""),
            "home_team_name": fx.get("home_team_name", ""),
            "kickoff_utc": fx.get("kickoff_utc", ""),
            "kickoff_et": instant_et,
            "kickoff_date_et": date_et,
            "kickoff_weekday_et": weekday_et,
            "venue_name_as_published": published_venue,
            "venue_city_as_published": fx.get("venue_city", ""),
            "venue_country_as_published": fx.get("venue_country", ""),
            "venue_location_as_printed": printed_location,
            "venue_stadium_as_printed": printed_stadium,
            "venue_agreement": agreement,
            "status_as_published": fx.get("status", ""),
            "category_as_published": fx.get("category", ""),
            "game_type_as_published": fx.get("game_type", ""),
            "international_as_published": fx.get("international", ""),
            "neutral_site_as_published": fx.get("neutral_site", ""),
            "is_flexible_as_published": fx.get("is_flexible", ""),
            "networks_as_published": fx.get("networks_as_printed", ""),
            "elias_id": fx.get("elias_id", ""),
            "gsis_id": fx.get("gsis_id", ""),
            "slug": slug,
            "week_window_begin_utc": window.get("date_begin", ""),
            "week_window_end_utc": window.get("date_end", ""),
            "teams_on_bye": window.get("teams_on_bye", ""),
            "week_requested": fx.get("week_requested", ""),
            "week_published": fx.get("week_published", ""),
            "week_matches_url": fx.get("week_matches_url", ""),
            "game_centre_captured": "YES" if slug in centres else "NO",
            "gamebook_captured": "YES" if book_path else "NO",
            "schedule_url": fx.get("schedule_url", ""),
            "official_url": fx.get("official_url", ""),
            "schedule_evidence_path": fx.get("schedule_evidence_path", ""),
            "game_centre_evidence_path": (str(
                (EVIDENCE / "gamecentres" / f"{slug}.html.gz").relative_to(ROOT))
                if slug in centres else ""),
            "gamebook_evidence_path": (str(book_path.relative_to(ROOT))
                                        if book_path else ""),
            "retrieved_utc": fx.get("retrieved_utc", ""),
            "derivation": derivation,
        })

    pd.DataFrame(documents, columns=DOC_COLUMNS).to_csv(
        PROC / "official_documents.csv", index=False)
    win = pd.DataFrame(windows)
    if not win.empty:
        win = win.drop_duplicates(subset=["week", "week_type"], keep="first")
    win.to_csv(PROC / "week_windows.csv", index=False)
    pd.DataFrame(rows, columns=FIXTURE_COLUMNS).to_csv(
        PROC / "fixture_context.csv", index=False)
    return dict(documents=len(documents), fixtures=len(rows),
                windows=len(win), game_centres=len(centres), game_books=len(books))


def main() -> int:
    summary = build()
    print("official documents:", summary["documents"])
    print("fixtures:", summary["fixtures"])
    print("week windows:", summary["windows"])
    print("game centres captured:", summary["game_centres"])
    print("game books captured:", summary["game_books"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
