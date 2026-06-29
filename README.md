# SCBKR 本地責任鏈模型

# SCBKR Local Responsibility Chain Model

![SCBKR 本地責任鏈模型](docs/images/scbkr-hero.png)

本地 AI 責任鏈工作台｜使用者簽名 Gate｜Data Center｜四庫引用｜Release Candidate  
Local AI responsibility-chain workbench | Owner Signature Gate | Data Center | Four-store evidence reuse | Release Candidate

SCBKR 不是一般聊天機器人。SCBKR 是一套本地 AI 責任鏈工作台。模型可以協助，但不能越權。使用者簽名後，責任鏈才成立。驗收後才可入庫。二次確認後才可寫入四庫。

SCBKR is not a general chatbot. It is a local AI responsibility-chain workbench. The model can assist, but it cannot overreach. Owner signature makes the responsibility chain valid. User review is required before storage, and storage requires second confirmation.

## 1. 快速理解｜Quick Overview

SCBKR 將「使用者意圖、確認單草案、使用者簽名、模型生成、使用者驗收、Storage Request、Second Confirmation、Data Center、四庫引用」串成可追溯的本地責任鏈。模型可以協助，但不能越權；模型不能簽名、不能驗收、不能自動 CLOSE、不能自動二次確認，也不能自動把輸出變成長期記憶。

SCBKR connects user intent, confirmation drafts, owner signature, model generation, user review, Storage Request, Second Confirmation, Data Center, and four-store evidence reuse into an auditable local responsibility chain. The model can assist, but it cannot overreach. The model cannot sign, review, auto-close a task, perform second confirmation, or create long-term memory by itself.

## 2. 目前版本｜Current Version

- 目前版本：0.15.0-rc.1
- Current version: 0.15.0-rc.1
- 目前階段：P15-Q Release Candidate + PATCH-2
- Current phase: P15-Q Release Candidate + PATCH-2
- 下一階段：P15-R 1.0 上線基礎整理
- Next phase: P15-R 1.0 product-readiness cleanup
- SCBKR Desktop release-candidate sidecar 預設 backend port：`http://127.0.0.1:8787`
- Default backend port for the SCBKR Desktop release-candidate sidecar: `http://127.0.0.1:8787`

## 3. 1.0 目前能做什麼｜What 1.0 Can Do

1.0 Release Candidate 目前支援 Chat 任務入口、Workbench 責任鏈確認單、S / C / B / K / R 草案、使用者簽名 Gate、模型生成、使用者驗收、Storage Request、Second Confirmation、Data Center、四庫引用、LM Studio / Ollama / OpenAI-compatible API 接入基礎、Windows desktop release candidate，以及手機透過 activeBackendUrl 連回本機後端的基礎設計。

The 1.0 Release Candidate supports chat task entry, Workbench responsibility-chain confirmation, S / C / B / K / R drafts, Owner Signature Gate, model generation, user review, Storage Request, Second Confirmation, Data Center, four-store evidence reuse, LM Studio / Ollama / OpenAI-compatible API foundations, Windows desktop release candidate packaging, and the mobile companion foundation that connects through activeBackendUrl back to the local backend.

## 4. 完整責任鏈流程｜Responsibility Chain Flow

Chat → Workbench → SCBKR Draft Grammar → Owner Signature → Model Generation → User Review → Storage Request → Second Confirmation → Data Center → Four-store Evidence Reuse

核心原則：模型可以協助，但不能越權。使用者簽名後，SCBKR 才成立。模型不能簽名。使用者修改確認單後，舊簽名必須作廢。使用者驗收後才可入庫。入庫必須二次確認。未驗收資料不得進入四庫。未有效資料不得被未來任務引用。模型不能自動建立長期記憶。模型不能自動 CLOSE。模型不能自動二次確認。

Core principles: The model can assist, but it cannot overreach. Owner signature makes the responsibility chain valid. The model cannot sign. Any draft change invalidates the old signature. Storage requires user review and second confirmation. Unreviewed data cannot enter the four stores. Invalid data cannot be reused by future tasks. The model cannot create long-term memory by itself. The model cannot auto-close a task. The model cannot perform second confirmation by itself.

![完整責任鏈流程](docs/images/responsibility-loop.png)

![Responsibility chain flow](docs/images/responsibility-loop-en.png)

## 5. Workbench 與使用者簽名｜Workbench and Owner Signature

Workbench 是責任鏈確認單的操作區。使用者必須檢查任務目的、草案內容、引用資料與入庫意圖後簽名；若確認單被修改，舊簽名必須作廢並重新簽名。簽名 Gate 不代表模型取得所有權，它只代表使用者允許模型在該責任鏈範圍內協助生成。

