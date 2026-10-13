# Public snapshot — 2026-10-14

This repository is a single-snapshot public export of the vocariri project, staged on 2026-10-14.
The full original working tree (unreduced Git history, cached media, raw model sessions, credentials)
is preserved privately and is **not** part of this export. No remote was created by the original
working copy; this snapshot is the first publication candidate.

## Scope

Included:

- The local application: `cli.mjs`, `src/`, `src-tauri/`, `examples/`, `tests/`, `scripts/`,
  `docs/`, `assets/`, the Tauri icon set, `package.json`/`package-lock.json`,
  `Cargo.toml`/`Cargo.lock`, `build.rs`, `LICENSE`, `THIRD_PARTY.md`, `AGENTS.md`,
  `README.md`, `index.html`.
- Locally authored research text under `research/`: work orders, reports, reference notes,
  source URL lists, observation records, and the mechanics study.
- Remotely collected authored research under `research-remote/vocariri-research/`
  (752 files): work orders, acquisition/source URL lists, discovery evidence, frame manifests,
  ffmpeg/PTS amendments, review receipts, and authored observation records.
- Remotely collected diagnostics under `research-remote/vocariri-diagnostics/`
  (24 files): the 2026-09-24 multimodal-perception recovery probe suite (scripts, manifests,
  state, concurrency metrics, result summaries).

Excluded (kept only in the private archive):

- Credentials, cookies, environment files, provider seat/config files (`seat-config.yml`),
  and any auth material.
- Raw model sessions: `.events.jsonl`, `.events.sse`, `.client.json`, `.response.txt`, and
  per-request completion dumps (soak/concurrent/sequential/replay/video/image probe outputs).
- Third-party cached media and non-redistributable references: extracted frames and contact
  sheets, source audio/video and partial fragments, cached Motion Canvas / Remotion / Bilibili
  web pages, npm archive bundles, and the reference-archive retention inventory
  (78,997 media entries).
- Dependencies, caches and build output: `node_modules/`, `dist/`, `src-tauri/target/`,
  `src-tauri/gen/`, `__pycache__/`, `*.pyc`.
- Local personal paths and machine identifiers.

## Redaction

Sensitive values were replaced in-place in the public copies (77 files touched):

| Pattern | Replaced with | Count |
| --- | --- | --- |
| Internal model names | `[redacted model]` | 260 |
| Self-hosted provider/model route | `[redacted self-hosted model]` | 27 |
| Research container name | `[research container]` | 14 |
| Local project paths | `[project root]` | 18 |
| Remote host names | `[remote host]` / `[container host]` | 11 |
| Internal provider name | `[redacted provider]` | 9 |
| Local home path | `[home]` | 7 |
| SSH user and private address | `[redacted ssh target]` / `[user]@` | 2 |
| Session UUIDs | `[session id]` | 2 |

After redaction, a targeted grep for the original hostnames, model names, tailnet IP, and user
identifiers returns zero matches across the staged tree.

## Secret scan

`gitleaks detect` (v8.30.1) scanned the single snapshot commit and
reported **zero findings** (empty JSON report `[]`). This is the scanner's result, not a
guarantee that every possible sensitive value can be recognized automatically.
## Source preservation

The original working tree and all excluded material remain intact in the private archive.
This export is byte-independent: nothing in it is a link to, or a modification of, the private
originals. The public project excludes third-party non-redistributable media, credentials, and
private raw model sessions per `AGENTS.md`.
