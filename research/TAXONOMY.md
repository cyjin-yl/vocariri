# Provisional annotation taxonomy

Every entry below is a testable visual category, not an observed result. No PV frames were accessible in this run. Use tags only after frame inspection; use `unknown` when evidence is insufficient.

| Family | Visual unit to annotate | Observable behavior to look for | Candidate 2D mechanism | Current evidence |
|---|---|---|---|---|
| Lyric as kinetic graphic | Glyph, mora/syllable grouping, word, line | Per-character timing; tracking/baseline changes; size contrast; type occlusion; text used as image or shape | Glyph/word transforms, vector masks, outline/fill layers, timed clipping | Hypothesis only |
| Layered dense stage | Type, illustration/cutout, graphic plane, background | Overlap, deliberate cropping, foreground/background exchange, parallax, visual density changes | Layer groups, depth order, pivot transforms, 2D virtual camera | Hypothesis only |
| Choreographed framing | Whole composition or nested panel | Snap zoom, pan, tilt, roll, push through a mask, reframing that anticipates the next layout | Camera transform, parented layer motion, nested scenes, beat/phrase keyframes | Hypothesis only |
| Motif mutation | Repeated icon, silhouette, object, shape, or word form | Recurrence changes in scale, count, orientation, crop, fill, color, or semantic relation | Reusable shape layers with keyframed state and instance transforms | Hypothesis only |
| Panel/collage grammar | Frame subdivision, paper/image layer, texture plane | Inset/split panels, grid changes, shuttering, photocopy/halftone/torn-edge appearance, text crossing boundaries | Nested masks, panel mattes, texture overlays, independent paper-plane transforms | Hypothesis only |

## Transition labels

- `hard_cut`: abrupt source/layout replacement; musical alignment must be checked separately.
- `match_cut`: a shape, position, direction, or type silhouette carries across the cut.
- `type_matte`: letters or words reveal/conceal the next visual field.
- `shape_matte`: a graphic silhouette expands, contracts, or wipes the scene.
- `panel_shutter`: a split frame opens/closes or replaces regions in sequence.
- `directional_wipe`: an edge or plane travels through frame; record direction and duration.
- `scale_through`: camera/graphic scale movement bridges layouts through a focal point or shape.
- `smear_or_whip`: motion blur/smear or rapid pan visually carries into a new composition.
- `fragment_or_reassemble`: type/image breaks into pieces or resolves from pieces; distinguish observed layers from compression artifacts.
- `unknown`: transition is visible but its operation or cause cannot be reliably classified.

For every transition, record entry/exit state, observed interval, duration, direction, trigger hypothesis, confidence, and linked frame/interval evidence. A beat or syllable trigger is only confirmed when the segment is synchronized against accessible audio; otherwise record `trigger: unverified`.

## Style matching to the user's request

The review criterion is ornate, unmistakably VOCALOID lyric-PV motion: dense composition, rhythm-aware typography, layered dramatic transitions, and camera choreography. “Dense” should be measured through visible layer count, overlap, occupied-frame proportion, and hierarchy changes, rather than used as a vague impression. Preserve subdued or sparse intervals and keep requested reference identities unresolved where the user left them ambiguous.
