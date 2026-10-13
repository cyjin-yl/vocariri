# Vocariri contributor rules

Build a VOCALOID-specialized lyric PV editor, with a deterministic local renderer and CLI. The product is not an agent. Human editing must not require model calls.

Read docs/product.md before changing scope. Artist/song examples are aesthetic references, not a restriction on the broad 500–800-form research requirement. Keep research-source observations separate from invented design proposals and parameter permutations. Never claim commercial/cinematic quality from passing code tests.

Use src/core.mjs as the shared time and motion source for preview, CLI and export. Audio is the authoring clock. Preserve explicit silence, stable token IDs, undo semantics and arbitrary-time rendering. Keep font metrics, alpha association, output color space and AE target capabilities explicit.

External models need expressive versioned data and explicitly selected local code modules. Do not execute code embedded in a project merely because it was opened. Never silently discard unsupported export features.

AE tests must launch minimized, preserve the user's foreground work, explicitly save intended output, close the test project with a declared save/discard policy, and exit normally. Never forcibly terminate AE, including on timeout. Do not change global preferences or dismiss crash recovery by resetting settings. Verify actual process exit; a script return or saved AEP does not prove shutdown. Do not stack new instances while an earlier test is still unresolved.

Desktop must use Tauri; Electron is explicitly prohibited by the user. Run npm test for core changes; npm run test:ui for editor changes; npm run build:desktop and native WebView smoke checks for shell changes on a supported local OS. Preserve test failures and source acquisition failures. Document which OS was actually tested. Do not assume Windows success proves macOS/Linux success.

Research cached originals and third-party media are not redistributable application assets. Do not publish personal data, local media or credentials. Do not create a public remote or publish a package as an incidental test. Preserve unrelated changes. Check .gitignore and package files allowlists before bundling.
