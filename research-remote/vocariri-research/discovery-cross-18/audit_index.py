"""Read-only public-media ID/title index of existing remote research cache."""

import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path('/tank/shared/projects/vocariri-research')
metadata = []
for prefix in (ROOT / 'media', ROOT / 'luna-public' / 'media',
               ROOT / 'discovery-cross-17' / 'sources'):
    for path in sorted(prefix.glob('*/source.json')):
        row = json.loads(path.read_text(encoding='utf-8'))
        metadata.append({'id': row.get('id'), 'title': row.get('title'),
                         'url': row.get('url'), 'sha256': row.get('sha256'),
                         'path': path.relative_to(ROOT).as_posix()})
ledgers = []
for relative in ('acquisition.jsonl', 'discovery.jsonl',
                 'discovery-cross-17/acquisition.jsonl'):
    path = ROOT / relative
    lines = path.read_text(encoding='utf-8').splitlines()
    ledgers.append({'path': relative, 'rows': len(lines),
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'entries': [{'id': row.get('id'), 'title': row.get('title'),
                                 'url': row.get('url'), 'state': row.get('state')}
                                for row in (json.loads(line) for line in lines)]})
print(json.dumps({'checked_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                  'metadata_count': len(metadata), 'metadata': metadata,
                  'ledgers': ledgers}, ensure_ascii=False, indent=2))
