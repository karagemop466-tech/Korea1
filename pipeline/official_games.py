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
   Active" lists.

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

# "- Colts at Texans, Thursday, November 19th, 8:15 PM, PRIME"   (pregame print)
_SCHEDULE_LABEL = re.compile(
    r"^\s*(?P<away>[A-Za-z0-9'&.\- ]+?)\s+at\s+(?P<home>[A-Za-z0-9'&.\- ]+?),"
    r"\s+(?P<day>[A-Za-z]+day,\s+[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?),"
    r"\s+(?P<time>\d{1,2}:\d{2}\s*[AP]M)"
    r"(?:,\s*(?P<network>[A-Za-z0-9+&.\- ]+?))?\s*$")
# "- Commanders 24, Giants 21, FINAL, Thursday, November 12th"   (final print).
# The league prints finished games this way on the by-week schedule page, so a
# week of already-played fixtures is readable from the same document as a
# week that has not started.  The score and the word FINAL are transcribed,
# never derived; a pregame row keeps them blank.
_FINAL_LABEL = re.compile(
    r"^\s*(?P<away>[A-Za-z0-9'&.\- ]+?)\s+(?P<away_score>\d{1,2}),\s*"
    r"(?P<home>[A-Za-z0-9'&.\- ]+?)\s+(?P<home_score>\d{1,2}),\s*FINAL,"
    r"\s*(?P<day>[A-Za-z]+day,\s+[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?)\s*$")

# The league serves the fixture link both ways: the flattened page captured on
# 2026-11-19 by the GitHub runner used *relative* hrefs ("/games/…") with the
# label inside a nested <span class="sr-only">, while simpler renders print an
# absolute href with the label as the anchor's direct text.  Both shapes are
# the same official link; only the markup differs.  Measured, not assumed:
# `data/evidence/official_games/schedule/REG10.html.gz` (2026-11-19) contains
# 13 fixture anchors, all of them relative.
_ANCHOR = re.compile(
    r"<a\b[^>]*?href=\"(?P<url>(?:https://www\.nfl\.com)?/games/[^\"]+)\"[^>]*>"
    r"(?P<label>.*?)</a>",
    re.I | re.S)
_SRONLY = re.compile(
    r"<span[^>]*class=\"[^\"]*sr-only[^\"]*\"[^>]*>(?P<t>.*?)</span>", re.I | re.S)
_HTML_HEADING = re.compile(r"<h[1-6]\b[^>]*>(?P<h>.*?)</h[1-6]>", re.I | re.S)


def slug_of(url: str) -> str:
    """The fixture slug an official game URL ends in (query and slash stripped)."""
    path = url.split("?")[0].split("#")[0].rstrip("/")
    return path.rsplit("/", 1)[-1]


def fixture_week(official_url: str) -> int | None:
    """The regular-season week printed in a fixture slug, or None if absent.

    ``commanders-at-giants-2026-reg-10`` → 10.  The week is read from the
    league's own slug; nothing is taken from the URL the page was requested
    with, because that is exactly the field the old capture got wrong.
    """
    m = re.search(r"-reg-(\d+)$", slug_of(official_url))
    return int(m.group(1)) if m else None


def week_mismatches(rows: list[dict], week: int) -> list[str]:
    """Every row whose slug week is not the requested week (empty = clean)."""
    bad: list[str] = []
    for r in rows:
        fw = fixture_week(r.get("official_url", ""))
        if fw is None:
            bad.append(f"{r.get('official_url', '')!r}: slug carries no -reg-<week>")
        elif fw != week:
            bad.append(f"{slug_of(r.get('official_url', ''))}: slug week {fw}, requested {week}")
    return bad


def game_link_slugs(raw_html: str) -> set[str]:
    """Every fixture slug the page links to under /games/ (any label shape).

    Used to cross-check the schedule page against the independently rendered
    scores page: two official documents must name the same fixture set before
    anything is captured.
    """
    return {slug_of(m.group("url")) for m in _ANCHOR.finditer(raw_html)}


