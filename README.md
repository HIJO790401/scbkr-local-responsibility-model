# SCBKR 本地責任鏈模型
# SCBKR Local Responsibility Chain Model

![SCBKR 本地責任鏈模型](docs/images/scbkr-hero.png)

正式產品身分由 [`config/product_manifest.json`](config/product_manifest.json) 定義；工程與 2.0 路線以 [`docs/SCBKR_MASTER_PLAN_FINAL.md`](docs/SCBKR_MASTER_PLAN_FINAL.md) 為母規格。SCBKR 是控制與編譯層，使用者連接的 LM Studio、Ollama 或 OpenAI-compatible 模型是可替換 Runtime。

The authoritative product identity is defined in [`config/product_manifest.json`](config/product_manifest.json), while [`docs/SCBKR_MASTER_PLAN_FINAL.md`](docs/SCBKR_MASTER_PLAN_FINAL.md) is the master engineering and 2.0 roadmap contract. SCBKR is the control and compilation layer; the user-connected LM Studio, Ollama, or OpenAI-compatible model is a replaceable runtime.

一般 AI 聊天產品｜SCBKR 規則責任鏈｜本地優先四庫｜簽名與回放治理｜手機配對
General AI chat product | SCBKR rule responsibility chain | Local-first four stores | Signature and replay governance | Mobile pairing

SCBKR 不是普通 chatbot，也不是純規則引擎。SCBKR 是「一般 AI 聊天產品 + 使用者規則責任鏈能力」。首頁是一般聊天；規則能力從聊天自然觸發，經第0原理建議閘、FREE 確認單草稿、Workbench 編輯、使用者簽名或雙簽模式後，才會進入規則中心與資料中心。

SCBKR is not a generic chatbot and not a pure rule engine. It is a general AI chat product with user-defined responsibility-chain rules. The home surface is chat; reusable rules are proposed from conversation through the Zeroth Principle Advisory Gate, FREE confirmation drafts, Workbench review, user signature or dual-signature rule mode, and then Rule Center / Data Center governance.

中文一句話：SCBKR 先讓使用者像一般大模型一樣聊天，再把「可重用、可引用、要承擔」的內容升級成 S/C/B/K/R 規則確認單。

English one-line: SCBKR starts as normal AI chat, then upgrades reusable, citable, responsibility-bearing content into S/C/B/K/R confirmation sheets.

## Productized Runnable Build｜完整可運行版

- 中文：目前前端已收束為四個主產品頁：一般聊天、SCBKR 工作台、規則中心、資料中心；手機版改為單欄主流程，避免桌機三欄介面擠壓。
- English: The current frontend is organized around four product pages: Chat, SCBKR Workbench, Rule Center, and Data Center; mobile now uses a single-column primary flow instead of squeezing the desktop three-column layout.
- 中文：聊天偵測到「幫我生成規則」時會先顯示第0原理建議閘；使用者按「草擬確認單」後立即進工作台，先顯示可編輯 S/C/B/K/R 草稿，再由後端正式 task 覆蓋。
- English: When chat detects rule-generation intent, it shows the Zeroth Principle Advisory Gate; pressing “Draft confirmation” immediately opens the Workbench with editable S/C/B/K/R, then replaces the provisional draft with the formal backend task.
- 中文：模型可草擬與補欄位，但不能簽名、驗收、入庫或啟用規則；正式引用只允許 signed / reviewed / active 的本地規則與資料。
- English: The model may draft and fill fields, but it cannot sign, review, store, or activate rules; formal citation is limited to signed / reviewed / active local rules and evidence.
- 中文：回答前會產生最小 `current_rule_package`，標記 `chat_context_used: false`，避免把完整記憶庫塞給模型；VECTOR 僅能做候選召回，不能當正式 K 依據。
- English: Before answering, SCBKR compiles a minimal `current_rule_package` with `chat_context_used: false`, avoiding full-memory prompts; VECTOR is recall-only and cannot be formal K evidence.
- 中文：本機開發啟動：`python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787`，另開一個視窗執行 `npm --prefix apps/web run dev`。
- English: Local development: run `python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787`, then run `npm --prefix apps/web run dev` in another terminal.
- 中文：驗收命令：`python -m pytest -q`、`npm --prefix apps/web run test:ui`、`npm --prefix apps/web run build`。
- English: Acceptance commands: `python -m pytest -q`, `npm --prefix apps/web run test:ui`, and `npm --prefix apps/web run build`.

