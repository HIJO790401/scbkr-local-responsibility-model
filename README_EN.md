# SCBKR Local Responsibility-Chain Model

Local AI responsibility-chain workbench | Owner Signature Gate | Data Center | Four-store evidence reuse | Release Candidate

SCBKR is not a general chatbot. It is a local AI responsibility-chain workbench. The model can assist, but it cannot overreach. Owner signature makes the responsibility chain valid. User review is required before storage, and storage requires user review and second confirmation.

## 1. What is SCBKR

SCBKR connects user intent, structured drafts, owner signature, model generation, user review, storage request, second confirmation, and evidence reuse into an auditable local workflow.

![SCBKR product hero](docs/images/scbkr-hero-en.png)

## 2. Core Principle

- The model can assist, but it cannot overreach.
- Owner signature makes the responsibility chain valid.
- The model cannot sign, review, store, update, or delete by itself.
- Editing a signed confirmation invalidates the old signature.
- Storage requires user review and second confirmation.
- Unreviewed data cannot enter the four stores.
- Invalid data cannot be reused by future tasks.

## 3. Current Status

Current version:

0.15.0-rc.1

Current phase:

P15-Q Release Candidate + PATCH-2

Next phase:

P15-R product-readiness documentation and 1.0 release preparation.

## 4. What 1.0 Can Do

- Chat task entry
- Workbench responsibility-chain confirmation
- S / C / B / K / R drafts
- Owner Signature Gate
- Model generation
- User review
- Storage Request
- Second Confirmation
- Data Center
- Four-store evidence reuse
- LM Studio / Ollama / OpenAI-compatible API foundation
- Windows desktop release candidate
- Mobile companion foundation through activeBackendUrl back to the local backend

## 5. Responsibility Chain Flow

Chat → Workbench → SCBKR Draft Grammar → Owner Signature → Model Generation → User Review → Storage Request → Second Confirmation → Data Center → Four-store Evidence Reuse

Rules, memories, and data are not established by the model alone. They become valid only after owner signature, user review, and second confirmation.

![Responsibility chain flow](docs/images/responsibility-loop-en.png)

## 6. Workbench and Owner Signature

The Workbench is where the user verifies intent, draft content, references, and storage intent. If the confirmation changes after signing, the old signature must be invalidated and the user must sign again.

![Workbench and owner signature](docs/images/workbench-owner-signature-en.png)

## 7. Data Center and Four Stores

Data Center storage is available only after user review and second confirmation. The formal four stores are:

- vector
- corpus
- logic
- memory

exports is not a formal four-store target. If exports exists in the future, it must remain an export/report feature and must not be mixed into selected_targets.

![Data Center and four stores](docs/images/four-store-evidence-en.png)

## 8. Local Model Support

SCBKR can connect to Sandbox, LM Studio, Ollama, OpenAI-compatible API, and custom endpoints.

localhost / 127.0.0.1 / ::1 means local model calls. 192.168.x.x means local network calls. External API endpoints send data to the user-configured service.

![Local model architecture](docs/images/local-model-architecture-en.png)

## 9. Windows Setup

1. Download the Windows installer / release artifact. Current package status is Release Candidate.
2. Install SCBKR Desktop.
3. Start the local backend / sidecar.
4. Open the desktop app.
5. Configure the model provider.
6. Create the first task.
7. Sign, generate, review, and store.

See [Windows setup](docs/INSTALL_WINDOWS.md).

## 10. Mobile Companion

The mobile companion is not an independent model runtime. It is an operation entry point that connects through activeBackendUrl back to the user's local computer. Phone and computer should be on the same Wi-Fi. The user must provide the computer LAN IP, such as 192.168.x.x, and Windows Firewall may need to allow SCBKR / FastAPI traffic.

![Mobile companion](docs/images/mobile-companion-en.png)

## 11. Privacy and Safety Boundary

- SCBKR is local-first.
- With local models, data stays on the user's machine or user-controlled LAN environment.
- With external OpenAI-compatible APIs, data is sent to the configured endpoint.
- The model cannot sign, review, store, update, or delete by itself.
- SCBKR does not let model output become long-term memory automatically.
- Data Center writes require user review and second confirmation.

## 12. Difference from Chatbot / Agent / RAG

| Type | Typical behavior | SCBKR difference |
|---|---|---|
| Chatbot | Replies directly. | SCBKR first establishes a responsibility chain. |
| RAG | Retrieves data and replies. | SCBKR reuses only valid evidence. |
| Agent | Attempts to execute tasks automatically. | SCBKR blocks bypassing signature, review, and second confirmation. |
| SCBKR | Builds a responsibility chain. | Model generation starts after owner signature; storage starts after user review. |

## 13. 2.0 Roadmap

The following items are Roadmap / Future Work and are not completed 1.0 features:

- Semantic Legality Gate
- Web Search Candidate Flow
- Rule Design Engine
- RulePack
- Tool Permission Gate
- Email Draft Tool
- Code Workspace
- Voice I/O
- Image Generation
- Rule Pack Subscription
- Team / Enterprise governance

![2.0 roadmap](docs/images/roadmap-2.0-en.png)

## 14. Developer Quick Start

```bash
python -m pytest -q
npm --prefix apps/web run build
npm --prefix apps/desktop run check:skeleton
npm --prefix apps/desktop run check:release
```

## 15. Testing and Validation

Run a full responsibility-chain smoke: create a task, open Workbench, sign, generate, review, request storage, second-confirm, and verify Data Center target alignment.

## 16. Project Status and Limitations

SCBKR 0.15.0-rc.1 is a 1.0 Release Candidate. Full user-facing i18n, Web Search, Semantic Legality Gate, Rule Design Engine, tool permission layer, and store releases are future work.

## 17. License / Author

Author: SCBKR project maintainers. License: see repository license file when provided.