def week_schedule_url(season: int, week: int) -> str:
    """The league's week-selecting schedule URL.

    Measured 2026-11-19: ``/schedules/<season>/REG<week>`` did **not** select
    the week for the capture client — the REG9 and REG10 fetches returned
    byte-identical current-week content (flag F-2026-11-19-08).  The by-week
    path prints the requested week's title and fixtures (re-read live the same
    day: ``…/by-week/week-10`` → "NFL Week 10 Schedule 2026").
    """
    return f"https://www.nfl.com/schedules/{season}/by-week/week-{week}"


def scores_week_url(season: int, week: int) -> str:
    """The league's week-selecting scores page (the completeness cross-check)."""
    return f"https://www.nfl.com/scores/{season}/week-{week}"


def _anchor_label(label_html: str) -> str:
    """The printed fixture label from an anchor's markup.

    The accessible name lives in a nested ``sr-only`` span when one is
    present; otherwise the anchor's own text is the label.  Tags are stripped
    and entities decoded — the words are the page's words, nothing added.
    """
    m = _SRONLY.search(label_html)
    src = m.group("t") if m else label_html
    txt = _TAG.sub(" ", src)
    return re.sub(r"\s+", " ", html_mod.unescape(txt)).strip()


def parse_schedule_page(raw_html: str) -> list[dict]:
    """Fixtures printed on an official NFL schedule page.

    The league prints each fixture as a link whose text is either

    * ``Colts at Texans, Thursday, November 19th, 8:15 PM, PRIME`` (pregame), or
    * ``Commanders 24, Giants 21, FINAL, Thursday, November 12th`` (final).

    Each row keeps that wording (scores and FINAL only when the page printed
    them), the section heading the row sits under, the absolute official
    game-centre URL and the page it was read from.  A link whose label matches
    neither shape is skipped — a fixture is never reconstructed from markup.
    """
    headings = [(m.start(), re.sub(r"\s+", " ", html_mod.unescape(m.group("h"))).strip())
                for m in _HTML_HEADING.finditer(raw_html)]
    rows: list[dict] = []
    for m in _ANCHOR.finditer(raw_html):
        url = m.group("url")
        if url.startswith("/"):
            url = "https://www.nfl.com" + url
        label = _anchor_label(m.group("label"))
        lab = _SCHEDULE_LABEL.match(label)
        is_final = False
        if lab is None:
            lab = _FINAL_LABEL.match(label)
            if lab is None:
                continue
            is_final = True
        heading = ""
        for pos, head in headings:
            if pos < m.start():
                heading = head
            else:
                break
        rows.append(dict(
            away_as_printed=lab.group("away").strip(),
            home_as_printed=lab.group("home").strip(),
            date_as_printed=re.sub(r"\s+", " ", lab.group("day")).strip(),
            time_as_printed="" if is_final else re.sub(r"\s+", " ", lab.group("time")).strip(),
            network_as_printed=("" if is_final else
                                 re.sub(r"\s+", " ", (lab.group("network") or "")).strip()),
            status_as_printed="FINAL" if is_final else "",
            away_score_as_printed=lab.group("away_score") if is_final else "",
            home_score_as_printed=lab.group("home_score") if is_final else "",
            section_heading=heading,
            official_url=url,
        ))
    return rows