## 1. 快速理解｜Quick Overview

- 中文：預設首頁是一般聊天；聊天可寫文案、摘要文件、讀四庫、查資料，也可以在使用者要求時升級成規則草稿。
- English: The default home surface is normal chat for writing, summarizing, reading stores, searching, and optionally promoting content into rule drafts.
- 中文：第0原理建議閘只在「變成規則、建立確認單、以後照這個做、可重複使用」等意圖出現時觸發；觸發後仍不自動建規則、不自動入庫。
- English: The Zeroth Principle Advisory Gate appears only when reusable-rule intent is detected; it does not auto-create rules or store data.
- 中文：模型可以聊天、摘要、草擬、建議與協作補欄位，但不能簽名、驗收、二次確認入庫、自動啟用規則或繞過 OwnerReview。
- English: The model may chat, summarize, draft, suggest, and help fill fields, but it cannot sign, review, second-confirm storage, activate rules, or bypass OwnerReview.

## 2. 目前版本｜Current Version

- 中文：產品版本為 `SCBKR 2.3`，階段為 `2.3-chat-first-ui-alignment`。
- English: Product version is `SCBKR 2.3`, stage `2.3-chat-first-ui-alignment`.
- 中文：Web 與 FastAPI Runtime 版本為 `2.3.0`；Desktop / Tauri metadata 仍保留既有 RC 線，避免混淆桌面殼版本與產品能力版本。
- English: The Web and FastAPI runtime versions are `2.3.0`; Desktop / Tauri metadata remains on its existing RC line so shell metadata and product capability versions stay distinct.
- 中文：安裝檔程式碼簽章、自動更新與商店封裝仍未提供，也不內建模型或 API key。
- English: Installer code signing, auto-update, and store packaging are not yet provided; no model or API key is bundled.

## 3. Chat-first Flow｜聊天優先流程

- 中文：一般聊天 → 第0原理建議閘 → FREE 確認單草稿 → Workbench 協作編輯 → 使用者簽名 / 雙簽模式 → 規則中心 → 資料中心。
- English: Normal chat → Zeroth Principle Advisory Gate → FREE confirmation draft → Workbench collaboration → user signature / dual-signature mode → Rule Center → Data Center.
- 中文：FREE 可以生成確認單草稿、S/C/B/K/R 初稿、送到 Workbench、模型協作補草稿、使用者自簽、入庫為使用者自己的規則。
- English: FREE can create confirmation drafts, S/C/B/K/R initial drafts, send them to Workbench, let the model assist with draft fields, allow user self-signature, and store user-owned rules.
- 中文：NT$690 是責任鏈結構輔助層，不是確認單生成門檻。
- English: NT$690 is the responsibility-structure assistance layer, not a paywall for creating confirmation drafts.
- 中文：NT$3,300 是規則書閉環層，包含沈耀強制簽名 + 使用者簽名、成立 / 失效條件、風險、修復、回放、RulePack 與 OwnerReview。
- English: NT$3,300 is the rulebook closure layer with ShenYao creator signature + user signature, formation / invalidation conditions, risks, repair paths, replay requirements, RulePacks, and OwnerReview.

## 4. 2.3 目前能做什麼｜What 2.3 Can Do

- 中文：建立 S/C/B/K/R 任務確認單、使用者簽名、生成、驗收、入庫請求、二次確認、Data Center 檢視與四庫引用。
- English: It supports S/C/B/K/R task confirmation, owner signature, generation, review, storage request, second confirmation, Data Center viewing, and four-store evidence reuse.
- 中文：模型只能提出草案或建議，不能自行簽名、驗收、入庫或修改已寫入資料。
- English: The model may draft or suggest, but it cannot sign, review, store, or rewrite committed evidence by itself.
- 中文：具名、版本化、簽名、Active 的規則可控制模型與工具；向量檢索只能找候選，不能取代正式 K 依據。
- English: Attributed, versioned, signed, Active rules control models and tools; vector retrieval may find candidates but cannot replace authoritative K evidence.

