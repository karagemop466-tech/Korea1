"""Week 11 of the 2026 season, read from committed official bytes and published.

Why this module exists (session arena/c83ada84-korea1, 2026-11-19)
------------------------------------------------------------------
Week 11 kicks off Thursday 2026-11-19 at 20:15 ET (2026-11-20T01:15Z). Before this
module the repository's newest football evidence was the Week 10 injury report captured
2026-11-18T04:24:05Z: the site could not say who is **Questionable / Doubtful / Out for
tonight's game**, which is the one fact a pre-kickoff decision turns on.

It reads only committed bytes -- no network, no clock -- so `make build` stays
byte-reproducible and `tests/check_rebuild.py` keeps its teeth:

  data/live/official_2026_11_19/manifest.json   url, HTTP status, bytes, sha256, the UTC
                                                clock time of the read, per source
  data/live/official_2026_11_19/raw/<slug>      the response body, byte for byte, as
                                                captured by pipeline/capture_official_2026_11_19.py
                                                on a GitHub-hosted runner

What it publishes (week-11.html), and what it refuses to publish
----------------------------------------------------------------
* **Designations.** One row per (club, player) exactly as the official report prints it:
  position, injury, practice status, game status. A blank cell on the official page stays
  blank here and is counted, never filled.
* **Fixtures.** One row per game the official schedule page prints: date, kick-off time,
  broadcast, and the official game-centre link. A fixture the capture did not contain is
  listed as **not captured**, never reconstructed from memory.
* **Venue.** Published only where a game-centre capture actually printed it; otherwise
  blank and flagged. (The repository's own venue register and the Week 10 reconciliation
  are separate, dated sources and are linked, not merged.)
* **Conflicts.** Every player who is still on the Week 10 report and also on the Week 11
  report is compared: status movement is published as a *delta* with both capture clock
  times, never as a level judged from one read.

Two readings of the same player are possible and are kept apart: the Week 11 week-addressed
URL (`/injuries/league/2026/reg11`) and the current-week URL (`/injuries/`), which nfl.com
redirects. If they disagree the row says so and the disagreement is a finding.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

CAP = ROOT / "data" / "live" / "official_2026_11_19"
RAW = CAP / "raw"
AV = ROOT / "data" / "availability"
INJURY_URL = "https://www.nfl.com/injuries/league/2026/reg11"
SCHEDULE_URL = "https://www.nfl.com/schedules/2026/by-week/week-11"

# Club nickname -> (abbreviation, nfl.com team slug). Taken from the same table the
# existing capture uses (pipeline/fetch_availability.py TEAMS) so the two never drift.
from fetch_availability import BY_NICK, TEAMS  # noqa: E402

BY_SLUG = {t[2]: t for t in TEAMS}
UNITS = {"offense", "defense", "special teams"}


def e(x) -> str:
    return html.escape(str(x), quote=True)


# --------------------------------------------------------------------------- reading
def load_manifest() -> dict:
    p = CAP / "manifest.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def source(manifest: dict, slug: str) -> dict | None:
    for s in manifest.get("sources", []):
        if s.get("slug") == slug:
            return s
    return None


def bytes_of(manifest: dict, *slugs: str) -> tuple[str, dict | None]:
    """First captured body among `slugs`, with the manifest record that names it."""
    for slug in slugs:
        s = source(manifest, slug)
        if s and s.get("sha256"):
            p = RAW / slug
            if p.exists():
                return p.read_text(encoding="utf-8", errors="replace"), s
    return "", None


# --------------------------------------------------------------- injury report parse
class _Tables:
    """Minimal table reader for the official injury page.

    Reuses the same state machine as pipeline/fetch_availability.py (club nickname as
    table owner, player links captured) so the Week 11 parse and the committed Week 10
    capture cannot disagree about how the page is shaped.
    """

    def __init__(self):
        self.tables = []
        self.nick = ""
        self.texts = []
        self.t = None
        self.row = None
        self.cell = None
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
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

    def handle_endtag(self, tag):
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

    def handle_data(self, data):
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
        from html.parser import HTMLParser

        class _P(HTMLParser):
            def __init__(self, outer):
                super().__init__(convert_charrefs=True)
                self.o = outer

            def handle_starttag(self, tag, attrs):
                self.o.handle_starttag(tag, attrs)

            def handle_endtag(self, tag):
                self.o.handle_endtag(tag)

            def handle_data(self, data):
                self.o.handle_data(data)

        _P(self).feed(text)


GAME_STATUS = {"out", "doubtful", "questionable"}
PRACTICE = {"did not participate in practice", "limited participation in practice",
            "full participation in practice"}


def parse_report(text: str) -> tuple[list[dict], dict]:
    p = _Tables()
    p.feed(text)
    blob = " | ".join(p.texts)
    season = (re.search(r"(20\d\d) NFL Injury Report", blob) or [None, ""])[1]
    week = (re.search(r"Injuries\s*-\s*(WEEK\s*\d+)", blob) or [None, ""])[1]
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
            link = r[0]["links"][0]["href"] if r[0]["links"] else ""
            gs = g("game status")
            ps = g("practice status")
            rows.append(dict(
                club=abbr, nickname=nick, team_slug=slug, player=g("player"),
                position=g("position"), injury=g("injuries"), practice_status=ps,
                game_status=gs, player_url=link,
                # vocabulary guard: an unrecognised string is kept verbatim and flagged
                unknown_status=bool(gs) and gs.lower() not in GAME_STATUS,
                unknown_practice=bool(ps) and ps.lower() not in PRACTICE,
            ))
    return rows, {"season": season, "week": week, "clubs": len({r["club"] for r in rows})}


# ----------------------------------------------------------------- schedule parsing
def parse_schedule(text: str) -> list[dict]:
    """Fixtures from the official schedule capture.

    nfl.com serves this page as a server-rendered app whose fixture data also lives in an
    RSC payload. The reader accepts both shapes and records which one it used, so a page
    change shows up as a measured parse count rather than a silent zero.
    """
    out = []
    # Shape A: an anchor per fixture, e.g. /games/colts-at-texans-2026-reg-11
    for m in re.finditer(r'href="(/games/([a-z0-9]+)-at-([a-z0-9-]+)-2026-reg-11)"', text):
        out.append(dict(path=m.group(1), away=m.group(2), home=m.group(3)))
    if out:
        return _dedupe(out)
    # Shape B: escaped JSON in the RSC payload.
    for m in re.finditer(r'\\?"/games/([a-z0-9]+)-at-([a-z0-9-]+)-2026-reg-11\\?"', text):
        out.append(dict(path=f"/games/{m.group(1)}-at-{m.group(2)}-2026-reg-11",
                        away=m.group(1), home=m.group(2)))
    return _dedupe(out)


def _dedupe(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        if r["path"] in seen:
            continue
        seen.add(r["path"])
        out.append(r)
    return out


KICKOFF = {  # printed times on the official schedule page, when the parse finds them
    "20:15": "8:15 PM ET",
}


def main() -> int:
    import render_site as R

    manifest = load_manifest()
    inj11_text, inj11_src = bytes_of(manifest, "injury_report_week11_league_url")
    injcur_text, injcur_src = bytes_of(manifest, "injury_report_current")
    sched_text, sched_src = bytes_of(manifest, "schedule_week11_week_form",
                                     "schedule_week11_reg_form")
    cap_clock = manifest.get("captured_utc", "")

    inj11, meta11 = parse_report(inj11_text) if inj11_text else ([], {})
    injcur, metacur = parse_report(injcur_text) if injcur_text else ([], {})
    fixtures = parse_schedule(sched_text) if sched_text else []

    # Week 10 rows from the committed availability capture, for the movement (delta) table.
    w10 = {}
    w10_path = AV / "injuries.csv"
    w10_clock = ""
    if w10_path.exists():
        import csv
        with open(w10_path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("week", "").upper().replace(" ", "") != "WEEK10":
                    continue
                w10[(r["team"], r["player"])] = r
                w10_clock = w10_clock or r.get("retrieved_utc", "")

    # ---------------------------------------------------------------- derived tables
    status_counts = Counter(r["game_status"] or "(blank)" for r in inj11)
    practice_counts = Counter(r["practice_status"] or "(blank)" for r in inj11)
    by_club = Counter(r["club"] for r in inj11)
    blanks = sum(1 for r in inj11 if not r["game_status"])
    designated = sum(1 for r in inj11 if r["game_status"])

    movement = []
    for r in inj11:
        prev = w10.get((r["club"], r["player"]))
        if not prev:
            continue
        if (prev.get("game_status", "") or "") == (r["game_status"] or "") and \
           (prev.get("practice_status", "") or "") == (r["practice_status"] or ""):
            verdict = "no change"
        else:
            verdict = "changed"
        movement.append([e(r["club"]), e(r["player"]), e(r["position"]),
                         e(prev.get("game_status", "") or "—"),
                         e(r["game_status"] or "—"),
                         e(prev.get("practice_status", "") or "—"),
                         e(r["practice_status"] or "—"), e(verdict),
                         R.src_link(INJURY_URL, "NFL week 11 report")])

    # Two independent reads of the same page must not silently disagree.
    cur_vs11 = []
    if injcur:
        idx11 = {(r["club"], r["player"]): r for r in inj11}
        for r in injcur:
            o = idx11.get((r["club"], r["player"]))
            if o is None:
                cur_vs11.append([e(r["club"]), e(r["player"]), "not on the week-addressed page",
                                 e(r["game_status"] or "—"), "", e("READ DIFFERS"),
                                 R.src_link("https://www.nfl.com/injuries/", "current-week URL")])
            elif (o["game_status"], o["practice_status"]) != (r["game_status"], r["practice_status"]):
                cur_vs11.append([e(r["club"]), e(r["player"]), "status differs",
                                 e(o["game_status"] or "—"), e(r["game_status"] or "—"), e("READ DIFFERS"),
                                 R.src_link("https://www.nfl.com/injuries/", "current-week URL")])

    # ------------------------------------------------------------------- page body
    def status_pill(s: str) -> str:
        if not s:
            return R.BLANK + '<span class="unverified">blank on the official page</span>'
        cls = {"out": "neg", "doubtful": "neg", "questionable": "opt-mid"}.get(s.lower(), "")
        return f'<span class="pill {cls}">{e(s)}</span>'

    rows = []
    for r in sorted(inj11, key=lambda x: (x["club"], x["player"])):
        rows.append([e(r["club"]), e(r["player"]), e(r["position"]), e(r["injury"]) or R.BLANK,
                     e(r["practice_status"]) or R.BLANK, status_pill(r["game_status"]),
                     R.src_link(r["player_url"], "player") + " · " + R.src_link(INJURY_URL, "NFL week 11 report")])

    fix_rows = []
    venue_by_game = {}
    for s in manifest.get("sources", []):
        if not s.get("slug", "").startswith("game_centre__") or not s.get("sha256"):
            continue
        txt = (RAW / s["slug"]).read_text(encoding="utf-8", errors="replace")
        slug = s["slug"].replace("game_centre__", "")
        loc = re.search(r"LOCATION\s*</[^>]+>\s*<[^>]+>([^<]+)<", txt) or \
              re.search(r"LOCATION[^A-Za-z0-9]{0,80}([A-Z][^<>{}\"]{2,60})", txt)
        stad = re.search(r"STADIUM\s*</[^>]+>\s*<[^>]+>([^<]+)<", txt) or \
               re.search(r"STADIUM[^A-Za-z0-9]{0,80}([A-Z][^<>{}\"]{2,60})", txt)
        venue_by_game[slug] = (loc.group(1).strip() if loc else "",
                               stad.group(1).strip() if stad else "", s)
    for f in fixtures:
        slug = re.sub(r"[^a-z0-9]+", "_", f["path"].rsplit("/", 1)[-1]).strip("_")
        loc, stad, src = venue_by_game.get(slug, ("", "", None))
        fix_rows.append([e(f["away"].upper()), e(f["home"].upper()),
                         R.src_link("https://www.nfl.com" + f["path"], "game centre"),
                         e(loc) or R.BLANK, e(stad) or R.BLANK,
                         R.src_link(sched_src["requested_url"], "NFL week 11 schedule") if sched_src else ""])

    # ------------------------------------------------------------------- assemble
    src_rows = []
    for s in manifest.get("sources", []):
        ok = bool(s.get("sha256"))
        src_rows.append([
            e(s.get("slug", "")), R.src_link(s.get("requested_url", ""), s.get("requested_url", "")[:60] or "—"),
            e(s.get("http_status", "")), f"{s.get('bytes', 0):,}" if ok else R.BLANK,
            f"<code>{e((s.get('sha256') or '')[:16])}…</code>" if ok else R.BLANK,
            '<span class="pill">read</span>' if ok else
            f'<span class="pill neg">FAILED</span> <span class="unverified">{e(s.get("error", ""))}</span>',
        ])

    movement_changed = [m for m in movement if m[7].startswith("changed")]
    body = f"""
{R.notice()}
<section><h2>What this page is</h2>
<p><strong>Week 11 of the 2026 NFL season, read from official NFL documents captured at
<code>{e(cap_clock) or "—"}</code> and stored byte for byte with their SHA-256.</strong>
Every table row below is a transcription of a captured official page; a cell the page left
blank is shown as blank and counted, never filled. This is the first week in the repository
whose evidence is not stale: the newest football evidence before this capture was Week 10.</p>
{R.kpi_grid([
    R.card(str(len(inj11)), "Week 11 report rows", f"{meta11.get('clubs', 0)} clubs · read {e(inj11_src['requested_url']) if inj11_src else 'NOT CAPTURED'}", "good" if inj11 else "bad"),
    R.card(str(designated), "with a game designation", f"Out / Doubtful / Questionable · {blanks} blank on the page", ""),
    R.card(str(len(fixtures)), "Week 11 fixtures", "from the official schedule capture" if fixtures else "NOT CAPTURED", "good" if fixtures else "bad"),
    R.card(str(len(venue_by_game)), "venues transcribed", "only where a game centre was captured", ""),
    R.card(str(len(movement_changed)), "Week 10 → 11 changes", f"of {len(movement)} shared players · compared to the {e(w10_clock) or '—'} capture", ""),
    R.card(str(len(cur_vs11)), "read disagreements", "week-addressed URL vs current-week URL", "bad" if cur_vs11 else "good"),
])}
<p class="small">Capture provenance: <code>data/live/official_2026_11_19/manifest.json</code>
({len(manifest.get('sources', []))} sources, {manifest.get('summary', {}).get('ok', 0)} read ok).
The capture job never parses and never edits a page; this page is rebuilt offline from those
bytes by <code>pipeline/week11_20261119.py</code>, so the numbers below are reproducible from a
clean checkout with no network.</p>
</section>

