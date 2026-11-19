"""Week 11 of the 2026 season, read from committed official bytes and published.

Why this module exists (session arena/c83ada84-korea1, 2026-11-19)
------------------------------------------------------------------
Week 11 kicks off Thursday 2026-11-19 at 20:15 ET (2026-11-20T01:15Z). Before this
module the repository's newest football evidence was the Week 10 injury report captured
2026-11-18T04:24:05Z, so the site could not say who is Out / Doubtful / Questionable for
the games being played tonight -- the one fact a pre-kickoff decision turns on.

It reads only committed bytes -- no network, no clock -- so `make build` stays
byte-reproducible and `tests/check_rebuild.py` keeps its teeth:

  data/live/official_2026_11_19/manifest.json   url, HTTP status, bytes, sha256 and the
                                                UTC clock time of the read, per source
  data/live/official_2026_11_19/raw/<slug>      the response body, byte for byte, stored
                                                by pipeline/capture_official_2026_11_19.py
                                                on a GitHub-hosted runner

What it publishes (week-11.html), and what it refuses to publish
----------------------------------------------------------------
* **Designations.** One row per (club, player) exactly as the official report prints it:
  position, injury, practice status, game status. A blank cell on the official page stays
  blank here and is counted, never filled.
* **Fixtures.** One row per game the official schedule page prints, with the day, date,
  kick-off time and broadcaster the page itself states, and the official game-centre link.
* **Venue.** Taken from the `Game Info` block of the captured game centre (LOCATION /
  STADIUM). Where no game centre was captured the cell is blank and says so.
* **Movement.** Every player on both the Week 10 capture and the Week 11 report is
  compared, and the change is published as a *delta* with both capture clock times --
  never as a level judged from a single read.

Two readings of the same page are kept apart: the week-addressed URL
(`/injuries/league/2026/reg11`) and the current-week URL (`/injuries/`), which nfl.com
redirects. If they disagree, the row says so.
"""
from __future__ import annotations

import csv
import html
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

CAP = ROOT / "data" / "live" / "official_2026_11_19"
RAW = CAP / "raw"
AV = ROOT / "data" / "availability"
INJURY_URL = "https://www.nfl.com/injuries/league/2026/reg11"
CURRENT_URL = "https://www.nfl.com/injuries/"
SCHEDULE_URL = "https://www.nfl.com/schedules/2026/by-week/week-11"

# Club nickname -> (abbreviation, nfl.com slug, club site). Reused from the module that
# owns the club table so the two can never drift.
from fetch_availability import BY_NICK, TEAMS  # noqa: E402

GAME_STATUS = {"out", "doubtful", "questionable"}
PRACTICE = {"did not participate in practice", "limited participation in practice",
            "full participation in practice"}
# The official report's three practice words, in the order the league uses them.
PRACTICE_SHORT = {"did not participate in practice": "DNP",
                  "limited participation in practice": "LP",
                  "full participation in practice": "FP"}


def e(x) -> str:
    return html.escape(str(x), quote=True)


# --------------------------------------------------------------------------- reading
def load_manifest() -> dict:
    p = CAP / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def source(manifest: dict, slug: str) -> dict | None:
    for s in manifest.get("sources", []):
        if s.get("slug") == slug:
            return s
    return None


def read_body(slug: str) -> str:
    p = RAW / slug
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def bytes_of(manifest: dict, *slugs: str) -> tuple[str, dict | None]:
    for slug in slugs:
        s = source(manifest, slug)
        if s and s.get("sha256"):
            body = read_body(slug)
            if body:
                return body, s
    return "", None


