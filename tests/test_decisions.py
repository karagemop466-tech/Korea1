"""Offline guards for review status, missing facts and read-only source collection."""
import copy
import gzip
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
from render_readiness import load_register, render
from verify_site import Collector, official_refs
from monitor_official import collect, validate_response


def test_register_ids_and_question_coverage():
    d = load_register()
    assert len(d['questions']) == 12 and len(d['suggestions']) == 8
    ids = {q['id'] for q in d['questions']}
    assert len(ids) == len(d['questions'])
    assert set(' '.join(s['questions'] for s in d['suggestions']).split()) == ids
    for q in d['questions']:
        assert all(q[k] for k in ('question', 'answer', 'missing', 'discovery', 'gate'))
        assert q['source'] in d['sources']
    for s in d['suggestions']:
        assert s['approved_at'] is None
        assert s['status'] == 'PROPOSED — NOT APPROVED'
        assert all(s[k] for k in ('alternative', 'acceptance', 'risk'))


def test_missing_lineup_facts_stay_null():
    d = load_register()
    assert len(d['lineups']) == 7
    for r in d['lineups']:
        assert r['observed_date'] == '2026-11-12'
        assert d['sources'][r['source']]['role'] == 'observation'
        for k in ('source_published_at', 'confirmed_starter', 'confirmed_replacement', 'replacement_depth_rank', 'impact_points'):
            assert r[k] is None
    r = next(r for r in d['lineups'] if r['player'] == 'Jayden Daniels')
    assert r['game_status'] is None and r['injury'] is None
    assert next(r for r in d['lineups'] if r['player'] == 'Lucas Patrick')['published_chart_row'] is None


def test_generated_pages_have_sources_captions_and_blank_roles():
    pages = render(load_register())
    assert set(pages) == {'decisions.html', 'lineups.html'}
    assert 'Parallel suggestion register' in pages['decisions.html']
    for name, content in pages.items():
        c = Collector(); c.feed(content)
        assert c.rows and c.tables == c.captions
        assert all(official_refs([u for _, us in row for u in us]) for row in c.rows)
        assert 'not a live' in content.lower() or name != 'lineups.html'
    c = Collector(); c.feed(pages['lineups.html'])
    for row in c.rows:
        assert all(row[i][0] == '' for i in (8, 9, 10, 11))
    d = copy.deepcopy(load_register())
    d['lineups'][0]['player'] = '<script>alert(1)</script>'
    assert '<script>alert(1)</script>' not in render(d)['lineups.html']


def test_exact_club_allowlist_no_lookalikes():
    assert official_refs(['https://www.commanders.com/team/depth-chart'])
    assert official_refs(['https://www.giants.com/team/depth-chart'])
    assert not official_refs(['https://www.giants.com.example.org/team/depth-chart'])


HTML = b'<html><table><tr><td>Fixture only</td></tr></table>' + b' ' * 1500 + b'</html>'


@pytest.mark.parametrize('url,status,ctype,data', [
    ('https://www.nfl.com.evil.org/injuries/', 200, 'text/html', HTML),
    ('https://www.nfl.com/injuries/', 404, 'text/html', HTML),
    ('https://www.nfl.com/injuries/', 200, 'application/json', HTML),
    ('https://www.nfl.com/injuries/', 200, 'text/html', b'404 - FLAG ON THE PLAY' + HTML),
    ('https://www.nfl.com/injuries/', 200, 'text/html', HTML.replace(b'table', b'other')),
])
def test_monitor_rejects_bad_response(url, status, ctype, data):
    with pytest.raises(ValueError):
        validate_response(url, status, ctype, data)


def test_monitor_success_is_not_verified_extraction(tmp_path):
    class Response:
        status = 200
        headers = {'Content-Type': 'text/html'}
        def __init__(self, url): self.url = url
        def geturl(self): return self.url
        def read(self, size): return HTML
        def __enter__(self): return self
        def __exit__(self, *args): pass
    d = load_register()
    m = collect(d['sources'], tmp_path, opener=lambda req, **kw: Response(req.full_url))
    assert len(m['sources']) == 3 and all(s['success'] for s in m['sources'])
    assert 'NOT VERIFIED EXTRACTION' in m['evidence_status']
    assert gzip.decompress((tmp_path / 'injuries.html.gz').read_bytes()) == HTML
    assert json.loads((tmp_path / 'manifest.json').read_text()) == m


def test_monitor_failure_manifest_not_fallback(tmp_path):
    def unavailable(*args, **kwargs): raise OSError('fixture offline')
    (tmp_path / 'injuries.html.gz').write_bytes(b'old success must not survive')
    m = collect(load_register()['sources'], tmp_path, opener=unavailable)
    assert not any(s['success'] for s in m['sources'])
    assert all('error' in s and 'sha256' not in s for s in m['sources'])
    assert not list(tmp_path.glob('*.gz'))