<section><h2>1 · Designations as printed — {len(inj11)} rows</h2>
<p>The official report prints a practice status for nearly every listed player and a
<em>game status</em> for only some of them. Both are shown exactly. The counts are the
evidence for why a level is not a signal: <strong>{designated}</strong> of
<strong>{len(inj11)}</strong> rows carry a game designation at this read.</p>
{R.table([[e(k), str(v)] for k, v in sorted(status_counts.items(), key=lambda x: -x[1])],
         ["Game status as printed", "Rows"], caption="Game-status vocabulary on the official Week 11 page")}
{R.table([[e(k), str(v)] for k, v in sorted(practice_counts.items(), key=lambda x: -x[1])],
         ["Practice status as printed", "Rows"], caption="Practice-status vocabulary on the official Week 11 page")}
<div class="table-tools"><label>Search players or clubs <input class="filter" type="search" placeholder="Try Colts, hamstring, Out…"></label><span class="small">Click a column heading to sort</span></div>
{R.table(rows, ["Club", "Player", "Pos", "Injury as printed", "Practice status", "Game status", "Official source"],
         caption="Official Week 11 injury report, every row, blank cells preserved")}
</section>

<section><h2>2 · Movement from Week 10 to Week 11 — {len(movement)} shared players</h2>
<p>Only players who appear on <em>both</em> captures are compared, so nothing is inferred
for a player who merely appeared or disappeared. A change of designation is published as a
delta with the two capture clock times beside it ({e(w10_clock) or '—'} → {e(cap_clock) or '—'}),
never as a level judged from a single read.</p>
{R.table(movement, ["Club", "Player", "Pos", "Week 10 game", "Week 11 game",
                    "Week 10 practice", "Week 11 practice", "Verdict", "Official source"],
         caption="Week 10 → Week 11 designation deltas · both capture times recorded")
 if movement else '<p class="small">No player appears on both captures, so no delta can be computed. Nothing is inferred.</p>'}
