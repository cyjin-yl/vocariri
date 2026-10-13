# Vocariri product contract

Build an open-source, local-first VOCALOID lyric PV editor for Windows, macOS and Linux. Human timing and animation editing must work with zero model calls. External Coding Agents are a first-class natural-language authoring path through the CLI and editable source. They may change every detail of animations, templates, compositions and renderer code; the product itself does not need an autonomous agent or a fixed model provider.

The intended output is elaborate VOCALOID kinetic typography: composed words and lines, deliberate rhythmic hierarchy, expressive transitions and coordinated cameras. A subtitle animator alone does not satisfy the product.

## Timing

Audio is the clock. `[` starts the selected token and selects the next token, closing the predecessor unless it has an explicit end. `]` ends the most recently started token. Gaps remain gaps. Arrow keys move between tokens and lines and seek to existing onset times. Untimed tokens have no fabricated timestamp. Han characters use grapheme boundaries; English uses words; romanized syllables allow explicit `|` segmentation. Undo, numerical correction, playback rate and loop audition are required.

## Research and template acceptance

Broad collection must test architectural generality as well as supply templates. Each reviewed mechanism should identify its object/time/compositing relationships, required capabilities, current representation gaps and a concrete counterexample. Preserve mechanisms that challenge the current implementation; do not filter research to fit existing presets. See [architecture implications and coverage work](architecture-from-research.md).

Artistic typography is a separate, equally necessary research output. Record evidence-linked letter anatomy, stroke/fill/outline treatments, texture, palette, spacing, script mixing, reading hierarchy, grouping, decorative composition, and changes over time. Separate observed design, aesthetic interpretation and original reconstruction recipes. Track reusable art patterns alongside motion forms and architecture coverage; unknown font identity stays unknown. Deliberately designed software-window/chat/pixel motifs inside a PV are art, distinguishable from incidental tutorial controls. The owner's added INTERNET OVERDOSE reference expands this study without narrowing other coverage. Meaningful style variants need visual review; appearance permutations do not inflate distinct motion-form counts.

Preserve reference frames and contact sheets until a similar editable prototype has been implemented and reviewed; cache naming does not permit cleanup. Keep third-party reference media outside public releases. Each pattern also needs lyric-and-image applicability, possible emotions/meanings, alternatives, use/avoid conditions and neighboring-shot context, distinguishing observed source context from conditional recommendations. See [reference and applicability contract](reference-and-applicability.md) and the [retention policy](../research/reference-retention-policy.json).

GPT-6 Luna must study 500–800 public VOCALOID text-PV forms, including animation template and project examples. Named artist references are aesthetic examples, not a limit on scope. Candidate discovery, template-code inspection, static visual inspection, motion inspection and aesthetic approval must be counted separately. Duplicate parameter permutations do not count as research observations.

Ship at least 1000 templates and variants only after each has a preview, meaningful parameter range, licensing provenance, performance assessment, supported export targets and a review state. The current 20 × 4 × 4 × 4 catalogue is 1280 procedural candidates, not 1280 finished compositions. Many entries are intentionally elementary probes; `still` variants can be visually redundant and are not unique accepted templates.

## Continuity and images

Eventually support explicit boundary contracts for position, velocity, scale, rotation, opacity, masks, noise state and camera ownership. Resolve conflicts before rendering. C0 continuity means matching endpoint values; C1 also matches speed. A smoothstep camera currently provides zero-velocity arrival/departure at keys, not artistic continuity for arbitrary adjacent effects. Hard cuts remain a valid authoring choice.

Background coverage uses inverse-transformed viewport corners. The current per-frame cover calculation prevents geometric exposure for an opaque rectangular image; it can cause visible scale breathing and crop important composition. A production solution needs an envelope over the entire shot, subject-safe regions, transparent-image handling, blur/displacement margins and a crop warning. Rotated parallax layers need individual bounds.

## Interchange and extensibility

Versioned JSON is the shared intermediate representation for GUI, CLI and renderers. An optional external model can construct projects and absolute-time custom tracks. This first schema only covers affine glyph tracks; it is not the final creative extension interface. Next add named scene nodes, curves, selectors, user-authored render modules and export capability declarations. Never silently flatten an unsupported operation. Preserve unknown extension payloads through load/save and give a visible target-support report.

Project version 2 now separates vocal tokens from independent visual instances. Instances can repeat a token, overlap, outlive its vocal end, and own layout groups, compositing order, affine transforms and scene-time curves. CLI, browser rendering and AE JSX baking share the evaluator; see [the instance contract](visual-instances.md). Version 1 projects remain readable. GUI visual-track editing, hierarchical image/mask/rig graphs and actual AE render parity remain unverified or unimplemented.

AE JSX currently generates editable text plus a 2D camera null. Native AEP generation requires executing that script in AE on a supported AE platform; Linux authoring/export preparation remains possible. Native AE import and rendering parity are unverified. Text shaping/font metrics, effects, color management and alpha association need explicit parity tests. PNG sequences are a portable lossless alpha interchange; movie encoders are a later integration.

## Platform decision

Prototype: native browser audio, Canvas 2D, portable JavaScript core and Node CLI. This avoids a model dependency and permits exact-time headless sampling. The user explicitly selected Tauri and prohibited Electron. Tauri 2 is the desktop shell; validate differences in WebView2, WKWebView and WebKitGTK using audio-clock, shaping and export benchmarks. The previous Electron experiment is retired. Final renderer must measure performance on the three operating systems and publish the tested hardware, fonts and output settings.

## Release gates

Complete representative song excerpts; verify readable typography, varied sentence composition, coherent beat structure, image protection and transitions. Review visual output, not just numerical correctness. Check 1080p realtime preview and offline 4K rendering with measured frame timings. Test alpha edges, color, font embedding/licensing, project migration, recovery, CLI parity and AE round-trip. Commercial/cinematic quality is a requested target, not a present claim.

## Commercial workflow acceptance (owner clarification, 2026-09-24)

The delivery must be a mature production workflow. A demo, elementary animation probe, passing test suite, or a large parameter catalogue cannot satisfy acceptance.

- After complete lyric timing, an external Coding Agent may arrange the entire song from lyric meaning, emotion and musical structure without per-effect confirmation. Preserve project revisions and allow optional later review and revision. Keep manual editing independent of model calls.
- Separate vocal timing from visual instances. Support repeated and overlapping lines, independent tracks, effect stacks and explicit compositing order. A line's vocal end must not force all of its visual instances to disappear.
- Assets are composable resources, not fixed background/portrait features. Preserve image metadata and descriptions, regions, masks, derived layers, transforms, curves, meshes, bones, constraints and extension data. Hair separation, hair movement and body motion must retain editable intermediate results and provenance. An extension contract does not mean these operations are already implemented.
- Adopt a real accessible component library; evaluate Proto-UI/shadcn from its public package surfaces. Keep the Codex-inspired project/conversation/workspace organization. Do not copy private screenshot content into distributed assets.
- Render selected AE intervals with dependency-aware invalidation and transition handles. Realtime playback refers to completed cached proxies. Export the full editable composition, including overlapping text and supported rig/effect structure. Unsupported operations require explicit capability reporting.
- Validate full-song composition and revisions, typography and emotional pacing, temporal transitions, camera coverage, alpha/color correctness, and editable AE output on real artifacts. Publish measured hardware/platform results. No commercial-quality claim until these gates actually pass.
