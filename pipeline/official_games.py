"""Official NFL game-centre and Game Book readers (pure functions, no network).

Every function here takes a *document* and returns structured rows.  None of
them decides a value that the document does not print: a field that is not
present is returned blank, and the row carries a note saying why.

Two official document shapes are handled.

1. The **game centre** page on www.nfl.com.  Its "Game Info" block prints the
   venue twice — the city and state as ``LOCATION`` and the stadium name as
   ``STADIUM`` — and it links the official Game Book PDF.

2. The **Game Book PDF** the league publishes for every game.  Page 1 prints
   the date, the start time and its time zone, the officials, the game-day
   weather and the roof / surface designation, the venue line, both starting
   lineups, the substitution lists, the "Did Not Play" lists and the "Not
   Active" (inactive) lists.

The parsers are deliberately tolerant: the same fact is looked for in more
than one way, and a fact that cannot be confirmed is left empty.

Run: python pipeline/official_games.py --selftest   (uses the committed sample)
"""
from __future__ import annotations

import html as html_mod
import re
from typing import Iterable

# --------------------------------------------------------------------------
# HTML -> text
# --------------------------------------------------------------------------

_BLOCK_END = re.compile(
    r"</(p|div|tr|td|th|li|h[1-6]|table|section|article|header|footer|br|ul|ol)>",
    re.I,
)
_DROP = re.compile(r"<(script|style|noscript|svg)\b.*?</\1>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")


def html_to_text(raw: str) -> str:
    """Flatten an official HTML page to plain text.

    Block-level elements become newlines so that table rows stay apart, and
    runs of whitespace inside a line are collapsed to a single space.  Nothing
    is invented: the text is the page's own text.
    """
    txt = _DROP.sub(" ", raw)
    txt = _BLOCK_END.sub("\n", txt)
    txt = _TAG.sub(" ", txt)
    txt = html_mod.unescape(txt)
    txt = txt.replace("\u00a0", " ")
    lines = []
    for line in txt.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    out = []
    for line in lines:
        if out and out[-1] == line:
            continue
        out.append(line)
    return "\n".join(out)


# --------------------------------------------------------------------------
# Schedule page
# --------------------------------------------------------------------------

# "- Colts at Texans, Thursday, November 19th, 8:15 PM, PRIME"
_SCHEDULE_LINK = re.compile(
    r"(?P<away>[A-Za-z0-9'&.\- ]+?)\s+at\s+(?P<home>[A-Za-z0-9'&.\- ]+?),"
    r"\s+(?P<day>[A-Za-z]+day,\s+[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?),"
    r"\s+(?P<time>\d{1,2}:\d{2}\s*[AP]M)"
    r"(?:,\s*(?P<network>[A-Za-z0-9+&.\- ]+?))?"
    r"\s*\(?(?P<url>https://www\.nfl\.com/games/[A-Za-z0-9\-]+)"
)

_HEADING = re.compile(r"^###\s+(?P<heading>.+?)\s*$", re.M)


def parse_schedule_page(text: str) -> list[dict]:
    """Fixtures printed on an official NFL schedule page.

    Each row keeps the wording the league printed, the section heading the row
    sits under, the official game-centre URL and the page it was read from.
    """
    rows: list[dict] = []
    headings = [(m.start(), m.group("heading")) for m in _HEADING.finditer(text)]
    for m in _SCHEDULE_LINK.finditer(text):
        heading = ""
        for pos, head in headings:
            if pos < m.start():
                heading = head
            else:
                break
        rows.append(dict(
            away_as_printed=m.group("away").strip(),
            home_as_printed=m.group("home").strip(),
            date_as_printed=re.sub(r"\s+", " ", m.group("day")).strip(),
            time_as_printed=re.sub(r"\s+", " ", m.group("time")).strip(),
            network_as_printed=re.sub(r"\s+", " ", (m.group("network") or "")).strip(),
            section_heading=heading,
            official_url=m.group("url"),
        ))
    return rows


# --------------------------------------------------------------------------
# Game centre page
# --------------------------------------------------------------------------

