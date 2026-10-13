# MP4 tail-frame diagnostic checkpoint — 2026-09-27

Status: One candidate is suitable for a formal R3b replay. This is an offline clip/receipt preflight, not a Qwen observation or a final R3b acceptance.

## Observations

- Source SHA-256 `9ab2c3cf22f64965ba76642c7fbb8d5fc8e760e51349d31692305a2f43ee84d7`; R3a MP4 SHA-256 `2c350b3886619f0492119abb474a98e078ae6181e6597ffedaf270ea256fdc59`. Rechecked in the container. FFmpeg: imageio_ffmpeg `7.0.2-static`.
- Source filter `select=between(n\,4258\,4275)` decoded 18 frames with time base `1/16000` and absolute PTS `[2271056,2271584,2272128,2272656,2273184,2273728,2274256,2274800,2275328,2275856,2276400,2276928,2277456,2278000,2278528,2279056,2279600,2280128]` (`source-check.json`, `source-scan.stderr`).
- Direct MP4 with `-fps_mode vfr`: SHA-256 identical to R3a, 17 decoded frames, missing relative PTS 9072; checked-client receipt failed `native_receipt_invalid` (`vfr-result.json`).
- MKV encode then MP4 stream-copy remux: `remux.mp4` SHA-256 `810e39509b34646f2432164e843231671e3b34a6099398b8fa48fb3c30d32653`, 209933 bytes, 18 decoded frames with time base `1/16000`, relative PTS `[0,528,1072,1600,2128,2672,3200,3744,4272,4800,5344,5872,6400,6944,7472,8000,8544,9072]`, exactly source PTS minus 2271056 (`remux-recheck-result.json`). The checked-client `probe_video` and `validate_native_receipt` passed, reporting duration 0.6 seconds and test-receipt SHA-256 `7dc39807c9dbeac9c8c28a3fd56e9eaa0f26a386333119d013d1d90d6e2ba352`. Client module SHA-256 `b93661cd6573ab1e5a95cfd7e83544b6379e23d2dec9192691618b2d89de952b`.
- Independent `framemd5` decode of `remux-input.mkv` and `remux.mp4` yielded 18 frames each, identical MD5 for every decoded frame; last-frame MD5 `17cfec79862f56d9f5d74ef399b4489f`.

## Reproduction

Within `[research container]` container at `/workspace`, use `/opt/pv-tools/bin/python r3atmp/codex-taildiag-20260927-7e2c/offline_check.py`. It invokes only the checked-client preflight and receipt verifier; it sends no model request. The exact encoder/muxer argv is in `diag.py` `method_remux`; inputs are original source and selected frame indices 4258–4275. Intermediate MKV SHA-256 `8404fb7a8d61a16f0b95bcc44821d42fd110d31371e50ba6acdfc9b8f4c9429f`.

## Failure and inference

The initial remux run under system `python3` completed encode/decode but crashed at checked-client import (`ModuleNotFoundError: yaml`), so no `remux-result.json` exists. Its logs and MP4 remain. The existing MP4 was then rechecked under `/opt/pv-tools/bin/python` with separate `remux-recheck-*` logs and test receipt. A preliminary shell probe also failed due nested Windows/SSH quoting and changed no files. The `tail` method was not run because remux passed. The evidence shows the alternate container path preserves the final decoded frame; it does not independently establish an `stts/ctts` root cause.

No model request, Qwen pane input, source/R1–R3a mutation, shared receipt mutation, or formal R3b copy was performed. Formal R3b still needs an exclusive copy, its own receipt and downstream observation/acceptance.
