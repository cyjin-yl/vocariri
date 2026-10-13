#!/usr/bin/env python3
"""Bounded, no-redirect HTTP acquisition with content-addressed immutable cache."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache"
LEDGER = ROOT / "acquisition.jsonl"
MAX_BYTES = 2 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def acquire(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "VocaRiri-Public-Research/1.0"})
    opener = urllib.request.build_opener(NoRedirect())
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    status = None
    payload = b""
    error = None
    try:
        with opener.open(request, timeout=20) as response:
            status = response.status
            payload = response.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                payload = payload[:MAX_BYTES]
                error = "truncated_at_limit"
    except urllib.error.HTTPError as exc:
        status = exc.code
        error = "http_error"
    except Exception as exc:
        error = type(exc).__name__
    digest = hashlib.sha256(payload).hexdigest() if payload else None
    cache_path = None
    if payload and status is not None and 200 <= status < 300:
        CACHE.mkdir(parents=True, exist_ok=True)
        dest = CACHE / digest
        if not dest.exists():
            with dest.open("xb") as f:
                f.write(payload)
        cache_path = str(dest.relative_to(ROOT)).replace("\\", "/")
    record = {
        "url": url,
        "retrieved_utc": timestamp,
        "http_status": status,
        "bytes": len(payload),
        "sha256": digest,
        "cache_path": cache_path,
        "error": error,
    }
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="+")
    args = parser.parse_args()
    for url in args.url:
        print(json.dumps(acquire(url), ensure_ascii=False))