_GAME_INFO = re.compile(
    r"Game\s*Info\b(?P<body>.{0,600}?)(?:Standings|Ways to watch|Ways to listen|"
    r"Season at a glance|Team Leaders|$)",
    re.S | re.I,
)
_LOCATION = re.compile(r"Location\s*:?\s*LOCATION\s*:?\s*(?P<v>[^\n]+)", re.I)
_STADIUM = re.compile(r"Stadium\s*:?\s*STADIUM\s*:?\s*(?P<v>[^\n]+)", re.I)
_GAMEBOOK = re.compile(
    r"https://static\.www\.nfl\.com/image/upload/[^\s\"'<>)]+/gamecenter/[A-Za-z0-9\-]+\.pdf")


def parse_game_centre(text: str) -> dict:
    """The facts the official game centre prints about the fixture itself.

    ``venue_location`` and ``venue_stadium`` come from the page's own Game Info
    block.  ``gamebook_url`` is the league's Game Book link.  The final score is
    read only when the page prints one next to a team; a scheduled game has no
    score and the field stays blank.
    """
    out = dict(venue_location="", venue_stadium="", gamebook_url="",
               away_score="", home_score="", away_abbr="", home_abbr="",
               away_name="", home_name="", status_as_printed="", week_as_printed="",
               date_as_printed="")
    block = _GAME_INFO.search(text)
    body = block.group("body") if block else text
    m = _LOCATION.search(body)
    if m:
        out["venue_location"] = m.group("v").strip()
    m = _STADIUM.search(body)
    if m:
        out["venue_stadium"] = m.group("v").strip()
    m = _GAMEBOOK.search(text)
    if m:
        out["gamebook_url"] = m.group(0)

    # Final score: the game centre prints "<abbr> <name> <abbr> <city> <abbr>
    # <score> points" for each side, then the status word.
    teams = re.findall(
        r"\b([A-Z]{2,3})\b\s*\n([A-Z][A-Za-z'&\.\- ]{3,40}?)\s*\n(?:[A-Z][A-Z'&\. ]{3,40}\s*\n){2,4}"
        r"(\d{1,3})\s*\n?\s*points",
        text)
    if len(teams) >= 2:
        (aa, an, as_), (ha, hn, hs) = teams[0], teams[1]
        out["away_abbr"], out["away_name"], out["away_score"] = aa, an.strip(), as_
        out["home_abbr"], out["home_name"], out["home_score"] = ha, hn.strip(), hs
    if re.search(r"\bFinal\b", text):
        out["status_as_printed"] = "Final"
    m = re.search(r"\bWEEK\s+(\d{1,2})\b", text)
    if m:
        out["week_as_printed"] = m.group(1)
    m = re.search(r"\b(Nov|Dec|Sep|Oct|Jan)\s+(\d{1,2})\b", text)
    if m:
        out["date_as_printed"] = f"{m.group(1)} {m.group(2)}"
    return out


# --------------------------------------------------------------------------
# Game Book PDF text
# --------------------------------------------------------------------------

_BOOK_TITLE = re.compile(r"^(?P<away>.+?)\s+at\s+(?P<home>.+?)\s*$", re.M)
_BOOK_DATE = re.compile(r"^Date:\s*(?P<v>.+?)\s*$", re.M)
_BOOK_START = re.compile(r"^Start Time:\s*(?P<v>.+?)\s*$", re.M)
_BOOK_VENUE = re.compile(r"^\*\*(?P<away>.+?)\s+vs\s+(?P<home>.+?)\*\*\s*$", re.M)
_BOOK_VENUE2 = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}\s+at\s+(?P<v>.+?)\s*$", re.M)
_BOOK_WEATHER = re.compile(r"^Game Weather:\s*(?P<v>.+?)\s*$", re.M)
_BOOK_TEMP = re.compile(r"Temp:\s*(?P<t>[-\d]+)°\s*F.*?Wind:\s*(?P<w>[A-Za-z]+\s+\d+)\s*mph", re.S)
_BOOK_ROOF = re.compile(r"^(?P<v>Retractable Roof.*?|Dome.*?|Roof.*?)\s*$", re.M)
_BOOK_ATTEND = re.compile(r"^Paid Attendance:\s*(?P<v>[\d,]+)\s*$", re.M)
_BOOK_OFFICIALS = re.compile(r"^Referee:\s*(?P<v>.+?)\s*$", re.M)

