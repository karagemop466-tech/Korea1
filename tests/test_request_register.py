"""CR1 tests (session arena/f84bc1d7-korea1): the request register must be complete,
sourced, and free of invented values.

Mutation-sensitive checks:
* every request item REQ-01..REQ-81 present exactly once, in request order;
* status in the closed set;
* every row carries an official/primary source URL (verify_site.ALLOW hosts only);
* every live-check id resolves to a committed CR2 spot-check row;
* the rendered page's tbody row count equals the CSV row count;
* the summary cards equal the CSV status counts;
* the register's ground-truth cells agree with the repository data they cite
  (Lions Out rows, Houston 0 rows, Green Bay jersey stripping, 31 depth clubs).
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
from verify_site import ALLOW  # noqa: E402

CSV = ROOT / "data" / "integration" / "request_register.csv"
HTML = ROOT / "request-register.html"
SPOT = ROOT / "data" / "live" / "request_spotcheck_2026_11_18" / "spotcheck.csv"

STATUSES = {"built", "partly built", "not built", "blocked (owner decision)",
            "rejected as requested", "process · executed"}
VERDICTS = {"VERIFIED LIVE", "REFUTED LIVE", "READ LIVE PARTIAL"}


class RowCounter(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = 0
        self.in_body = False

    def handle_starttag(self, tag, attrs):
        if tag == "tbody":
            self.in_body = True
        elif tag == "tr" and self.in_body:
            self.rows += 1

    def handle_endtag(self, tag):
        if tag == "tbody":
            self.in_body = False


def test_register_rows_complete_unique_and_ordered():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    assert len(d) == 81
    ids = d.req_id.tolist()
    assert ids == [f"REQ-{i:02d}" for i in range(1, 82)]


def test_status_closed_set_and_counts_match_cards():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    assert set(d.status) <= STATUSES
    counts = d.status.value_counts().to_dict()
    html = HTML.read_text(encoding="utf-8")
    combined = counts.get("not built", 0) + counts.get("blocked (owner decision)", 0)
    for status in ("built", "partly built", "rejected as requested", "process · executed"):
        n = counts.get(status, 0)
        if n:
            assert f">{n}</div>" in html or f">{n} " in html, f"card for {status} ({n}) missing"
    if combined:
        assert f">{combined}</div>" in html or f">{combined} " in html, \
            f"combined not-built/blocked card ({combined}) missing"


def test_every_row_has_official_source_and_nonempty_gate_and_clears():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    for r in d.itertuples(index=False):
        host = re.sub(r"^https://([^/]+)/.*$", r"\1", r.source_url)
        assert host in ALLOW, f"{r.req_id} source host {host} not in official allow-list"
        assert r.gate.strip(), f"{r.req_id} has no blocking gate"
        assert r.clears.strip(), f"{r.req_id} has no clearing number/condition"
        assert r.published.strip(), f"{r.req_id} has no evidence cell"


def test_live_check_ids_resolve_to_spotcheck_rows():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    s = pd.read_csv(SPOT, dtype=str, keep_default_na=False)
    assert set(s.verdict) <= VERDICTS
    known = set(s.check_id)
    for r in d.itertuples(index=False):
        if r.live_check:
            assert r.live_check in known, f"{r.req_id} cites unknown spot-check {r.live_check}"


def test_html_row_count_matches_csv():
    c = RowCounter()
    c.feed(HTML.read_text(encoding="utf-8"))
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    # two tables: the register (81 rows) + the spot-check table (9 rows)
    s = pd.read_csv(SPOT, dtype=str, keep_default_na=False)
    assert c.rows == len(d) + len(s)


def test_no_blank_or_token_cells_in_register():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    for r in d.itertuples(index=False):
        for name in ("request", "status", "gate", "clears", "published", "source_url"):
            v = getattr(r, name).strip()
            assert v, f"{r.req_id}.{name} blank"
            assert not re.search(r"(?<![\w/])(nan|NaN|None|inf|-inf)(?![\w/-])", v), \
                f"{r.req_id}.{name} leaks a token: {v[:40]}"


def test_ground_truth_cells_match_the_repository():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False).set_index("req_id")
    # Pinned to the capture the register's cells were written against: the rolling
    # injuries/depth files are rewritten by the scheduled fetch, and the three Lions
    # rows this test names are Week-10 facts (F-2026-11-19-03 defect class).
    inj = pd.read_csv(ROOT / "data" / "availability" / "history" / "2026-11-18" / "injuries.csv",
                      dtype=str, keep_default_na=False)
    for name in ("Kerby Joseph", "Cade Mays", "D.J. Reed"):
        row = inj[inj.player == name]
        assert len(row) == 1 and row.iloc[0].game_status == "Out", name
    assert "Out" in d.loc["REQ-48", "clears"] or "S1" in d.loc["REQ-48", "live_check"]
    dc = pd.read_csv(ROOT / "data" / "availability" / "history" / "2026-11-18" / "depth_charts.csv", dtype=str, keep_default_na=False)
    assert len(dc[dc.team == "HOU"]) == 0
    assert "0 rows" in d.loc["REQ-32", "published"]
    gb = dc[dc.team == "GB"]
    assert len(gb) > 0 and (gb.player_raw.str.contains(r"\d")).any()
    assert dc.team.nunique() == 31
    assert "31/32" in d.loc["REQ-13", "published"] or "31" in d.loc["REQ-43", "published"]
    # refuted claim stays refuted (verdict lives in the CR2 spot-check file)
    spot = pd.read_csv(SPOT, dtype=str, keep_default_na=False).set_index("check_id")
    assert d.loc["REQ-46", "live_check"] == "S8"
    assert spot.loc["S8", "verdict"] == "REFUTED LIVE"
