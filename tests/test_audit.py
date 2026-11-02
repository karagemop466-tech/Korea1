"""Regression checks for audit disclosures, not verification of NFL values."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_all_published_pages_disclose_review_status():
    pages = list(ROOT.glob('*.html')) + list((ROOT / 'lab').glob('*.html'))
    assert pages
    for page in pages:
        assert 'Research under review' in page.read_text(), page


def test_open_board_disabled_and_independence_not_asserted():
    lines = (ROOT / 'lines.html').read_text()
    corr = (ROOT / 'correlations.html').read_text()
    assert 'Open board — disabled pending review' in lines
    assert 'No current prices are published' in lines
    assert 'CI includes zero; independence unproven' in corr
    assert 'If the interval contains zero, cross-game legs can be multiplied' not in corr


def test_audit_and_primary_source_link_are_published():
    page = (ROOT / 'flagged.html').read_text()
    assert 'id="audit-2026"' in page
    assert 'https://www.nfl.com/games/ravens-at-bills-2026-reg-8' in page
    assert 'AUDIT_2026-11-02.md' in page