def parse_scores_page(raw_html: str) -> list[dict]:
    """Finals printed on an official NFL scores page, one row per fixture.

    Added 2026-11-19 (session `arena/7134ec74-korea1`, flag F-2026-11-19-W12).
    The scheduled fetcher already downloads this page every run and threw the
    bytes away, keeping only a SHA-256; settlement therefore rested on the
    by-week schedule page alone.  The scores page prints, per fixture, in this
    order (verbatim shape read live 2026-11-19):

        - [View Commanders Giants game](/games/commanders-at-giants-2026-reg-10)
        COMMANDERS Washington Commanders WAS Washington Commanders
        24
        24 points
        GIANTS New York Giants NYG New York Giants
        21
        21 points
        Final

    Pairing is **positional**: the i-th "View … game" label belongs to the
    i-th fixture link, because that is the order the page prints them in.  The
    pairing is then checked against the link's own slug; a label that does not
    name the slug's clubs is returned blank with ``label_matches_slug = 0``.

    Conservative by design: a block whose pure-integer lines are not exactly
    two carries blank scores.  Nothing is inferred and no value is defaulted.
    """
    text = html_to_text(raw_html)
    lines = text.split("\n")
    # The label may share its line with the first club block when the page prints the
    # anchor and the block without a block-level break, so the pattern is anchored at the
    # start of the line and takes the first ``game`` as its end.
    label_pat = re.compile(r"^\s*(?:-\s*)?View\s+(?P<label>.+?)\s+game\b", re.I)
    label_idx = [k for k, ln in enumerate(lines) if label_pat.match(ln)]
    slugs = [slug_of(m.group("url")) for m in _ANCHOR.finditer(raw_html)]
    out: list[dict] = []
    for i, slug in enumerate(slugs):
        row = dict(slug=slug, away_as_printed="", home_as_printed="",
                   away_score_as_printed="", home_score_as_printed="",
                   status_as_printed="", score_block_found=0, label_matches_slug=0)
        if i >= len(label_idx):
            out.append(row)
            continue
        k = label_idx[i]
        label = label_pat.match(lines[k]).group("label").strip()
        away, home = _split_fixture_label(label, slug)
        stop = label_idx[i + 1] if i + 1 < len(label_idx) else min(k + 60, len(lines))
        block = [ln.strip() for ln in lines[k + 1:stop]]
        nums = [ln for ln in block if re.fullmatch(r"\d{1,3}", ln)]
        status = next((ln for ln in block if ln.lower() in
                       ("final", "final/ot", "in progress", "pregame", "postponed")), "")
        row.update(
            away_as_printed=away, home_as_printed=home,
            status_as_printed=status,
            label_matches_slug=int(_slug_names_clubs(slug, away, home)),
        )
        if len(nums) == 2:
            row.update(away_score_as_printed=nums[0], home_score_as_printed=nums[1],
                       score_block_found=1)
        out.append(row)
    return out


def _slug_names_clubs(slug: str, away: str, home: str) -> bool:
    """Does ``<away>-at-<home>-<season>-reg-<week>`` print these two club words?"""
    m = re.match(r"(.+)-at-(.+)-(\d{4})-reg-(\d+)$", slug)
    if not m:
        return False
    norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())            # noqa: E731
    return norm(m.group(1)) == norm(away) and norm(m.group(2)) == norm(home)


def _split_fixture_label(label: str, slug: str) -> tuple[str, str]:
    """Split ``Commanders Giants`` into the visiting and home club as printed.

    The slug (``commanders-at-giants-2026-reg-10``) carries the clubs in order
    and is the league's own identifier, so it is used to decide which half of
    the printed label is the visitor.  The label itself is returned unchanged.
    """
    parts = label.split()
    m = re.match(r"(.+)-at-(.+)-\d{4}-reg-\d+$", slug)
    if not m:
        return (parts[0] if parts else ""), (parts[1] if len(parts) > 1 else "")
    away_key, home_key = m.group(1), m.group(2)
    mid = None
    for k in range(1, len(parts)):
        left = "-".join(parts[:k]).lower().replace(" ", "-")
        if left == away_key:
            mid = k
            break
    if mid is None:
        return (parts[0] if parts else ""), (parts[1] if len(parts) > 1 else "")
    return " ".join(parts[:mid]), " ".join(parts[mid:])


# --------------------------------------------------------------------------
# Game centre page
# --------------------------------------------------------------------------

