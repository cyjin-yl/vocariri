"""Screen video while preserving selected source-frame timestamps and bytes.

Unlike an fps filter, select does not invent output-grid timestamps. Existing
extractions are immutable: a failed extraction must be inspected, not overwritten.
"""
import hashlib
import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def parse_showinfo(text):
    bases = re.findall(r'config in time_base:\s*(\d+/\d+)', text)
    if not bases or len(set(bases)) != 1:
        raise ValueError('Missing or changing source time base')
    time_base = Fraction(bases[0])
    rows = [(int(n), int(pts)) for n, pts in re.findall(
        r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:', text)]
    if not rows or [n for n, _ in rows] != list(range(len(rows))):
        raise ValueError('Missing or nonsequential selected-frame records')
    if any(b[1] <= a[1] for a, b in zip(rows, rows[1:])):
        raise ValueError('Nonmonotonic source timestamps require manual review')
    return time_base, rows


def sample_frames(media, destination, ffmpeg, *, sampling_fps=4, width=320,
                  expected_source_sha256=None, timeout=1200):
    media, destination = Path(media), Path(destination)
    if not isinstance(sampling_fps, int) or not 1 <= sampling_fps <= 120:
        raise ValueError('Invalid screening rate')
    if not isinstance(width, int) or width < 2:
        raise ValueError('Invalid width')
    source_hash = digest(media)
    if expected_source_sha256 and source_hash != expected_source_sha256:
        raise ValueError('Source changed before extraction')
    destination.mkdir(parents=True, exist_ok=False)
    # First decoded frame in each occupied source-time bucket. Low frame-rate
    # inputs produce fewer samples; gaps are retained rather than duplicated.
    expression = (f"select='isnan(prev_selected_t)+"
                  f"gte(floor(t*{sampling_fps}),floor(prev_selected_t*{sampling_fps})+1)',"
                  f'scale={width}:-2,showinfo')
    command = [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'info',
               '-copyts', '-i', str(media), '-map', '0:v:0', '-an',
               '-vf', expression, '-fps_mode', 'passthrough', '-q:v', '3',
               '-n', str(destination / 'f-%06d.jpg')]
    with (destination / 'decode.log').open('wb') as log:
        subprocess.run(command, check=True, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=log)
    time_base, selected = parse_showinfo(
        (destination / 'decode.log').read_text(encoding='utf-8', errors='replace'))
    images = sorted(destination.glob('f-*.jpg'))
    if len(images) != len(selected):
        raise ValueError('Frame/time count mismatch')
    frames = []
    for image, (number, pts) in zip(images, selected):
        if image.name != f'f-{number + 1:06d}.jpg':
            raise ValueError('Frame filename mismatch')
        seconds = pts * time_base
        frames.append({'file': image.name, 'source_pts': pts,
                       'source_pts_seconds': float(seconds),
                       'source_bucket': int(seconds * sampling_fps // 1),
                       'sha256': digest(image)})
    manifest = {'version': 1, 'method': 'first_source_frame_in_occupied_bucket',
                'requested_sampling_fps': sampling_fps,
                'source_sha256': source_hash, 'time_base': str(time_base),
                'timestamp_domain': 'source_video_pts_preserved_with_copyts',
                'playback_origin_seconds': None,
                'origin_note': 'Source PTS is not automatically the audio/editor clock. '
                               'Resolve stream/container start offsets before synchronization.',
                'frames': frames}
    with (destination / 'source-frames.json').open('x', encoding='utf-8') as out:
        json.dump(manifest, out, indent=2)
        out.write('\n')
    return manifest
