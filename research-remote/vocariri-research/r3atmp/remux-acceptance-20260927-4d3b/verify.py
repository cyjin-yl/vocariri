"""Independent, offline acceptance of the exact native-PTS remux candidate.

Run only in the pre-existing [research container] container. This script never calls
request entry points, opens protected configuration, or modifies producer files.
"""

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from unittest import mock

import imageio_ffmpeg


WORKSPACE = Path('/workspace')
OUT = WORKSPACE / 'r3atmp/remux-acceptance-20260927-4d3b'
SOURCE = WORKSPACE / 'media/BV1zrbCzLEH4/source.mp4'
CLIP = WORKSPACE / 'r3atmp/codex-taildiag-20260927-7e2c/remux.mp4'
RECEIPT = WORKSPACE / 'r3atmp/codex-taildiag-20260927-7e2c/remux-recheck-test-receipt.json'
CLIENT = WORKSPACE / 'checked-client-20260927/remote/video_request_checked.py'
START, END = 4258, 4275
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv, name, timeout=240):
    result = subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
    (OUT / (name + '.stderr')).write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError(f'{name}: ffmpeg exit {result.returncode}')
    return result


def showinfo(path, name, limit=None):
    argv = [FFMPEG, '-nostdin', '-hide_banner', '-loglevel', 'info', '-copyts',
            '-noautorotate', '-i', str(path), '-map', '0:v:0', '-an', '-sn', '-dn',
            '-vf', 'showinfo', '-fps_mode', 'passthrough']
    if limit:
        argv += ['-frames:v', str(limit)]
    argv += ['-f', 'null', '-']
    result = command(argv, name)
    log = result.stderr.decode('utf-8', errors='replace')
    bases = re.findall(r'config in time_base:\s*([1-9]\d*/[1-9]\d*)', log)
    frames = []
    for line in log.splitlines():
        if 'Parsed_showinfo_' not in line or not re.search(r'\bn:\s*\d+\s+pts:', line):
            continue
        n = re.search(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:', line)
        size = re.search(r'\bs:(\d+)x(\d+)\b', line)
        if not n or not size:
            raise RuntimeError(f'{name}: incomplete showinfo frame')
        frames.append({'n': int(n.group(1)), 'pts': int(n.group(2)),
                       'width': int(size.group(1)), 'height': int(size.group(2))})
    if len(bases) != 1 or not frames or [x['n'] for x in frames] != list(range(len(frames))):
        raise RuntimeError(f'{name}: ambiguous showinfo sequence or time base')
    return {'time_base': bases[0], 'frames': frames,
            'stderr_sha256': hashlib.sha256(result.stderr).hexdigest(),
            'argv': argv}


def raw_frames(path, name, width, height, first=None, last=None):
    argv = [FFMPEG, '-nostdin', '-hide_banner', '-loglevel', 'error', '-noautorotate',
            '-i', str(path), '-map', '0:v:0', '-an', '-sn', '-dn']
    if first is not None:
        argv += ['-vf', f'select=between(n\\,{first}\\,{last})']
    argv += ['-fps_mode', 'passthrough', '-pix_fmt', 'rgb24']
    if first is not None:
        argv += ['-frames:v', str(last - first + 1)]
    argv += ['-f', 'rawvideo', '-']
    result = command(argv, name)
    frame_bytes = width * height * 3
    if len(result.stdout) % frame_bytes:
        raise RuntimeError(f'{name}: incomplete RGB frame')
    return [result.stdout[i:i + frame_bytes]
            for i in range(0, len(result.stdout), frame_bytes)]


def main():
    # The directory and the script must be exclusively created by the caller.
    for path in (SOURCE, CLIP, RECEIPT, CLIENT):
        if not path.is_file():
            raise RuntimeError(f'missing exact input: {path}')
    report = {'inputs': {key: {'path': str(path), 'bytes': path.stat().st_size,
                              'sha256': digest(path)}
                         for key, path in [('source', SOURCE), ('clip', CLIP),
                                           ('receipt', RECEIPT), ('client', CLIENT)]},
              'ffmpeg': FFMPEG,
              'ffmpeg_version': subprocess.run([FFMPEG, '-version'], check=True,
                                               capture_output=True, text=True).stdout.splitlines()[0]}
    original = showinfo(SOURCE, 'source-showinfo', END + 2)
    candidate = showinfo(CLIP, 'clip-showinfo')
    source_frames = original['frames'][START:END + 1]
    clip_frames = candidate['frames']
    source_pts = [x['pts'] for x in source_frames]
    clip_pts = [x['pts'] for x in clip_frames]
    expected = [x - source_pts[0] for x in source_pts]
    report['source_mapping'] = {'indices': [x['n'] for x in source_frames],
                                'time_base': original['time_base'], 'pts': source_pts,
                                'scan_count_through_neighbor': len(original['frames']),
                                'trace_sha256': original['stderr_sha256'],
                                'scan_argv': original['argv']}
    report['candidate_decode'] = {'count': len(clip_frames),
                                  'time_base': candidate['time_base'], 'pts': clip_pts,
                                  'relative_source_pts': expected,
                                  'trace_sha256': candidate['stderr_sha256'],
                                  'scan_argv': candidate['argv']}
    source_size = {(x['width'], x['height']) for x in source_frames}
    clip_size = {(x['width'], x['height']) for x in clip_frames}
    if len(source_frames) != 18 or len(clip_frames) != 18 or len(source_size) != 1 or \
            source_size != clip_size or original['time_base'] != '1/16000' or \
            candidate['time_base'] != '1/16000' or clip_pts != expected or \
            expected[-1] != 9072 or any(b <= a for a, b in zip(clip_pts, clip_pts[1:])):
        raise RuntimeError('source mapping, cadence, dimensions, or final frame failed')
    width, height = next(iter(source_size))
    # Decode a source neighbor on either side to test for accidental off-by-one.
    source_rgb = raw_frames(SOURCE, 'source-rgb', width, height, START - 1, END + 1)
    clip_rgb = raw_frames(CLIP, 'clip-rgb', width, height)
    if len(source_rgb) != 20 or len(clip_rgb) != 18:
        raise RuntimeError('RGB decode count failed')
    pixels = []
    for i, frame in enumerate(clip_rgb):
        counterpart = source_rgb[i + 1]
        # Exact RGB identity is stronger than a lossy PSNR comparison for this
        # stream-copy remux. Record both hashes for every frame.
        matches = [START - 1 + j for j, source in enumerate(source_rgb)
                   if source == frame]
        pixels.append({'clip_index': i, 'source_index': START + i,
                       'clip_rgb_sha256': hashlib.sha256(frame).hexdigest(),
                       'source_rgb_sha256': hashlib.sha256(counterpart).hexdigest(),
                       'pixel_exact': frame == counterpart,
                       'matches_within_20_frame_neighborhood': matches})
    report['pixels'] = {'format': 'rgb24', 'width': width, 'height': height,
                        'all_18_exact': all(x['pixel_exact'] for x in pixels),
                        'frames': pixels}
    if not report['pixels']['all_18_exact']:
        raise RuntimeError('candidate source pixel mismatch')
    receipt = json.loads(RECEIPT.read_bytes())
    report['receipt_claim_matches_independent_source'] = (
        receipt.get('source_sha256') == report['inputs']['source']['sha256'] and
        receipt.get('clip_sha256') == report['inputs']['clip']['sha256'] and
        receipt.get('source_time_base') == original['time_base'] and
        receipt.get('source_pts') == source_pts)
    if not report['receipt_claim_matches_independent_source']:
        raise RuntimeError('receipt source binding mismatch')
    sys.path.insert(0, str(CLIENT.parent))
    spec = importlib.util.spec_from_file_location('acceptance_checked_client', CLIENT)
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    with mock.patch.object(client, 'load_route', side_effect=AssertionError('route forbidden')), \
         mock.patch.object(client, 'stream_request', side_effect=AssertionError('request forbidden')), \
         mock.patch.object(client.socket, 'create_connection', side_effect=AssertionError('network forbidden')), \
         mock.patch.object(client.socket, 'getaddrinfo', side_effect=AssertionError('network forbidden')):
        probe = client.probe_video(CLIP)
        validation = client.validate_native_receipt(
            RECEIPT, WORKSPACE, report['inputs']['clip']['sha256'], probe)
        if probe['decoded_frames'] != 18 or probe['pts'] != clip_pts:
            raise RuntimeError('checked-client probe differs from independent decode')
        altered = dict(receipt)
        altered['source_pts'] = list(source_pts)
        altered['source_pts'][-1] += 16
        bad_pts = OUT / 'mutated-final-pts.json'
        with bad_pts.open('x', encoding='utf-8') as output:
            json.dump(altered, output)
        try:
            client.validate_native_receipt(bad_pts, WORKSPACE,
                                           report['inputs']['clip']['sha256'], probe)
        except client.ClientError as error:
            bad_pts_result = error.category
        else:
            bad_pts_result = 'unexpectedly_accepted'
        altered = dict(receipt)
        altered['clip_sha256'] = '0' * 64
        bad_hash = OUT / 'mutated-clip-hash.json'
        with bad_hash.open('x', encoding='utf-8') as output:
            json.dump(altered, output)
        try:
            client.validate_native_receipt(bad_hash, WORKSPACE,
                                           report['inputs']['clip']['sha256'], probe)
        except client.ClientError as error:
            bad_hash_result = error.category
        else:
            bad_hash_result = 'unexpectedly_accepted'
    report['deployed_client_offline'] = {'probe': probe, 'receipt': validation,
                                         'network_entry_points_blocked': True,
                                         'mutated_final_pts': bad_pts_result,
                                         'mutated_clip_hash': bad_hash_result}
    if bad_pts_result != 'native_receipt_invalid' or bad_hash_result != 'native_receipt_invalid':
        raise RuntimeError('negative receipt tests failed')
    report['conclusion'] = 'transport_cadence_and_source_frame_identity_pass'
    report['limits'] = ('No inference request, server-side sampling inspection, model visual '
                        'understanding, accepted form, or template follows from this pass.')
    with (OUT / 'review.json').open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
    files = [{'path': str(path.relative_to(OUT)), 'bytes': path.stat().st_size,
              'sha256': digest(path)} for path in sorted(OUT.iterdir())
             if path.is_file() and path.name != 'artifact-manifest.json']
    manifest = {'generated_by': 'verify.py',
                'script_sha256': digest(OUT / 'verify.py'),
                'upstream_sha256': {k: v['sha256'] for k, v in report['inputs'].items()},
                'files': files,
                'self_reference': 'artifact-manifest.json is omitted to avoid recursive self-hashing'}
    with (OUT / 'artifact-manifest.json').open('x', encoding='utf-8') as output:
        json.dump(manifest, output, indent=2)
        output.write('\n')
    print(json.dumps({'conclusion': report['conclusion'],
                      'review_sha256': digest(OUT / 'review.json'),
                      'manifest_sha256': digest(OUT / 'artifact-manifest.json'),
                      'source_count': len(source_frames), 'clip_count': len(clip_frames),
                      'final_relative_pts': clip_pts[-1],
                      'pixel_exact_frames': sum(x['pixel_exact'] for x in pixels),
                      'negative_tests': [bad_pts_result, bad_hash_result]}))


if __name__ == '__main__':
    main()
