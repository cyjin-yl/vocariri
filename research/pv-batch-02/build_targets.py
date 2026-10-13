#!/usr/bin/env python3
"""Build a prioritized public video ingest list from the frozen discovery register."""
import datetime as dt
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DISCOVERY = HERE / "source-discovery-register.jsonl"
OUT = HERE / "targets.jsonl"
CHECK = HERE / "validation.json"

PV_IDS = [
    "BV1H7411T73W", "BV1U1421S7wL", "BV1PW411S7Kj", "BV1VoeJ6iEpy",
    "BV1hiWnzQENg", "BV1LD8s6gEw2", "BV1k72LYzEmV", "BV1vs411D7WM",
    "BV1j94y147Rb", "BV1YAfzYnEan", "BV1QshW6wEgs", "BV1ue4y1e78R",
    "BV1zrbCzLEH4", "BV1xMG8zkEgg", "BV1BW411Y7Dk",
]
TUTORIAL_IDS = [
    "BV1sQhFziEwT", "BV1Xc8E6JEvf", "BV1QZ421W7Pm", "BV13bAuzKEz3",
    "BV1gi4y1j7kA", "BV1eryzYWEo6", "BV1ef4y167N6", "BV1qf4y117Wf",
    "BV1ZQBrBGE3A",
]
PAGE_HASHES = {
    "BV1sQhFziEwT": "12158c2e2ed2100aa53190b182c887e55e3ffacfe5b50a62383a7da6dd14f6a7",
    "BV1Xc8E6JEvf": "e72e73e58e2b85ab51cdd433834bbde8e9622af8c9e27f3826876bead1d3c83d",
    "BV1QZ421W7Pm": "1ca03a8084972a79edeb1b08849c7291f5e675a5f0df2b4cfba6111702dd36aa",
    "BV13bAuzKEz3": "83a659d7d8b977e096eb8cdbcedfa37a449229ac34e779e8847220b6ef007fb4",
    "BV1ZQBrBGE3A": "75414fe2510ecee70a5510aa04056a4cf9faa0cae811e0d472f5d151ca7be320",
}
PAGE_FILES = {bvid: f"sources/{bvid}.html" for bvid in PAGE_HASHES}
SEARCH_FILES = {
    "63adc4e24e5252351c404d690eb0785452ce1d12ac9e84a99f18d14280453f9d": "sources/bilibili-search-vocaloid-pv.html",
    "1d91b24b65de16378004b268458dbe3406c2cc21f5683eefb7b49a8e055d337d": "sources/bilibili-search-ae-lyric-pv.html",
}
SEARCH_URLS = {
    "63adc4e24e5252351c404d690eb0785452ce1d12ac9e84a99f18d14280453f9d": "https://search.bilibili.com/all?keyword=VOCALOID%20PV%20%E5%AD%97%E5%B9%95%E5%8A%A8%E7%94%BB%20%E5%88%B6%E4%BD%9C%E6%95%99%E7%A8%8B",
    "1d91b24b65de16378004b268458dbe3406c2cc21f5683eefb7b49a8e055d337d": "https://search.bilibili.com/all?keyword=AE%20%E6%96%87%E5%AD%97PV%E6%95%99%E7%A8%8B%20%E6%AD%8C%E8%AF%8D%E5%8A%A8%E7%94%BB",
}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    if OUT.exists() or CHECK.exists():
        raise SystemExit("batch outputs already exist; refusing overwrite")
    discovered = {row["bvid"]: row for row in read_jsonl(DISCOVERY)}
    selected = PV_IDS + TUTORIAL_IDS
    if len(selected) != len(set(selected)):
        raise SystemExit("duplicate BVID in target list")
    missing = [bvid for bvid in selected if bvid not in discovered]
    if missing:
        raise SystemExit(f"IDs absent from frozen discovery: {missing}")
    acquisition = read_jsonl(HERE / "sources" / "acquisition.jsonl")
    acquisition_by_url_hash = {(item["url"], item.get("sha256")) for item in acquisition}
    errors = []
    for digest, relpath in SEARCH_FILES.items():
        if not (HERE / relpath).is_file() or hashlib.sha256((HERE / relpath).read_bytes()).hexdigest() != digest:
            errors.append(f"search source hash mismatch: {relpath}")
    for bvid, digest in PAGE_HASHES.items():
        relpath = PAGE_FILES[bvid]
        if not (HERE / relpath).is_file() or hashlib.sha256((HERE / relpath).read_bytes()).hexdigest() != digest:
            errors.append(f"page source hash mismatch: {relpath}")
    expected = {(SEARCH_URLS[digest], digest) for digest in SEARCH_FILES}
    expected.update((f"https://www.bilibili.com/video/{bvid}/", digest) for bvid, digest in PAGE_HASHES.items())
    errors.extend(f"missing acquisition record: {url}" for url, digest in expected if (url, digest) not in acquisition_by_url_hash)
    if errors:
        raise SystemExit(json.dumps({"errors": errors}, ensure_ascii=False))
    rows = []
    for rank, bvid in enumerate(selected, 1):
        source = discovered[bvid]
        page_hash = PAGE_HASHES.get(bvid)
        rows.append({
            "batch_rank": rank,
            "candidate_class": "public_pv_candidate" if bvid in PV_IDS else "tutorial_or_project_candidate",
            "bvid": bvid,
            "title_from_search_metadata": source["title"],
            "public_url": source["video_url"],
            "page_metadata_hash": page_hash,
            "selection_basis": "Title/search metadata only; selected for first visual-ingest pass. This is not confirmation of video contents, accessibility, motion, or a distinct form.",
            "search_evidence": source["search_evidence"],
            "search_register_state": source["evidence_state"],
        })
    with OUT.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    check = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "input": {
            "path": "source-discovery-register.jsonl",
            "sha256": hashlib.sha256(DISCOVERY.read_bytes()).hexdigest(),
            "rows": len(discovered),
        },
        "selected": len(rows),
        "unique_bvids": len({row["bvid"] for row in rows}),
        "public_pv_candidates": sum(row["candidate_class"] == "public_pv_candidate" for row in rows),
        "tutorial_or_project_candidates": sum(row["candidate_class"] == "tutorial_or_project_candidate" for row in rows),
        "page_hashes_attached": sum(bool(row["page_metadata_hash"]) for row in rows),
        "acquisition_records_preserved": len(acquisition),
        "source_files_hash_checked": len(SEARCH_FILES) + len(PAGE_FILES),
        "preparation_events": [
            "An initial local copy attempt used a mistyped digest for BV13bAuzKEz3 and failed with file-not-found; the cache copy was repeated using the acquisition-ledger SHA-256. No source bytes were changed.",
            "The first target-build attempt reversed URL/hash values in its acquisition check and aborted before writing outputs; the check logic was corrected before generation.",
            "A second audit attempt compared a source filename to the acquisition URL and aborted before writing outputs; the audit now keeps source URL, local path, and digest in separate maps."
        ],
        "errors": errors,
    }
    CHECK.write_text(json.dumps(check, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(check, ensure_ascii=False))


if __name__ == "__main__":
    main()