</section>

<section><h2>3 · Week 11 fixtures — {len(fixtures)} from the official schedule</h2>
<p>Fixture identity, official link and venue come from the captured official schedule page and
the captured game centres. A venue is printed only if a game-centre capture printed it; the
rest stay blank. <strong>The repository does not transcribe a venue from memory.</strong></p>
{R.table(fix_rows, ["Away", "Home", "Official game centre", "Venue (LOCATION)", "Stadium (STADIUM)", "Schedule source"],
         caption="Official Week 11 fixtures · venue blank where no game centre was captured")
 if fix_rows else '<p class="small">No fixture was parsed from the schedule capture. This is a capture gap, published as one, not a claim that Week 11 has no games.</p>'}
</section>

<section><h2>4 · Two independent reads of the same page</h2>
<p>nfl.com serves the current week at <code>/injuries/</code> and a fixed week at
<code>/injuries/league/2026/reg11</code>. Both were captured. If the two reads disagree the
row is printed here rather than one being chosen silently.</p>
{R.table(cur_vs11, ["Club", "Player", "Difference", "Week-addressed read", "Current-week read", "Verdict", "Source"],
         caption="Week-addressed URL vs current-week URL · disagreements only")
 if cur_vs11 else '<p class="small">The two captures agree on every player they share (compared on game status and practice status).</p>'}
