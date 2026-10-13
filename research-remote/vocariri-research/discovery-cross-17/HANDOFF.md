# Cross-source batch 17 handoff (2026-09-27)

## One-line state

Three public videos have immutable cached originals, directly inspected sparse and half-second PTS frames, and a successful offline byte-for-byte frame replay; no motion form or template has been accepted.

## What the next reviewer needs to know

- The three originals are official Project Voltage YouTube `C-7TIDIKc98`, Niconico Scratch-title `sm46155083`, and Niconico Alight Motion/Blurrr-title `sm46137276`. Visual evidence supports three contrasting treatments, but title claims do not establish VOCALOID identity, an editable source, a particular font, or use of Blurrr. The Alight Motion watermark is visible in the third source.
- The AE tutorial `sm46546276` is still metadata-only. Its corrected download reached the 360-second limit with about 29 MB of fragments. Partial bytes are retained for reconciliation, **not** a verified original. Its title's “13” has not been counted as forms.
- `observations.json` links every visual claim to cached-media PTS and records conditional lyric/emotion applicability separately from observed source context. Audio and complete timelines were not reviewed. Counts remain **3 screened sources, 0 accepted forms, 0 accepted templates**.
- `verification.json` reports 3 source hashes and 101 generated frames (36 sparse, 65 short-window) replayed offline with zero errors. This is script reproducibility, not an independent aesthetic acceptance. `artifact-manifest.json` is the package hash inventory and intentionally omits itself.
- Early attempts on three sources failed because the first yt-dlp selector required combined audio/video. A metadata-only diagnosis showed separate tracks, and the corrected selector succeeded for the three cached originals. Keep those failures in the ledger.

## Paths

| Purpose | Path |
|---|---|
| Remote independent batch | `/workspaces/vocariri-research/discovery-cross-17` in CT102 (`/tank/shared/projects/vocariri-research/discovery-cross-17` from the host) |
| Local ignored review cache | `[project root]\research\cache\discovery-cross-17` |
| Originals and source records | remote `sources/<id>/source.*`, `sources/<id>/source.json` |
| Request history | remote `acquisition.jsonl`, `diagnostic.jsonl` |
| Sparse and dense evidence | remote `derived/<id>/`, `sequences/<id>/`; locally copied hash-checked sheets under `<id>/` |
| Visual observations | remote/local `observations.json` |
| Offline check and package inventory | remote `verification.json`, `artifact-manifest.json` |

## Execution environment

- SSH alias `[remote host]`; CT102 commands use `sudo -n /usr/sbin/pct exec 102 -- ...`. The helper image is `vocariri/research-tools:20260924` (inspected image ID begins `d5ce0193`), run as uid/gid 1000 with only the batch directory mounted at `/work`. No running agent container or existing media directory was changed. No remote Agent was started; these were bounded one-shot helper processes, so no tmux Agent seat is claimed.
- Acquisition script caps a video at 180 MiB and 18 minutes and each process at 360 seconds, has zero retries, no cookies/login, and stops urllib 3xx redirects. Native HLS downloads are requested. It records a logical source attempt; yt-dlp's internal individual HTTP requests/statuses and any non-urllib redirect behavior are not independently audited. `http_status: null` means unknown, not success/failure.
- Scripts `acquire.py`, `acquire-v2.py`, `extract.py`, `sequence.py`, `sequence-v1.py`, `diagnose.py`, `verify.py` are in the remote batch. The earlier selector version's three failed attempts are retained in the ledger; its exact script file was not preserved.

## Do not touch

- Do not put third-party video or frame images into Git, application assets or Qwen formal R3b paths. They are research cache only. Do not edit the running `[research container]` or `[research container]-luna` workspaces, sources, or tmux panes.
- Do not treat cached thumbnails, titles, watermarks, sparse frame changes or script replay as full motion review or aesthetic acceptance. Do not count the AE title's claimed methods or partial fragments.
- Do not retry the timed-out tutorial blindly. Reconcile its retained fragments and route limits first. No login, cookies, browser state, access bypass or redistribution is authorized.

## Next steps

1. **Independent acceptance gate:** review `artifact-manifest.json`, `verification.json`, ledger and PTS sheets against `observations.json`; report unsupported claims or hash mismatches. A producer's verifier alone is insufficient to accept forms.
2. For any form to count, watch or densely inspect the relevant full shot and neighboring shots with audio where available, distinguish actual lyric typography from framing/captions and background dance, and document a reproducible interval plus an independent reviewer record.
3. Resolve source song/vocal-synth and editable-project identity only from primary evidence. The paired Nico `sm43084181` is a separate edition whose visual identity with the YouTube MV is unknown.
4. If the AE tutorial is still valuable, decide on a separately authorized, bounded reconciliation of its partial fragments and duration; preserve the current failure either way.

## Known limitations

- The metadata title-page caches originate in batches 15 and 16. Batch 17's verified media and frame evidence is separate from those pages.
- The `source-intake` per-HTTP-request ideal is not fully met by opaque yt-dlp extraction. The ledger contains source-level attempts, result bytes/status when exposed, and exact source URLs, while CDN/fragment request statuses are unknown. Do not claim request-level completeness.
- PTS values come from cached files after downloader remux and are not proven to match the platform's original stream timeline. Half-second sampling misses faster events, and audio/emotion fit remains unknown.
