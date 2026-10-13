# Tail-frame candidate handoff — 2026-09-27

## Status and key caution

`remux.mp4` passes 18/18 decoded frames, exact relative source PTS and offline checked-client receipt validation. It is a diagnostic candidate only; no formal R3b media, receipt or Qwen run has been made. The original direct MP4 VFR path still yields 17 frames. The MP4 sample-table root cause remains unproven.

## Paths and mapping

- [remote host] host source: `/tank/shared/projects/vocariri-research/r3atmp/codex-taildiag-20260927-7e2c/remux.mp4`.
- CT102 source: `/workspaces/vocariri-research/r3atmp/codex-taildiag-20260927-7e2c/remux.mp4`.
- `[research container]` and its Qwen pane source: `/workspace/r3atmp/codex-taildiag-20260927-7e2c/remux.mp4`.
- Proposed formal R3b destination, not created: [remote host] `/tank/shared/projects/vocariri-research/evidence/native/win-a-scale-native-r3b.mp4` = CT102 `/workspaces/vocariri-research/evidence/native/win-a-scale-native-r3b.mp4` = container `/workspace/evidence/native/win-a-scale-native-r3b.mp4`. It was absent at the check; check again before copying.
- Reproduction and evidence in the same diagnostic directory: `diag.py`, `offline_check.py`, `source-check.json`, `remux-recheck-result.json`, `remux-recheck-test-receipt.json`, `vfr-result.json`, logs, `CHECKPOINT.md`, `artifact-manifest.json`.
- Original source (read only): container `/workspace/media/BV1zrbCzLEH4/source.mp4`. Checked-client module: `/workspace/checked-client-20260927/remote/video_request_checked.py`.

## Environment and exact candidate method

Connect through `tailscale ssh [user]@[remote host]`; CT102 command prefix: `sudo -n pct exec 102 -- docker exec --user 1000:1000 -w /workspace [research container]`. `/workspace` is a bind mount of CT102 `/workspaces/vocariri-research`, itself mapped from [remote host] `/tank/shared/projects/vocariri-research`. FFmpeg binary is `/opt/pv-tools/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2`; checked-client Python is `/opt/pv-tools/bin/python`. No `ffprobe` is installed in this container; checked-client uses its imageio_ffmpeg fallback.

Run the two argv arrays in `diag.py:method_remux`: first select source video frames 4258–4275, `setpts=PTS-STARTPTS`, `-fps_mode passthrough`, `-enc_time_base filter`, encode libx264 CRF 12 yuv420p to `remux-input.mkv`; then `-c:v copy -video_track_timescale 16000 -movflags +faststart` from that MKV into `remux.mp4`. The source filter/exact arguments are in the script; do not substitute a direct MP4 encode. This path has not proved why the prior mux lost its tail frame.

## Formal copy procedure for the Qwen R3b work order

In the same container, after confirming the proposed destination is still absent, copy only the verified MP4 with exclusive creation, then rehash. Never overwrite an existing R3b or R1–R3a file. A copy command that fails if destination exists:

```python
from pathlib import Path
import hashlib, shutil
src = Path('/workspace/r3atmp/codex-taildiag-20260927-7e2c/remux.mp4')
dst = Path('/workspace/evidence/native/win-a-scale-native-r3b.mp4')
expected = '810e39509b34646f2432164e843231671e3b34a6099398b8fa48fb3c30d32653'
assert hashlib.sha256(src.read_bytes()).hexdigest() == expected
with src.open('rb') as inp, dst.open('xb') as out:
    shutil.copyfileobj(inp, out)
assert hashlib.sha256(dst.read_bytes()).hexdigest() == expected
```

If exclusive open fails or the post-copy hash differs, stop and reconcile, retaining both artifacts. Formal receipt creation/validation and Qwen observation belong to the separate R3b work order; the diagnostic `remux-recheck-test-receipt.json` is a test fixture, not the shared receipt.

## Checked offline result and next gate

Command in `[research container]`: `/opt/pv-tools/bin/python r3atmp/codex-taildiag-20260927-7e2c/offline_check.py`. It pins client module SHA `b93661cd6573ab1e5a95cfd7e83544b6379e23d2dec9192691618b2d89de952b`, pins candidate SHA, runs `probe_video`, then `validate_native_receipt`, and asserts 18 frames with source-relative PTS. Observed receipt SHA `7dc39807c9dbeac9c8c28a3fd56e9eaa0f26a386333119d013d1d90d6e2ba352`. Independent acceptance by another seat is pending. Once that passes, the coordinator can dispatch the formal R3b copy/receipt/model work in the existing Qwen pane.

## Do not touch; known gaps

Do not alter original source, R1–R3a, checked-client, Qwen pane/config, shared receipts, or unrelated `/workspace` content. No external model request was made. Initial system Python lacked `yaml`; use `/opt/pv-tools/bin/python` for checked-client. VFR yielded the same 17-frame MP4 as R3a. A `tail` candidate was intentionally not run once remux passed. This package stays in the exclusive diagnostic directory; no Git commit/push or cross-project export was performed.
