#!/usr/bin/env python3
"""Read only public, embedded Bilibili page metadata from an acquired response."""
import argparse
import gzip
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_file", type=Path)
    args = parser.parse_args()
    payload = args.cache_file.read_bytes()
    if payload.startswith(b"\x1f\x8b"):
        payload = gzip.decompress(payload)
    page = payload.decode("utf-8", errors="replace")
    marker = "window.__INITIAL_STATE__="
    start = page.find(marker)
    if start < 0:
        raise SystemExit("No embedded initial-state JSON found")
    state, _ = json.JSONDecoder().raw_decode(page[start + len(marker):])
    video = state.get("videoData", {})
    description = video.get("desc", "")
    urls = sorted(set(re.findall(r"https?://[^\s<>\"']+", description)))
    output = {
        "bvid": video.get("bvid"),
        "title": video.get("title"),
        "duration_seconds": video.get("duration"),
        "published_epoch": video.get("pubdate"),
        "thumbnail_url": video.get("pic"),
        "description_characters": len(description),
        "description_external_urls": urls,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