_GAME_INFO = re.compile(
    r"Game\s*Info\b(?P<body>.{0,800}?)(?:Standings|Ways to watch|Ways to listen|"
    r"Season at a glance|Team Leaders|REGULAR SEASON AT A GLANCE|$)",
    re.S | re.I,
)
_LOCATION = re.compile(
    r"Location[^\S\n]*:?[^\S\n]*LOCATION[^\S\n]*:?[^\S\n]*(?P<v>[^\n]+)|"
    r"Location[^\S\n]*:?[^\S\n]*LOCATION[^\S\n]*\n[^\S\n]*(?P<v2>[^\n]+)", re.I)
_STADIUM = re.compile(
    r"Stadium[^\S\n]*:?[^\S\n]*STADIUM[^\S\n]*:?[^\S\n]*(?P<v>[^\n]+)|"
    r"Stadium[^\S\n]*:?[^\S\n]*STADIUM[^\S\n]*\n[^\S\n]*(?P<v2>[^\n]+)", re.I)
_GAMEBOOK = re.compile(
    r"https://static\.www\.nfl\.com/image/upload/[^\s\"'<>)]+/gamecenter/[A-Za-z0-9\-]+\.pdf")


def parse_game_centre(text: str, raw_html: str = "") -> dict:
    """The facts the official game centre prints about the fixture itself.

    ``venue_location`` and ``venue_stadium`` come from the page's own Game Info
    block.  ``gamebook_url`` is the league's Game Book link; the league
    publishes it only for a finished game, so its presence is also the
    game's own statement that the fixture has been played.  The link lives in
    the page's markup, so it is read from ``raw_html`` when it is supplied.
    """
    out = dict(venue_location="", venue_stadium="", gamebook_url="")
    block = _GAME_INFO.search(text)
    body = block.group("body") if block else text
    m = _LOCATION.search(body)
    if m:
        out["venue_location"] = (m.group("v") or m.group("v2") or "").strip()
    m = _STADIUM.search(body)
    if m:
        out["venue_stadium"] = (m.group("v") or m.group("v2") or "").strip()
    m = _GAMEBOOK.search(raw_html) or _GAMEBOOK.search(text)
    if m:
        out["gamebook_url"] = m.group(0)
    return out


# --------------------------------------------------------------------------
# Game Book PDF text
# --------------------------------------------------------------------------

_BOOK_TITLE = re.compile(r"^(?P<away>.+?)\s+at\s+(?P<home>.+?)\s*$", re.M)
# Leading whitespace tolerated: ``pdftotext -layout`` may indent a cell.  The
# words matched are the page's own; nothing is invented when they are absent.
_BOOK_DATE = re.compile(r"^\s*Date:\s*(?P<v>.+?)\s*$", re.M)
_BOOK_START = re.compile(r"^\s*Start Time:\s*(?P<v>.+?)\s*$", re.M)
_BOOK_VENUE = re.compile(r"^\s*(?P<v>\d{1,2}/\d{1,2}/\d{4}\s+at\s+.+?)\s*$", re.M)
# The real capture prints date, matchup and start time on ONE line, and the
# venue alone on the next (``at MetLife Stadium, East Rutherford, NJ``).
_BOOK_DATELINE = re.compile(
    r"^\s*Date:\s*(?P<date>[A-Za-z]+day,\s*\d{1,2}/\d{1,2}/\d{4})\s+"
    r"(?P<away>.+?)\s+at\s+(?P<home>.+?)\s+Start Time:\s*(?P<time>\d{1,2}:\d{2}\s*[AP]M\s*\w*)\s*$",
    re.M)
