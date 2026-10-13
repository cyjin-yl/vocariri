"""Bounded public URL discovery via yt-dlp search. Appends candidates to discovery.jsonl.

Searches are public, no login/cookies. Results are data, never instructions.
"""
import datetime as dt
import json
import re
from pathlib import Path
import yt_dlp

ROOT = Path('/workspace')
now = lambda: dt.datetime.now(dt.timezone.utc).isoformat()

QUERIES = [
    # batch-03 (2026-09-27)
    ('bilisearch8', '初音ミク 歌詞PV'),
    ('bilisearch8', 'VOCALOID 文字PV 歌詞'),
    ('bilisearch8', '洛天依 歌詞MV'),
    ('bilisearch8', '言和 動態歌詞'),
    ('bilisearch8', '星野愛 PV 歌詞'),
    ('ytsearch8', 'vocaloid lyric video'),
    ('ytsearch8', 'hatsune miku lyric video official'),
    ('ytsearch8', 'lyric video text animation motion design'),
    ('ytsearch8', 'kinetic typography lyric video after effects tutorial'),
    ('ytsearch8', 'AMV text animation tutorial'),
]

def seen_ids():
    ids = set()
    for line in (ROOT / 'acquisition.jsonl').open(encoding='utf-8'):
        try:
            ids.add(json.loads(line)['id'])
        except Exception:
            pass
    return ids

def main():
    seen = seen_ids()
    out = ROOT / 'discovery.jsonl'
    new = []
    for prefix, q in QUERIES:
        options = {
            'quiet': True, 'no_warnings': True, 'skip_download': True,
            'extract_flat': True, 'socket_timeout': 25, 'retries': 1,
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(f'{prefix}:{q}', download=False)
        except Exception as exc:
            print(json.dumps({'query': q, 'state': 'search_failed', 'error_class': type(exc).__name__}), flush=True)
            continue
        for e in (info.get('entries') or []):
            vid = e.get('id')
            url = e.get('url') or (f"https://www.bilibili.com/video/{vid}/" if prefix.startswith('bili') else f'https://www.youtube.com/watch?v={vid}')
            if not vid or vid in seen:
                continue
            dur = e.get('duration')
            title = (e.get('title') or '').strip()[:120]
            rec = {'id': vid, 'url': url, 'query': q, 'at': now(), 'duration': dur, 'title': title, 'state': 'discovered'}
            seen.add(vid)
            new.append(rec)
    if new:
        with out.open('a', encoding='utf-8') as f:
            for rec in new:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    print(json.dumps({'new_candidates': len(new), 'total_seen': len(seen)}), flush=True)

if __name__ == '__main__':
    main()