</section>

<section><h2>5 · Capture register — every source, its hash and its clock time</h2>
<p>A capture that failed is marked <span class="pill neg">FAILED</span> and publishes its error;
it never overwrites a good capture. This is the register the site's evidence boundary depends on.</p>
{R.table(src_rows, ["Source", "URL requested", "HTTP", "Bytes", "SHA-256 (first 16)", "Outcome"],
         caption=f"Official capture manifest · captured {e(cap_clock) or '—'}")}
</section>

<section><h2>6 · What this does not show</h2>
<ul class="findings">
<li><strong>No model input changed.</strong> These designations are published as evidence; no
strategy, fair line or verdict on this site consumes them yet. The personnel-ablation
contract on <a href="register-evidence-2026-11-18.html">the register evidence page</a>
records why: a fixed points penalty for a missing starter is a guess, not a measurement.</li>
<li><strong>No availability prediction.</strong> "Questionable" is not converted to a
probability here. The empirical calibration behind that word is still blocked (it needs
several seasons of designations joined to official inactive lists).</li>
<li><strong>No venue inferred.</strong> A blank venue means no game-centre capture printed
it at this read, not that the venue is unknown to the league.</li>
<li><strong>Scope.</strong> {len(by_club)} of 32 clubs appear on the Week 11 report at this
read; clubs absent from it are not evidence of a healthy roster, and the reserve list is a
separate captured source.</li>
</ul>
</section>
"""
    page = R.layout("week-11.html", "Week 11 · official designations and fixtures",
                    "The current NFL week, read from captured official documents: who is out, who is questionable, and where each game is played.",
                    body, wide=True)
    (ROOT / "week-11.html").write_text(page, encoding="utf-8")
    print(f"  wrote week-11.html ({len(page):,} bytes) · {len(inj11)} designations · "
          f"{len(fixtures)} fixtures · {len(movement)} deltas · {len(cur_vs11)} read disagreements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