The Workbench is where the user verifies intent, draft content, references, and storage intent. If the confirmation changes after signing, the old signature must be invalidated and the user must sign again. The signature gate does not transfer ownership to the model; it only authorizes model assistance within that specific responsibility-chain scope.

![Workbench 與使用者簽名](docs/images/workbench-owner-signature.png)

![Workbench and owner signature](docs/images/workbench-owner-signature-en.png)

## 6. Data Center 與四庫｜Data Center and Four Stores

Data Center 只對已驗收且通過二次確認的內容開放正式入庫。正式四庫只能是：

- vector
- corpus
- logic
- memory

exports 不是正式四庫入庫目標。若未來存在 exports，只能是匯出 / 報告功能，不得混入 selected_targets。未驗收資料不得進入四庫，未有效資料不得被未來任務引用。

Data Center storage is available only after user review and second confirmation. The formal four stores are:

- vector
- corpus
- logic
- memory

exports is not a formal four-store storage target. If exports exists in the future, it may only be an export/report feature and must not be mixed into selected_targets. Unreviewed data cannot enter the four stores, and invalid data cannot be reused by future tasks.

![Data Center 與四庫](docs/images/four-store-evidence.png)

![Data Center and four stores](docs/images/four-store-evidence-en.png)

## 7. 本地模型支援｜Local Model Support

SCBKR 可接 Sandbox、LM Studio、Ollama、OpenAI-compatible API 與 Custom endpoint。`localhost` / `127.0.0.1` / `::1` 代表本機模型呼叫，資料送到同一台電腦。`192.168.x.x` 代表區網呼叫，資料送到同一 Wi-Fi / LAN 內的指定主機。external API endpoint 會把資料送到使用者設定的外部服務；請先確認 endpoint、服務條款、資料保留政策與 API key 權限。不要把 API key commit 到 Git，也不要貼在公開 issue、截圖或文件中。

SCBKR can connect to Sandbox, LM Studio, Ollama, OpenAI-compatible API, and custom endpoints. `localhost` / `127.0.0.1` / `::1` means local model calls to the same computer. `192.168.x.x` means local-network calls inside the same Wi-Fi / LAN. An external API endpoint sends data to the user-configured external service, so users should check endpoint ownership, terms, retention policy, and API-key scope. Do not commit API keys to Git or expose them in public issues, screenshots, or documents.

![本地模型架構](docs/images/architecture.png)

![Local model architecture](docs/images/local-model-architecture-en.png)

## 8. Windows 安裝與啟動｜Windows Setup

Windows 使用流程：下載 Release Candidate installer / artifact，安裝 SCBKR Desktop，啟動桌面 app，確認 backend health，設定模型 provider，建立第一個任務，到 Workbench 檢查確認單，使用者簽名，模型生成，使用者驗收，建立 Storage Request，Second Confirmation，最後由 Data Center / 四庫寫入。健康檢查指令：

```bash
curl http://127.0.0.1:8787/health
```

Windows flow: download the Release Candidate installer / artifact, install SCBKR Desktop, start the desktop app, confirm backend health, configure the model provider, create the first task, review the confirmation in Workbench, sign as the owner, run model generation, perform user review, create a Storage Request, complete Second Confirmation, and then write through Data Center into the four stores. Health check command:

```bash
curl http://127.0.0.1:8787/health
```

## 9. 手機連回本機電腦｜Mobile Companion

手機端不是獨立模型主體，而是操作入口。手機端透過 activeBackendUrl 連回本機電腦，範例：`http://192.168.x.x:8787`。手機與電腦通常需要在同一 Wi-Fi / LAN；電腦區網 IP 類似 `192.168.x.x`，可在 Windows PowerShell 用 `ipconfig` 查詢。Windows 防火牆可能需要允許 SCBKR / FastAPI 通訊。手機端不能繞過本機 Runtime，不能獨立判定規則，也不能繞過簽名、驗收與二次確認。

The mobile companion is not an independent model authority; it is an operation entry point. It connects through activeBackendUrl back to the user's local computer, for example `http://192.168.x.x:8787`. The phone and computer usually need to be on the same Wi-Fi / LAN. The computer LAN IP looks like `192.168.x.x` and can be checked with `ipconfig` in Windows PowerShell. Windows Firewall may need to allow SCBKR / FastAPI traffic. The mobile side cannot bypass the local Runtime, cannot independently decide rules, and cannot bypass signature, review, or second confirmation.

![Mobile companion](docs/images/mobile-companion-en.png)

## 10. 隱私與安全邊界｜Privacy and Safety Boundary

SCBKR 是 local-first。使用本地模型時，資料留在本機或使用者指定的區網環境；使用外部 OpenAI-compatible API 或 custom endpoint 時，資料會送往使用者設定的 endpoint。模型不能簽名、不能驗收、不能自動二次確認入庫、不能自動把輸出變成長期記憶，也不能繞過 Data Center Gate。Data Center 寫入需要使用者驗收與二次確認。

