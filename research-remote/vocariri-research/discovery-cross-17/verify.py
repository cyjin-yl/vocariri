"""Offline hash validation, frame replay and self-excluding artifact manifest."""

import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

ROOT = Path('/work')


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def replay(item_id, kind, manifest, media, errors):
    folder = ROOT / kind / item_id
    target = ROOT / 'replay' / kind / item_id
    if target.exists():
        errors.append(f'replay target already exists: {kind}/{item_id}')
        return
    target.mkdir(parents=True)
    selection = manifest['selection_filter'] if kind == 'derived' else manifest['filter']
    count_limit = '24' if kind == 'derived' else '30'
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-nostdin', '-v', 'info',
           '-i', str(media), '-vf', selection, '-frames:v', count_limit,
           '-fps_mode', 'vfr', '-q:v', '3', str(target / 'frame-%03d.jpg')]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    (target / 'ffmpeg-log.txt').write_text(result.stderr, encoding='utf-8')
    if result.returncode:
        errors.append(f'replay ffmpeg exit {result.returncode}: {kind}/{item_id}')
        return
    pts = re.findall(r'\[Parsed_showinfo_[^]]+\]\s+n:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:\s*([\d.]+)', result.stderr)
    frames = manifest['frames']
    files = sorted(target.glob('frame-*.jpg'))
    if len(files) != len(frames) or len(pts) != len(frames):
        errors.append(f'replay frame count mismatch: {kind}/{item_id}')
        return
    for file, row, timestamp in zip(files, frames, pts):
        if sha256(file) != row['sha256']:
            errors.append(f'replay hash mismatch: {kind}/{item_id}/{file.name}')
        expected = row['cached_media_pts'] if kind == 'derived' else row['pts']
        if int(timestamp[1]) != expected:
            errors.append(f'replay PTS mismatch: {kind}/{item_id}/{file.name}')


def main():
    errors = []
    completed = []
    for source_json in sorted((ROOT / 'sources').glob('*/source.json')):
        row = json.loads(source_json.read_text(encoding='utf-8'))
        media = ROOT / row['file']
        if not media.is_file() or media.stat().st_size != row['bytes'] or sha256(media) != row['sha256']:
            errors.append(f'source mismatch: {row["id"]}')
            continue
        completed.append(row)
        for kind, name in [('derived', 'frames.json'), ('sequences', 'sequence.json')]:
            manifest_path = ROOT / kind / row['id'] / name
            if not manifest_path.exists():
                if kind == 'derived':
                    errors.append(f'missing sparse frames: {row["id"]}')
                continue
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if manifest['source_sha256'] != row['sha256']:
                errors.append(f'derived source mismatch: {kind}/{row["id"]}')
            script_hashes = {sha256(p) for p in (ROOT / 'extract.py', ROOT / 'sequence.py', ROOT / 'sequence-v1.py') if p.exists()}
            if manifest['script_sha256'] not in script_hashes:
                errors.append(f'derivation script missing: {kind}/{row["id"]}')
            for element in manifest['frames'] + manifest['sheets']:
                file = manifest_path.parent / element['file']
                if not file.is_file() or file.stat().st_size != element['bytes'] or sha256(file) != element['sha256']:
                    errors.append(f'derived hash mismatch: {kind}/{row["id"]}/{element["file"]}')
            replay(row['id'], kind, manifest, media, errors)

    acquisition = [json.loads(line) for line in (ROOT / 'acquisition.jsonl').read_text(encoding='utf-8').splitlines()]
    failures = [row for row in acquisition if row['state'] == 'failed']
    result = {'checked_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'mode': 'offline; container network disabled',
              'source_count': len(completed), 'source_ids': [r['id'] for r in completed],
              'acquisition_rows': len(acquisition), 'failed_attempts': len(failures),
              'replayed_sparse_count': len(list((ROOT / 'replay' / 'derived').glob('*/frame-*.jpg'))),
              'replayed_sequence_count': len(list((ROOT / 'replay' / 'sequences').glob('*/frame-*.jpg'))),
              'accepted_forms': 0, 'accepted_templates': 0,
              'errors': errors}
    (ROOT / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    files = []
    for path in sorted(ROOT.rglob('*')):
        if path.is_file() and path.name != 'artifact-manifest.json' and '__pycache__' not in path.parts:
            files.append({'path': relative(path), 'bytes': path.stat().st_size,
                          'sha256': sha256(path)})
    artifact = {'created_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                'generator': 'verify.py', 'generator_sha256': sha256(Path(__file__)),
                'upstream_sources': [{'url': row['url'], 'sha256': row['sha256'],
                                      'bytes': row['bytes']} for row in completed],
                'files': files,
                'self_reference_note': 'artifact-manifest.json omits itself to avoid recursive self-hash.',
                'verification_errors': len(errors),
                'freezing_note': 'A frozen cache version is not dataset completion, acceptance, or approval.'}
    (ROOT / 'artifact-manifest.json').write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'source_count': len(completed), 'failed_attempts': len(failures),
                      'replayed_sparse_count': result['replayed_sparse_count'],
                      'replayed_sequence_count': result['replayed_sequence_count'],
                      'verification_errors': len(errors), 'manifest_files': len(files)}), flush=True)
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
