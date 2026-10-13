"""Read-only ID and title dedup audit of the existing remote public-media cache."""

import json
from pathlib import Path
import unicodedata
import hashlib
import datetime as dt

ROOT = Path("/tank/shared/projects/vocariri-research")
TARGET_IDS = {"C-7TIDIKc98", "sm43084181", "sm46546276", "sm46155083", "sm46320139", "sm45786816"}
WORK_TITLES = ["ボルテッカー", "文字PVの作り方13選", "個々々々々々人", "ライアーダンサー", "アンノウン・マザーグース"]


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


items = []
for prefix in (ROOT / "media", ROOT / "luna-public/media"):
    for path in prefix.glob("*/source.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        items.append({"id": str(row.get("id", "")), "title": str(row.get("title", "")),
                      "url": str(row.get("url", "")), "metadata_path": str(path.relative_to(ROOT))})

matches = [row for row in items if row["id"] in TARGET_IDS or any(normalized(title) in normalized(row["title"]) for title in WORK_TITLES)]
ledger_matches = {}
for name in ("acquisition.jsonl", "discovery.jsonl"):
    path = ROOT / name
    if path.is_file():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        ledger_matches[name] = {"rows": len(lines), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                "target_id_hits": {target: sum(target in line for line in lines) for target in sorted(TARGET_IDS)}}

print(json.dumps({"checked_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                  "media_metadata_rows": len(items),
                  "media_metadata_index_sha256": hashlib.sha256(json.dumps(items, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                  "matches": matches,
                  "ledger_matches": ledger_matches}, ensure_ascii=False, indent=2))
