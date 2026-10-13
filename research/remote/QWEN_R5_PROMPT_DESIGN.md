# Qwen R5b — native-video prompt proposal (2026-09-27)

## Status and basis

This is a **source-independent prompt design**, not a deployed client change or an inference result. It accepts **zero PV forms and zero templates**. The R5a work order prepares a different retained source/window offline; its chosen frames and observations are not assumed here, and its pane must remain untouched. Any R5a response requires its own transport gate and independent original-frame review before it can inform form acceptance.

Observed basis: the independent [R4 audit](../reviews/qwen-r4-independent-20260927/REVIEW.md) checked all 18 original frames of the `win-a-scale` control. The checked client currently asks broadly for frame-indexed entrances, occluders, anatomy and scale, yet its R4 answer placed `而` one frame early, put sharp `伤` too early, called pale shapes foreground occluders without overlap-order evidence, classified customized glyphs as Song/Ming, and promoted a possible blur mechanism into an observation. The remote checked-client file at `/tank/shared/projects/vocariri-research/checked-client-20260927/remote/video_request_checked.py` was read **only at the `PROMPT` lines and SHA-256**; it matched the local candidate `research/remote/video_request_checked.py` at SHA-256 `b93661cd6573ab1e5a95cfd7e83544b6379e23d2dec9192691618b2d89de952b`. Protected route/configuration and model service were not inspected.

The proposal cannot establish which frames the server processor actually presented to the model. The client's `do_sample_frames=false` request, decoded-PTS receipt and a model's `input_observed` self-report do not prove processor sampling or dimensions. An exact-index claim remains subject to the independent source-frame check.

## Candidate prompt text

Use this as the replacement value of `PROMPT` in a **separately reviewed future client version**. At request time append the client-decoded frame map described below; the map is timing metadata, not evidence that the vision processor displayed every frame. Do not include the R4 audit, R5a observations, a caption, or an answer key in the model request.

```text
Analyze the ATTACHED SILENT VIDEO as a short kinetic-typography window. Use the
1-based decoded-frame index map below for time labels. Describe only what the
visible frames support. The map comes from the client decoder, not from your
vision processor; if an image or transition is not resolved, say unknown or
give a bracketed interval. Do not claim you saw every indexed frame merely
because it appears in the map.

Return one valid JSON object, with no Markdown. Use the keys input_observed,
frames_used, groups, events, occlusion, typography, scale, anchoring,
uncertainties, and proposed_implementation. Use [] for no supported entries;
use null for an unknown boundary. Every nontrivial observation needs at least
one frame-indexed visual cue. Frame numbers must be within the map. If the
video was not visually observed, set input_observed=false, frames_used=[],
groups/events/occlusion/typography/scale/anchoring/proposed_implementation=[],
and explain the limitation in uncertainties. If you cannot tell which indexed
images were presented, frames_used may be []; never fill it from the map.
frames_used is a self-report, not proof of server frame selection.

For each distinct visible text group, assign a stable G1/G2/... ID. In groups,
give a short legible anchor (or null), frame-1 presence as visible/absent/unknown,
first_visible_frame, first_sharp_frame, last_visible_frame, end state and
frame-indexed evidence. If already present, first_visible_frame may be 1, but
its entrance time is unknown. Presence at frame 1 is NOT an entrance in this window.
Do not infer a glyph's earlier entrance or a later hold outside the decoded
window. For changed glyphs, record separate first visible (including faint or
streaked), first sharp and disappearance frames when resolvable. Keep a
staggered suffix distinct from the entrance of the entire group. If cropped,
blurred or illegible, use a shape description instead of guessing characters.

In events, describe actual before/after changes of glyphs, groups, line art,
objects and blur, with a stable event ID, target ID, change type, first/last supporting frames,
the visible cues at those frames and uncertainty. Do not require a minimum
number of events. Distinguish the outgoing blurred group from a newly sharp
group; do not name depth of field, rack focus, motion blur or cross-fade as an
observed cause merely because a group is smeared or changes sharpness.

In occlusion, list relevant rounded bars or other overlapping shapes. Give
overlap frame indices, an order of in_front_of_text/behind_text/undetermined,
and the pixel-level cue: a glyph stroke or line disappears at the shape's
boundary and reappears, a consistent T-junction, or a converse cue showing
text over the shape. Adjacency, pallor, darkness and blur alone do not prove
foreground order. If order is undetermined, retain the shape as an observation
without calling it a foreground mask.

In typography, describe each group's visible fill, outline, stroke weight,
terminals/cutouts, fine lines crossing or extending from glyphs, spacing,
crop and hierarchy where visible. Record custom geometry before considering a
font family. Set font identity/family to unknown unless a distinctive visual
feature rules out reasonable alternatives; do not substitute a generic
Song/Ming or sans-serif label for observed anatomy.

In scale, compare only the SAME identifiable glyph or rigid group across
indexed frames, noting fixed reference cues and crop/translation ambiguity.
Report growing, shrinking, stable or reversal only with a visible trajectory;
reversal needs a before/turn/after sequence. A larger glyph than its neighbor
is size hierarchy, not temporal scale direction. Use undetermined otherwise.
In anchoring, compare text/object positions with visible background landmarks
before calling motion screen-space or scene/object-space; use undetermined if
the landmarks or camera behavior cannot separate them. Describe visible layer
order separately from any proposed authoring graph.

Put uncertain identity, unreadable glyphs, mechanism, off-window timing and
processor visibility in uncertainties. Put optional reconstruction recipes
ONLY in proposed_implementation, linked to observed event IDs and labeled as
possible methods rather than source facts. Do not infer a character/voicebank
identity, intent, beat, lyric emotion or full lyric transcription from this
silent window. A short glyph anchor is enough.

DECODED FRAME MAP (timing metadata, not visual proof):
{frame_map}
```

