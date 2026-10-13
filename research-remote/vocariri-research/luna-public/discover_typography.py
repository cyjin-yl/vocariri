"""Bounded public-video discovery; preserve raw results, don't infer visual forms."""
import argparse
import datetime
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import yt_dlp

QUERIES = ['VOCALOID 文字PV モーショングラフィックス', 'ボカロ タイポグラフィ MV',
           'ボカロ 文字PV AviUtl', 'VOCALOID kinetic typography MV']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=int, default=4)
    parser.add_argument('--query', action='append')
    parser.add_argument('--results-per-query', type=int, default=8)
    parser.add_argument('--limit', type=int, default=16)
    args = parser.parse_args()
    if not 1 <= args.batch <= 999 or not 1 <= args.results_per_query <= 30 or not 1 <= args.limit <= 100:
        parser.error('batch/count limits exceeded')
    queries = args.query or QUERIES
    root = Path.cwd()
    dest = root / f'discovery-{args.batch:02d}'
    dest.mkdir(exist_ok=True)
    seen = set()
    for p in root.glob('queue-*.json'):
        if p.name == f'queue-expansion-{args.batch:02d}.json':
            continue
        for x in json.loads(p.read_text()):
            if isinstance(x, dict):
                seen.add(x.get('url'))
    selected, leads = [], []
    for i, query in enumerate(queries):
        cache = dest / f'query-{i}.json'
        if cache.exists():
            result = json.loads(cache.read_text())
            if result.get('query') != query and result.get('original_url') != f'ytsearch{args.results_per_query}:' + query:
                raise SystemExit('Cached query differs; use another batch number')
        else:
            record = {'query': query, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'state': 'attempting'}
            with (dest / 'requests.jsonl').open('a') as f:
                f.write(json.dumps(record) + '\n')
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'skip_download': True,
                                      'socket_timeout': 25, 'retries': 0}) as ydl:
                    result = ydl.extract_info(f'ytsearch{args.results_per_query}:' + query, download=False)
                result['query'] = query
                cache.write_text(json.dumps(result, ensure_ascii=False))
                record.update(state='received', sha256=hashlib.sha256(cache.read_bytes()).hexdigest())
            except Exception as exc:
                record.update(state='failed', error_class=type(exc).__name__)
                with (dest / 'requests.jsonl').open('a') as f:
                    f.write(json.dumps(record) + '\n')
                raise SystemExit('Discovery stopped; reconcile failed query before retry')
            with (dest / 'requests.jsonl').open('a') as f:
                f.write(json.dumps(record) + '\n')
        for x in result.get('entries') or []:
            if not x:
                continue
            url = x.get('url') or x.get('webpage_url')
            title = x.get('title') or ''
            reason = 'queued_for_visual_screening'
            if not url or urlparse(url).hostname not in ('www.youtube.com', 'youtube.com'):
                reason = 'unsupported_source'
            elif url in seen:
                reason = 'already_queued'
            elif re.search(r'MMD|gameplay|full combo|歌ってみた|dance practice', title, re.I):
                reason = 'preserved_scene_or_cover_lead_not_priority_in_this_typography_batch'
            elif x.get('duration') and x['duration'] > 1200:
                reason = 'duration_exceeds_acquisition_bound'
            leads.append({'query': query, 'id': x.get('id'), 'title': title, 'url': url,
                          'duration': x.get('duration'), 'disposition': reason,
                          'evidence': 'search metadata only; typography density and motion unverified'})
            if reason == 'queued_for_visual_screening':
                seen.add(url)
                selected.append({'id': 'YT_' + x['id'], 'url': url})
        (dest / 'selection.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in leads))
        (root / f'queue-expansion-{args.batch:02d}.json').write_text(json.dumps(selected[:args.limit], indent=2))
        print('queries completed', i + 1, 'unique acquisition leads', min(len(selected), args.limit), flush=True)
