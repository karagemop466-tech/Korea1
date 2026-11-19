"""Readers for the league's own published JSON, embedded in an official page.

Why this module exists
----------------------
`pipeline/official_games.py` reads the *flattened text* of an official page and
the *markup* of a game centre.  That is enough for a game centre, but it is no
longer enough for the league's **schedule** page: nfl.com serves the schedule
as a server-rendered Next.js application, so the HTML it returns contains the
week's fixtures only inside the page's RSC flight payload (the `self.__next_f`
chunks), and it contains **no** `/games/` anchor at all.  The anchor-based
reader therefore returns zero fixtures, the capture stores two identical
documents, and the whole Game Book chain is dead.

This module reads that payload.  It is the league's own published data — the
same fixture list the page renders — so a row read from it is an official
observation, not an inference.

Three payload queries are read:

* ``useFetchFootballWeeklyGameDetails`` — the week's fixtures: both clubs, the
  kickoff instant, the week, the status, the venue, the broadcast networks and
  the league's own external identifiers (Elias, GSIS, slug);
* ``useFetchExperienceWeekSelectorBySeason`` — the season's week windows and
  the clubs on a bye in each week;
* the game centre's Game Info block — ``LOCATION`` and ``STADIUM``.

Nothing is invented.  A field the payload does not print is returned blank.

Run: python pipeline/official_payload.py --selftest
"""
from __future__ import annotations

import json
import re
from typing import Any

# The RSC payload is delivered as a sequence of JavaScript string literals.
# Each literal is unescaped with the JSON string rules, which is what the
# browser's own JSON.parse does with the same bytes.
_FLIGHT_CHUNK = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')

_WEEKLY_GAMES_KEY = "useFetchFootballWeeklyGameDetails"
_WEEK_SELECTOR_KEY = "useFetchExperienceWeekSelectorBySeason"

# The game centre's Game Info block, as the league prints it.
_INFO_VALUE = re.compile(
    r'"data-testid":"info-card-item-value-(?P<field>[a-z]+)","children":"(?P<value>[^"]{1,160})"')

# The game centre's own "Download Game Book (PDF)" module.
_GAMEBOOK_MODULE = re.compile(r'data-testid="GameBook-\d+"')
# Only the league's Game Book links live under ``/gamecenter/``.  A looser
# "any PDF" pattern picked up the Record & Fact Book media-guide PDF that the
# game-centre page also references for an unplayed fixture, and thirteen
# future games were captured as if they had a Game Book (measured 2026-11-19;
# repaired by session arena/7cbb2e60-korea1).
_PDF_HREF = re.compile(
    r'href="(https://static\.www\.nfl\.com/[^"]*/gamecenter/[^"]+\.pdf)"')