## 5. Desktop Mode 與 LAN Companion Mode｜Desktop Mode and LAN Companion Mode

### Desktop Mode｜預設模式

- 中文：Windows Desktop RC 預設綁定 `http://127.0.0.1:8787`，只能本機電腦連線，這是最安全模式。
- English: The Windows Desktop RC binds to `http://127.0.0.1:8787` by default; only the local computer can connect, which is the safest mode.
- 中文：預設模式下，手機不能直接用 `192.168.x.x` 連入。
- English: In default mode, a phone cannot directly connect through `192.168.x.x`.

### LAN Companion Mode｜使用者手動開啟

- 中文：使用者手動啟動 LAN Companion Mode 後，sidecar 才可綁定 `0.0.0.0:8787`。
- English: Only after the user manually starts LAN Companion Mode may the sidecar bind to `0.0.0.0:8787`.
- 中文：手機可在同 Wi-Fi / LAN 開啟 `http://192.168.x.x:8787/`，再輸入桌機產生的 6 位數一次性配對碼。
- English: A phone on the same Wi-Fi / LAN opens `http://192.168.x.x:8787/` and enters the one-time six-digit code generated on the desktop.
- 中文：LAN Companion Mode 不會預設開啟；配對碼 10 分鐘失效且只能使用一次，桌機可撤銷已配對裝置。
- English: LAN Companion Mode is never enabled by default. Pairing codes expire after ten minutes, are one-time use, and paired devices can be revoked from the desktop.

## 6. 完整責任鏈流程｜Responsibility Chain Flow

![責任鏈流程](docs/images/responsibility-loop.png)
![Responsibility chain flow](docs/images/responsibility-loop-en.png)

- 中文：輸入任務 → 產生確認單 → 使用者簽名 → 模型生成 → 使用者驗收 → 入庫建議 → 二次確認 → 寫入四庫 / Data Center。
- English: Input task → build confirmation sheet → owner signature → model generation → user review → storage suggestion → second confirmation → write to four stores / Data Center.

## 7. Workbench 與使用者簽名｜Workbench and Owner Signature

![Workbench 使用者簽名](docs/images/workbench-owner-signature.png)
![Workbench owner signature](docs/images/workbench-owner-signature-en.png)

- 中文：Workbench 是使用者檢查與修改 S/C/B/K/R 的地方；任何修改都會使舊簽名與下游生成、驗收、入庫狀態作廢。
- English: The Workbench is where the user reviews and edits S/C/B/K/R; any edit invalidates the old signature and downstream generation, review, and storage state.
- 中文：模型不能簽名，`confirmed_by` 必須是 `user`，signature 不可空。
- English: The model cannot sign; `confirmed_by` must be `user`, and the signature cannot be empty.

## 8. Data Center 與四庫｜Data Center and Four Stores

![四庫引用](docs/images/four-store-evidence.png)
![Four-store evidence](docs/images/four-store-evidence-en.png)

- 中文：四庫只能是 `vector`、`corpus`、`logic`、`memory`。
- English: The only allowed stores are `vector`, `corpus`, `logic`, and `memory`.
- 中文：`exports` 不是 storage target，也不得恢復為 storage target。
- English: `exports` is not a storage target and must not be restored as one.
- 中文：Data Center 更新 / 刪除必須有使用者簽名；revoked / archived / superseded 資料不得作為可用引用。
- English: Data Center update / delete requires user signature; revoked / archived / superseded evidence cannot be reused as available evidence.

## 9. 本地模型支援｜Local Model Support

![本地模型架構](docs/images/architecture.png)
![Local model architecture](docs/images/local-model-architecture-en.png)

- 中文：2.0 支援 sandbox、本地 LLM、LM Studio、Ollama 或 OpenAI-compatible endpoint 設定。
- English: 2.0 supports sandbox, local LLM, LM Studio, Ollama, or an OpenAI-compatible endpoint.
- 中文：外部 API 權限預設關閉；非 loopback 模型網址需要使用者開啟 external API guard。
- English: External API permission is off by default; non-loopback model URLs require the user to enable the external API guard.