# --------------------------------------------------------------- injury report parse
class InjuryTables:
    """Table reader for the official injury page.

    The same state machine as pipeline/fetch_availability.py (club nickname owns the
    table, player links are captured), so the Week 11 parse and the committed Week 10
    capture cannot disagree about how the page is shaped.
    """

    def __init__(self):
        self.tables, self.texts = [], []
        self.nick = ""
        self.t = self.row = self.cell = None
        self.skip = 0
        outer = self

        class _P(HTMLParser):
            def handle_starttag(self, tag, attrs):
                outer._start(tag, dict(attrs))

            def handle_endtag(self, tag):
                outer._end(tag)

            def handle_data(self, data):
                outer._data(data)

        self._parser = _P(convert_charrefs=True)

    def _start(self, tag, a):
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "a" and a.get("href") and self.cell is not None:
            href = a["href"]
            if href.startswith("/"):
                href = "https://www.nfl.com" + href
            self.cell["links"].append({"href": href, "text": ""})
        if tag == "table":
            self.t = {"nick": self.nick, "rows": []}
        elif tag == "tr" and self.t is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = {"text": "", "links": [], "th": tag == "th"}

    def _end(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag in ("td", "th") and self.cell is not None:
            self.cell["text"] = " ".join(self.cell["text"].split())
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None and self.t is not None:
            if self.row:
                self.t["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.t is not None:
            self.tables.append(self.t)
            self.t = None

    def _data(self, data):
        if self.skip:
            return
        if self.cell is not None:
            self.cell["text"] += data
            if self.cell["links"]:
                self.cell["links"][-1]["text"] += data
            return
        s = " ".join(data.split())
        if not s:
            return
        if s in BY_NICK:
            self.nick = s
        if len(s) < 200:
            self.texts.append(s)

    def feed(self, text: str):
        self._parser.feed(text)
        self._parser.close()
        return self


def parse_report(text: str) -> tuple[list[dict], dict]:
    p = InjuryTables().feed(text)
    blob = " | ".join(p.texts)
    season = (re.search(r"(20\d\d) NFL Injury Report", blob) or [None, ""])[1]
    week = " ".join((re.search(r"Injuries\s*-\s*(WEEK\s*\d+)", blob) or [None, ""])[1].split())
    rows = []
    for t in p.tables:
        if not t["rows"]:
            continue
        head = [c["text"].strip().lower() for c in t["rows"][0]]
        if head[:2] != ["player", "position"] or t["nick"] not in BY_NICK:
            continue
        abbr, nick, slug, _ = BY_NICK[t["nick"]]
        idx = {h: i for i, h in enumerate(head)}
        for r in t["rows"][1:]:
            if len(r) < len(head) or r[0]["th"]:
                continue
            g = lambda k: r[idx[k]]["text"].strip() if k in idx and idx[k] < len(r) else ""  # noqa: E731
            gs, ps = g("game status"), g("practice status")
            rows.append(dict(
                club=abbr, nickname=nick, team_slug=slug, player=g("player"),
                position=g("position"), injury=g("injuries"), practice_status=ps,
                game_status=gs, player_url=(r[0]["links"][0]["href"] if r[0]["links"] else ""),
                # vocabulary guard: an unrecognised word is kept verbatim and flagged
                unknown_status=bool(gs) and gs.lower() not in GAME_STATUS,
                unknown_practice=bool(ps) and ps.lower() not in PRACTICE,
            ))
    return rows, {"season": season, "week": week, "clubs": len({r["club"] for r in rows})}


# ----------------------------------------------------------------- schedule parsing
FIXTURE_LINE = re.compile(
    r"(?P<away>[A-Za-z0-9.]+) at (?P<home>[A-Za-z0-9.]+), (?P<day>[A-Z][a-z]+)day, "
    r"(?P<date>[A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?), (?P<time>\d{1,2}:\d{2} [AP]M), "
    r"(?P<tv>[A-Z0-9+]+)")
GAME_PATH = re.compile(r'href="(/games/(?P<slug>[a-z0-9]+)-at-(?P<home2>[a-z0-9-]+)-2026-reg-11)"')


def parse_fixtures(text: str) -> tuple[list[dict], str]:
    """Fixtures in page order, from the anchor's own printed label.

    The official page prints the full line in a screen-reader span
    ("Colts at Texans, Thursday, November 19th, 8:15 PM, PRIME") immediately inside the
    anchor that links the game centre, so the label and the link are read together and
    belong to each other by construction. Shape B (an escaped-JSON payload) is used only
    if Shape A yields nothing, and the shape used is returned so a page change shows up
    as a measured difference rather than a silent zero.
    """
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="(/games/[a-z0-9-]+-2026-reg-11)"[^>]*>\s*<span[^>]*>([^<]+)</span>',
                         text):
        line = FIXTURE_LINE.search(m.group(2))
        if not line or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        out.append(dict(path=m.group(1), label=" ".join(m.group(2).split()), **line.groupdict()))
    if out:
        return out, "anchors with printed labels"
    # Shape B: an escaped-JSON payload that still carries the label text.
    for m in re.finditer(r'\\"(/games/[a-z0-9-]+-2026-reg-11)\\"', text):
        if m.group(1) in seen:
            continue
        seen.add(m.group(1))
        out.append(dict(path=m.group(1), label="", away="", home="", day="", date="",
                        time="", tv=""))
    return out, "escaped JSON paths only (labels not printed)" if out else "no fixture found"


# ------------------------------------------------------------------ game-centre venue
INFO_CARD = re.compile(r'data-testid="info-card-item-value-([a-z]+)"[^>]*>([^<]+)<')


def parse_venue(text: str) -> dict:
    vals = {k: " ".join(v.split()) for k, v in INFO_CARD.findall(text)}
    return {"location": vals.get("location", ""), "stadium": vals.get("stadium", "")}


def game_slug(path: str) -> str:
    return "game_centre__" + re.sub(r"[^a-z0-9]+", "_", path.rsplit("/", 1)[-1]).strip("_")


# ------------------------------------------------------------------------ week 10 ref
def week10_rows() -> tuple[dict, str]:
    out, clock = {}, ""
    p = AV / "injuries.csv"
    if not p.exists():
        return out, clock
    with open(p, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if (r.get("week") or "").upper().replace(" ", "") != "WEEK10":
                continue
            out[(r["team"], r["player"])] = r
            clock = clock or r.get("retrieved_utc", "")
    return out, clock


# ----------------------------------------------------------------------------- render
def build_page() -> str:
    import render_site as R

    manifest = load_manifest()
    capt = manifest.get("captured_utc", "")
    inj11_text, inj11_src = bytes_of(manifest, "injury_report_week11_league_url")
    injcur_text, injcur_src = bytes_of(manifest, "injury_report_current")
    sched_text, sched_src = bytes_of(manifest, "schedule_week11_week_form",
                                     "schedule_week11_reg_form")

    inj11, meta = parse_report(inj11_text) if inj11_text else ([], {})
    injcur, metacur = parse_report(injcur_text) if injcur_text else ([], {})
    fixtures, shape = parse_fixtures(sched_text) if sched_text else ([], "not captured")
    w10, w10_clock = week10_rows()

    status_counts = Counter(r["game_status"] or "(blank)" for r in inj11)
    practice_counts = Counter(r["practice_status"] or "(blank)" for r in inj11)
    designated = sum(1 for r in inj11 if r["game_status"])
    blanks = len(inj11) - designated
    clubs = sorted({r["club"] for r in inj11})
    flagged_vocab = [r for r in inj11 if r["unknown_status"] or r["unknown_practice"]]

    # venue per fixture, only from a captured game centre
    venues = {}
    for f in fixtures:
        slug = game_slug(f["path"])
        s = source(manifest, slug)
        if s and s.get("sha256"):
            venues[f["path"]] = (parse_venue(read_body(slug)), s)
    missing_venue = [f for f in fixtures if f["path"] not in venues]

    # movement week 10 -> week 11
    movement = []
    for r in inj11:
        prev = w10.get((r["club"], r["player"]))
        if not prev:
            continue
        p_gs = (prev.get("game_status") or "").strip()
        p_ps = (prev.get("practice_status") or "").strip()
        changed = (p_gs != (r["game_status"] or "")) or (p_ps != (r["practice_status"] or ""))
        movement.append(dict(club=r["club"], player=r["player"], position=r["position"],
                             gs0=p_gs, gs1=r["game_status"], ps0=p_ps, ps1=r["practice_status"],
                             changed=changed, url=r["player_url"]))
    changed = [m for m in movement if m["changed"]]

    def _dir(m: dict) -> dict:
        """Classify a designation move without calling it a recovery or a setback.

        The official report is a *weekly reporting instrument*: a designation present on
        Week 10 and absent on Week 11 is a change of reporting, not proof the player is
        healthy. So the move is described in the report's own direction words and is
        never described as recovered / cleared / worsened.
        """
        g0, g1 = (m["gs0"] or "").lower(), (m["gs1"] or "").lower()
        if g0 and not g1:
            return dict(kind="designation not carried forward",
                        say="carried a game designation on Week 10; none printed on Week 11")
        if not g0 and g1:
            return dict(kind="designation newly printed",
                        say="no game designation on Week 10; one is printed on Week 11")
        sev = {"out": 3, "doubtful": 2, "questionable": 1, "": 0}
        if g0 and g1 and sev.get(g1, 9) > sev.get(g0, 9):
            return dict(kind="more restrictive", say=f"{m['gs0']} → {m['gs1']}")
        if g0 and g1 and sev.get(g1, 9) < sev.get(g0, 9):
            return dict(kind="less restrictive", say=f"{m['gs0']} → {m['gs1']}")
        order = {"did not participate in practice": 0, "limited participation in practice": 1,
                 "full participation in practice": 2}
        p0, p1 = order.get((m["ps0"] or "").lower(), 9), order.get((m["ps1"] or "").lower(), 9)
        if p0 < 9 and p1 < 9 and p1 > p0:
            return dict(kind="practice participation increased", say=f"{m['ps0']} → {m['ps1']}")
        if p0 < 9 and p1 < 9 and p1 < p0:
            return dict(kind="practice participation reduced", say=f"{m['ps0']} → {m['ps1']}")
        return dict(kind="changed", say="see the two reads")

    for m in movement:
        m.update(_dir(m) if m["changed"] else dict(kind="no change", say="identical on both reads"))
    direction_counts = Counter(m["kind"] for m in movement)

    # the two reads of the same page
    disagreements = []
    if injcur:
        idx = {(r["club"], r["player"]): r for r in inj11}
        for r in injcur:
            o = idx.get((r["club"], r["player"]))
            if o is None:
                disagreements.append((r["club"], r["player"], "only on the current-week read",
                                      "", r["game_status"] or "—"))
            elif (o["game_status"], o["practice_status"]) != (r["game_status"], r["practice_status"]):
                disagreements.append((r["club"], r["player"], "designation differs",
                                      o["game_status"] or "—", r["game_status"] or "—"))

    def pill(s: str, kind: str = "game") -> str:
        if not s:
            return R.BLANK + '<span class="unverified">blank on the official page</span>'
        cls = {"out": "neg", "doubtful": "neg", "questionable": "opt-mid"}.get(s.lower(), "")
        return f'<span class="pill {cls}">{e(s)}</span>'

    def practice(s: str) -> str:
        if not s:
            return R.BLANK
        short = PRACTICE_SHORT.get(s.lower(), "")
        return f'{e(s)}' + (f' <span class="small">({short})</span>' if short else
                            ' <span class="pill neg">unexpected wording</span>')

    design_rows = [[e(r["club"]), e(r["player"]), e(r["position"]), e(r["injury"]) or R.BLANK,
                    practice(r["practice_status"]), pill(r["game_status"]),
                    R.src_link(r["player_url"], "player") + " · " + R.src_link(INJURY_URL, "report")]
                   for r in sorted(inj11, key=lambda x: (x["club"], x["player"]))]

    fix_rows = []
    for f in fixtures:
        v, s = venues.get(f["path"], ({}, None))
        fix_rows.append([
            e(f["away"] or "—"), e(f["home"] or "—"), e(f["day"]),
            e((f["date"] or "").rstrip(",.")), e(f["time"]), e(f["tv"]),
            e(v.get("location", "")) or R.BLANK, e(v.get("stadium", "")) or R.BLANK,
            R.src_link("https://www.nfl.com" + f["path"], "game centre") + " · " +
            R.src_link(SCHEDULE_URL, "schedule")])

    move_rows = [[e(m["club"]), e(m["player"]), e(m["position"]),
                  pill(m["gs0"]) if m["gs0"] else R.BLANK, pill(m["gs1"]),
                  practice(m["ps0"]) if m["ps0"] else R.BLANK, practice(m["ps1"]),
                  (f'<span class="pill neg">{e(m["kind"])}</span><br><span class="small">{e(m["say"])}</span>'
                   if m["changed"] else '<span class="pill">no change</span>'),
                  R.src_link(INJURY_URL, "report")] for m in movement]

    src_rows = []
    for s in manifest.get("sources", []):
        ok = bool(s.get("sha256"))
        src_rows.append([
            e(s.get("slug", "")),
            R.src_link(s.get("requested_url", ""), s.get("requested_url", "")[:64] or "—"),
            e(s.get("http_status", "")), f"{s.get('bytes', 0):,}" if ok else R.BLANK,
            f"<code>{e((s.get('sha256') or '')[:16])}…</code>" if ok else R.BLANK,
            '<span class="pill">read</span>' if ok else
            f'<span class="pill neg">FAILED</span> <span class="unverified">{e(s.get("error", ""))}</span>'])

    summary = manifest.get("summary", {})
    cards = [
        R.card(str(len(inj11)), "Week 11 report rows",
               f"{meta.get('clubs', 0)} clubs · {'read ' + capt if inj11 else 'NOT CAPTURED'}",
               "good" if inj11 else "bad"),
        R.card(str(designated), "carry a game designation",
               f"Out / Doubtful / Questionable · {blanks} blank on the page", ""),
        R.card(str(len(fixtures)), "Week 11 fixtures",
               "from the official schedule capture" if fixtures else "NOT CAPTURED",
               "good" if fixtures else "bad"),
        R.card(f"{len(venues)}/{len(fixtures)}" if fixtures else "0",
               "venues transcribed", "only from a captured game centre", ""),
        R.card(str(len(changed)), "Week 10 → 11 changes",
               f"of {len(movement)} players on both captures", ""),
        R.card(str(len(disagreements)), "read disagreements",
               "week-addressed vs current-week URL", "bad" if disagreements else "good"),
    ]

    body = f"""
{R.notice()}
<section><h2>Week 11, from official captures — not from memory</h2>
<p><strong>Every number on this page is parsed from official NFL documents captured at
<code>{e(capt) or "—"}</code> and stored byte for byte with their SHA-256.</strong> A cell the
official page left blank is shown blank and counted; nothing is inferred, converted to a
probability or carried over from an earlier week. The capture job only downloads and stores
bytes; this page is rebuilt offline from them, so a clean checkout reproduces every row with
no network.</p>
{R.kpi_grid(cards)}
<p class="small">Provenance: <code>data/live/official_2026_11_19/manifest.json</code> —
{summary.get('ok', 0)} of {len(manifest.get('sources', []))} sources read with a hash.
Capture is triggered by a push to a single workflow file, because this repository's token
cannot create a <code>workflow_dispatch</code> event (HTTP 403, measured 2026-11-19).</p>
</section>

<section><h2>1 · Every designation, as printed — {len(inj11)} rows, {len(clubs)} clubs</h2>
<p>The league prints a practice status for most listed players and a <em>game status</em> for
few of them. Both are published verbatim. That gap is the finding: <strong>{designated}</strong>
of <strong>{len(inj11)}</strong> rows carry a game designation at this read, so a single
"Questionable" is not a level a model can consume without calibration.</p>
{R.table([[e(k), str(v), R.src_link(INJURY_URL, "NFL week 11 report")]
          for k, v in sorted(status_counts.items(), key=lambda x: -x[1])],
         ["Game status as printed", "Rows", "Official source"],
         caption="Game-status vocabulary on the official Week 11 report")}
{R.table([[e(k), str(v), R.src_link(INJURY_URL, "NFL week 11 report")]
          for k, v in sorted(practice_counts.items(), key=lambda x: -x[1])],
         ["Practice status as printed", "Rows", "Official source"],
         caption="Practice-status vocabulary on the official Week 11 report")}
<div class="table-tools"><label>Search players, clubs or injuries
<input class="filter" type="search" placeholder="Try Colts, hamstring, Out…"></label>
<span class="small">Click a column heading to sort</span></div>
{R.table(design_rows, ["Club", "Player", "Pos", "Injury as printed", "Practice status",
                       "Game status", "Official source"],
         caption="Official Week 11 injury report · every row · blank cells preserved")}
</section>

<section><h2>2 · Week 10 → Week 11 movement — {len(changed)} of {len(movement)} shared players changed</h2>
{R.table([[e(k), str(v), R.src_link(INJURY_URL, "NFL week 11 report")]
          for k, v in direction_counts.most_common()],
         ["Direction of the reported move", "Players", "Official source"],
         caption="What actually moved between the two dated reads")}
<p class="small"><strong>Read this as reporting, not recovery.</strong> The official report is a
weekly instrument: a designation printed on Week 10 and absent on Week 11 shows the
designation was not carried forward — the report does not state, and this page does not
claim, that the player is healthy. Of the moves above,
<strong>{direction_counts.get("designation not carried forward", 0)}</strong> are a Week 10
designation that is simply absent on Week 11. That is why the count of "changes" is large and
why a level taken from one week cannot be used as a signal.</p>
<p>Only players on <em>both</em> captures are compared, so nothing is inferred for a player who
appeared or disappeared. The two capture clock times are <code>{e(w10_clock) or "—"}</code>
(Week 10) and <code>{e(capt) or "—"}</code> (Week 11). A designation that moved is a delta, not
a level: the direction is only meaningful against a dated earlier read, which is why both are
printed.</p>
{R.table(move_rows, ["Club", "Player", "Pos", "Week 10 game", "Week 11 game",
                     "Week 10 practice", "Week 11 practice", "Verdict", "Official source"],
         caption="Designation deltas between two dated official reads")
 if move_rows else '<p class="small">No player appears on both captures, so no delta can be computed. Nothing is inferred.</p>'}
</section>

<section><h2>3 · The 13 Week 11 fixtures — kick-off, broadcaster and venue</h2>
<p>Day, date, time and broadcaster are the label the official schedule page prints on each
fixture card. Venue is the <code>Game Info</code> block of that fixture's official game centre.
The parse used: <strong>{e(shape)}</strong>.{"" if not missing_venue else
f" <strong>{len(missing_venue)} fixtures have no captured game centre</strong>, so their venue is blank."}</p>
{R.table(fix_rows, ["Away", "Home", "Day", "Date", "Kick-off", "TV", "Venue (LOCATION)",
                    "Stadium", "Official source"],
         caption="Official Week 11 fixtures · venue only where a game centre was captured")
 if fix_rows else '<p class="small">No fixture was parsed from the schedule capture. That is a capture gap, published as one — not a claim that Week 11 has no games.</p>'}
</section>

<section><h2>4 · Two independent reads of the same report</h2>
<p>nfl.com serves the live week at <code>/injuries/</code> and a fixed week at
<code>/injuries/league/2026/reg11</code>. Both were captured in the same run. Disagreements are
printed here instead of one read being chosen silently.</p>
{R.table([[e(a), e(b), e(c), e(d) or "—", e(f) or "—", R.src_link(CURRENT_URL, "current-week read") + " · " + R.src_link(INJURY_URL, "week-addressed read")]
          for a, b, c, d, f in disagreements],
         ["Club", "Player", "Difference", "Week-addressed", "Current-week", "Sources"],
         caption="Week-addressed URL vs current-week URL · disagreements only")
 if disagreements else '<p class="small">The two captures agree on every player they share, on both game status and practice status.</p>'}
</section>

<section><h2>5 · Capture register — every source, its hash and its clock time</h2>
<p>A failed capture is published as <span class="pill neg">FAILED</span> with its error and never
overwrites a good one. This register is what the rest of the page depends on.</p>
{R.table(src_rows, ["Source", "URL requested", "HTTP", "Bytes", "SHA-256 (first 16)", "Outcome"],
         caption=f"Official capture manifest · captured {e(capt) or '—'}")}
</section>

<section><h2>6 · What this page does not claim</h2>
<ul class="findings">
<li><strong>No model consumes these rows yet.</strong> They are published as evidence. A fixed
points penalty for a missing starter is a guess; the personnel-ablation contract on
<a href="register-evidence-2026-11-18.html">the register evidence page</a> records why the
ablation, not a penalty, is the test.</li>
<li><strong>No probability for "Questionable".</strong> The empirical calibration behind that
word is still blocked; it needs several seasons of designations joined to official inactive
lists, which this repository does not hold.</li>
<li><strong>No inferred depth order.</strong> The Week 11 report names a player's designation,
not his rank. Depth comes only from each club's own published chart, with its own limits.</li>
<li><strong>{len(clubs)} of 32 clubs</strong> appear on this report at this read. A club that is
absent is <em>not</em> evidence of a healthy roster — byes, the reserve list and the weekly
reporting rules all produce absence.</li>
<li><strong>No venue from memory.</strong> {len(missing_venue)} fixture(s) lack a captured game
centre, so their venue cells are blank rather than filled from a remembered stadium.</li>
{"" if not flagged_vocab else f"<li><strong>{len(flagged_vocab)} row(s) print a status word this page does not recognise.</strong> They are kept verbatim and flagged rather than normalised.</li>"}
</ul>
</section>
"""
    return R.layout("week-11.html", "Week 11 · designations, fixtures and venue",
                    "The current NFL week read from captured official documents: who is out, who is questionable, where and when each game is played.",
                    body, wide=True)


def main() -> int:
    page = build_page()
    (ROOT / "week-11.html").write_text(page, encoding="utf-8")
    print(f"  wrote week-11.html ({len(page):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
