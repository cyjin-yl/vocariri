"""Offline exact-ID and conservative title-collision screen for cached leads."""

import difflib
import json
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
CACHE = ROOT.parent
index = json.loads((ROOT / 'remote-index.json').read_text(encoding='utf-8-sig'))
media = index['metadata']
ledger_ids = {str(x['id']) for ledger in index['ledgers'] for x in ledger['entries'] if x.get('id')}


def url_id(url):
    parsed = urlparse(url or '')
    if parsed.hostname and 'youtube.com' in parsed.hostname:
        return (parse_qs(parsed.query).get('v') or [None])[0]
    if parsed.hostname and 'nicovideo.jp' in parsed.hostname:
        return parsed.path.rstrip('/').split('/')[-1]
    return None


metadata_url_ids = {url_id(m.get('url')) for m in media}
ledger_url_ids = {url_id(e.get('url')) for ledger in index['ledgers'] for e in ledger['entries']}


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKC', str(s or '')).casefold() if c.isalnum())


out = []
for batch in ('discovery-cross-15', 'discovery-cross-16'):
    candidates = json.loads((CACHE / batch / 'candidates.json').read_text(encoding='utf-8'))['candidates']
    for row in candidates:
        identity = row.get('work_title_on_official_page') or row.get('work_identity_key_from_title') or row.get('search_result_title')
        nid = row['candidate_id'].split('-', 1)[1]
        candidate_url = row.get('youtube_url') or row.get('niconico_url')
        uid = url_id(candidate_url)
        key = norm(identity)
        hits = []
        for prior in media:
            title = norm(prior['title'])
            if not key or not title:
                continue
            score = difflib.SequenceMatcher(None, key, title).ratio()
            if key in title or title in key:
                score = max(score, 0.9)
            hits.append((score, prior['id'], prior['title']))
        top = sorted(hits, reverse=True)[:2]
        out.append({'id': row['candidate_id'], 'identity': identity,
                    'url': candidate_url,
                    'exact_metadata_id': row['candidate_id'] in {str(m['id']) for m in media}
                    or nid in {str(m['id']) for m in media} or uid in metadata_url_ids,
                    'exact_ledger_id': row['candidate_id'] in ledger_ids or nid in ledger_ids
                    or uid in ledger_url_ids,
                    'closest': [{'score': round(score, 3), 'id': mid, 'title': title}
                                for score, mid, title in top]})
(ROOT / 'candidate-comparison.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for row in out:
    best = row['closest'][0] if row['closest'] else {'score': 0, 'id': None, 'title': None}
    print(row['id'], 'exact=', row['exact_metadata_id'] or row['exact_ledger_id'],
          'nearest=', best['score'], best['id'], row['identity'])
