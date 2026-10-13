"""One actual official-main attempt each after retained pre-network guard failures."""
import datetime as dt
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
    with (ROOT / 'main-r2-job.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(row, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    assert not (ROOT / 'main-r2-job.jsonl').exists(), 'Existing corrected job requires reconciliation'
    old = [json.loads(x) for x in (ROOT / 'acquisition.jsonl').read_text().splitlines()]
    for item in IDS:
        rows = [x for x in old if x.get('id') == item]
        assert rows[-1]['state'] == 'failed' and rows[-1]['reason'] == 'unexpected cookie state'
        assert rows[-1]['bytes'] == 0 and rows[-1]['partial_files_retained'] == []
        assert not list((ROOT / 'sources' / item).iterdir())
    append({'state': 'corrected_main_tool_job_started', 'ids': IDS,
            'previous_failure_stage': 'before request send; synthesized public cookie guard',
            'no_main_network_replay': True, 'model_request_made': False})
    for item in IDS:
        append({'state': 'first_network_item_process_attempting', 'id': item})
        begun = time.monotonic()
        try:
            result = subprocess.run([sys.executable, '-u', str(ROOT / 'acquire-r2.py'), item], timeout=375)
            append({'state': 'corrected_main_process_completed', 'id': item,
                    'returncode': result.returncode, 'elapsed_seconds': round(time.monotonic() - begun, 3)})
        except subprocess.TimeoutExpired:
            append({'state': 'corrected_main_timeout_requires_reconciliation', 'id': item})
            break
    append({'state': 'corrected_main_tool_job_finished', 'forms_increment': 0, 'templates_increment': 0})
