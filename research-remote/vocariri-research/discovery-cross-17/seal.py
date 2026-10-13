"""Validate final batch receipts and refresh the self-excluding hash inventory."""

import datetime as dt
import hashlib
import json
import stat
from pathlib import Path

ROOT = Path('/work')


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    verification = json.loads((ROOT / 'verification.json').read_text(encoding='utf-8'))
    observations = json.loads((ROOT / 'observations.json').read_text(encoding='utf-8'))
    assert not verification['errors']
    assert verification['source_count'] == observations['counts']['completed_media_sources'] == 3
    assert observations['counts']['accepted_distinct_forms'] == 0
    assert observations['counts']['accepted_templates'] == 0
    sources = []
    for item in observations['sources']:
        row = json.loads((ROOT / 'sources' / item['id'] / 'source.json').read_text(encoding='utf-8'))
        media = ROOT / row['file']
        assert row['sha256'] == item['source_sha256'] == sha256(media)
        assert media.stat().st_size == row['bytes']
        assert stat.S_IMODE(media.stat().st_mode) == 0o444
        sources.append({'id': item['id'], 'url': row['url'], 'sha256': row['sha256'],
                        'bytes': row['bytes']})
    files = [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha256(p),
              'bytes': p.stat().st_size}
             for p in sorted(ROOT.rglob('*'))
             if p.is_file() and p.name != 'artifact-manifest.json']
    inventory = {'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                 'generator': 'seal.py', 'generator_sha256': sha256(Path(__file__)),
                 'source_originals': sources, 'file_count': len(files), 'files': files,
                 'verification_errors': 0, 'accepted_forms': 0, 'accepted_templates': 0,
                 'self_reference_note': 'artifact-manifest.json omits itself to avoid recursive self-hash.',
                 'freeze_limit': 'Version frozen for audit; not dataset completion or aesthetic acceptance.'}
    (ROOT / 'artifact-manifest.json').write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'files': len(files), 'sources': sources,
                      'manifest_sha256': sha256(ROOT / 'artifact-manifest.json')}), flush=True)


if __name__ == '__main__':
    main()