_BOOK_VENUE_AT = re.compile(r"^\s*at\s+(?P<v>[A-Z].+?)\s*$", re.M)
_BOOK_WEATHER = re.compile(r"^Game Weather:\s*(?P<v>.*?)(?:\s+Temp:|\s*$)", re.M)
_BOOK_TEMP = re.compile(r"Temp:\s*(?P<t>[-\d]+)°\s*F.*?Wind:\s*(?P<w>[A-Za-z]+\s+\d+)\s*mph", re.S)
_BOOK_ROOF = re.compile(r"^\s*(?P<v>(?:Retractable Roof|Dome|Roof).*?)\s*$", re.M)
_BOOK_SURFACE = re.compile(r"on\s+(?P<v>Grass|Field Turf|Turf|AstroTurf|Synthetic Turf)", re.I)
_BOOK_ATTEND = re.compile(r"^\s*Paid Attendance:\s*(?P<v>[\d,]+)\s*$", re.M)
_BOOK_OFFICIALS = re.compile(r"^\s*Referee:\s*(?P<v>.+?)\s*$", re.M)

# Initial.Surname, extended for the two-word surnames the real books print
# (``G.Van Roten``, ``A.St. Brown``).  An extra word must contain a lowercase
# letter, so an all-caps position token (``CB``, ``OLB``, ``EDGE``) or a
# single-letter position (``S``) still ends the name.
_NAME = (r"[A-Z][A-Za-z'\-]*\.[A-Za-z'\-]+"
        r"(?:[ .]+[A-Z]?[a-z][A-Za-z'\-]*)*")
_CELL = re.compile(
    r"(?P<pos>(?:\d?[A-Z]{1,3}|OL B|CB|FS|SS))\s+"
    r"(?P<num>\d{1,2})\s+"
    rf"(?P<name>{_NAME})")
# The four-column lineup grid pads inside a cell too: the committed Game Book
# bytes print ``     WR     14 A.Williams`` — five spaces between position and
# jersey — while the gap between two printed columns is about twenty.  A run
# of two spaces therefore cannot be a column boundary here (that is why the
# captured lineups parsed as ``lineup_unreadable`` before this pattern).
# Measured on ``data/evidence/official_games/gamebooks/``; nothing is guessed:
# a row that does not yield exactly four pos-jersey-name cells still falls
# back to the wide-gap split and is flagged unreadable if it does not read.
_CELL_TOLERANT = re.compile(
    rf"(?<![\w.])(?P<pos>(?:\d?[A-Z]{{1,4}}|OL B|CB|FS|SS))\s+"
    rf"(?P<num>\d{{1,2}})\s+(?P<name>{_NAME})")


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
    )
    # The league prints the whole identification strip on one line in the
    # captured PDFs — ``Date: Thursday, 11/12/2026   Washington Commanders at
    # New York Giants   Start Time: 8:15 PM EST`` — with the venue on the
    # following line (``at MetLife Stadium, East Rutherford, NJ``).  That
    # combined line is read first so the title and date cannot swallow each
    # other; the three own-line forms below remain as the fallback for prints
    # (and the repository's synthetic fixtures) that set them on separate
    # lines.  Measured on ``data/evidence/official_games/gamebooks/``.
    m = _BOOK_DATELINE.search(text)
    if m:
        out["date_as_printed"] = m.group("date").strip()
        out["away_as_printed"] = m.group("away").strip()
        out["home_as_printed"] = m.group("home").strip()
        out["start_time_as_printed"] = m.group("time").strip()
    else:
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
    m = _BOOK_VENUE.search(text)
    if not m:
        m = _BOOK_VENUE_AT.search(text)
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
        out["roof_as_printed"] = m.group("v").strip()
        s = _BOOK_SURFACE.search(out["roof_as_printed"])
        if s:
            out["surface_as_printed"] = s.group("v").strip()
    m = _BOOK_ATTEND.search(text)
    if m:
        out["attendance_as_printed"] = m.group("v").strip()
    m = _BOOK_OFFICIALS.search(text)
    if m:
        out["referee_as_printed"] = m.group("v").strip()

    lineups = _split_block(text, "Lineups", ["Substitutions", "Did Not Play", "Not Active"])
    if not lineups:
        # Some official prints of page 1 omit the word "Lineups" itself; the
        # block still sits between the officials line and the Substitutions
        # row.  The fallback reads that span — it does not move content in.
        off = _BOOK_OFFICIALS.search(text)
        start = off.end() if off else 0
        cut = len(text)
        for marker in ("Substitutions", "Did Not Play", "Not Active"):
            j = text.find(marker, start)
            if 0 <= j < cut:
                cut = j
        lineups = text[start:cut] if cut > start else ""
    out["lineups"] = lineups
    out["substitutions"] = _split_block(text, "Substitutions", ["Did Not Play", "Not Active"])
    out["did_not_play"] = _split_block(text, "Did Not Play", ["Not Active"])
    out["not_active"] = _split_block(text, "Not Active",
                                     ["Field Goals", "Scoring Plays", "Paid Attendance"])
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
        found = list(_CELL.finditer(chunk))
        if found:
            for m in found:
                entries.append(dict(position=m.group("pos"), jersey=m.group("num"),
                                    player=m.group("name")))
        else:
            entries.append(dict(position="", jersey="", player=chunk))
    return entries