SCBKR is local-first. With local models, data stays on the user's machine or user-controlled LAN environment. With an external OpenAI-compatible API or custom endpoint, data is sent to the user-configured endpoint. The model cannot sign, review, automatically second-confirm storage, turn output into long-term memory by itself, or bypass the Data Center Gate. Data Center writes require user review and second confirmation.

## 11. 與 Chatbot / Agent / RAG 的差異｜Difference from Chatbot / Agent / RAG

| 類型 / Type | 一般行為 / Typical behavior | SCBKR 差異 / SCBKR difference |
|---|---|---|
| Chatbot | 直接回覆。 / Replies directly. | SCBKR 先建立責任鏈。 / SCBKR first establishes a responsibility chain. |
| RAG | 檢索資料後回覆。 / Retrieves data and replies. | SCBKR 只重用已驗收且有效的證據。 / SCBKR reuses only reviewed and valid evidence. |
| Agent | 嘗試自動執行任務。 / Attempts to execute tasks automatically. | SCBKR 阻擋繞過簽名、驗收與二次確認。 / SCBKR blocks bypassing signature, review, and second confirmation. |
| SCBKR | 先建立責任鏈，使用者簽名後才允許模型生成，驗收後才允許入庫。 / Builds a responsibility chain first; model generation starts after owner signature, and storage starts after user review. | 責任鏈、簽名、驗收、二次確認與四庫引用是核心。 / Responsibility chain, signature, review, second confirmation, and four-store evidence reuse are the core. |

## 12. 2.0 Roadmap｜2.0 Roadmap

以下屬於 Roadmap / Future Work，不屬於目前 1.0 已完成功能：P15-R-I18N Bilingual UI、Semantic Legality Gate、Web Search Candidate Flow、Rule Design Engine、RulePack、Tool Permission Gate、Email Draft Tool、Code Workspace、Voice I/O、Image Generation、Rule Pack Subscription、Team / Enterprise governance。

The following items are Roadmap / Future Work and are not completed 1.0 features: P15-R-I18N Bilingual UI, Semantic Legality Gate, Web Search Candidate Flow, Rule Design Engine, RulePack, Tool Permission Gate, Email Draft Tool, Code Workspace, Voice I/O, Image Generation, Rule Pack Subscription, and Team / Enterprise governance.

![2.0 roadmap](docs/images/roadmap-2.0-en.png)

## 13. 開發者快速啟動｜Developer Quick Start

開發者可先安裝依賴，再執行測試、web build 與 desktop release-candidate checks。此段僅描述檢查流程，不代表新增 API、UI、資料庫 schema 或工具層。

Developers can install dependencies first, then run tests, the web build, and desktop release-candidate checks. This section describes validation only; it does not add APIs, UI, database schema, or tool layers.

```bash
python -m pytest -q
npm --prefix apps/web run build
npm --prefix apps/desktop run check:skeleton
npm --prefix apps/desktop run check:release
```

## 14. 測試與驗收｜Testing and Validation

建議驗收流程：建立任務，進入 Workbench，檢查 S / C / B / K / R 草案，完成使用者簽名，執行模型生成，使用者驗收，建立 Storage Request，選擇 vector / corpus / logic / memory 中的正式目標，完成 Second Confirmation，最後在 Data Center 檢查四庫寫入與引用狀態。

Recommended validation flow: create a task, enter Workbench, review the S / C / B / K / R draft, complete owner signature, run model generation, perform user review, create a Storage Request, select formal targets from vector / corpus / logic / memory, complete Second Confirmation, and then verify four-store writes and evidence reuse in Data Center.

## 15. 專案狀態與限制｜Project Status and Limitations

SCBKR 0.15.0-rc.1 是 1.0 Release Candidate。完整使用者介面雙語化、Web Search、Semantic Legality Gate、Rule Design Engine、RulePack、Tool Permission Gate、Email Draft Tool、Code Workspace、Voice I/O、Image Generation、Rule Pack Subscription、Team / Enterprise governance 與各商店正式上架皆屬未來工作；目前不得宣稱為 1.0 已完成功能。

SCBKR 0.15.0-rc.1 is a 1.0 Release Candidate. Full user-facing bilingual UI, Web Search, Semantic Legality Gate, Rule Design Engine, RulePack, Tool Permission Gate, Email Draft Tool, Code Workspace, Voice I/O, Image Generation, Rule Pack Subscription, Team / Enterprise governance, and store releases are future work and must not be described as completed 1.0 features.

## 16. License / Author

Author / Maintainer: 許文耀 / HIJO790401  
Author / Maintainer: Yao Shen / HIJO790401  
Project: SCBKR Local Responsibility Chain Model
