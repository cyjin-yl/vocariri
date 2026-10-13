# Handoff

## Goal

Build a source-grounded, distinct set of lyric-PV/template observations in this directory. The 500-observation number is a target; count generic primitives separately from actual template items and authored PV compositions.

## Current state

- Read-only duplication audit is in `WORK_ORDER.md`.
- The parent corpus had 42 rows (32 generic effects, 10 candidate videos) and its separate discovery ledger had 76 distinct videos, all not media-inspected.
- Four prioritized public Bilibili previews are in `priority-media.md`. They are candidates only.
- No sources have yet been acquired into this batch. Continue to append every HTTP attempt, including errors, to `acquisition.jsonl`; cache exact response bytes immutably under `cache/`.
- Parent is checking remote media storage. Do not download preview media in bulk to local disk; provide prioritized URLs and await destination/status before larger transfers.

## Constraints

Only edit `[project root]/research/template-batch-02/`. Public HTTP/CLI only; no browser UI. No credentials, paywall bypass, paid project assets, third-party contact, publication, or parent corpus/report changes. Owner authorizes public `yt-dlp` preview download and frame analysis; visual model routing is Luna/Qwen only, Flash text-only.

## Next action

Identify diverse candidate packs and their individually inspectable items (Japanese/Chinese tutorials and AE template ecosystems). For each candidate, first inspect the public source page/preview metadata, verify access and license status, then plan bounded frame sampling. Keep metadata-only discoveries in a candidate list until visual/source inspection supports an observation.
