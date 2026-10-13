"""Bounded, single-attempt public-video acquisition for cross-source batch 18.

Run only in the one-shot research-tools container with /work bound to the
independent discovery-cross-18 directory. No authentication state is used.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import signal
import time
import urllib.error
from pathlib import Path
from urllib.parse import urlsplit

import imageio_ffmpeg
import yt_dlp
from yt_dlp.networking import _urllib


ROOT = Path('/work')
MAX_BYTES = 180 * 1024 * 1024
MAX_DURATION = 18 * 60
MAX_SECONDS = 360
ITEMS = {
    'PVOLT-njKdvdYQ-xE': 'https://www.youtube.com/watch?v=njKdvdYQ-xE',
    'NICO-sm45786816': 'https://www.nicovideo.jp/watch/sm45786816',
    'NICO-sm45669453': 'https://www.nicovideo.jp/watch/sm45669453',
    'NICO-sm46320139': 'https://www.nicovideo.jp/watch/sm46320139',
}
CURRENT_ID = None
NETWORK_SEQUENCE = 0
ACTIVE = []
SOURCE_HTTP_STATUS = None
BLOCKED_REDIRECTS = 0


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def append(row):
    with (ROOT / 'acquisition.jsonl').open('a', encoding='utf-8') as out:
        out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
        out.flush()
        os.fsync(out.fileno())


def append_network(row):
    with (ROOT / 'network-requests.jsonl').open('a', encoding='utf-8') as out:
        out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
        out.flush()
        os.fsync(out.fileno())


def safe_url(url):
    """Only public source URLs remain exact; never persist signed CDN paths/queries."""
    if url in ITEMS.values():
        return url
    parsed = urlsplit(str(url))
    if parsed.scheme == 'data':
        return 'data:[body redacted]'
    return f'{parsed.scheme}://{parsed.hostname or "unknown"}/[path-and-query-redacted]'


def status_of(exc):
    value = getattr(exc, 'status', None) or getattr(exc, 'code', None)
    if isinstance(value, int):
        return value
    match = re.search(r'(?:HTTP Error|HTTP error|status)\s*[: ]\s*(\d{3})', str(exc))
    return int(match.group(1)) if match else None


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as inp:
        for block in iter(lambda: inp.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class Quiet:
    def debug(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


def timed_out(signum, frame):
    raise TimeoutError('wall-clock cap exceeded')


def stop_redirect(self, request, response, status, message, headers, target):
    """Do not automatically follow a platform or media HTTP redirect."""
    global BLOCKED_REDIRECTS
    BLOCKED_REDIRECTS += 1
    append_network({'id': CURRENT_ID, 'at_utc': utcnow(), 'state': 'redirect_blocked',
                    'url': safe_url(request.full_url), 'http_status': status,
                    'location': safe_url(target), 'bytes_read': 0})
    raise urllib.error.HTTPError(request.full_url, status, 'redirect blocked', headers, response)


_urllib.RedirectHandler.redirect_request = stop_redirect


def finish(tracker, state='response_complete'):
    if tracker['done']:
        return
    tracker['done'] = True
    append_network({'id': CURRENT_ID, 'request_id': tracker['request_id'],
                    'at_utc': utcnow(), 'state': state, 'url': tracker['url'],
                    'http_status': tracker['http_status'],
                    'bytes_read': tracker['bytes_read'],
                    'response_handler': tracker['response_handler']})


_ORIGINAL_READ = _urllib.UrllibResponseAdapter.read
_ORIGINAL_CLOSE = _urllib.UrllibResponseAdapter.close


def tracked_read(self, amt=None):
    tracker = getattr(self, '_batch18_tracker', None)
    if tracker:
        tracker['in_read'] = True
    try:
        data = _ORIGINAL_READ(self, amt)
        if tracker:
            tracker['bytes_read'] += len(data)
        return data
    finally:
        if tracker:
            tracker['in_read'] = False
            if self.closed:
                finish(tracker)


def tracked_close(self):
    tracker = getattr(self, '_batch18_tracker', None)
    result = _ORIGINAL_CLOSE(self)
    if tracker and not tracker['in_read']:
        finish(tracker)
    return result


_urllib.UrllibResponseAdapter.read = tracked_read
_urllib.UrllibResponseAdapter.close = tracked_close


class LoggedDL(yt_dlp.YoutubeDL):
    def urlopen(self, request):
        global NETWORK_SEQUENCE, SOURCE_HTTP_STATUS
        raw_url = request if isinstance(request, str) else getattr(request, 'url', None) or getattr(request, 'full_url', '')
        NETWORK_SEQUENCE += 1
        rid = f'{CURRENT_ID}-{NETWORK_SEQUENCE:05d}'
        append_network({'id': CURRENT_ID, 'request_id': rid, 'at_utc': utcnow(),
                        'state': 'attempting', 'url': safe_url(raw_url)})
        try:
            response = super().urlopen(request)
        except Exception as exc:
            append_network({'id': CURRENT_ID, 'request_id': rid, 'at_utc': utcnow(),
                            'state': 'failed', 'url': safe_url(raw_url),
                            'http_status': status_of(exc), 'bytes_read': 0,
                            'error_class': type(exc).__name__})
            raise
        if raw_url == ITEMS.get(CURRENT_ID):
            SOURCE_HTTP_STATUS = response.status
        tracker = {'request_id': rid, 'url': safe_url(raw_url),
                   'http_status': response.status, 'bytes_read': 0,
                   'response_handler': type(response).__name__,
                   'in_read': False, 'done': False}
        ACTIVE.append(tracker)
        response._batch18_tracker = tracker
        return response


def acquire(item_id):
    global CURRENT_ID
    CURRENT_ID = item_id
    url = ITEMS[item_id]
    directory = ROOT / 'sources' / item_id
    directory.mkdir(parents=True, exist_ok=True)
    existing = list(directory.iterdir())
    if existing:
        print(json.dumps({'id': item_id, 'state': 'existing_requires_reconciliation',
                          'files': [p.name for p in existing]}), flush=True)
        return 2
    if shutil.disk_usage(ROOT).free < 25 * 1024**3:
        print(json.dumps({'id': item_id, 'state': 'blocked_disk_reserve'}), flush=True)
        return 2

    begun = time.monotonic()
    attempt = {'id': item_id, 'url': url, 'at_utc': utcnow(),
               'state': 'attempting', 'size_cap_bytes': MAX_BYTES,
               'wall_cap_seconds': MAX_SECONDS, 'duration_cap_seconds': MAX_DURATION,
               'credentials': 'none', 'redirect_handling':
               'yt-dlp urllib redirect handler stops at 3xx; native HLS',
               'format_selector_revision': 3,
               'request_ledger': 'network-requests.jsonl; signed internal URLs redacted'}
    append(attempt)

    def limit_hook(state):
        if state.get('downloaded_bytes', 0) > MAX_BYTES:
            raise ValueError('download size cap exceeded')
        if time.monotonic() - begun > MAX_SECONDS:
            raise TimeoutError('wall-clock cap exceeded')

    options = {
        'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]/bestvideo[height<=480]/best',
        'noplaylist': True, 'outtmpl': str(directory / 'source.%(ext)s'),
        'merge_output_format': 'mp4', 'socket_timeout': 15,
        'hls_prefer_native': True,
        'retries': 0, 'fragment_retries': 0, 'extractor_retries': 0,
        'max_filesize': MAX_BYTES, 'ratelimit': 8 * 1024 * 1024,
        'overwrites': False, 'quiet': True, 'logger': Quiet(),
        'progress_hooks': [limit_hook],
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
    }
    signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(MAX_SECONDS)
    try:
        with LoggedDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get('duration')
            if duration is None or duration <= 0 or duration > MAX_DURATION:
                raise ValueError('unknown or excessive duration')
            ydl.process_info(info)
        files = [p for p in directory.iterdir() if p.is_file()
                 and not p.name.endswith(('.part', '.ytdl'))]
        if len(files) != 1 or files[0].stat().st_size == 0:
            raise ValueError('completed single media source not found')
        media = files[0]
        if media.stat().st_size > MAX_BYTES:
            raise ValueError('completed media exceeds size cap')
        record = {'id': item_id, 'url': url, 'at_utc': utcnow(),
                  'state': 'downloaded_uninspected', 'http_status': SOURCE_HTTP_STATUS,
                  'bytes': media.stat().st_size, 'sha256': sha256(media),
                  'file': str(media.relative_to(ROOT)), 'duration_seconds': duration,
                  'title': info.get('title'), 'uploader': info.get('uploader'),
                  'extractor': info.get('extractor_key'),
                  'yt_dlp_version': yt_dlp.version.__version__,
                  'blocked_redirects': BLOCKED_REDIRECTS}
        (directory / 'source.json').write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        append(record)
        print(json.dumps({'id': item_id, 'state': record['state'],
                          'bytes': record['bytes'], 'sha256': record['sha256']}), flush=True)
        return 0
    except Exception as exc:
        reason = re.sub(r'https?://\S+', '[URL]', str(exc))[:250]
        result = {'id': item_id, 'url': url, 'at_utc': utcnow(), 'state': 'failed',
                  'http_status': status_of(exc), 'blocked_redirects': BLOCKED_REDIRECTS,
                  'bytes': sum(p.stat().st_size for p in directory.glob('*') if p.is_file()),
                  'error_class': type(exc).__name__, 'reason': reason,
                  'partial_files_retained': [p.name for p in directory.iterdir()]}
        append(result)
        print(json.dumps({'id': item_id, 'state': 'failed',
                          'http_status': result['http_status'],
                          'error_class': result['error_class']}), flush=True)
        return 1
    finally:
        signal.alarm(0)
        for tracker in ACTIVE:
            finish(tracker, 'response_unclosed_at_attempt_end')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('id', choices=sorted(ITEMS))
    args = parser.parse_args()
    raise SystemExit(acquire(args.id))
