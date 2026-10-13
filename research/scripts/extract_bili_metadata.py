#!/usr/bin/env python3
"""Extract minimal public Bilibili search-result titles and IDs from a cached page."""
import argparse
import html
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_file", type=Path)
    args = parser.parse_args()
    page = args.cache_file.read_text(encoding="utf-8", errors="replace")
    results = []
    pattern = re.compile(r'bvid:"([^"\\]+)",title:"((?:\\.|[^"\\])*)"')
    for match in pattern.finditer(page):
        bvid = match.group(1)
        escaped_title = match.group(2)
        try:
            title = json.loads('"' + escaped_title + '"')
        except json.JSONDecodeError:
            continue
        title = re.sub(r"<[^>]*>", "", html.unescape(title))
        results.append({"bvid": bvid, "title": title})
    print(json.dumps({"count": len(results), "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
