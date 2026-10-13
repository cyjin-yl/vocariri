"""Only paired Nico URLs after main failures and current no-success reconciliation."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/work')
PAIRS = [('PVOLT-HbS1T4d1P70', 'NICO-sm43449029'),
         ('PVOLT-lIoi2r3f5fU', 'NICO-sm43086737')]

def append(row):
    row['at_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    with (ROOT / 'fallback-job.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(row, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    assert not (ROOT / 'fallback-job.jsonl').exists(), 'Existing fallback requires reconciliation'
    old = [json.loads(x) for x in (ROOT / 'acquisition.jsonl').read_text().splitlines()]
    assert any(json.loads(x).get('state') == 'tool_job_finished'
               for x in (ROOT / 'job.jsonl').read_text().splitlines())
    for main, fallback in PAIRS:
        rows = [x for x in old if x.get('id') == main]
        assert rows and rows[-1]['state'] == 'failed'
        assert not any(x.get('state') == 'downloaded_uninspected' for x in rows)
        assert not list((ROOT / 'sources' / main).iterdir()), 'Unknown main media requires reconciliation'
        assert not (ROOT / 'sources' / fallback).exists(), 'Existing fallback path requires reconciliation'
    append({'state': 'fallback_tool_job_started', 'pairs': PAIRS, 'model_request_made': False})
    for main, fallback in PAIRS:
        append({'state': 'paired_fallback_process_attempting', 'id': fallback,
                'main_id': main, 'main_documented_failed': True, 'main_success_or_media_present': False})
        begun = time.monotonic()
        try:
            result = subprocess.run([sys.executable, '-u', str(ROOT / 'acquire-r2.py'), fallback], timeout=375)
            append({'state': 'fallback_process_completed', 'id': fallback,
                    'returncode': result.returncode, 'elapsed_seconds': round(time.monotonic() - begun, 3)})
        except subprocess.TimeoutExpired:
            append({'state': 'fallback_process_timeout_requires_reconciliation', 'id': fallback})
            break
    append({'state': 'fallback_tool_job_finished', 'forms_increment': 0, 'templates_increment': 0})