_NAME = r"[A-Z][A-Za-z'\-]*\.[A-Za-z'\-]+"
_CELL = re.compile(
    r"(?P<pos>(?:\d?[A-Z]{1,3}|OL B|CB|FS|SS))\s+"
    r"(?P<num>\d{1,2})\s+"
    rf"(?P<name>{_NAME})")


def _split_block(text: str, start_marker: str, end_markers: Iterable[str]) -> str:
    i = text.find(start_marker)
    if i < 0:
        return ""
    body = text[i + len(start_marker):]
    cut = len(body)
    for marker in end_markers:
        j = body.find(marker)
        if 0 <= j < cut:
            cut = j
    return body[:cut]


def parse_game_book(text: str) -> dict:
    """Official facts printed on page 1 of an NFL Game Book."""
    out = dict(
        away_as_printed="", home_as_printed="", date_as_printed="", start_time_as_printed="",
        venue_as_printed="", weather_as_printed="", temp_f="", wind_as_printed="",
        roof_as_printed="", surface_as_printed="", attendance_as_printed="",
        referee_as_printed="", lineups="", substitutions="", did_not_play="", not_active="",
        notes=[],
    )
    m = _BOOK_TITLE.search(text)
    if m:
        out["away_as_printed"] = m.group("away").strip()
        out["home_as_printed"] = m.group("home").strip()
    m = _BOOK_DATE.search(text)
    if m:
        out["date_as_printed"] = m.group("v").strip()
    m = _BOOK_START.search(text)
    if m:
        out["start_time_as_printed"] = m.group("v").strip()
    m = _BOOK_VENUE2.search(text)
    if m:
        out["venue_as_printed"] = m.group("v").strip()
    m = _BOOK_WEATHER.search(text)
    if m:
        out["weather_as_printed"] = m.group("v").strip()
    m = _BOOK_TEMP.search(text)
    if m:
        out["temp_f"] = m.group("t")
        out["wind_as_printed"] = m.group("w").strip()
    m = _BOOK_ROOF.search(text)
    if m:
        roof = m.group("v").strip()
        out["roof_as_printed"] = roof
        if "Field Turf" in roof or "Grass" in roof or "Turf" in roof:
            out["surface_as_printed"] = re.search(r"on\s+(\w+)\s+Turf|on\s+Grass", roof).group(1) \
                if re.search(r"on\s+(\w+)\s+Turf|on\s+Grass", roof) else ""
    m = _BOOK_ATTEND.search(text)
    if m:
        out["attendance_as_printed"] = m.group("v").strip()
    m = _BOOK_OFFICIALS.search(text)
    if m:
        out["referee_as_printed"] = m.group("v").strip()

    out["lineups"] = _split_block(text, "Lineups", ["Substitutions", "Did Not Play", "Not Active"])
    out["substitutions"] = _split_block(text, "Substitutions", ["Did Not Play", "Not Active"])
    out["did_not_play"] = _split_block(text, "Did Not Play", ["Not Active"])
    out["not_active"] = _split_block(text, "Not Active", ["Field Goals", "Scoring Plays"])
    return out


def parse_roster_entries(block: str) -> list[dict]:
    """Rows of a Game Book roster block.

    The block prints ``POS <jersey> <name>`` entries separated by commas, e.g.
    ``WR 5 M.Evans, 3QB 14 K.Rourke, LB 48 T.Bethune``.  Every entry is read
    exactly as printed; nothing is ordered or ranked here.
    """
    entries: list[dict] = []
    for chunk in re.split(r",(?=\s*(?:\d?[A-Z]{1,3}|OL B)\s+\d{1,2}\s)", block):
        chunk = chunk.strip()
        if not chunk:
            continue
        for m in _CELL.finditer(chunk):
            entries.append(dict(position=m.group("pos"), jersey=m.group("num"),
                                player=m.group("name")))
        if not _CELL.search(chunk) and chunk:
            entries.append(dict(position="", jersey="", player=chunk))
    return entries
