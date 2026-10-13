"""Native-fps dense contact sheets for fast-motion / typography intervals.

Usage: dense_sheet.py <source.mp4> <start> <end> <out.jpg> [fps] [cols]
Extracts frames at the given fps (default 30) from [start,end), tiles into a
grid with absolute timecode labels. 4fps sheets are screening only; this is
for inspecting impacts, cuts, and quick glyph changes the 4fps pass misses.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw

source, start, end = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
out = Path(sys.argv[4])
fps = float(sys.argv[5]) if len(sys.argv) > 5 else 30.0
cols = int(sys.argv[6]) if len(sys.argv) > 6 else 6
cell_w = 240

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
tmp = Path(tempfile.mkdtemp(prefix='dense-'))
subprocess.run(
    [ffmpeg, '-nostdin', '-v', 'error', '-ss', str(start), '-i', source,
     '-t', str(end - start), '-vf', f'fps={fps},scale={cell_w}:-2',
     '-q:v', '3', '-n', str(tmp / 'f-%05d.jpg')],
    check=True, timeout=600)
frames = sorted(tmp.glob('f-*.jpg'))
if not frames:
    raise SystemExit('No frames extracted')
step = 1.0 / fps
rows = (len(frames) + cols - 1) // cols
th = int(cell_w * 9 / 16)
sheet = Image.new('RGB', (cols * cell_w, rows * (th + 18)), 'black')
draw = ImageDraw.Draw(sheet)
for i, f in enumerate(frames):
    r, c = divmod(i, cols)
    im = Image.open(f).resize((cell_w, th), Image.LANCZOS)
    x, y = c * cell_w, r * (th + 18)
    sheet.paste(im, (x, y))
    draw.text((x + 4, y + th + 2), f'{start + i * step:.2f}s', fill='yellow')
out.parent.mkdir(parents=True, exist_ok=True)
sheet.save(out, quality=85)
print(json.dumps({'out': str(out), 'frames': len(frames), 'fps': fps,
                  'span_seconds': round(end - start, 3)}))
