"""T14a — fetch the official availability inputs (injury report + club depth charts).

Sources (both official; nothing else is read):

  * https://www.nfl.com/injuries/            the league's official weekly injury report
  * https://www.<club site>/team/depth-chart each club's own published depth chart

Where this runs
---------------
The Arena build sandbox cannot reach nfl.com or the club sites from the shell (egress
allowlist), so this module is executed by `.github/workflows/availability.yml` on a
GitHub-hosted runner, on a schedule, with no manual input. `make build` never calls it:
the build only *reads* the committed snapshot in `data/availability/`, so the site build
stays deterministic and offline.

Rules
-----
* Nothing is inferred. A cell that is empty on the official page is written empty.
* Every row carries the URL of the official page it was read from and the retrieval time.
* Every response is SHA-256 hashed; HTTP status, byte count and parsed-row count are
  written to `manifest.json`. A page that fails to download or parses to zero rows is
  recorded as a failure and published on the Flagged-for-Review page — the previous
  snapshot for that source is kept, and its older retrieval time stays on its rows.
* The fetch aborts without touching the snapshot if the injury report itself cannot be
  parsed, so a broken upstream page can never blank the published table.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "availability"
INJURY_URL = "https://www.nfl.com/injuries/"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")

# abbr, nickname (as printed on nfl.com/injuries), nfl.com team slug, official club site
TEAMS = [
    ("ARI", "Cardinals", "arizona-cardinals", "www.azcardinals.com"),
    ("ATL", "Falcons", "atlanta-falcons", "www.atlantafalcons.com"),
    ("BAL", "Ravens", "baltimore-ravens", "www.baltimoreravens.com"),
    ("BUF", "Bills", "buffalo-bills", "www.buffalobills.com"),
    ("CAR", "Panthers", "carolina-panthers", "www.panthers.com"),
    ("CHI", "Bears", "chicago-bears", "www.chicagobears.com"),
    ("CIN", "Bengals", "cincinnati-bengals", "www.bengals.com"),
    ("CLE", "Browns", "cleveland-browns", "www.clevelandbrowns.com"),
    ("DAL", "Cowboys", "dallas-cowboys", "www.dallascowboys.com"),
    ("DEN", "Broncos", "denver-broncos", "www.denverbroncos.com"),
    ("DET", "Lions", "detroit-lions", "www.detroitlions.com"),
    ("GB", "Packers", "green-bay-packers", "www.packers.com"),
    ("HOU", "Texans", "houston-texans", "www.houstontexans.com"),
    ("IND", "Colts", "indianapolis-colts", "www.colts.com"),
    ("JAX", "Jaguars", "jacksonville-jaguars", "www.jaguars.com"),
    ("KC", "Chiefs", "kansas-city-chiefs", "www.chiefs.com"),
    ("LV", "Raiders", "las-vegas-raiders", "www.raiders.com"),
    ("LAC", "Chargers", "los-angeles-chargers", "www.chargers.com"),
    ("LA", "Rams", "los-angeles-rams", "www.therams.com"),
    ("MIA", "Dolphins", "miami-dolphins", "www.miamidolphins.com"),
    ("MIN", "Vikings", "minnesota-vikings", "www.vikings.com"),
    ("NE", "Patriots", "new-england-patriots", "www.patriots.com"),
    ("NO", "Saints", "new-orleans-saints", "www.neworleanssaints.com"),
    ("NYG", "Giants", "new-york-giants", "www.giants.com"),
    ("NYJ", "Jets", "new-york-jets", "www.newyorkjets.com"),
    ("PHI", "Eagles", "philadelphia-eagles", "www.philadelphiaeagles.com"),
    ("PIT", "Steelers", "pittsburgh-steelers", "www.steelers.com"),
    ("SF", "49ers", "san-francisco-49ers", "www.49ers.com"),
    ("SEA", "Seahawks", "seattle-seahawks", "www.seahawks.com"),
    ("TB", "Buccaneers", "tampa-bay-buccaneers", "www.buccaneers.com"),
    ("TEN", "Titans", "tennessee-titans", "www.tennesseetitans.com"),
    ("WAS", "Commanders", "washington-commanders", "www.commanders.com"),
]
BY_NICK = {t[1]: t for t in TEAMS}
BY_SLUG = {t[2]: t for t in TEAMS}
UNITS = {"offense": "Offense", "defense": "Defense", "special teams": "Special Teams"}

INJ_COLS = ["season", "week", "team", "club", "opponent", "player", "position", "injury",
            "practice_status", "game_status", "player_url", "source_url", "retrieved_utc"]
DEPTH_COLS = ["team", "club", "unit", "slot", "position", "depth_rank", "player",
              "player_url", "source_url", "retrieved_utc"]


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
        except Exception as ex:  # noqa: BLE001 - recorded, never swallowed silently
            err = f"{type(ex).__name__}: {ex}"
        time.sleep(2 + 3 * i)
    return 0, b"", err


class Tables(HTMLParser):
    """Generic table reader that also remembers the page context around each table."""

    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.tables = []            # dicts: nick, unit, teams(list of slugs), rows
        self.nick = ""              # last text node that is exactly a club nickname
        self.unit = ""              # last text node that is exactly Offense/Defense/Special Teams
        self.team_slugs = []        # nfl.com /teams/<slug>/ links seen so far, in order
        self.texts = []             # headline text nodes (for season / week)
        self.t = None; self.row = None; self.cell = None
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "a" and a.get("href"):
            m = re.search(r"/teams/([a-z0-9-]+)/?$", a["href"])
            if m and m.group(1) in BY_SLUG and self.t is None:
                if not self.team_slugs or self.team_slugs[-1] != m.group(1):
                    self.team_slugs.append(m.group(1))
            if self.cell is not None:
                href = a["href"]
                if href.startswith("/"):
                    href = self.base + href
                self.cell["links"].append({"href": href, "text": ""})
        if tag == "table":
            self.t = {"nick": self.nick, "unit": self.unit,
                      "teams": self.team_slugs[-2:], "rows": []}
        elif tag == "tr" and self.t is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = {"text": "", "links": [], "th": tag == "th"}

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag in ("td", "th") and self.cell is not None:
            self.cell["text"] = " ".join(self.cell["text"].split())
            self.row.append(self.cell); self.cell = None
        elif tag == "tr" and self.row is not None and self.t is not None:
            if self.row:
                self.t["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.t is not None:
            self.tables.append(self.t); self.t = None

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
        if s.lower() in UNITS:
            self.unit = UNITS[s.lower()]
        if len(s) < 120:
            self.texts.append(s)


def parse_injuries(html_text: str, retrieved: str) -> tuple[list[dict], dict]:
    p = Tables("https://www.nfl.com"); p.feed(html_text)
    blob = " | ".join(p.texts)
    season = (re.search(r"(20\d\d) NFL Injury Report", blob) or [None, ""])[1]
    week = (re.search(r"Injuries\s*-\s*([A-Za-z0-9 ]*?WEEK\s*\d+|[A-Z][A-Za-z ]+?)\s*\|", blob) or [None, ""])[1]
    rows = []
    for t in p.tables:
        head = [c["text"].strip().lower() for c in t["rows"][0]] if t["rows"] else []
        if head[:2] != ["player", "position"] or t["nick"] not in BY_NICK:
            continue
        abbr, nick, slug, _ = BY_NICK[t["nick"]]
        opp = [BY_SLUG[s][0] for s in t["teams"] if s != slug] if slug in t["teams"] else []
        idx = {h: i for i, h in enumerate(head)}
        for r in t["rows"][1:]:
            if len(r) < len(head) or r[0]["th"]:
                continue
            g = lambda k: r[idx[k]]["text"].strip() if k in idx else ""  # noqa: E731
            link = r[0]["links"][0]["href"] if r[0]["links"] else ""
            rows.append(dict(season=season, week=week.strip(), team=abbr, club=nick,
                             opponent=opp[0] if len(opp) == 1 else "",
                             player=g("player"), position=g("position"), injury=g("injuries"),
                             practice_status=g("practice status"), game_status=g("game status"),
                             player_url=link, source_url=INJURY_URL, retrieved_utc=retrieved))
    return rows, {"season": season, "week": week.strip()}


def parse_depth(html_text: str, team, url: str, retrieved: str) -> list[dict]:
    abbr, nick, _, host = team
    p = Tables("https://" + host); p.feed(html_text)
    rows, slot = [], 0
    for t in p.tables:
        if not t["unit"]:
            continue
        for r in t["rows"]:
            if len(r) < 2 or r[0]["th"] and all(c["th"] for c in r):
                continue
            pos = r[0]["text"].strip()
            if not pos or len(pos) > 8 or pos.lower() in ("pos", "position"):
                continue
            slot += 1
            for rank, c in enumerate(r[1:], 1):
                names = [(l["text"], l["href"]) for l in c["links"] if l["text"].strip()] or \
                        ([(c["text"], "")] if c["text"].strip() else [])
                for name, href in names:
                    rows.append(dict(team=abbr, club=nick, unit=t["unit"], slot=slot, position=pos,
                                     depth_rank=rank, player=" ".join(name.split()),
                                     player_url=href, source_url=url, retrieved_utc=retrieved))
    return rows


def write_csv(path: Path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n"); w.writeheader(); w.writerows(rows)


def read_csv(path: Path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    retrieved = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {"retrieved_utc": retrieved, "runner": "GitHub Actions (.github/workflows/availability.yml)",
                "sources": []}

    status, body, err = http_get(INJURY_URL)
    text = body.decode("utf-8", "replace")
    inj, meta = parse_injuries(text, retrieved) if body else ([], {})
    manifest["sources"].append(dict(kind="injury_report", team="NFL", url=INJURY_URL, http_status=status,
                                    bytes=len(body), sha256=hashlib.sha256(body).hexdigest() if body else "",
                                    rows=len(inj), error=err or ("" if inj else "parsed 0 rows")))
    if not inj:
        print(f"injury report not parsed (status={status}, bytes={len(body)}, err={err}); snapshot left untouched")
        if "--debug" in sys.argv and body:
            (OUT / "debug_injuries.html").write_bytes(body[:400_000])
        return 2
    manifest.update(meta)

    old_depth = read_csv(OUT / "depth_charts.csv")
    depth = []
    for team in TEAMS:
        url = f"https://{team[3]}/team/depth-chart"
        status, body, err = http_get(url)
        rows = parse_depth(body.decode("utf-8", "replace"), team, url, retrieved) if body else []
        kept = False
        if not rows:  # keep the previous snapshot of this club, with its older timestamp
            rows = [r for r in old_depth if r["team"] == team[0]]
            kept = bool(rows)
            err = err or "parsed 0 rows"
            if "--debug" in sys.argv and body:
                (OUT / f"debug_depth_{team[0]}.html").write_bytes(body[:400_000])
        else:
            err = ""
        depth += rows
        manifest["sources"].append(dict(kind="depth_chart", team=team[0], url=url, http_status=status,
                                        bytes=len(body), sha256=hashlib.sha256(body).hexdigest() if body else "",
                                        rows=0 if err else len(rows), error=err,
                                        previous_snapshot_kept=kept))
        print(f"{team[0]:4s} depth rows={len(rows):3d} status={status} {err}")
        time.sleep(0.5)

    write_csv(OUT / "injuries.csv", INJ_COLS, inj)
    write_csv(OUT / "depth_charts.csv", DEPTH_COLS, depth)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    day = OUT / "history" / now.strftime("%Y-%m-%d")
    write_csv(day / "injuries.csv", INJ_COLS, inj)
    write_csv(day / "depth_charts.csv", DEPTH_COLS, depth)
    (day / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    ok = sum(1 for s in manifest["sources"] if s["kind"] == "depth_chart" and not s["error"])
    print(f"injury rows={len(inj)} ({meta}); depth charts parsed for {ok}/32 clubs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
