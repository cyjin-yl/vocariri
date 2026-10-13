#!/usr/bin/env python3
"""Build a deduplicated, metadata-only discovery register from cached Bilibili searches."""
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "acquisition.jsonl"
DESTINATION = ROOT / "video_discovery.jsonl"
SEARCHES = [
    (
        "https://search.bilibili.com/all?keyword=VOCALOID%20PV%20%E5%AD%97%E5%B9%95%E5%8A%A8%E7%94%BB%20%E5%88%B6%E4%BD%9C%E6%95%99%E7%A8%8B",
        "63adc4e24e5252351c404d690eb0785452ce1d12ac9e84a99f18d14280453f9d",
    ),
    (
        "https://search.bilibili.com/all?keyword=AE%20%E6%96%87%E5%AD%97PV%E6%95%99%E7%A8%8B%20%E6%AD%8C%E8%AF%8D%E5%8A%A8%E7%94%BB",
        "1d91b24b65de16378004b268458dbe3406c2cc21f5683eefb7b49a8e055d337d",
    ),
]
PATTERN = re.compile(r'bvid:"([^"\\]+)",title:"((?:\\.|[^"\\])*)"')


def main():
    if DESTINATION.exists():
        raise SystemExit(f"Refusing to overwrite {DESTINATION}")
    ledger = [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    ledger_by_url = {row["url"]: row for row in ledger}
    merged = {}
    raw_count = 0
    for url, digest in SEARCHES:
        source = ROOT / "cache" / digest
        if not source.is_file():
            raise SystemExit(f"missing cache object {digest}")
        acquisition = ledger_by_url[url]
        page = source.read_text(encoding="utf-8", errors="replace")
        found = 0
        for match in PATTERN.finditer(page):
            try:
                title = json.loads('"' + match.group(2) + '"')
            except json.JSONDecodeError:
                continue
            bvid = match.group(1)
            row = merged.setdefault(bvid, {
                "bvid": bvid,
                "video_url": f"https://www.bilibili.com/video/{bvid}/",
                "title": html.unescape(re.sub(r"<[^>]*>", "", title)),
                "evidence_state": "discovered_video",
                "media_inspected": False,
                "search_evidence": [],
            })
            row["search_evidence"].append({
                "url": url,
                "retrieved_utc": acquisition["retrieved_utc"],
                "sha256": digest,
            })
            found += 1
        raw_count += found
    with DESTINATION.open("x", encoding="utf-8", newline="\n") as stream:
        for row in merged.values():
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps({"search_result_rows": raw_count, "distinct_video_ids": len(merged), "output": str(DESTINATION.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
