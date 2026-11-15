"""CB4 (arena/c79b2684-korea1) - official reserve-list capture (NFL.com transactions, reserve list).

Why: a player on injured reserve, the reserve/COVID list or the physically-unable-to-perform list is
absent from the weekly injury report. "Not listed" therefore cannot mean "available". This module
captures the official monthly reserve-list pages so an absence can be explained.

Source (official, NFL.com):
  https://www.nfl.com/transactions/league/reserve-list/<year>/<month>
  The current and the previous calendar month are fetched on every run, because a move made at the
  end of one month is listed on that month's page (e.g. the Ravens' early-November moves).

Fail-loud rules (the drift alarm)
  * The table header must be exactly From | To | Date | Name | Position | Transaction. Any other
    header exits non-zero and the committed snapshot is left untouched.
  * Every data row must have six cells, a club link, a player link and a MM/DD date. A row that does
    not parse makes the run fail; it is never published as a blank.
  * An HTTP failure or a page with no table fails the run.

Outputs (committed, one folder per UTC capture, nothing overwritten)
  data/availability/reserve/history/<UTC>/reserve_list.csv
  data/availability/reserve/history/<UTC>/manifest.json   (URL, HTTP status, bytes, sha256, rows)
  data/availability/reserve/latest.csv                    (copy of the newest capture)
The raw HTML is not committed (size); its sha256 is, and the URL reproduces the page.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_availability import BY_SLUG, http_get  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "availability" / "reserve"
HEADER = ["From", "To", "Date", "Name", "Position", "Transaction"]
COLS = ["capture_utc", "month", "date", "team", "player", "position", "transaction",
        "player_url", "team_url", "source_url", "page_sha256"]
TEAM_RE = re.compile(r"/teams/([a-z0-9-]+)/?")
DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})$")


class _Cell:
    __slots__ = ("text", "links", "th")

    def __init__(self, th: bool):
        self.text, self.links, self.th = "", [], th


class TableReader(HTMLParser):
    """Collects every <table> as a list of rows; each cell keeps its text and its links."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[_Cell]]] = []
        self._table = None
        self._row = None
        self._cell = None
        self._href = None
        self._link_text = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = _Cell(tag == "th")
            self._row.append(self._cell)
        elif tag == "a" and self._cell is not None:
            self._href = a.get("href", "")
            self._link_text = ""

    def handle_endtag(self, tag):
        if tag == "a" and self._cell is not None and self._href is not None:
            self._cell.links.append((" ".join(self._link_text.split()), self._href))
            self._href = None
        elif tag in ("td", "th") and self._cell is not None:
            self._cell.text = " ".join(self._cell.text.split())
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.text += data
        if self._href is not None:
            self._link_text += data


def parse_reserve_page(html_text: str, month: str, capture_utc: str, source_url: str,
                       page_sha256: str) -> tuple[list[dict], str]:
    """Return (rows, error). error is non-empty when the page cannot be trusted."""
    rd = TableReader()
    rd.feed(html_text)
    year, mm = (int(x) for x in month.split("-"))
    table = None
    for t in rd.tables:
        if not t:
            continue
        head = [c.text.strip() for c in t[0]]
        if head == HEADER:
            table = t
            break
    if table is None:
        return [], f"no table with header {HEADER} on {source_url}"
    rows, errors = [], []
    for r in table[1:]:
        if not r:
            continue
        if len(r) != 6:
            errors.append(f"row has {len(r)} cells, expected 6")
            continue
        frm, _to, date_c, name_c, pos_c, trn_c = r
        m = DATE_RE.match(date_c.text.strip())
        if not m or not name_c.links:
            errors.append(f"unparseable row: date={date_c.text!r} name links={len(name_c.links)}")
            continue
        team_link = next((h for _, h in frm.links if TEAM_RE.search(h)), "")
        slug = TEAM_RE.search(team_link).group(1) if team_link else ""
        if slug not in BY_SLUG:
            errors.append(f"unknown club slug {slug!r}")
            continue
        player_text, player_href = name_c.links[0]
        rows.append(dict(
            capture_utc=capture_utc, month=month,
            date=f"{year:04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}",
            team=BY_SLUG[slug][0], player=player_text, position=pos_c.text.strip(),
            transaction=trn_c.text.strip(), player_url=player_href, team_url=team_link,
            source_url=source_url, page_sha256=page_sha256))
    if errors:
        return rows, "; ".join(errors[:5]) + (f" (+{len(errors) - 5} more)" if len(errors) > 5 else "")
    if mm < 1 or mm > 12:
        return rows, "bad month"
    return rows, ""


def _months(today: dt.date) -> list[str]:
    cur = f"{today.year:04d}-{today.month:02d}"
    prev_m = today.month - 1 or 12
    prev_y = today.year - (1 if today.month == 1 else 0)
    return [f"{prev_y:04d}-{prev_m:02d}", cur]


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    folder = OUT / "history" / stamp.replace(":", "")
    manifest = {"retrieved_utc": stamp, "runner": "GitHub Actions (.github/workflows/reserve-list.yml)",
                "pages": []}
    all_rows, failed = [], []
    for month in _months(now.date()):
        y, m = month.split("-")
        url = f"https://www.nfl.com/transactions/league/reserve-list/{int(y)}/{int(m)}"
        status, body, err = http_get(url)
        sha = hashlib.sha256(body).hexdigest() if body else ""
        rows, perr = (parse_reserve_page(body.decode("utf-8", "replace"), month, stamp, url, sha)
                      if body else ([], "empty response"))
        page_err = err or perr
        manifest["pages"].append(dict(month=month, url=url, http_status=status, bytes=len(body),
                                      sha256=sha, rows=len(rows), error=page_err))
        print(f"{month} status={status} bytes={len(body)} rows={len(rows)} {page_err}")
        if page_err:
            failed.append(f"{month}: {page_err}")
        else:
            all_rows += rows
    if failed:
        print("reserve list NOT written (snapshot untouched):\n  " + "\n  ".join(failed))
        return 2
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "reserve_list.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(all_rows)
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with (OUT / "latest.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(all_rows)
    print(f"wrote {len(all_rows)} reserve-list rows to {folder.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
