"""Offline smoke test for batch-18 HTTP byte and redirect receipt hooks."""

import email.message
import io
import json
import tempfile
import urllib.error
import urllib.request
import urllib.response
from pathlib import Path

import acquire
from yt_dlp.networking import _urllib

with tempfile.TemporaryDirectory() as root:
    acquire.ROOT = Path(root)
    acquire.CURRENT_ID = 'SELFTEST'
    response = urllib.response.addinfourl(io.BytesIO(b'abc'), email.message.Message(),
                                          'https://example.test/object', code=200)
    adapter = _urllib.UrllibResponseAdapter(response)
    tracker = {'request_id': 'test-1', 'url': 'https://example.test/[path-and-query-redacted]',
               'http_status': 200, 'bytes_read': 0, 'response_handler': type(adapter).__name__,
               'in_read': False, 'done': False}
    adapter._batch18_tracker = tracker
    assert adapter.read(2) == b'ab'
    assert adapter.read() == b'c'
    adapter.close()
    assert tracker['bytes_read'] == 3 and tracker['done']
    try:
        acquire.stop_redirect(None, urllib.request.Request('https://example.test/a'),
                              io.BytesIO(), 302, 'Found', {'Location': 'https://other.test/b?token=x'},
                              'https://other.test/b?token=x')
    except urllib.error.HTTPError as exc:
        assert exc.code == 302
    else:
        raise AssertionError('redirect unexpectedly followed')
    rows = [json.loads(line) for line in (Path(root) / 'network-requests.jsonl').read_text().splitlines()]
    assert rows[0]['bytes_read'] == 3 and rows[0]['http_status'] == 200
    assert rows[1]['state'] == 'redirect_blocked' and rows[1]['http_status'] == 302
    assert 'token=x' not in json.dumps(rows)
print('offline request hook smoke test passed')
