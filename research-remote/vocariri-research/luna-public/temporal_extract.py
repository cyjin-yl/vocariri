"""Extract bounded native-rate frame sequences from cached public media only."""
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
import imageio_ffmpeg
from PIL import Image, ImageDraw


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def extract(root, item):
    source = root / item['media']
    if digest(source) != item['source_sha256']:
        raise ValueError('Source hash mismatch')
    if not 0 < item['duration'] <= 5:
        raise ValueError('Temporal excerpt must be bounded to five seconds')
    out = root / 'temporal' / item['id']
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / 'manifest.json'
    if manifest.exists():
        print(item['id'], 'cached; preserve original extraction', flush=True)
        return
    if list(out.glob('f-*.png')):
        raise ValueError('Partial prior extraction needs reconciliation')
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-hide_banner',
               '-ss', str(item['start']), '-i', str(source), '-t', str(item['duration']),
               '-an', '-vf', 'scale=480:-2,showinfo', '-vsync', '0', '-n', str(out / 'f-%05d.png')]
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
    (out / 'ffmpeg.log').write_bytes(result.stderr)
    result.check_returncode()
    frames = sorted(out.glob('f-*.png'))
    pts = [float(x) for x in re.findall(rb'\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([-\d.e+]+)', result.stderr)]
    # showinfo can log a trailing decoded frame beyond the output duration.
    if len(pts) < len(frames):
        raise ValueError('Missing frame timestamps')
    records = [{'file': f.name, 'relative_pts': pts[i], 'source_seconds': item['start'] + pts[i],
                'sha256': digest(f)} for i, f in enumerate(frames)]
    sheets = []
    for offset in range(0, len(frames), 24):
        batch = frames[offset:offset + 24]
        with Image.open(batch[0]) as first:
            w, h = first.size
        sheet = Image.new('RGB', (w * 6, (h + 25) * math.ceil(len(batch) / 6)), '#171717')
        draw = ImageDraw.Draw(sheet)
        for i, frame in enumerate(batch):
            x, y = i % 6 * w, i // 6 * (h + 25)
            with Image.open(frame) as im:
                sheet.paste(im, (x, y))
            draw.text((x + 5, y + h + 4), f"{records[offset+i]['source_seconds']:.4f}s", fill='white')
        dest = out / f'dense-{offset//24:03d}.jpg'
        sheet.save(dest, quality=94)
        sheets.append({'file': dest.name, 'sha256': digest(dest)})
    manifest.write_text(json.dumps({'source': item, 'frames': records, 'sheets': sheets,
        'sampling': 'native decoded frames; no fps filter; seek plus decoded PTS labels',
        'limits': 'Silent frames only. Native source-frame quantization remains. No audio/beat/easing inference.'}, indent=2))
    print(item['id'], len(frames), 'frames', len(sheets), 'sheets', flush=True)


if __name__ == '__main__':
    root = Path.cwd()
    for item in json.loads((root / 'temporal-queue.json').read_text()):
        extract(root, item)
