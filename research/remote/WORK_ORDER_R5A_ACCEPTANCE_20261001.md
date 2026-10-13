# R5a independent offline acceptance

## Scope and workspace

Independently review the retained DECO lyric-video R5a preparation. Work in the Vocariri research workspace; obey the project AGENTS.md. This is public-media research. Do not inspect unrelated private repositories or model/provider authentication.

## Read first

Read `remote/WORK_ORDER_QWEN_DECO_R5A.md`, `remote/video_request_checked.py`, and the six files in `cache/r5a-acceptance-20261001/`. Producer observations and status are claims under review, not acceptance evidence. Use file listings and JSON keys to confirm actual structure; do not assume paths or fields.

## Inputs

The input directory contains `source.mp4`, `source.json`, `deco-ki-native-r5a.mp4`, `deco-ki-pts-r5a.json`, `qwen-r5a-deco-window.json`, and `qwen-r5a-deco.status.json`. Coordinator verified six transport SHA-256 values; independently recompute them. Available local decoder: `C:/Program Files/Common Files/AEJuice/ffmpeg.exe`. Other installed decoder tools may be used without changing global configuration.

## Steps

1. Independently decode source native frames 519 through 554, preserving showinfo integer PTS/timebase and raw yuv420p checksums. Decode clip without imposing a nominal frame rate. Compare all 36 absolute source PTS and all 36 relative clip PTS to the receipt, and compare recorded source-frame MD5s. Record decoder version and any version-dependent pixel mismatch honestly.
2. Run the retained client's offline native receipt validator against actual clip bytes. Add independently chosen falsifying receipt variations, including nonterminal PTS, reordered PTS, hash, and source timebase changes. Freeze the real receipt; use copies only.
3. Inspect native resolution source frames visually with view_image. A contact sheet can locate transitions but does not alone establish glyph anatomy. Inspect both sides of each reported glyph entrance and the same-glyph scale trajectory. Record actual inspected filenames/PTS. Verify glyph identification, font stroke contrast, occlusion order, positions, grouping and what remains unknown. Never infer a precise implementation, identity, lyric meaning or emotion from silent frames alone.
4. The failed MKV intermediate is not in this six-file transfer. State that limit; do not invent inspection of it. Independently test timestamp quantization if local tools permit and label it as a separate replication rather than the original failed artifact.
5. Write new `reviews/r5a-independent-20261001/REVIEW.md`, `review.json`, extraction/check scripts and logs, original-resolution selected frames and a hash manifest excluding itself. Preserve inputs and producer records unchanged. Outputs are original observations and conditional implementation guidance; no finished form or template counts.

## Acceptance

Separate transport pass/fail from visual claim acceptance. Conclusion must be `pass`, `conditional_pass` or `fail`, with concrete missing evidence and the next permitted action. A request-level video inference can proceed only if the real transport contract passes; it does not prove server-side all-frame processing. Reviewed form and finished-template increments remain zero.

## Boundaries and interruption

Offline only: no model API calls, download, service/config change, publication, source deletion or overwrite. Preserve existing unrelated work. If tools, quota or visual decoding fail, save completed steps and exact next action in `status.json`; do not spin on retries. Final reply names real files and checks rather than trusting producer prose.