The arrays are intentionally sparse rather than fill-in-the-blanks. A downstream reviewer should reject malformed JSON, out-of-range indices and ungrounded assertions; the model's JSON is untrusted data, never an automatically accepted annotation. A fixed schema can refine field names after an offline parser test, but must preserve the observed/uncertain/proposed split and the frame-cue requirement.

## Exact integration suggestion (not performed)

In `research/remote/video_request_checked.py`, keep the protected route and payload path unchanged. Replace only the `PROMPT` constant in a new, separately reviewed checked-client version. In `build_payload(video_bytes, video_probe, ...)`, calculate the 1-based map from its already decoded `video_probe['pts']` and `Fraction(video_probe['time_base'])`, relative to the first decoded PTS, and substitute it for `{frame_map}` in `messages[0]['content'][0]['text']`. The concrete insertion point is:

```python
base = Fraction(video_probe['time_base'])
pts = video_probe['pts']
frame_map = ', '.join(
    f'{i}={float((p - pts[0]) * base):.3f}s'
    for i, p in enumerate(pts, 1))
prompt_text = PROMPT.replace('{frame_map}', frame_map)
# Use prompt_text in the existing text content item; retain the video part.
```

For R4 this yields `1=0.000s`, `2=0.033s`, ..., `18=0.567s`. Label it explicitly as **clip decoded PTS**, not source identity or processor-observed frames. The native receipt still binds the clip cadence separately. Do not append an invented frame at nominal container duration. Reject a map/count mismatch or timestamps that collide at three-decimal display precision offline before making a request; use greater precision for such a clip and test it before integration.

Retain `reasoning_effort: xhigh`, `chat_template_kwargs.enable_thinking: true`, and **no `max_tokens`/`max_completion_tokens` or other user-imposed output cap**. Retain the video part, sampling policy, SSE capture, existing fail-closed route checks and `response_received_unreviewed` state. Do not inject the R4 expected answer into the prompt. A new prompt changes request behavior and should get a distinct client version/hash and exclusive output filenames; it does not reinterpret or overwrite R4's frozen record. A separate authorization and fresh capacity/route gate are needed before any inference; this document grants neither.

## Falsifiable evaluation before adoption

1. **Offline payload check:** with the frozen 18 PTS, the map has exactly indices 1–18, starts `1=0.000s`, ends `18=0.567s`, has no `19=0.600s`, and is strictly increasing at displayed precision. Parse a canned response with the expected keys; reject an out-of-range frame, malformed JSON and an exact entrance with no frame-indexed evidence field. Whether its cited cue actually exists is a separate visual-review question. Verify the request construction still has xhigh/thinking and no output cap, with no network request.
2. **R4 calibration, independently judged:** after a separately authorized one-request run, compare against the 18 originals, not the model's reasoning. A usable answer must distinguish `非常痛苦` already visible at frame 1 from `而` by frame 2; `悲` at frame 4, a faint/streaked right glyph during frames 5–7 and sharp `伤` by frame 8; the old group smeared by frame 10, a residual by frame 15, and the new sharp group at frames 16–18. Allow an honest uncertainty interval for unresolved faint glyphs. No hold beyond frame 18 is supported. At least the suffix reveal and outgoing/new group handoff must be captured with boundaries within one decoded frame; an all-unknown answer fails recall even if it makes no false claims.
3. **R4 false-positive checks:** pale forms at frames 1–2 must not be called foreground occluders without an actual covering cue. The pale illustration can be described behind text at frames 8–9 and changed toward the right at frame 10, without naming a voicebank or inventing a fade. Typography must preserve thick block-like/wedge or cutout anatomy and fine parallel horizontal line treatment instead of asserting Song/Ming identity. Scale direction remains undetermined without a same-glyph trajectory. Blur may be observed; depth-of-field/rack focus/cross-fade must be quarantined as proposals. Any unsupported high-confidence foreground order, font family, scale reversal or mechanism fails the critical-claim gate.
4. **Independent R5a transfer check:** first obtain its offline-passing native clip/receipt and an independent original-frame annotation from another seat. Without inserting those annotations into the request, test the same candidate on that different source only after a distinct authorization and transport/processor gate. The reviewer checks changed glyph/group boundaries, first/last visible and sharp states, object overlap order, custom anatomy, same-glyph scale and anchoring against its actual frames. Success on R4 alone is calibration, not transfer. Report missed events as well as hallucinated ones; no form or template count follows from a prompt pass.
5. **Transport limit:** preserve `server_sampling_verified=false` until an independent processor-side check establishes the presented frame count/dimensions/selection for this exact model/template. Without that check, describe visual-index performance as conditional on the returned clip and independent frame agreement, never as proof that all 18 frames reached the model.

## Handoff and boundaries

The next implementer can start from the matching checked-client SHA above and this candidate text, make an isolated version, add an offline map/schema test, then request independent review before any inference. R5a continues in its own visible pane and supplies a new source/window only after its offline evidence is finished. The R4 audit is the correction layer; its original clip, frames, response and SSE stay frozen. No client file, OMP pane, protected configuration, model service, source media or shared form ledger was changed for this proposal. No inference, push or publication was performed.