_CANONICAL = re.compile(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"')
_TITLE = re.compile(r"<title>(.*?)</title>", re.S)


def flight_payload(html: str) -> str:
    """Concatenate and unescape the page's RSC flight chunks.

    Returns an empty string when the page carries no such chunk, which is the
    case for a page the league serves as plain markup.
    """
    parts: list[str] = []
    for m in _FLIGHT_CHUNK.finditer(html):
        try:
            parts.append(json.loads('"' + m.group(1) + '"'))
        except ValueError:
            # A chunk that is not a well-formed string literal is skipped; the
            # rest of the payload is still readable.
            continue
    return "".join(parts)


def _balanced(text: str, start: int) -> str | None:
    """Return the JSON value that starts at ``text[start]``, brackets balanced.

    String literals are respected so that a bracket inside a value cannot end
    the scan early.
    """
    if start < 0 or start >= len(text) or text[start] not in "[{":
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _query_record(payload: str, query_key: str) -> tuple[int, int]:
    """Locate the dehydrated React-Query record for ``query_key``.

    The league's payload writes the record as
    ``{"dehydratedAt":…,"state":{…},"queryKey":["<key>",{…}]}`` — the state
    comes *before* the query key inside the same record, so the record start is
    searched backwards from the query key.
    """
    qk = payload.find(f'"queryKey":["{query_key}"')
    if qk < 0:
        return -1, -1
    rec = payload.rfind('{"dehydratedAt":', 0, qk)
    if rec < 0:
        rec = 0
    return rec, qk


def _payload_arrays(payload: str, required: tuple[str, ...]) -> list[list[dict]]:
    """Every JSON array in the payload whose items carry ``required`` keys.

    The league's page carries the same fixture list twice — once in the
    server-rendered record and once in the hydration copy — and the two copies
    are not identical: the hydration copy is the one with the club
    abbreviations, the venue and the status.  Scanning for the arrays rather
    than for one record's offsets is therefore both simpler and more
    faithful: whichever copy holds the fact is the copy that is read.
    """
    out: list[list[dict]] = []
    pos = 0
    while True:
        i = payload.find('"data":[', pos)
        if i < 0:
            break
        pos = i + 8
        raw = _balanced(payload, i + 7)
        if raw is None:
            continue
        try:
            value = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(value, list) or not value:
            continue
        if isinstance(value[0], dict) and all(k in value[0] for k in required):
            out.append(value)
    return out


def _external_ids(game: dict) -> dict[str, str]:
    """The league's own identifiers for a fixture, keyed by source."""
    out: dict[str, str] = {}
    for item in game.get("externalIds") or []:
        if isinstance(item, dict) and item.get("source"):
            out[str(item["source"])] = str(item.get("id") or "")
    return out


def _channels(game: dict) -> str:
    """The broadcast channels the league prints for the fixture."""
    info = game.get("broadcastInfo") or {}
    names: list[str] = []
    for key in ("homeNetworkChannels", "awayNetworkChannels"):
        for value in info.get(key) or []:
            if value and value not in names:
                names.append(str(value))
    return ", ".join(names)


def parse_schedule_payload(html: str) -> list[dict]:
    """The week's fixtures, as the league publishes them.

    Each row keeps the league's own field names for the facts that are not
    renamed (week, week type, season, status, category, venue, external ids)
    and adds the derived ``official_url`` the league's own slug implies.
    """
    payload = flight_payload(html)
    if not payload:
        return []
    # The league's page prints each fixture in more than one copy, and the
    # copies are complementary: one carries the week, the venue, the status
    # and the kickoff instant, the other carries the club abbreviations, the
    # league's external identifiers and the flexibility flags.  Neither copy
    # alone is a complete fixture, so the copies are merged on the league's
    # own fixture id.  Where two copies disagree about the same field the
    # disagreement is recorded, not silently resolved.
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for value in _payload_arrays(payload, ("homeTeam", "awayTeam")):
        for game in value:
            if not isinstance(game, dict):
                continue
            fixture_id = str(game.get("id") or "")
            if not fixture_id:
                continue
            if fixture_id not in groups:
                groups[fixture_id] = []
                order.append(fixture_id)
            groups[fixture_id].append(game)

    rows: list[dict] = []
    for fixture_id in order:
        copies = groups[fixture_id]
        flat: dict[str, Any] = {}
        conflicts: list[str] = []
        for game in copies:
            for field, value in game.items():
                if field in ("homeTeam", "awayTeam", "venue"):
                    continue
                if value in ("", None):
                    continue
                if isinstance(value, (dict, list)):
                    # A structured field (the broadcast block, the standings)
                    # differs between the copies by construction; a copy
                    # difference is not a disagreement about a fact.
                    continue
                if field not in flat:
                    flat[field] = value
                elif not _consistent(flat[field], value):
                    conflicts.append(field)
        home = _merge_teams(copies, "homeTeam")
        away = _merge_teams(copies, "awayTeam")
        venue: dict[str, Any] = {}
        for game in copies:
            v = game.get("venue") or {}
            if not isinstance(v, dict):
                continue
            for field, value in v.items():
                if value in ("", None):
                    continue
                if field not in venue:
                    venue[field] = value
                elif not _consistent(venue[field], value):
                    conflicts.append(f"venue.{field}")
        ids: dict[str, str] = {}
        for game in copies:
            for source, value in _external_ids(game).items():
                ids.setdefault(source, value)
        slug = ids.get("slug", "")
        rows.append(dict(
            fixture_id=fixture_id,
            season=flat.get("season", ""),
            season_type=flat.get("seasonType", ""),
            week=flat.get("week", ""),
            week_type=flat.get("weekType", ""),
            away_team=away.get("abbreviation", "") or away.get("triCode", ""),
            away_team_name=away.get("fullName", ""),
            away_team_id=away.get("id", ""),
            home_team=home.get("abbreviation", "") or home.get("triCode", ""),
            home_team_name=home.get("fullName", ""),
            home_team_id=home.get("id", ""),
            kickoff_utc=flat.get("time", "") or flat.get("date", ""),
            kickoff_date_as_printed=flat.get("date", ""),
            venue_name=venue.get("name", ""),
            venue_city=venue.get("city", ""),
            venue_country=venue.get("country", ""),
            status=flat.get("status", ""),
            category=flat.get("category", ""),
            game_type=flat.get("gameType", ""),
            international=flat.get("international", ""),
            neutral_site=flat.get("neutralSite", ""),
            is_flexible=flat.get("isFlexible", ""),
            networks_as_printed=_channels(flat),
            elias_id=ids.get("elias", ""),
            gsis_id=ids.get("gsis", ""),
            slug=slug,
            official_url=f"https://www.nfl.com/games/{slug}" if slug else "",
            payload_conflicts=",".join(sorted(set(conflicts))),
        ))
    return rows


def _consistent(a: Any, b: Any) -> bool:
    """True when two copies of a fact agree.

    A date and the instant that date begins are the same fact printed at two
    lengths, so a prefix is agreement; everything else must match exactly.
    """
    if a == b:
        return True
    if isinstance(a, str) and isinstance(b, str):
        return bool(a) and bool(b) and (a.startswith(b) or b.startswith(a))
    return False


def _merge_teams(copies: list[dict], key: str) -> dict[str, Any]:
    """One club's fields, merged across the copies that carry it."""
    out: dict[str, Any] = {}
    for game in copies:
        team = game.get(key) or {}
        if not isinstance(team, dict):
            continue
        for field, value in team.items():
            if value in ("", None):
                continue
            out.setdefault(field, value)
    return out


def published_week(html: str) -> str:
    """The week the captured page actually publishes.

    The league's schedule page is an application: the week in the URL is not
    always the week the payload carries.  Reading the published week from the
    payload is what lets the capture notice the difference instead of
    silently labelling one week's fixtures with another week's number.
    """
    payload = flight_payload(html)
    if not payload:
        return ""
    rec, qk = _query_record(payload, _WEEKLY_GAMES_KEY)
    if rec < 0:
        return ""
    body = payload[rec:qk]
    m = re.search(r'"season":"(?P<season>\d{4})","seasonType":"(?P<stype>[A-Z]+)",'
                  r'"week":(?P<week>\d+)', body)
    if m:
        return m.group("week")
    for value in _payload_arrays(payload, ("homeTeam", "awayTeam")):
        for game in value:
            if isinstance(game, dict) and game.get("week") != "":
                return str(game["week"])
    return ""


def parse_week_selector(html: str) -> list[dict]:
    """The season's week windows and the clubs on a bye in each week.

    Every field is the league's own: ``week``, ``weekLabel``, ``weekType``,
    ``season``, ``seasonType``, ``dateBegin``, ``dateEnd`` and
    ``teamsOnBye``.
    """
    payload = flight_payload(html)
    if not payload:
        return []
    rows: list[dict] = []
    for value in _payload_arrays(payload, ("weekLabel", "teamsOnBye")):
        for week in value:
            if not isinstance(week, dict) or week.get("week") in (None, ""):
                continue
            byes = [str(t.get("triCode") or "")
                    for t in (week.get("teamsOnBye") or []) if isinstance(t, dict)]
            rows.append(dict(
                week=week.get("week", ""),
                week_label=week.get("weekLabel", ""),
                week_type=week.get("weekType", ""),
                season=week.get("season", ""),
                season_type=week.get("seasonType", ""),
                date_begin=week.get("dateBegin", ""),
                date_end=week.get("dateEnd", ""),
                teams_on_bye=",".join(b for b in byes if b),
            ))
        if rows:
            break
    return rows


def parse_game_centre_info(html: str) -> dict:
    """The venue the league's game centre prints, and its Game Book link.

    The league renders the Game Info block with stable test ids, so the
    values are read from the page's own payload rather than guessed from the
    flattened text.
    """
    payload = flight_payload(html)
    out = dict(venue_location="", venue_stadium="", gamebook_url="",
               canonical_url="", page_title="")
    for m in _INFO_VALUE.finditer(payload):
        field, value = m.group("field"), m.group("value")
        if field == "location" and not out["venue_location"]:
            out["venue_location"] = value
        elif field == "stadium" and not out["venue_stadium"]:
            out["venue_stadium"] = value
    module = _GAMEBOOK_MODULE.search(html)
    if module:
        seg = html[module.start():module.start() + 8000]
        link = _PDF_HREF.search(seg)
        if link:
            out["gamebook_url"] = link.group(1)
    if not out["gamebook_url"]:
        link = _PDF_HREF.search(html)
        if link:
            out["gamebook_url"] = link.group(1)
    canon = _CANONICAL.search(html)
    if canon:
        out["canonical_url"] = canon.group(1)
    title = _TITLE.search(html)
    if title:
        out["page_title"] = re.sub(r"\s+", " ", title.group(1)).strip()
    return out


def _selftest() -> int:
    """Read the committed official capture and print what it yields."""
    import gzip
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    path = root / "data/evidence/official_games/schedule/REG10.html.gz"
    if not path.exists():
        print("no committed schedule capture to read")
        return 0
    html = gzip.open(path, "rt", encoding="utf-8").read()
    rows = parse_schedule_payload(html)
    print(f"fixtures parsed: {len(rows)}")
    print(f"published week: {published_week(html)}")
    weeks = parse_week_selector(html)
    print(f"week windows: {len(weeks)}")
    for row in rows[:3]:
        print("  ", row["away_team"], "at", row["home_team"], "|", row["kickoff_utc"],
              "|", row["venue_name"], "|", row["status"], "|", row["official_url"])
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
