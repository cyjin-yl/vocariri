"""Public-video research ingestion; run in the dedicated remote container.

Raw media never belongs in Git. Download success is not visual inspection.
Each item is resumable, bounded, and produces source hashes plus timestamped frames.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw
import yt_dlp

ROOT = Path('/workspace')
def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def append(path, value):
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False) + '\n')

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

class Quiet:
    def debug(self, message): pass
    def warning(self, message): pass
    def error(self, message): pass

def run(item):
    item_id = item['id']
    if not item_id.replace('-', '').replace('_', '').isalnum():
        raise ValueError('Unsafe item ID')
    dest = ROOT / 'media' / item_id
    dest.mkdir(parents=True, exist_ok=True)
    record_path = dest / 'source.json'
    if record_path.exists():
        record = json.loads(record_path.read_text())
        media = dest / record['file']
        if digest(media) != record['sha256']:
            raise ValueError('Existing source hash mismatch')
    else:
        attempt = {'id': item_id, 'url': item['url'], 'at': now(), 'state': 'attempting'}
        append(ROOT / 'acquisition.jsonl', attempt)
        def limit_hook(state):
            if state.get('downloaded_bytes', 0) > 750 * 1024 * 1024:
                raise ValueError('Download size limit')
        options = {
            'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best', 'noplaylist': True,
            'merge_output_format': 'mp4',
            'outtmpl': str(dest / 'source.%(ext)s'),
            'socket_timeout': 25, 'retries': 1, 'fragment_retries': 1,
            'max_filesize': 750 * 1024 * 1024, 'overwrites': False,
            'quiet': True, 'logger': Quiet(), 'progress_hooks': [limit_hook],
            'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(item['url'], download=False)
                duration = info.get('duration')
                if duration is None or duration > 1200:
                    raise ValueError('Unknown or excessive duration')
                ydl.process_info(info)
                media = Path(ydl.prepare_filename(info))
                if not media.exists() and (dest / 'source.mp4').exists():
                    media = dest / 'source.mp4'
            if not media.is_file() or media.stat().st_size == 0:
                raise ValueError('No completed media file')
            record = {
                'id': item_id, 'url': item['url'], 'at': now(),
                'title': info.get('title'), 'uploader': info.get('uploader'),
                'duration': duration, 'fps': info.get('fps'),
                'width': info.get('width'), 'height': info.get('height'),
                'extractor': info.get('extractor_key'), 'license': info.get('license'),
                'file': media.name, 'bytes': media.stat().st_size,
                'sha256': digest(media), 'state': 'downloaded_uninspected',
                'yt_dlp_version': yt_dlp.version.__version__,
            }
            # Deliberately exclude transient signed CDN URLs/cookies from metadata.
            record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            append(ROOT / 'acquisition.jsonl', record)
        except Exception as exc:
            reason = re.sub(r'https?://\S+', '[URL]', str(exc))[:500]
            append(ROOT / 'acquisition.jsonl', {
                **attempt, 'at': now(), 'state': 'failed', 'error_class': type(exc).__name__, 'reason': reason})
            print(json.dumps({'id': item_id, 'state': 'failed', 'error_class': type(exc).__name__}), flush=True)
            return
    derived = ROOT / 'frames' / item_id
    derived.mkdir(parents=True, exist_ok=True)
    manifest = derived / 'manifest.json'
    if manifest.exists():
        print(json.dumps({'id': item_id, 'state': 'cached_frames'}), flush=True)
        return
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    # Four samples per second are a screening pass, never full motion verification.
    subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-i', str(media),
        '-vf', 'fps=4,scale=320:-2', '-q:v', '3', '-n', str(derived / 'f-%06d.jpg')],
        check=True, timeout=1200, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    frames = sorted(derived.glob('f-*.jpg'))
    sheets = []
    for offset in range(0, len(frames), 32):
        batch = frames[offset:offset+32]
        with Image.open(batch[0]) as first:
            w, h = first.size
        sheet = Image.new('RGB', (w * 8, (h + 24) * 4), '#171717')
        draw = ImageDraw.Draw(sheet)
        for j, file in enumerate(batch):
            x, y = (j % 8) * w, (j // 8) * (h + 24)
            with Image.open(file) as frame:
                sheet.paste(frame, (x, y))
            draw.text((x+5, y+h+4), f'{(offset+j)/4:.2f}s', fill='white')
        output = derived / f'sheet-{offset//32:04d}.jpg'
        sheet.save(output, quality=88)
        sheets.append({'file': output.name, 'start': offset/4,
                       'end': min((offset+len(batch))/4, record['duration']),
                       'sha256': digest(output)})
    manifest.write_text(json.dumps({
        'source_sha256': record['sha256'], 'sampling_fps': 4,
        'state': 'extracted_uninspected', 'frame_count': len(frames),
        'sheets': sheets, 'note': 'Review at source FPS for short impacts/glitches and cut boundaries.'
    }, indent=2), encoding='utf-8')
    print(json.dumps({'id': item_id, 'state': 'extracted_uninspected',
                      'frames': len(frames), 'sheets': len(sheets)}), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('queue')
    parser.add_argument('--limit', type=int, default=3)
    args = parser.parse_args()
    for item in json.loads(Path(args.queue).read_text(encoding='utf-8-sig'))[:args.limit]:
        if shutil.disk_usage(ROOT).free < 50 * 1024**3:
            raise SystemExit('Free space below reserve')
        run(item)
