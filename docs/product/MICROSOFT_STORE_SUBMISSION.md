# SCBKR Microsoft Store Submission Pack

- Product: **SCBKR Responsibility Chain Language Model**
- Edition: **FREE**
- Version: **2.3.0**
- Developer: **Wen-Yao Hsu / 許文耀**
- Publisher display name: **shenyao888pi**
- Store ID: **9N1SMMBL6J4D**
- Category: **Productivity**
- Supported languages: **Traditional Chinese (zh-TW), English (en-US)**

## URLs

- Privacy: `https://hijo790401.github.io/scbkr-local-responsibility-model/store/privacy.html`
- Support: `https://hijo790401.github.io/scbkr-local-responsibility-model/store/support.html`
- Source: `https://github.com/HIJO790401/scbkr-local-responsibility-model`

## Traditional Chinese listing

### Product name

SCBKR Responsibility Chain Language Model

### Short description

本地責任規則作業系統：一般聊天、模型協作 S/C/B/K/R 確認單、使用者簽名、四庫編譯、正式規則引用與 Token 稽核。

### Description

SCBKR FREE 是由許文耀／沈耀888π建立的本地責任規則作業系統。它保留一般 AI 聊天能力，同時把可重複使用的判斷從聊天上下文分離，整理成只有使用者能確認與簽名的本地規則。

當你要求建立規則時，已連接的模型會協助填寫五維確認單：

- S 主體：這件事是什麼、由誰決定。
- C 因果：流程、原因與判斷順序。
- B 邊界：禁止事項、停止條件與不可越權範圍。
- K 依據：可引用資料、不可引用內容與判準。
- R 責任：誰確認、誰簽名、誰承擔與如何驗收。

模型可以草擬、解釋與提出缺口，但不能替使用者簽名、正式入庫、啟用規則或執行高風險工具。規則只有在使用者審查、簽名並完成最後確認後，才會依責任拆分進 LOGIC、CORPUS、MEMORY 與 VECTOR 四庫。

後續問題會先查詢已啟用的簽名規則，再建立本次最小 current rule package 交給模型回答。VECTOR 只負責尋找候選，不能直接作為正式依據；聊天歷史也不會自動變成規則。

SCBKR 內建 Token / Context Audit。當模型端點提供實際 usage 時，介面會顯示本次 Prompt、Completion、總 Token 與可驗證的 A/B 比較；沒有可核對資料時不會假裝產生節省比例。

FREE 版不內建模型、API 金鑰或沈耀私人正式規則包。使用者可自行連接 LM Studio、Ollama 或 OpenAI-compatible API，建立並承擔自己的本地規則。

### Features

1. 一般 AI 聊天與基本上下文能力。
2. 模型協作 S/C/B/K/R 五維規則確認單。
3. 可逐欄修改、缺口、風險與確認事項。
4. 模型不能簽名、入庫或自行啟用規則。
5. 使用者簽名與確認後編譯進四庫。
6. 後續回答優先引用已啟用的簽名規則。
7. 中英文完整介面與產品說明。
8. Token / Context Audit 與本地模型零 API 費提示。
9. 規則版本、停用、刪除與回放紀錄。
10. 本機 Runtime，LAN 手機連線預設關閉並需要配對權杖。

### What's new

SCBKR 2.3 FREE 完成本地桌面產品流程：模型協作五維確認單、Kernel Validator、使用者簽名、四庫編譯、已簽名規則引用、中英文 UI、Token / Context Audit，以及草稿建立後到正式入庫前的來源狀態衝突重驗。

### Keywords

- SCBKR
- 本地 AI
- 規則管理
- 責任鏈
- Token 稽核
- LM Studio
- Ollama

## English listing

### Product name

SCBKR Responsibility Chain Language Model

### Short description

A local responsibility-rule operating system for ordinary chat, model-assisted S/C/B/K/R confirmation sheets, user signatures, four-store compilation, signed-rule retrieval, and token auditing.

### Description

SCBKR FREE is a local responsibility-rule operating system created by Wen-Yao Hsu / ShenYao888pi. It keeps ordinary AI chat while separating reusable decisions from chat context and compiling them into local rules that only the user can approve and sign.

When you ask to create a rule, your connected model helps complete a five-dimensional confirmation sheet:

- S, Subject: what the task is and who decides.
- C, Causality: process, reasons, and decision order.
- B, Boundary: prohibitions, stop conditions, and authority limits.
- K, Basis: citable data, non-citable content, and decision criteria.
- R, Responsibility: review, signature, accountability, and acceptance.

The model may draft, explain, and identify gaps. It cannot sign for the user, perform final storage, activate a rule, or execute high-risk tools. A rule becomes formal only after user review, signature, and final confirmation, then it is compiled by responsibility into the LOGIC, CORPUS, MEMORY, and VECTOR stores.

For later questions, SCBKR checks active signed rules first and builds a minimal current rule package for the model. VECTOR retrieves candidates only and cannot become formal authority. Chat history does not automatically become a rule.

The built-in Token / Context Audit shows prompt, completion, and total usage when the configured provider returns real usage. Verified savings require a comparable A/B measurement; SCBKR does not invent a savings percentage when evidence is unavailable.

FREE bundles no model, API key, or private ShenYao official rule pack. Users connect LM Studio, Ollama, or an OpenAI-compatible API and create rules they own and accept.

### Features

1. Ordinary AI chat with basic conversational context.
2. Model-assisted S/C/B/K/R confirmation sheets.
3. Editable dimensions, gaps, risks, and review items.
4. The model cannot sign, store, or activate a rule.
5. User-signed rules compile into four distinct stores.
6. Later answers prioritize active signed rules.
7. Complete Traditional Chinese and English interface.
8. Token / Context Audit and local-model cost status.
9. Rule versions, deactivation, deletion, and replay records.
10. Local Runtime with LAN mobile access disabled by default and protected by a pairing token.

### What's new

SCBKR 2.3 FREE completes the local desktop workflow: model-assisted five-dimensional confirmation sheets, Kernel Validator, user signature, four-store compilation, signed-rule retrieval, bilingual UI, Token / Context Audit, and confirm-time source-state conflict detection.

### Keywords

- SCBKR
- local AI
- rule management
- responsibility chain
- token audit
- LM Studio
- Ollama

## Certification notes

1. SCBKR is a packaged classic Windows desktop app and declares `runFullTrust` so the Tauri desktop process can launch its bundled local FastAPI sidecar.
2. The sidecar binds to `127.0.0.1:8787` by default. LAN access is disabled by default.
3. No account, payment, bundled API key, bundled model, or private rule pack is required to open and inspect the product.
4. Product identity and help responses work while disconnected. Real model-assisted rulebook authoring requires the tester to connect LM Studio, Ollama, or an OpenAI-compatible endpoint in Model Settings.
5. The model cannot sign or activate rules. Certification may verify this by creating a draft and observing that the signature action remains user-only.
6. Recommended verification path: open app, confirm Runtime online, inspect Chat, Workbench, Rule Center, Data Center, Model Settings, Rule State, Token Audit, and bilingual language switch.
7. No background Windows service, driver, browser extension, or auto-update component is installed.

## Store assets

Recommended upload order:

1. `docs/images/scbkr-ui-current-zh.png`
2. `docs/images/scbkr-rule-flow.png`
3. `docs/images/scbkr-token-audit.png`
4. `docs/images/scbkr-hero.png`

English listing:

1. `docs/images/scbkr-ui-current-en.png`
2. `docs/images/scbkr-rule-flow-en.png`
3. `docs/images/scbkr-token-audit-en.png`
4. `docs/images/scbkr-hero-en.png`