## 10. Windows 安裝與啟動｜Windows Setup

- 中文：Desktop RC 預設啟動本機 sidecar：`http://127.0.0.1:8787`。
- English: The Desktop RC starts the local sidecar by default at `http://127.0.0.1:8787`.
- 中文：健康檢查：`curl http://127.0.0.1:8787/health`。
- English: Health check: `curl http://127.0.0.1:8787/health`.
- 中文：一般使用者不需要 Python、Node、npm、uvicorn、PowerShell、LM Studio、Ollama 或 API key 即可測試 sandbox 流程。
- English: Normal users do not need Python, Node, npm, uvicorn, PowerShell, LM Studio, Ollama, or an API key to test the sandbox flow.

## 11. 手機遙控｜Mobile Companion

![Mobile Companion](docs/images/mobile-companion-en.png)

- 中文：手機不是直接連本地 LLM。
- English: The phone does not connect directly to the local LLM.
- 中文：手機只是操作入口。
- English: The phone is only an operation entry point.
- 中文：手機瀏覽器先連到電腦上的 SCBKR LAN Companion Web UI。
- English: The phone browser connects to the SCBKR LAN Companion Web UI running on the computer.
- 中文：手機 → SCBKR 後端 → 本地 LLM。所有模型呼叫仍由電腦上的 SCBKR 後端執行。
- English: Phone → SCBKR backend → local LLM. All model calls are still executed by the SCBKR backend on the computer.
- 中文：本地 LLM / LM Studio / Ollama / OpenAI-compatible API 仍由電腦端設定。
- English: Local LLM / LM Studio / Ollama / OpenAI-compatible API settings remain computer-side settings.
- 中文：手機端不能繞過使用者簽名、驗收、二次確認、Data Center Gate 或四庫限制。
- English: The phone cannot bypass owner signature, user review, second confirmation, the Data Center Gate, or four-store limits.
- 中文：啟動方式：在 Windows 上執行 `powershell -ExecutionPolicy Bypass -File scripts/start_lan_companion_windows.ps1`，依畫面顯示的 URL 在手機瀏覽器開啟。
- English: Start it on Windows with `powershell -ExecutionPolicy Bypass -File scripts/start_lan_companion_windows.ps1`, then open the displayed URL in the phone browser.

## 12. 隱私與安全邊界｜Privacy and Safety Boundary

- 中文：預設 Desktop Mode 僅本機可連，LAN Companion Mode 只適合可信任 Wi‑Fi。
- English: Default Desktop Mode is local-only; LAN Companion Mode should only be used on trusted Wi‑Fi.
- 中文：不要公開手機配對碼或已配對憑證；憑證不寫入 Git，也不固定寫死。
- English: Do not publish pairing codes or paired-device credentials; credentials are never committed to Git or hard-coded.

## 13. 與 Chatbot / Agent / RAG 的差異｜Difference from Chatbot / Agent / RAG

- 中文：Chatbot 重點是對話；Agent 重點是自動行動；RAG 重點是檢索增強。SCBKR 重點是責任鏈、簽名、驗收、入庫與未來引用邊界。
- English: Chatbots focus on conversation; agents focus on autonomous action; RAG focuses on retrieval augmentation. SCBKR focuses on responsibility chain, signature, review, storage, and future reuse boundaries.

## 14. 2.1 規則狀態與上線層｜2.1 Rule State and Launch Layer

![2.0 Roadmap](docs/images/roadmap-2.0-en.png)

