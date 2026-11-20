"""Checks for the Baltimore QB recheck evidence (task BQ1, session arena/83a6b711-korea1).

These tests read only committed files. They do not touch the network. They check that the
evidence folder is well formed, that every claim row carries an official source, and that the
reserve-list window claim is supported by the committed captures.
"""

import csv
import glob
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVID = ROOT / "data" / "live" / "ravens_qb_recheck_2026_11_20"
CLAIMS = EVID / "claims.csv"
PAGE = EVID / "reserve_page_nov_2026.csv"
LATEST = ROOT / "data" / "availability" / "reserve" / "latest.csv"
HISTORY = sorted(glob.glob(str(ROOT / "data" / "availability" / "reserve" / "history" / "*" / "reserve_list.csv")))

ALLOWED_VERDICTS = {
    "CONTRADICTED_BY_OFFICIAL",
    "CONFIRMED_BY_OFFICIAL_NEWS",
    "MATCHES_REPO",
    "NOT_IN_OFFICIAL_PAGE_AS_READ",
    "UNVERIFIED",
    "UNVERIFIABLE_IDENTIFIER",
    "INCONSISTENT_OFFICIAL_TEXT",
}
OFFICIAL_DOMAINS = ("https://www.nfl.com/", "https://www.baltimoreravens.com/")


def _rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_claims_schema_and_sources():
    rows = _rows(CLAIMS)
    assert rows, "claims.csv is empty"
    required = {"claim_id", "claim_under_test", "source_url", "official_text_quoted",
                "read_basis", "repo_comparison", "verdict", "note"}
    assert required <= set(rows[0].keys())
    for r in rows:
        assert all(r[k].strip() for k in required if k != "note"), f"blank cell in {r['claim_id']}"
        assert r["verdict"] in ALLOWED_VERDICTS, f"unknown verdict in {r['claim_id']}"
        if r["verdict"] != "UNVERIFIABLE_IDENTIFIER":
            assert r["source_url"].startswith(OFFICIAL_DOMAINS), f"non-official source in {r['claim_id']}"


def test_depth_claim_is_contradicted_and_repo_matches_official_chart():
    rows = {r["claim_id"]: r for r in _rows(CLAIMS)}
    assert rows["BQ-01"]["verdict"] == "CONTRADICTED_BY_OFFICIAL"
    assert rows["BQ-02"]["verdict"] == "MATCHES_REPO"
    # The committed capture carries the same three QBs in rank order as the official chart read.
    depth = _rows(ROOT / "data" / "availability" / "depth_charts.csv")
    qbs = sorted((r for r in depth if r["team"] == "BAL" and r["position"] == "QB" and r["unit"] == "Offense"),
                 key=lambda r: int(r["depth_rank"]))
    assert [r["player"] for r in qbs][:3] == ["Jacoby Brissett", "Joe Fagnano", "Kedon Slovis"]


def test_page_rows_are_nov_window_with_official_source():
    rows = _rows(PAGE)
    assert len(rows) == 25, "the official November page read holds 25 rows"
    dates = sorted(r["page_date"] for r in rows)
    assert dates[0] == "11/12" and dates[-1] == "11/19"
    assert all(r["source_url"] == "https://www.nfl.com/transactions/league/reserve-list/2026/11" for r in rows)
    names = [r["player"] for r in rows]
    assert "Lamar Jackson" not in names and "Tyler Huntley" not in names


def test_page_window_overlaps_committed_capture_only_by_roll():
    page = {(f"2026-11-{r['page_date'][3:]}", r["team"], r["player"], r["transaction"]) for r in _rows(PAGE)}
    latest = {(r["date"], r["team"], r["player"], r["transaction"])
              for r in _rows(LATEST) if r["month"] == "2026-11"}
    assert len(page) == 25 and len(latest) == 25
    only_page = page - latest
    only_repo = latest - page
    assert only_page == {("2026-11-19", "LA", "Puka Nacua", "Reserve/Suspended By Commissioner-Less than One Year")}
    assert only_repo == {("2026-11-10", "LA", "Jordan Whittington", "Reserve/Injured")}
    assert len(page & latest) == 24


def test_every_committed_snapshot_is_a_25_row_per_month_window():
    assert HISTORY, "no reserve history found"
    for path in HISTORY:
        counts = Counter(r["month"] for r in _rows(path))
        assert counts == Counter({"2026-10": 25, "2026-11": 25}), f"{path} is not a 25-row window"


def test_identifier_row_records_label_only_status():
    # The brief's labels appear in registers but no committed file defines them; the row must say so.
    row = {r["claim_id"]: r for r in _rows(CLAIMS)}["BQ-09"]
    assert row["verdict"] == "UNVERIFIABLE_IDENTIFIER"
    assert "only as labels" in row["repo_comparison"] + row["note"] or "no committed file maps" in row["repo_comparison"]
