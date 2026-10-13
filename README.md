# Vocariri

A local lyric-timing editor and motion-study prototype for VOCALOID PV production. Runs without model calls. This is **not yet a production PV tool**: the broad reference study, designed template library, AE parity and cross-platform release tests remain unfinished.

## Run

Requires Node.js 22 or newer.

```sh
npm ci
npm start
```

Open `http://127.0.0.1:4173`. Drop local audio, enter lyrics, and mark syllables/words using `[` and `]`. Arrow keys select and seek; Space toggles playback. `|` gives explicit romanization groups. The editor supports loop playback, waveform seeking, undo/redo and numerical corrections. Images are local and must be relinked after opening a saved project.

Choose a motion, scope it to one word, one line, a time range or the whole project, then apply. Six layouts and sentence retention are available. Camera keys interpolate globally or cut deliberately. Opaque rectangular backgrounds use inverse-camera coverage; scale breathing, subject-safe cropping and transparent artwork still require further work.

The current catalogue is **20 basic motions with 1280 procedural combinations**, not 1000 approved artistic compositions. Research sample counts live in `research/`; catalogue permutations do not count as observations.

## CLI

```sh
node cli.mjs init lyrics.txt project.json
node cli.mjs validate project.json --timed
node cli.mjs presets
node cli.mjs sample project.json 1.25
node cli.mjs apply project.json rise-sharp-1-fade changed.json
node cli.mjs transform project.json examples/custom-motion.mjs custom.json
node cli.mjs export-ae project.json output.jsx
```

`transform` explicitly runs a local JavaScript module selected by the caller. It is an escape hatch for model-generated or hand-authored procedural work; project files do not execute modules automatically. Modules receive the project and core library and may generate any valid project structure. Preserve the source module alongside generated data. Custom affine tracks support linear, hold, smoothstep and Hermite interpolation with endpoint tangents. Richer render-node extensions remain on the roadmap.

For deterministic transparent PNG sequences:

```sh
npx playwright install chromium --no-shell
node cli.mjs render project.json exports/frames
```

The CLI currently renders text and camera; it does not load background, portrait or audio media. Existing output files are never silently overwritten. Use a new directory for each render. A system FFmpeg can encode the PNG sequence, for example:

```sh
ffmpeg -framerate 30 -i exports/frames/%06d.png -c:v prores_ks -profile:v 4 -pix_fmt yuva444p10le text-alpha.mov
```

Use the project's actual fps. FFmpeg encoding is an optional external step and has not been validated by the prototype's tests.

## AE interchange

Run the exported JSX in After Effects to create editable text layers and a baked 2D camera null, then save as AEP. This requires AE. It does not produce a native AEP on Linux. Audio and artwork are not embedded; font metrics may differ. Import execution, AE rendering and cross-application pixel parity are **unverified**.

## Checks and platform status

```sh
npm test
npm run test:ui
```

The automated tests run on Windows Chromium. macOS/Linux and desktop packaging are not yet tested. The desktop shell uses Tauri 2, as required. Install the Rust stable toolchain and platform prerequisites, then run `npm run desktop` or `npm run build:desktop`. Windows uses WebView2, macOS WKWebView, Linux WebKitGTK. The former Electron prototype has been removed; its historical smoke test is not evidence for Tauri.

See [product contract](docs/product.md) and [current handoff](HANDOFF.md). The project is intended for open-source release. No public remote has been created; the original application code uses MIT; third-party asset review remains a release prerequisite. Research media and templates are references, not assets licensed for redistribution.
