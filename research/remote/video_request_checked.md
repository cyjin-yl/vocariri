# Checked Qwen video request (local candidate, not deployed)

`video_request_checked.py` is an alternative to the existing `video_request.py`.
It accepts only an MP4 short window (0.5–1.6 s), records every decoded frame's
PTS/time base with `ffprobe`, or with the installed `imageio_ffmpeg` executable's
`showinfo` filter when `ffprobe` is absent, and sends the original MP4 bytes.
The fallback requires one input duration, one filter time base, consistent
decoded dimensions, sequential frame numbers and integer PTS for every frame,
one `showinfo` filter instance, and a matching unambiguous final ffmpeg progress
frame count. Missing, ambiguous or
inconsistent fields fail closed. Because ffmpeg prints a rounded container
duration, a value too close to the 0.5 or 1.6 s boundary is rejected when its
display precision cannot establish the limit. An installed but failing `ffprobe` does not
trigger the fallback. The fallback uses `-fps_mode passthrough` and a null
output, with `-copyts` to retain input timestamps; it does not re-encode the
attached file or apply an fps filter. It
requests the actual decoded frame count and `do_sample_frames=false`; this is a request to
the current processor, not proof of its internal behavior. The client does not
run an fps filter, re-encode, or create a frame grid.

The CLI takes the same positional `video output` and `--source-id`, `--start`
fields as the old client. It also requires:

- `--native-pts-receipt`: a JSON file inside `/workspace` with `version: 1`,
  `clip_sha256`, `source_sha256`, `source_time_base` (rational string), and
  `source_pts` (one integer per decoded clip frame). Its claim about the source
  file must be independently verified. The client checks the exact clip hash,
  frame count, monotonicity, and elapsed source-versus-clip PTS relative to
  their first frames using exact rational arithmetic. Integer time-base
  quantization is allowed only within one tick of each representation, while
  every frame's drift must also remain strictly below half its nearest source
  frame gap so its index stays unambiguous. This rejects sustained 25 fps-like
  timestamp drift and a one-frame PTS gap; coarse, ambiguous conversions can
  also be rejected. It cannot detect duplicated pixels, establish pixel
  identity, or prove that the receipt came from the original.
  The independently supplied `--start` is a label, not verified against the
  source PTS origin. Duplicate JSON keys and non-rational time bases are
  rejected. The clip is re-read after probing and compared to the attached
  bytes, catching a file that remains changed at that check. This is not an
  atomic snapshot against a concurrent replace-and-restore of the source.
- `--route-pin`: an operator-reviewed JSON file **outside `/workspace`**, owned
  by the running user and mode 0600 on POSIX. It has `provider` set to
  `[redacted provider]`, `model` set to `[redacted model]`,
  `route_kind` set to `operator_verified_direct_self_hosted`, `base_url`
  exactly matching the protected OMP provider setting, and `allowed_ips`
  containing the independently checked private/Tailnet address(es). A pin
  belongs in protected per-user runtime/configuration storage, never Git.

The protected OMP `models.yml` is read **inside the process only** to resolve
its already configured authentication. It must be outside `/workspace` and
owned by the running user. On POSIX, mode 0600 is accepted. An owner-owned
group/other-readable file, including mode 0644 on a read-only bind, is accepted
only when effectively read-only and its resolved path is inside
the private home behind an owner-owned 0700 directory, every intervening
directory is owner-owned and not writable by others, and the file has no
outside hard link. The route pin has no such exception and remains mode 0600.
Agents must not inspect or print either file. Ambiguous duplicate mapping keys
in either protected file are rejected.
There is no model/provider fallback. The endpoint must use HTTPS with the
`/v1` base path. DNS must resolve exclusively to pinned private addresses; the
connection uses a checked IP directly, while TLS validates the pinned hostname.
It does not use environment HTTP proxies and never follows redirects. A
private address and operator assertion alone cannot prove that the server
does not relay to an external upstream; this needs independent operator review.
If the deployed endpoint lacks HTTPS or a reviewed route pin, the client
**fails closed**. No private hostnames or credentials are embedded in code.

The request always uses `thinking=true`, `reasoning_effort=xhigh` and no
user-imposed output-token limit. HTTP 200 must carry `text/event-stream`;
ordinary JSON responses and malformed/error SSE events fail closed. Accepted
SSE bytes are saved as `.events.sse`; an invalid event is withheld because
error payloads can contain sensitive server details. The status JSON saves
reasoning, answer, usage and termination for later review. All accepted server
text is marked untrusted research data and is never printed or executed.
Duplicate JSON keys and an unterminated final SSE event are rejected or withheld.
Terminal output contains only a fixed state/error category. Both the initial
status and later revisions publish atomically, and existing status or stream
files are never replaced by a fresh inference. A stream missing `[DONE]` or
a finish reason is incomplete, even if it contains partial answer text.

The operator must check fresh shared slot capacity and waiting queue before
each call. This client does not make a gateway metrics call. The existing
three-request/sequential seat limit, native source verification, processor
observability and independent frame comparison remain external work-order
gates. Nothing here changes the shared gateway, seat defaults or V2/MTP.

Offline tests (no DNS or model request):

```text
python -m unittest discover -s research/tests -p test_video_request_checked.py -v
```
