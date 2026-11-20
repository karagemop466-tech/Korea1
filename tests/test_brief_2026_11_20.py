"""Guards for the 2026-11-20 brief trace + decision hub (DV2, arena/0ead6a90-korea1).

Each test targets a rule that could break without anyone noticing: a trace row that loses
its gate or its clearing number, a count on the page that drifts from the committed
artefact behind it, an official link that leaves the allow-list, or a decision hub whose
three sections (trace, questions, suggestions) silently shrink.
"""
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

PAGE = ROOT / "brief-2026-11-20.html"
TRACE = ROOT / "data" / "processed" / "brief_2026_11_20.csv"
MIRROR = ROOT / "assets" / "data" / "brief_2026_11_20.csv"
QUESTIONS = ROOT / "data" / "review" / "questions.csv"
SUGGESTIONS = ROOT / "data" / "review" / "suggestions.csv"


def _trace() -> pd.DataFrame:
    return pd.read_csv(TRACE, dtype=str, keep_default_na=False)


def test_trace_has_one_row_per_register_item():
    rr = pd.read_csv(ROOT / "assets" / "data" / "request_register_2026_11_18.csv",
                     dtype=str, keep_default_na=False)
    t = _trace()
    assert len(rr) == len(t) == 81
    assert list(t["id"]) == list(rr["id"])  # same order, no item dropped or duplicated


def test_every_trace_row_has_status_gate_and_clearing_number():
    for r in _trace().itertuples(index=False):
        assert r.status.strip(), r.id
        assert r.blocking_gate.strip(), r.id
        assert r.clearing_number.strip(), r.id
        assert r.requirement.strip(), r.id


def test_every_trace_row_links_an_official_host_or_is_flagged_as_text():
    from verify_site import ALLOW
    t = _trace()
    sourced = t[t["source_url"].str.strip() != ""]
    unsourced = t[t["source_url"].str.strip() == ""]
    assert len(sourced) == 74 and len(unsourced) == 7
    for r in sourced.itertuples(index=False):
        host = urlsplit(r.source_url).hostname or ""
        assert host in ALLOW, (r.id, host)
        assert urlsplit(r.source_url).scheme == "https", r.id
    for r in unsourced.itertuples(index=False):
        assert "no official source" in r.source_label.lower(), r.id


def test_unsourced_rows_are_flagged_prose_not_table_rows():
    html = PAGE.read_text(encoding="utf-8")
    for r in _trace().itertuples(index=False):
        if r.source_url.strip():
            continue
        assert f"<strong>{r.id}" in html, r.id  # present as flagged prose
        assert "never filled in" in html
        # and its row in the CSV keeps the blank URL (nothing inferred)
        assert r.source_url == ""


def test_site_mirror_matches_the_processed_trace_byte_for_byte():
    assert MIRROR.read_bytes() == TRACE.read_bytes()


def test_page_exists_and_carries_all_three_decision_sections():
    html = PAGE.read_text(encoding="utf-8")
    for marker in ("Executive summary", "Decision readiness: one row per requirement",
                   "Questions, information and answers",
                   "Suggestions — review and choose before implementing"):
        assert marker in html, marker


def test_page_headline_counts_match_the_committed_artefacts():
    """The page states 0 of 18 validated, 65 picks, 14 official finals, 1714 graph rows."""
    strat = pd.read_csv(ROOT / "data" / "processed" / "strategy_summary.csv",
                        dtype=str, keep_default_na=False)
    graded = pd.read_csv(ROOT / "data" / "forward" / "graded_cards.csv",
                         dtype=str, keep_default_na=False)
    picks = pd.read_csv(ROOT / "data" / "forward" / "picks.csv",
                        dtype=str, keep_default_na=False)
    graph = pd.read_csv(ROOT / "data" / "processed" / "availability_graph.csv",
                        dtype=str, keep_default_na=False)
    assert int((strat["verdict"] == "VALIDATED").sum()) == 0
    assert len(strat) == 18
    assert int((graded["status"] == "OFFICIAL").sum()) == 14
    assert len(picks) == 65
    assert len(graph) == 1714
    html = PAGE.read_text(encoding="utf-8")
    assert "0 of 18" in html
    assert "65" in html and "14 official finals" in html
    assert "1714" in html


def test_page_rows_all_carry_an_official_link():
    """check_sources covers the canonical page set; this asserts the new page directly."""
    from verify_site import Collector, official_refs
    c = Collector()
    c.feed(PAGE.read_text(encoding="utf-8"))
    assert c.rows, "page must contain table rows"
    for i, row in enumerate(c.rows, 1):
        hrefs = [h for _, links in row for h in links]
        assert official_refs(hrefs), f"row {i} has no official/primary source"


def test_questions_and_suggestions_sections_cover_every_register_row():
    q = pd.read_csv(QUESTIONS, dtype=str, keep_default_na=False)
    s = pd.read_csv(SUGGESTIONS, dtype=str, keep_default_na=False)
    html = PAGE.read_text(encoding="utf-8")
    for r in q.itertuples(index=False):
        assert r.id in html, r.id
    for r in s.itertuples(index=False):
        assert r.id in html, r.id


def test_page_is_registered_in_the_nav_and_the_checkers():
    nav = (ROOT / "pipeline" / "render_site.py").read_text(encoding="utf-8")
    assert '"brief-2026-11-20.html"' in nav
    for checker in ("pipeline/verify_site.py", "tests/check_sources.py", "tests/check_links.py"):
        assert "brief-2026-11-20.html" in (ROOT / checker).read_text(encoding="utf-8"), checker


def test_page_uses_the_site_layout_not_a_hand_rolled_shell():
    html = PAGE.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="assets/style.css">' in html
    assert 'class="brand"' in html  # the shared site shell
    # No CDN or external asset dependency.
    assert "cdn." not in html and "unpkg" not in html and "jsdelivr" not in html
