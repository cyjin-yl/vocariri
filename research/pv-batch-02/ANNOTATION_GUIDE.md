# Observation guide

Use this schema for actual visible occurrences in publicly accessible video, tutorial previews, or project renders. Each row represents one bounded occurrence, not one title and not a generic effect name. Do not copy lyrics into the record.

1. Link the row to the exact public source and the acquisition receipt. Store source media only on the authorized remote research volume. For each reviewed interval, export low-resolution frames to the remote evidence directory, hash each frame, and record its source timecode. Do not commit large media or frame collections here.
2. `frame_inspected_segment` means at least one actual frame was opened. `motion_verified_segment` requires evidence across time that supports the written change. Record at least two timestamped frames or one continuously reviewed interval before using it. Record only visual behavior; title metadata cannot establish what appears in the clip.
3. Describe the composition before naming an effect: where the main type and imagery sit, how the frame is divided, and whether density or framing changes. Describe typography as seen: unit, entry, movement, scale/rotation, clipping, and legibility. Do not infer whether a layer was built in 2D or 3D.
4. List only layers that are visually separable. For each layer, record role, visible behavior, and its overlap/depth relation. Use low confidence when a still or compression makes the layer ambiguous.
5. Split an interval when the motion grammar changes. Separate entrance, hold, and exit phases when they have different behavior. For transitions, describe both sides and what visibly carries across; use `unknown` for cause or trigger without evidence.
6. Keep `form_id` null until a deduplication pass compares trajectories and visual roles across samples. Different direction, duration, color, or amplitude alone is a variant. Keep occurrence rows even when they map to a shared form.
7. Leave audio synchronization unknown unless accessible audio has been compared to the visual timing. Do not infer beat, syllable, or lyric onset from title, captions, recollection, or a single frame.
8. Record counterexamples, quiet frames, and rejected/uncertain labels. The public title is a search clue, never an annotation instruction.