def split_columns(line: str) -> list[str]:
    """Split a Game Book table row into its printed columns.

    The Game Book lays its tables out with a wide gap between columns and a
    narrow gap inside a cell, so a run of two or more spaces is a column
    boundary.  A row whose columns do not separate is returned as one column,
    which the caller records as an unreadable row rather than guessing.
    """
    parts = [p.strip() for p in re.split(r"\s{2,}", line.strip()) if p.strip()]
    return parts


def parse_lineup_rows(block: str) -> list[dict]:
    """The starting-lineup rows of a Game Book, with their printed column.

    The page prints four columns: the visiting club's offence, the visiting
    club's defence, the home club's offence and the home club's defence.  A row
    that does not yield four columns is returned with ``column=-1`` and is
    reported as unreadable; it is never redistributed by guesswork.
    """
    rows: list[dict] = []
    for line in block.splitlines():
        line = line.strip()
        if not line or re.match(r"^(Offense|Defense|Special Teams)\b", line):
            continue
        # Preferred path: four pos-jersey-name cells found left to right, in
        # printed order.  It survives the padded position-to-jersey gaps the
        # real PDF prints, which the wide-gap split cannot separate.
        cells = list(_CELL_TOLERANT.finditer(line))
        if len(cells) == 4:
            for idx, m in enumerate(cells):
                rows.append(dict(column=idx, position=m.group("pos"), jersey=m.group("num"),
                                 player=m.group("name"), raw=m.group(0).strip()))
            continue
        cols = split_columns(line)
        if len(cols) != 4:
            rows.append(dict(column=-1, position="", jersey="", player="", raw=line))
            continue
        for idx, col in enumerate(cols):
            m = _CELL.match(col.strip())
            if not m:
                rows.append(dict(column=idx, position="", jersey="", player="", raw=col.strip()))
                continue
            rows.append(dict(column=idx, position=m.group("pos"), jersey=m.group("num"),
                             player=m.group("name"), raw=col.strip()))
    return rows


def parse_two_column_roster(block: str) -> dict:
    """A Game Book block printed as two club columns.

    The Game Book prints one club's list on the left of the page and the
    other's on the right.  A line that yields two printed columns is split
    between them.  A line that yields only one column cannot be attributed
    to a club from the document alone, so it is returned under ``unattributed``
    and is never assigned to a club by guesswork.
    """
    left: list[dict] = []
    right: list[dict] = []
    unattributed: list[dict] = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        cols = split_columns(line)
        if len(cols) >= 2:
            left.extend(parse_roster_entries(cols[0]))
            right.extend(parse_roster_entries(cols[-1]))
        elif len(cols) == 1:
            unattributed.extend(parse_roster_entries(cols[0]))
    return dict(left=left, right=right, unattributed=unattributed)
