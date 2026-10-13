# PV batch 02

This directory stages a prioritized public URL list for remote visual ingest. It contains no downloaded media and makes no claim that any title identifies a matching PV, that a URL remains accessible, or that an interval exhibits a particular effect.

`targets.jsonl` contains 24 unique Bilibili video URLs selected from the existing 76-ID public search register: 15 PV candidates and 9 tutorial/project candidates. Five candidates have existing page-metadata hashes in the parent corpus. All other entries have search-title evidence only. Parent-search response bodies and hashes remain in `../cache/`; the source register hash is recorded in `validation.json` and `artifact-manifest.json`.

The owner has authorized normal public video download for remote frame-by-frame analysis. This batch is for parent-side ingestion on the authorized remote storage path. Do not use authentication state, access codes, private sources, or bypasses. Keep remote media outside this repository. This batch is a URL shortlist, not a motion dataset; observations must be added only after actual frames or intervals are inspected.

Regenerate only if outputs are absent: `python build_targets.py`. The script refuses to overwrite outputs. The acquisition/inspection receipt should be recorded by the ingesting agent after an actual attempt; no video download has occurred in this preparation step.
