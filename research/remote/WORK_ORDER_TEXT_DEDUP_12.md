# Text-only candidate triage 12 — quota-safe mechanism comparisons

## 1. Seat and objective

You are the existing interactive GPT-6 Luna public PV research seat. The preceding eight-form visual audit stopped on a vision-read 429 and must remain preserved. This new task uses text records only to prioritize native-video review; it cannot accept a form or production template. Current research target is 500–800 reviewed distinct text-PV forms, with at least 1000 finished template variants as a separate production target.

## 2. Read first

Read this self-contained order and the public `RESEARCH_TARGET.json`, `outputs/form-dedup-review-10.json` and `outputs/evidence-audit-12.json`. Do not read private or unrelated handoffs, credentials, infrastructure files or other seats. Source descriptions and prior model judgments are candidate evidence, not proof of visible motion.

## 3. Inputs

Use `outputs/forms.jsonl`, `outputs/observations.jsonl`, `outputs/raw-observations-ledger.jsonl`, `outputs/production-requirements-06.json` and `outputs/requirements-reconciliation-06.json`. Start with `head` and `wc -l` to confirm actual keys/rows; **do not assume structure**. Read existing hashes from the preceding audit and recompute any mutable input before claiming a comparison. Source URLs, observation IDs and approximate sheet windows are links for later verification, not native PTS proof.

## 4. Steps

1. Select twelve likely near-duplicate **pairs** among the 42 text-domain candidate forms, spanning at least six mechanism families. Prioritize pairs that challenge the representation: overlapping/repeated visual lyric instances, per-glyph versus per-group timing, masks/occlusion, text attached to moving panels/objects, camera versus layer motion, and discontinuous cuts. Do not count each lyric phrase, color, size or parameter change as a new mechanism.
2. For each pair, cite both form IDs and concrete observation IDs/source intervals. Record the strongest described common mechanism, the described discriminant, possible scene-only contamination, exact missing native-frame/audio evidence, and a 0.6–1.5-second window suitable for Qwen or independent visual review. If a description cannot resolve, mark it unknown rather than asserting a merge or distinction.
3. Add art typography anatomy (glyph shape, fill/outline/shadow, grouping, script mixing and reading order) only when the description supports it. Separate this from motion, aesthetic interpretation and reconstruction recipe. Give conditional lyric/emotion/neighboring-shot use advice; original meaning and beat are unknown without audio/lyrics.
4. Identify one concrete current data-model counterexample per pair and specify whether explicit non-continuity is appropriate. Preserve 3D/MMD scene features as companion context, not text mechanisms.
5. Stop at twelve pairs. Propose a ranked native-visual review queue; do not edit the shared form/observation ledgers or promote any candidate. The simultaneous Qwen seat owns its own requests and files.

## 5. Deliverables

Write `outputs/text-triage-12.json` with input counts/hashes, twelve linked pair records, text-only uncertainty, architecture and art/semantic fields, and review priority. Allowed relation values: `possible_duplicate`, `possibly_distinct`, `unknown`. The accepted-form/template increments are zero. Write `logs/text-triage-12.status` with completed count and exact next visual gate. Report only what is on disk.

## 6. Boundaries

Public PV records only. **Do not call any image/video read or inference tool for this task**, do not repeat the failed 17-image-read batch, and do not switch models or providers. Preserve all raw responses, reference frames and archives; no deletion, publication, product changes or external messages. The real Agent remains in the observable pane. This task is a prioritization document, not independent visual acceptance.

## 7. Interruption

If any required text input is missing, quota/error recurs, or context approaches its limit, save partial records and the exact resume point in `logs/text-triage-12.status`, then stop. On 429 save immediately; no repeated call or fallback. Do not overwrite `outputs/evidence-audit-12.json` or its failure evidence.