- 中文：2.0 基礎能力仍包含 Rule Registry、使用者自有 RulePack 匯入、規則命中 Gate、五道工具權限 Gate、執行回放、嚴格 JSON 編譯器與 token 效率統計。
- English: The 2.0 foundation still includes the Rule Registry, user-owned RulePack import, rule-match gates, five tool permission gates, execution replay, a strict JSON compiler, and token-efficiency metrics.
- 中文：2.1 加入受保護的沈耀規則狀態 Runtime、版本／模式選擇、使用者規則覆寫驗算、真實網頁搜尋與閱讀、訂閱介面及上線準備中心。
- English: 2.1 adds the protected ShenYao Rule State Runtime, version and mode selection, user-overlay validation, real web search and page reading, subscription surfaces, and a launch readiness center.
- 中文：RuleStateManager 會在每次模型呼叫前注入 `EMPTY / DRAFTING / RULE_ACTIVE / RULEPACK_ACTIVE` 狀態；只有已驗證的沈耀 Runtime 可輸出「沈耀交我判的／主責歸耀／唯真長存」，失效或未授權狀態會自動阻擋。
- English: RuleStateManager injects `EMPTY / DRAFTING / RULE_ACTIVE / RULEPACK_ACTIVE` before every model call. ShenYao ownership declarations are allowed only under a verified ShenYao runtime and are blocked after expiry or without authorization.
- 中文：訂閱提供 Runtime 執行資格，不散布私有規則原始碼。使用者仍可匯入自己擁有的規則；未啟用沈耀狀態時會明確顯示為獨立規則狀態。
- English: Subscriptions grant runtime execution entitlement without distributing private rule source. Users may still import rules they own; without ShenYao state, the product clearly reports an independent rule state.

## 15. 開發者快速啟動｜Developer Quick Start

```bash
python -m pytest -q
npm --prefix apps/web run build
npm --prefix apps/desktop run check:skeleton
npm --prefix apps/desktop run check:release
```

- Windows 一鍵開啟完整本機 UI：`powershell -ExecutionPolicy Bypass -File scripts/start_ui_review_windows.ps1`
- 桌機與手機版實機驗收：`powershell -ExecutionPolicy Bypass -File scripts/run_ui_acceptance_windows.ps1`
- UI 驗收會啟動真實 FastAPI 與 Web UI、操作主要頁面、檢查瀏覽器錯誤與畫面溢出，並將各頁截圖附在 HTML 報告中。
- UI acceptance starts the real FastAPI and Web UI, exercises primary pages, checks browser errors and viewport overflow, and attaches screenshots to an HTML report.

- 中文：本機 API 預設：`http://127.0.0.1:8787`。
- English: Default local API: `http://127.0.0.1:8787`.
- 中文：API base 會依 runtime matrix 判斷：LAN Companion 頁面使用目前頁面 origin；localhost dev / preview 頁面仍連回 FastAPI sidecar `http://127.0.0.1:8787`；`VITE_SCBKR_API_URL` 永遠最高優先。
- English: The API base follows a runtime matrix: LAN Companion pages use the current page origin, localhost dev / preview pages still call the FastAPI sidecar at `http://127.0.0.1:8787`, and `VITE_SCBKR_API_URL` always has the highest priority.

## 16. 測試與驗收｜Testing and Validation

- 中文：Release readiness 檢查包含 sidecar host/port、LAN token、web-dist 服務、frontend API base、Gate 保存、README 圖片與文件連結。
- English: Release readiness checks cover sidecar host/port, LAN token, web-dist serving, frontend API base, gate preservation, README images, and documentation links.
- 中文：Windows 上可執行 release build / smoke / LAN Companion smoke PowerShell 腳本。
- English: On Windows, run the release build / smoke / LAN Companion smoke PowerShell scripts.

## 17. 2.1 發布狀態｜2.1 Release Readiness

- 中文：`2.1.0` 為上線候選版。產品內已提供上線中心與準備度檢查；正式送審仍需作者提供網域、Supabase、Stripe、搜尋服務、Partner Center、簽章及法律頁面資料。
- English: `2.1.0` is a launch candidate. The app includes a launch center and readiness checks; store submission still requires owner-provided domain, Supabase, Stripe, search, Partner Center, signing, and legal configuration.
- 中文：Desktop Mode 預設 local-only；LAN Companion Mode 需手動啟動並以一次性配對碼授權手機。
- English: Desktop Mode is local-only by default; LAN Companion Mode requires manual launch and one-time code pairing.

## 18. License / Author

- 中文：作者：許文耀／沈耀888pi，語意防火牆。授權請以 repository license 為準。
- English: Author: Wen-Yao Hsu / ShenYao888pi, Semantic Firewall. License follows the repository license.
