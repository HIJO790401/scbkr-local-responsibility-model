# P14-B Desktop Runtime Contract

P14-B is not installer work. P14-B is a desktop launch skeleton and runtime contract so P14-C can later package a production desktop runtime.

P14-C pending items include Windows installer, packaged sidecar runtime, GitHub Actions release, code signing, and production desktop distribution.

## Launch target

Desktop Shell → Web UI → FastAPI local server → SCBKR workflow → sandbox or local model endpoint.

The desktop shell is only a carrier. It must not bypass SCBKR responsibility gates.

## Test path A: Sandbox Mode

Sandbox path:

Desktop Shell → Web UI → FastAPI → P12/P10 gates → `sandbox_mock_model` → review → storage request → signed storage confirm → retrieval advisory result.

Sandbox Mode requires no model, no API key, no external API call, no LM Studio/Ollama, and no model download. Sandbox output must remain marked as sandbox and must not be presented as a real model result.

## Test path B: LM Studio local endpoint

LM Studio local path uses a user-managed OpenAI-compatible local endpoint:

- Base URL: `http://127.0.0.1:1234/v1`
- API Key: `lm-studio`
- Model Name: supplied by the LM Studio API Model Identifier, for example `qwen2.5-vl-7b-instruct`

Rules:

- The local model endpoint is the user's own local service.
- SCBKR does not download models.
- SCBKR does not install LM Studio or Ollama.
- SCBKR only connects to OpenAI-compatible APIs when the user explicitly runs model test/generation through existing gates.
- API key for LM Studio may be a placeholder.
- Computers that cannot install Python/Node are out of P14-B scope; P14-C installer work will address packaged runtime concerns.

## Data path contract

Future desktop mode should use an app data directory. P14-B does not migrate P13-A/B/C data paths. Existing `data/` behavior remains in place, and any desktop path helper added in future work must be a preview/contract until migration is explicitly implemented.

## Non-goals

- No production installer.
- No `.exe`, `.msi`, or `.dmg` output.
- No GitHub Release upload.
- No auto-update.
- No code signing.
- No cloud requirement.
- No account or multi-user system.
- No bundled or downloaded model.

## P14-C Windows Preview Package

P14-C adds the Windows preview packaging path. The package is an unsigned preview package, not a final production installer. It has no code signing and no auto-update.

### Sidecar runtime

The preview package includes a FastAPI sidecar target named `scbkr-api.exe`. The sidecar runs `apps.api.main:app` on `127.0.0.1:8787`, checks whether the port is already occupied, and must not bind to an external host. The sidecar does not call models, download models, or require API keys at startup. `/health` must be reachable after startup.

### App data path

The sidecar sets `SCBKR_DATA_DIR` to an app data location such as `%APPDATA%/SCBKR/data` unless the environment already provides an override. SQLite, JSONL, corpus, logic, exports, memory, and retrieval files should use that data directory in desktop preview mode. Dev mode keeps the existing repo `data/` behavior.

### Preview artifact

GitHub Actions uploads an artifact named `scbkr-windows-desktop-preview`. The artifact should include the desktop preview bundle, `scbkr-api.exe`, `README_PREVIEW.md`, and `VERSION` metadata. It must not include a model or API key.

### P14-C boundaries

P14-C does not add macOS/Linux production packages, code signing, auto-update, cloud accounts, bundled models, model downloads, or external embedding APIs. SCBKR gates remain authoritative: desktop launch does not bypass confirmation, sealed snapshot validation, `model_generate`, review, signed storage, memory rules, or advisory retrieval.

### P14-C Windows sidecar staging rule

Tauri v2 sidecars are staged under the `src-tauri` project using the configured
external binary base name plus the Windows target triple. The preview config uses
`bundle.externalBin = ["sidecar/scbkr-api"]`, so the Windows preview build must
stage this file before `tauri build`:

```text
apps/desktop/src-tauri/sidecar/scbkr-api-x86_64-pc-windows-msvc.exe
```

The canonical PyInstaller output remains
`dist/windows-preview/sidecar/scbkr-api.exe`. The Windows sidecar build script
copies that executable to the Tauri staging path and fails if the target-triple
file is not present. The desktop preview packaging script also checks the staged
sidecar before building Tauri, then copies the Tauri desktop executable or NSIS
installer into `dist/scbkr-windows-desktop-preview/desktop/`. If Tauri reports a
successful build but no desktop executable or NSIS installer exists, preview
packaging fails.
