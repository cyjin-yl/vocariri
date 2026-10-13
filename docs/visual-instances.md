# Independent visual instances

`tokens` remains the lyric and vocal-timing record. Project version 2 adds optional `visualInstances` as the complete visual layer list: omitting it preserves the old renderer; an empty array intentionally draws no text. The shared evaluator, CLI sampling, browser renderer and AE JSX exporter consume the same list. Version 1 projects remain readable, but adding instances requires explicitly upgrading to version 2 so older clients reject the project instead of silently dropping its composition.

Each instance requires a unique `id`, an existing `tokenId`, a `groupId`, and its own `start`/`end` in scene seconds. Its range may extend beyond the vocal end or overlap another instance of the same word. Editing an instance never changes vocal timings. Entries in each group determine glyph layout in array order; unrelated groups have independent layouts. Lower `zIndex` values paint first, with array order breaking ties.

Optional fields:

- `preset`: override the source token's preset.
- `tracks`: scene-time x, y, scaleX, scaleY, rotation and alpha curves, using linear, soft, hold or Hermite interpolation. Properties override the source token's custom tracks.
- `transform`: x/y offsets, positive uniform scale, rotation in degrees and alpha multiplier. It applies after glyph curves, around the canvas center, before the shared camera. Apply the same transform to group members to move the group together.
- Extension metadata may stay on the project/instances and survives ordinary JSON serialization. It is not executed as code or interpreted as a supported rendering effect.

For example, `examples/overlapping-lines.mjs` is an explicitly selected CLI transform. It creates lead and delayed echo layers, retains a line beyond its sung ending, and allows the following line to overlap. It is a mechanical workflow example, not an accepted commercial template.

```
node cli.mjs transform timed.json examples/overlapping-lines.mjs overlap.json
node cli.mjs validate overlap.json --timed
node cli.mjs sample overlap.json 2.5
node cli.mjs export-ae overlap.json overlap.jsx
```

AE export creates one editable text layer per visual instance and bakes the same sampled geometry in paint order. Tests inspect generated layer data and frame values; native AE rendering, font parity and compositing parity remain unverified. The current GUI timeline still displays vocal timing and does not yet provide visual-track editing. Image/mask/rig graphs, per-instance cameras, effect stacks and automated whole-song direction remain separate work.
