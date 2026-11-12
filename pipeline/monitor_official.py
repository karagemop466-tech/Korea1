"""Read-only official response archiver. Never treats collection as verified lineup extraction.

Raw HTML and manifest go to an ignored output directory / Actions artifacts, not Git.
A failure is recorded and returns nonzero; no fallback to cached 'current' data.
"""
from __future__ import annotations
import argparse
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
HOSTS = {'www.nfl.com', 'www.commanders.com', 'www.giants.com'}
MAX_BYTES = 12_000_000


def validate_response(url, status, content_type, data):
    if urlsplit(url).scheme != 'https' or urlsplit(url).hostname not in HOSTS:
        raise ValueError('redirect outside the exact official host allowlist')
    if status != 200 or 'text/html' not in content_type.lower():
        raise ValueError('expected successful HTML response')
    text = data.decode('utf-8', errors='replace').lower()
    if len(data) < 1000 or len(data) > MAX_BYTES:
        raise ValueError('unexpected response length')
    if any(token in text for token in ('404 - flag on the play', '<title>access denied', 'captcha', 'cf-chl-')):
        raise ValueError('error or challenge page, not usable source content')
    # This is only a content sanity test, NOT a schema/field verification.
    if '<table' not in text:
        raise ValueError('no source table found; page format or access may have changed')
    return True


def collect(sources, output, opener=urlopen):
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'collected_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                'evidence_status': 'RAW COLLECTION ONLY — NOT VERIFIED EXTRACTION', 'sources': []}
    for key in ('injuries', 'was_depth', 'nyg_depth'):
        s = sources[key]
        # A reused output directory must not bundle stale success beside a failed manifest.
        (output / (key + '.html.gz')).unlink(missing_ok=True)
        entry = {'source_id': key, 'requested_url': s['url'], 'success': False,
                 'started_at': dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            with opener(Request(s['url'], headers={'User-Agent': 'NFL-Line-Lab-Source-Monitor/1.0'}), timeout=45) as response:
                data = response.read(MAX_BYTES + 1)
                entry.update(final_url=response.geturl(), http_status=response.status,
                             content_type=response.headers.get('Content-Type', ''),
                             retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                             bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                validate_response(entry['final_url'], entry['http_status'], entry['content_type'], data)
                filename = key + '.html.gz'
                (output / filename).write_bytes(gzip.compress(data, mtime=0))
                entry.update(success=True, artifact_file=filename)
        except Exception as exc:
            entry['error'] = f'{type(exc).__name__}: {exc}'
        manifest['sources'].append(entry)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.cache/official-monitor')
    args = parser.parse_args()
    sources = json.loads((ROOT / 'research/decision-register.json').read_text())['sources']
    result = collect(sources, args.output)
    for item in result['sources']:
        print(item['source_id'], 'COLLECTED' if item['success'] else item['error'])
    return 0 if all(s['success'] for s in result['sources']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
