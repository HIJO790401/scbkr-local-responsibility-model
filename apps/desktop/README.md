# SCBKR Desktop Launch Skeleton — P14-B

P14-B is a desktop launch skeleton, not a production installer.

This folder provides the minimum Tauri-oriented structure and runtime contract for a future desktop shell. It does not build or publish `.exe`, `.msi`, `.dmg`, installers, auto-updaters, code signing assets, or GitHub Releases. P14-C remains responsible for packaged sidecar runtime and release automation.

## Development contract

- Desktop shell points at the existing Web UI dev server: `http://localhost:5500`.
- Web UI talks to the existing local FastAPI server, normally `http://localhost:8787`.
- Sandbox Mode remains the safest default path and requires no model, API key, model download, or external call.
- LM Studio / Ollama / OpenAI-compatible endpoints remain user-provided local services; SCBKR does not install or download models.
- Desktop skeleton must not bypass SCBKR gates: confirm, sealed snapshot, `model_generate`, review, signed storage confirm, and advisory retrieval locks remain in FastAPI/workflow code.

## Non-goals in P14-B

- No production installer.
- No formal Tauri build requirement in CI.
- No auto-update.
- No code signing.
- No cloud account system.
- No bundled large model.
