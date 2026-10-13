"""One bounded, metadata-only format probe; never persists signed media URLs."""

import argparse
import datetime as dt
import json
import signal
from pathlib import Path

import yt_dlp

ROOT = Path('/work')
ITEMS = {
    'NICO-sm46546276': 'https://www.nicovideo.jp/watch/sm46546276',
    'PVOLT-C-7TIDIKc98': 'https://www.youtube.com/watch?v=C-7TIDIKc98',
}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def append(record):
    with (ROOT / 'diagnostic.jsonl').open('a', encoding='utf-8') as out:
        out.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
        out.flush()


class Quiet:
    def debug(self, message):
        pass
    def warning(self, message):
        pass
    def error(self, message):
        pass


def alarm(signum, frame):
    raise TimeoutError('diagnostic time cap')


def main(item_id):
    url = ITEMS[item_id]
    append({'id': item_id, 'url': url, 'at_utc': now(),
            'state': 'diagnostic_attempting', 'network': 'metadata_only',
            'credentials': 'none', 'wall_cap_seconds': 45})
    signal.signal(signal.SIGALRM, alarm)
    signal.alarm(45)
    try:
        with yt_dlp.YoutubeDL({'skip_download': True, 'ignore_no_formats_error': True,
                               'noplaylist': True, 'socket_timeout': 10,
                               'retries': 0, 'extractor_retries': 0,
                               'fragment_retries': 0, 'quiet': True,
                               'logger': Quiet()}) as ydl:
            info = ydl.extract_info(url, download=False)
        formats = info.get('formats') or []
        record = {'id': item_id, 'url': url, 'at_utc': now(),
                  'state': 'diagnostic_complete', 'format_count': len(formats),
                  'formats': [{'id': f.get('format_id'), 'ext': f.get('ext'),
                               'protocol': f.get('protocol'), 'height': f.get('height')}
                              for f in formats[:20]],
                  'duration_seconds': info.get('duration'),
                  'availability': info.get('availability'),
                  'yt_dlp_version': yt_dlp.version.__version__}
        append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        record = {'id': item_id, 'url': url, 'at_utc': now(),
                  'state': 'diagnostic_failed', 'error_class': type(exc).__name__}
        append(record)
        print(json.dumps(record), flush=True)
        return 1
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('id', choices=sorted(ITEMS))
    raise SystemExit(main(parser.parse_args().id))
