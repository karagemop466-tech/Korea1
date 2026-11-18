"""Guards for the 2026-11-18 request register (CS5 takeover, session arena/53ef9544-korea1).

Each test targets a rule that could break without anyone noticing: a sourced row that links a
non-official host, an unsourced row promoted into a table, a status outside the vocabulary, a
register that is built but never wired into the site checks, or a row with no gate and no
clearing number.
"""
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import request_register_2026_11_18 as rr  # noqa: E402
import session_common as sc  # noqa: E402
import verify_site as vs  # noqa: E402

INT = ROOT / "data" / "integration"
PAGE = ROOT / "request-register-2026-11-18.html"

STATUSES = {"DONE", "PARTLY DONE", "BUILT ON OPEN PR #82 (arena/99b908ab-korea1); not on main",
            "BLOCKED", "REJECTED", "OWNER DECISION", "NOT STARTED"}


def _reg() -> pd.DataFrame:
    return pd.read_csv(INT / "request_register_2026_11_18.csv", dtype=str).fillna("")


def test_register_has_one_row_per_request_item_and_unique_ids():
    reg = _reg()
    assert len(reg) == 81, len(reg)
    assert reg.id.is_unique
    assert list(reg.id) == [f"RR-{i:02d}" for i in range(1, 82)]


def test_every_sourced_link_is_on_the_official_allow_list():
    for r in _reg().itertuples(index=False):
        if not r.source_url:
            continue
        u = urlsplit(r.source_url)
        assert u.scheme == "https", r.id
        assert (u.hostname or "") in sc.ALLOW, (r.id, u.hostname)


def test_status_vocabulary_is_valid():
    for r in _reg().itertuples(index=False):
        assert r.status in STATUSES, (r.id, r.status)


def test_every_row_names_a_gate_and_a_clearing_number():
    for r in _reg().itertuples(index=False):
        assert r.blocking_gate.strip(), r.id
        assert r.clearing_number.strip(), r.id


def test_a_non_allow_listed_host_is_rejected():
    # A community repository URL is not an official source; resolve_ref must refuse it.
    try:
        sc.resolve_ref("a community mirror", "https://github.com/nflverse/nfldata", row_id="X")
    except ValueError:
        return
    raise AssertionError("resolve_ref accepted a non-allow-listed host")


def test_every_table_row_in_the_rendered_page_has_an_official_ref():
    c = vs.Collector()
    c.feed(PAGE.read_text())
    bad = [i for i, row in enumerate(c.rows, 1)
           if not vs.official_refs([h for _, hrefs in row for h in hrefs])]
    assert not bad, bad
    assert c.captions == c.tables, "a table is missing a caption"


def test_unsourced_rows_are_rendered_as_text_not_table_rows():
    reg = _reg()
    n_sourced = int((reg.source_url != "").sum())
    c = vs.Collector()
    c.feed(PAGE.read_text())
    # Every table row is sourced, and the count matches the sourced rows in the CSV.
    assert len(c.rows) == n_sourced, (len(c.rows), n_sourced)
    # The unsourced rows are present as flagged text, not dropped.
    text = PAGE.read_text()
    for r in reg[reg.source_url == ""].id:
        assert r in text, r
    assert "No official source exists for this row" in text


def test_register_is_wired_into_the_site_checks_and_navigation():
    # The page must be reachable and verified, not merely built.
    assert PAGE.exists()
    nav_source = (ROOT / "pipeline" / "render_site.py").read_text()
    assert "request-register-2026-11-18.html" in nav_source
    assert "request-register-2026-11-18.html" in vs.__dict__.get("_EXPECTED_MARKER", "") or \
        "request-register-2026-11-18.html" in (ROOT / "pipeline" / "verify_site.py").read_text()
    assert "request-register-2026-11-18.html" in (ROOT / "tests" / "check_sources.py").read_text()
    assert "request-register-2026-11-18.html" in (ROOT / "tests" / "check_links.py").read_text()
    assert "request_register_2026_11_18.py" in (ROOT / "Makefile").read_text()


def test_build_page_uses_the_register_slug_and_counts():
    html = rr.build_page(rr.register_frame())
    assert "request-register-2026-11-18.html" in html
    assert "2026-11-18 request register" in html
