"""Offline bounded locator and native-frame evidence for two retained tutorials."""
import datetime
import hashlib
import json
import math
import pathlib
import re
import subprocess
import sys
from fractions import Fraction

from PIL import Image, ImageDraw
import imageio_ffmpeg

WORKSPACE = pathlib.Path('/workspace')
ROOT = WORKSPACE / 'evidence/batch19-reuse-native-r1'
EXPECTED = {
    'YT_b0XgjrWSV7k': {'bytes': 34515185,
                     'sha256': '7667f999dc1f4e8f9fedc1f5ae1e24e311a336f4d421cf02aa4a3138cf2ee958',
                     'sidecar_sha256': 'af0e9ccdf3cabebf2c31b962d981aab9c939332f5c04296fc2059a9e3fb75d95'},
    'YT_3Jf_sabP4e0': {'bytes': 19922877,
                     'sha256': '67af7fce3d05102a689038b1c08838b8c6cb6e5b83f0a8e9ba10c0a47bbdd3c7',
                     'sidecar_sha256': '1c4af29b86168995690207656c7c5e07a251d26043f8a7fa95653de34f58c746'}
}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def record(row):
    row = dict(row, at_utc=now(), extraction_revision=2)
    with (ROOT / 'job-r2.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(row) + '\n')
    print(json.dumps(row), flush=True)


def save(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


def source(ident):
    assert ident in EXPECTED
    path = WORKSPACE / 'luna-public/media' / ident / 'source.mp4'
    assert path.resolve().is_relative_to((WORKSPACE / 'luna-public/media').resolve())
    sidecar = path.with_name('source.json')
    actual = {'id': ident, 'file': path.relative_to(WORKSPACE).as_posix(),
              'bytes': path.stat().st_size, 'sha256': sha(path),
              'sidecar_sha256': sha(sidecar), 'checked_at_utc': now()}
    assert all(actual[key] == value for key, value in EXPECTED[ident].items()), 'source drift'
    return path, actual


def run(command, out, timeout=180):
    save(out / 'command.json', {'command': command, 'timeout_seconds': timeout,
                              'offline': True, 'model_request_made': False})
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    (out / 'decode.stderr').write_text(result.stderr, encoding='utf-8')
    (out / 'decode.stdout').write_text(result.stdout, encoding='utf-8')
    assert result.returncode == 0, 'ffmpeg nonzero exit'
    return result.stderr


def showinfo(text):
    match = re.search(r'config in time_base:\s*(\d+/\d+)', text)
    assert match, 'source timebase unavailable'
    timebase = match[1]
    rows = []
    for line in text.splitlines():
        match = re.search(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:\s*([\d.eE+-]+).*?fmt:(\S+).*?s:(\d+)x(\d+)', line)
        if not match:
            continue
        row = {'selected_counter': int(match[1]), 'source_pts': int(match[2]),
               'timebase': timebase, 'showinfo_seconds': float(match[3]),
               'decoded_pixel_format': match[4], 'width': int(match[5]), 'height': int(match[6])}
        exact = Fraction(row['source_pts']) * Fraction(timebase)
        assert abs(float(exact) - row['showinfo_seconds']) <= 0.0001
        row['source_seconds_exact'] = str(exact)
        rows.append(row)
    assert rows and all(row['selected_counter'] == index for index, row in enumerate(rows))
    return timebase, rows


def plane_bytes(pixel_format, width, height):
    packed = {'rgb24': 3, 'bgr24': 3, 'rgba': 4, 'bgra': 4, 'gray': 1, 'gray8': 1}
    if pixel_format in packed:
        return width * height * packed[pixel_format]
    planar = {'yuv420p': (2, 2, 1), 'yuvj420p': (2, 2, 1),
              'yuv422p': (2, 1, 1), 'yuvj422p': (2, 1, 1),
              'yuv444p': (1, 1, 1), 'yuvj444p': (1, 1, 1),
              'yuv420p10le': (2, 2, 2), 'yuv422p10le': (2, 1, 2), 'yuv444p10le': (1, 1, 2)}
    assert pixel_format in planar, 'unknown decoded plane layout'
    horizontal, vertical, bytes_per_sample = planar[pixel_format]
    return (width * height + 2 * math.ceil(width / horizontal) * math.ceil(height / vertical)) * bytes_per_sample


def seal(folder):
    entries = [{'path': path.relative_to(folder).as_posix(), 'bytes': path.stat().st_size,
                'sha256': sha(path)} for path in sorted(folder.rglob('*'))
               if path.is_file() and path != folder / 'artifact-manifest-r2.json']
    save(folder / 'artifact-manifest-r2.json', {'generated_at_utc': now(),
         'self_exclusion': 'artifact-manifest-r2.json is excluded because a recursive self-hash cannot be included; the immutable r1 manifest is retained',
         'freeze_meaning': 'Stable evidence version only; not full-source inspection, form or template acceptance',
         'generator': {'path': 'scripts/batch19-reuse-native-r2.py', 'sha256': sha(pathlib.Path(__file__))},
         'files': entries, 'formsAcceptedIncrement': 0, 'templatesAcceptedIncrement': 0})


def locator(ffmpeg):
    out = ROOT / 'locator/YT_b0XgjrWSV7k'
    out.mkdir(parents=True, exist_ok=False)
    media, original = source('YT_b0XgjrWSV7k')
    graph = "select='between(n,0,750)*not(mod(n,30))',showinfo,scale=640:-2"
    command = [ffmpeg, '-hide_banner', '-nostdin', '-threads', '2', '-copyts',
               '-protocol_whitelist', 'file,pipe', '-i', str(media), '-vf', graph,
               '-frames:v', '26', '-fps_mode', 'passthrough', '-an', '-threads', '2',
               str(out / 'locator-%03d.png')]
    record({'state': 'locator_decode_started', 'id': original['id'],
            'selection_source_n': '0..750 inclusive, multiples of 30', 'expected_count': 26})
    text = run(command, out)
    timebase, rows = showinfo(text)
    images = sorted(out.glob('locator-*.png'))
    assert len(images) == len(rows) == 26, 'locator count mismatch'
    for index, (row, path) in enumerate(zip(rows, images)):
        row.update({'source_n': index * 30, 'file': path.relative_to(ROOT).as_posix(),
                    'png_bytes': path.stat().st_size, 'png_sha256': sha(path),
                    'role': 'scaled 1-second locator, not native motion proof'})
    assert sha(media) == original['sha256'], 'source changed during locator decode'
    thumbs = []
    for row, path in zip(rows, images):
        with Image.open(path) as image:
            image.thumbnail((320, 180))
            thumb = Image.new('RGB', (320, 204), '#111111')
            thumb.paste(image, (0, 0))
        ImageDraw.Draw(thumb).text((4, 183), f"n{row['source_n']} PTS{row['source_pts']} {row['showinfo_seconds']:.3f}s", fill='white')
        thumbs.append(thumb)
    sheet = Image.new('RGB', (4 * 320, math.ceil(len(thumbs) / 4) * 204), '#111111')
    for index, image in enumerate(thumbs):
        sheet.paste(image, ((index % 4) * 320, (index // 4) * 204))
    sheet.save(out / 'LOCATOR-sheet.png')
    save(out / 'locator.json', {'created_at_utc': now(), 'source': original, 'selection': graph,
         'source_timebase': timebase, 'count': 26, 'frames': rows,
         'sheet': {'file': 'locator/YT_b0XgjrWSV7k/LOCATOR-sheet.png',
                   'bytes': (out / 'LOCATOR-sheet.png').stat().st_size,
                   'sha256': sha(out / 'LOCATOR-sheet.png')},
         'native_evidence': False, 'formsAcceptedIncrement': 0, 'templatesAcceptedIncrement': 0})
    record({'state': 'locator_finished_unviewed', 'count': len(rows), 'source_unchanged': True})
    seal(ROOT / 'locator')


def native(ffmpeg):
    selection = json.loads((ROOT / 'native-selection.json').read_text(encoding='utf-8'))
    assert len(selection['windows']) == 2
    assert {row['id'] for row in selection['windows']} == set(EXPECTED)
    failures = []
    for window in selection['windows']:
        ident = window['id']
        start, end = window['source_n_start'], window['source_n_end_inclusive']
        assert isinstance(start, int) and isinstance(end, int) and 0 <= start <= end
        count = end - start + 1
        assert count <= 60 and window['maximum_window_seconds'] == 2
        out = ROOT / 'native-r2' / ident
        out.mkdir(parents=True, exist_ok=False)
        record({'state': 'native_decode_attempting', 'id': ident, 'source_n_start': start,
                'source_n_end_inclusive': end, 'requested_maximum_seconds': 2})
        try:
            media, original = source(ident)
            # The prior scoped screening established this source timebase; showinfo and
            # framehash below must independently agree with it for this extraction.
            timebase = '1/15360'
            graph = f"[0:v]select='between(n,{start},{end})',showinfo,split=2[png][raw]"
            command = [ffmpeg, '-hide_banner', '-nostdin', '-threads', '2', '-copyts',
                       '-protocol_whitelist', 'file,pipe', '-i', str(media),
                       '-filter_complex_threads', '1', '-filter_complex', graph,
                       '-map', '[png]', '-an', '-c:v', 'png', '-threads', '2', '-pix_fmt', 'rgb24',
                       '-frames:v', str(count), '-enc_time_base:v', timebase, '-fps_mode', 'passthrough',
                       str(out / 'native-%03d.png'),
                       '-map', '[raw]', '-an', '-c:v', 'rawvideo', '-threads', '2', '-pix_fmt', 'yuv420p',
                       '-frames:v', str(count), '-enc_time_base:v', timebase, '-fps_mode', 'passthrough',
                       '-f', 'framehash', '-hash', 'SHA256', str(out / 'decoded-native.framehash')]
            text = run(command, out)
            actual_timebase, rows = showinfo(text)
            images = sorted(out.glob('native-*.png'))
            assert actual_timebase == timebase
            assert all(row['decoded_pixel_format'] == 'yuv420p' for row in rows), 'source pixel format drift'
            hashes_text = (out / 'decoded-native.framehash').read_text(encoding='utf-8')
            assert re.search(r'#tb 0:\s*' + re.escape(timebase) + r'\s*$', hashes_text, re.MULTILINE)
            hashes = [[value.strip() for value in line.split(',')] for line in hashes_text.splitlines()
                      if line.strip() and not line.startswith('#')]
            assert len(rows) == len(images) == len(hashes) == count, 'native count mismatch'
            for index, (row, path, raw) in enumerate(zip(rows, images, hashes)):
                assert len(raw) == 6 and raw[0] == '0'
                frame_pts, frame_duration, size = int(raw[2]), int(raw[3]), int(raw[4])
                expected_size = plane_bytes(row['decoded_pixel_format'], row['width'], row['height'])
                assert frame_pts == row['source_pts'] and size == expected_size and frame_duration > 0
                with Image.open(path) as image:
                    assert image.size == (row['width'], row['height']) and image.mode == 'RGB'
                row.update({'source_n': start + index, 'file': path.relative_to(ROOT).as_posix(),
                            'source_duration_pts': frame_duration, 'complete_decoded_plane_bytes': expected_size,
                            'decoded_native_planes_sha256': raw[5], 'png_bytes': path.stat().st_size,
                            'png_sha256': sha(path), 'png_pixel_format': 'rgb24',
                            'role': 'native-resolution source frame; PNG conversion and plane hashes are separate'})
            elapsed = Fraction(rows[-1]['source_pts'] + rows[-1]['source_duration_pts'] - rows[0]['source_pts']) * Fraction(timebase)
            assert elapsed <= 2 and all(row['source_pts'] < following['source_pts']
                                        for row, following in zip(rows, rows[1:])), 'native time cap or order failure'
            assert sha(media) == original['sha256'], 'source changed during native decode'
            save(out / 'native.json', {'created_at_utc': now(), 'extraction_revision': 2, 'source': original, 'selection': window,
                 'command': command, 'source_timebase': timebase, 'decoded_pixel_format': rows[0]['decoded_pixel_format'],
                 'native_dimensions': [rows[0]['width'], rows[0]['height']], 'framehash_pixel_format': 'yuv420p', 'count': count,
                 'actual_window_seconds_exact': str(elapsed), 'frame_pts_preserved': True,
                 'source_n_mapping': 'Source-index select before showinfo; output counter i maps to start+i; no seek, setpts, scale or fps override',
                 'frames': rows, 'viewed_in_this_process': False,
                 'formsAcceptedIncrement': 0, 'templatesAcceptedIncrement': 0})
            record({'state': 'native_decode_complete_unviewed', 'id': ident, 'count': count,
                    'native_dimensions': [rows[0]['width'], rows[0]['height']],
                    'decoded_pixel_format': rows[0]['decoded_pixel_format'],
                    'complete_decoded_plane_bytes_per_frame': rows[0]['complete_decoded_plane_bytes'],
                    'source_unchanged': True, 'actual_window_seconds_exact': str(elapsed)})
        except Exception as error:
            failures.append(ident)
            save(out / 'failure.json', {'state': 'failed', 'error_class': type(error).__name__,
                                      'partial_files_retained': True, 'no_retry': True, 'at_utc': now()})
            record({'state': 'native_decode_failed', 'id': ident, 'failure_class': type(error).__name__,
                    'partial_files_retained': True})
    record({'state': 'native_phase_finished', 'failed_sources': failures,
            'model_request_made': False, 'formsAcceptedIncrement': 0, 'templatesAcceptedIncrement': 0})
    seal(ROOT)
    return 1 if failures else 0


def main():
    assert len(sys.argv) == 2 and sys.argv[1] == 'native'
    assert ROOT.is_dir() and (ROOT / 'artifact-manifest.json').is_file()
    assert not (ROOT / 'artifact-manifest-r2.json').exists() and not (ROOT / 'native-r2').exists()
    record({'state': 'offline_auxiliary_phase_started', 'phase': 'native-r2',
            'process': 'python + FFmpeg offline tool, not a model agent', 'model_request_made': False,
            'correction': 'Raw branch uses observed yuv420p; PNG branch retains needed format conversion. Same zero-output r1 windows.'})
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    originals = [source(ident)[1] for ident in EXPECTED]
    save(ROOT / 'native-r2-source-preflight.json', {'checked_at_utc': now(), 'sources': originals,
         'ffmpeg_binary': ffmpeg, 'ffmpeg_sha256': sha(pathlib.Path(ffmpeg)), 'phase': 'native-r2',
         'python': sys.version, 'model_request_made': False})
    return native(ffmpeg)


if __name__ == '__main__':
    raise SystemExit(main())
