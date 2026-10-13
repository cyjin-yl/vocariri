"""Observable finite tool job: two official main URLs, one fresh process each."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/work')
IDS = ['PVOLT-HbS1T4d1P70', 'PVOLT-lIoi2r3f5fU']

def append(row):
    row['at_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    with (ROOT / 'job.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(row, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    assert not (ROOT / 'job.jsonl').exists(), 'Existing job requires reconciliation'
    append({'state': 'tool_job_started', 'ids': IDS, 'model_request_made': False})
    for item in IDS:
        append({'state': 'item_process_attempting', 'id': item})
        begun = time.monotonic()
        try:
            process = subprocess.run([sys.executable, '-u', str(ROOT / 'acquire.py'), item],
                                     timeout=375)
            append({'state': 'item_process_completed', 'id': item,
                    'returncode': process.returncode,
                    'elapsed_seconds': round(time.monotonic() - begun, 3)})
        except subprocess.TimeoutExpired:
            append({'state': 'item_process_timeout_requires_reconciliation', 'id': item,
                    'elapsed_seconds': round(time.monotonic() - begun, 3)})
            break
    append({'state': 'tool_job_finished', 'forms_increment': 0, 'templates_increment': 0})
