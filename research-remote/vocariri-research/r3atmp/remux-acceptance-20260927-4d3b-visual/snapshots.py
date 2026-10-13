"""Create first/middle/final stills from the independently accepted clip."""

import hashlib
import json
from pathlib import Path
import subprocess

import imageio_ffmpeg

CLIP = Path('/workspace/r3atmp/codex-taildiag-20260927-7e2c/remux.mp4')
OUT = Path('/workspace/r3atmp/remux-acceptance-20260927-4d3b-visual')
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sha(CLIP) != '810e39509b34646f2432164e843231671e3b34a6099398b8fa48fb3c30d32653':
        raise RuntimeError('candidate drift')
    images = []
    for index in (0, 9, 17):
        output = OUT / f'frame-{index:02d}.png'
        args = [FFMPEG, '-nostdin', '-hide_banner', '-loglevel', 'error', '-noautorotate',
                '-i', str(CLIP), '-map', '0:v:0', '-vf', f'select=eq(n\\,{index})',
                '-frames:v', '1', '-n', str(output)]
        result = subprocess.run(args, capture_output=True, check=False, timeout=30)
        if result.returncode or not output.is_file():
            raise RuntimeError(f'frame {index} extraction failed: exit {result.returncode}')
        images.append({'frame': index, 'file': output.name,
                       'bytes': output.stat().st_size, 'sha256': sha(output)})
    record = {'clip_sha256': sha(CLIP), 'decoder': FFMPEG, 'images': images,
              'purpose': 'Visual spot-check only; not model video understanding.'}
    with (OUT / 'snapshots.json').open('x', encoding='utf-8') as file:
        json.dump(record, file, indent=2)
        file.write('\n')
    manifest = {'files': [{'path': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)}
                          for p in sorted(OUT.iterdir()) if p.is_file() and
                          p.name != 'artifact-manifest.json'],
                'self_reference': 'artifact-manifest.json omitted to avoid recursive self-hashing'}
    with (OUT / 'artifact-manifest.json').open('x', encoding='utf-8') as file:
        json.dump(manifest, file, indent=2)
        file.write('\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
