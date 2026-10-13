"""Sparse visual screening with cached-media PTS and reproducible frame hashes."""

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

ROOT = Path('/work')


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as inp:
        for block in iter(lambda: inp.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def extract(item_id):
    source = ROOT / 'sources' / item_id / 'source.json'
    row = json.loads(source.read_text(encoding='utf-8'))
    media = ROOT / row['file']
    if sha256(media) != row['sha256']:
        raise ValueError('source checksum mismatch')
    out = ROOT / 'derived' / item_id
    if out.exists():
        raise ValueError('derived directory exists; never overwrite')
    out.mkdir(parents=True)
    duration = float(row['duration_seconds'])
    interval = max(5.0, math.ceil(duration / 23.0))
    filter_spec = f'select=isnan(prev_selected_t)+gte(t-prev_selected_t\\,{interval:g}),scale=480:-2,showinfo'
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [ffmpeg, '-hide_banner', '-nostdin', '-v', 'info', '-i', str(media),
               '-vf', filter_spec, '-frames:v', '24', '-fps_mode', 'vfr',
               '-q:v', '3', str(out / 'frame-%03d.jpg')]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    (out / 'ffmpeg-log.txt').write_text(result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'ffmpeg exit {result.returncode}; see retained log')
    time_base_match = re.search(r'config in time_base:\s*(\d+/\d+)', result.stderr)
    if not time_base_match:
        raise ValueError('showinfo time base missing')
    time_base = time_base_match.group(1)
    pts = re.findall(r'\[Parsed_showinfo_[^]]+\]\s+n:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:\s*([\d.]+)', result.stderr)
    files = sorted(out.glob('frame-*.jpg'))
    if not files or len(files) != len(pts):
        raise ValueError(f'frame/PTS mismatch: files={len(files)}, PTS={len(pts)}')
    frames = []
    for path, (number, timestamp, seconds) in zip(files, pts):
        frames.append({'file': path.name, 'frame_index': int(number),
                       'cached_media_pts': int(timestamp), 'cached_media_time_base': time_base,
                       'cached_media_pts_seconds': float(seconds),
                       'bytes': path.stat().st_size, 'sha256': sha256(path)})
    sheets = []
    for start in range(0, len(frames), 12):
        batch = frames[start:start + 12]
        with Image.open(out / batch[0]['file']) as first:
            width, height = first.size
        sheet = Image.new('RGB', (width * 3, (height + 26) * 4), '#171717')
        draw = ImageDraw.Draw(sheet)
        for pos, entry in enumerate(batch):
            x, y = pos % 3 * width, pos // 3 * (height + 26)
            with Image.open(out / entry['file']) as frame:
                sheet.paste(frame, (x, y))
            draw.text((x + 6, y + height + 5),
                      f"PTS {entry['cached_media_pts_seconds']:.3f}s", fill='white')
        path = out / f'sheet-{start // 12:02d}.jpg'
        sheet.save(path, quality=90)
        sheets.append({'file': path.name, 'bytes': path.stat().st_size,
                       'sha256': sha256(path), 'frame_count': len(batch)})
    manifest = {'id': item_id, 'source_file': row['file'],
                'source_sha256': row['sha256'], 'script_sha256': sha256(Path(__file__)),
                'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                'ffmpeg_binary': ffmpeg, 'selection_interval_seconds': interval,
                'selection_filter': filter_spec,
                'pts_scope': 'PTS in the cached media file; remux may differ from platform stream',
                'evidence_state': 'sparse_frames_uninspected',
                'frames': frames, 'sheets': sheets}
    (out / 'frames.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                     encoding='utf-8')
    print(json.dumps({'id': item_id, 'state': 'sparse_frames_uninspected',
                      'frames': len(frames), 'sheets': len(sheets),
                      'first_pts_seconds': frames[0]['cached_media_pts_seconds'],
                      'last_pts_seconds': frames[-1]['cached_media_pts_seconds']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('id')
    extract(parser.parse_args().id)
