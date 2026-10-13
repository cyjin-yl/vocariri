# Video input for motion research

Enable Qwen thinking and use an effort supported by the deployed template. The current template supports `xhigh`, `medium`, and `low`; the research client defaults to `xhigh`. Do not impose output-token or prompt word-count limits. Preserve streamed events, reasoning presence, final answers, usage and termination status.

Temporal sampling and spatial resolution are separate controls. In the tested Qwen3-VL video processor, `size.longest_edge` contributes a **whole-video pixel budget**. Treating it like a single-image size can destroy detail when frame count increases.

CPU replay with the installed processor and the same 512 × 288 clip:

| Requested frames | Whole-video budget | Processed frame dimensions | Vision tokens |
| --- | --- | --- | --- |
| 8 | 262,144 | 224 × 128 | 112 |
| 32 | 262,144 | 96 × 64 | 96 |
| 32 | 4,718,592 | 512 × 288 | 2,304 |

The old 8-versus-32 comparison therefore also changed spatial detail. Increasing input token counts alone did not establish more visual detail: timestamps and placeholders also contribute to those counts.

`research/remote/video_input_policy.py` budgets pixels from frame count and intended frame dimensions. The client defaults to 32 frames and a 768px long-edge target, preserving source size for smaller clips. These are input/performance settings, not generation limits. Frame dimensions are aligned to the tested processor's 32px spatial lattice; the audit records the intended dimensions, not an assertion that all future processors will emit them unchanged.

The decoder already selects frames. The client explicitly passes `do_sample_frames=false` to the HF processor, including when a short video has fewer frames than requested. Otherwise the decoder's all-frames metadata can allow a second sampling step. Recheck actual decoder and processor outputs when upgrading the model/runtime.

Verify derived clips rather than trusting conversion arguments: source hash, first source frame, actual output FPS, decoded frame count, duration and processed dimensions. A first short-window conversion unexpectedly produced 25fps clips; those files and responses were retained, and a separately named 30fps version was generated and checked before its rerun. A requested native frame rate is not evidence of native-rate output.

The spatial-budget fix is request-local. It does not change the shared inference server's V2 runner, MTP or slot configuration. Earlier synthetic-image errors remain a separate unresolved incident. Improved descriptions do not establish exact easing, source layer structure or commercial-template acceptance.
