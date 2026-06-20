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
