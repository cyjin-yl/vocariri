"""Content-aware, source-local work planning; no model calls or mutations."""
import hashlib
import json
from collections import Counter, defaultdict


def plan_batches(root, size=3):
    completed = Counter()
    unresolved = []
    for path in sorted((root / 'outputs' / 'visual-batches').glob('*.status.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        files = set(record['files'].items())
        if record.get('state') == 'response_received_unreviewed':
            response = json.loads(path.with_name(record['id'] + '.json').read_text(encoding='utf-8'))
            if response.get('input_observed') is not True:
                raise ValueError('Completed batch lacks grounded response: ' + record['id'])
            completed.update(files)
        elif record.get('state') not in ('retry_authorized', 'cancelled_redundant'):
            unresolved.append((record['id'], files))
    groups = defaultdict(list)
    current = set()
    for path in sorted((root / 'materials').glob('*/sheet-*.jpg')):
        key = (path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
        current.add(key)
        if key not in completed:
            groups[path.parent.name].append(path)
    pending = current - completed.keys()
    for batch_id, files in unresolved:
        if files & pending:
            raise ValueError('Reconcile incomplete sheet request before regrouping: ' + batch_id)
    batches = [files[i:i + size] for files in groups.values() for i in range(0, len(files), size)]
    return batches, {
        'current_sheets': len(current),
        'completed_unique_sheet_contents': len(completed),
        'repeated_completed_sheet_appearances': sum(completed.values()) - len(completed),
        'pending_sheets': len(pending),
        'pending_batches': len(batches),
    }
