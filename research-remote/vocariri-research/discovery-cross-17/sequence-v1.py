"""Bounded short-window visual sequence retaining cached-media source PTS."""

import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

ROOT = Path('/work')
WINDOWS = {
    'PVOLT-C-7TIDIKc98': (89.0, 101.0, 0.5),
    'NICO-sm46155083': (27.0, 38.0, 0.5),
}


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def run(item_id):
    start, end, step = WINDOWS[item_id]
    source = json.loads((ROOT / 'sources' / item_id / 'source.json').read_text(encoding='utf-8'))
    media = ROOT / source['file']
    if sha256(media) != source['sha256']:
        raise ValueError('source checksum mismatch')
    out = ROOT / 'sequences' / item_id
    if out.exists():
        raise ValueError('sequence already exists; no overwrite')
    out.mkdir(parents=True)
    filt = (f'select=between(t\\,{start:g}\\,{end:g})*'
            f'(isnan(prev_selected_t)+gte(t-prev_selected_t\\,{step:g})),'
            'scale=400:-2,showinfo')
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-nostdin', '-v', 'info',
               '-i', str(media), '-vf', filt, '-frames:v', '30', '-fps_mode', 'vfr',
               '-q:v', '3', str(out / 'frame-%03d.jpg')]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    (out / 'ffmpeg-log.txt').write_text(result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'ffmpeg exit {result.returncode}; log retained')
    match = re.search(r'config in time_base:\s*(\d+/\d+)', result.stderr)
    rows = re.findall(r'\[Parsed_showinfo_[^]]+\]\s+n:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:\s*([\d.]+)', result.stderr)
    files = sorted(out.glob('frame-*.jpg'))
    if not match or not files or len(files) != len(rows):
        raise ValueError('frame and PTS verification failed')
    frames = [{'file': path.name, 'index': int(row[0]), 'pts': int(row[1]),
               'pts_seconds': float(row[2]), 'time_base': match.group(1),
               'sha256': sha256(path), 'bytes': path.stat().st_size}
              for path, row in zip(files, rows)]
    sheets = []
    for offset in range(0, len(frames), 20):
        batch = frames[offset:offset + 20]
        with Image.open(out / batch[0]['file']) as first:
            width, height = first.size
        sheet = Image.new('RGB', (width * 4, (height + 22) * 5), '#171717')
        draw = ImageDraw.Draw(sheet)
        for pos, frame in enumerate(batch):
            x, y = pos % 4 * width, pos // 4 * (height + 22)
            with Image.open(out / frame['file']) as image:
                sheet.paste(image, (x, y))
            draw.text((x + 5, y + height + 3), f"{frame['pts_seconds']:.3f}s", fill='white')
        path = out / f'sheet-{offset // 20:02d}.jpg'
        sheet.save(path, quality=90)
        sheets.append({'file': path.name, 'bytes': path.stat().st_size, 'sha256': sha256(path)})
    manifest = {'id': item_id, 'source_sha256': source['sha256'],
                'script_sha256': sha256(Path(__file__)),
                'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                'window_seconds': [start, end], 'minimum_selection_step_seconds': step,
                'filter': filt, 'pts_scope': 'cached media file',
                'evidence_state': 'short_sequence_uninspected',
                'frames': frames, 'sheets': sheets}
    (out / 'sequence.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                       encoding='utf-8')
    print(json.dumps({'id': item_id, 'frames': len(frames), 'sheets': len(sheets),
                      'first_pts_seconds': frames[0]['pts_seconds'],
                      'last_pts_seconds': frames[-1]['pts_seconds']}), flush=True)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in WINDOWS:
        raise SystemExit('choose one configured source')
    run(sys.argv[1])
