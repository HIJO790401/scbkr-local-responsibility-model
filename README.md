SCBKR 本地責任鏈模型｜自接入 MVP App

SCBKR Local Responsibility Chain Model｜Self-Connected MVP App

---

中文版

一、產品定位

SCBKR 本地責任鏈模型 是一套本地 AI 工作流控制層。

它不是一般聊天機器人。
它不是單純 RAG。
它不是大模型公司。
它不是直接替使用者產生答案的工具。

SCBKR 的核心不是讓模型「立刻回答」，而是讓模型在回答之前，先交代任務責任鏈。

它讓使用者可以在自己的電腦上，自行接入：

- LM Studio
- Ollama
- OpenAI-compatible API
- 其他自訂模型 endpoint

並透過 SCBKR 五維確認流程，建立一套可確認、可驗收、可回放、可持續累積的本地 AI 工作台。

核心理念：

«模型不是先回答，而是先交代。
模型不是先生成，而是先確認。
不要讓模型替你決定對錯。
建立你自己的責任鏈模型。»

---

二、SCBKR 解決什麼問題

一般 AI 工具常見問題是：

- 使用者一輸入，模型立刻生成。
- 任務目的不清楚，模型仍然硬答。
- 權限、資料來源、風格、驗收條件沒有先確認。
- 模型生成錯誤後，使用者只能重問。
- 每次任務都從零開始，無法累積有效判準。
- 成本浪費在大量無效 token、重複生成、錯誤修正與無責任輸出上。

SCBKR 改變這個流程。

SCBKR 不讓模型直接衝出去回答，而是先建立一份 SCBKR 五維確認單：

- S｜介面 / 主體：確認任務名稱、主體、輸入、輸出形式。
- C｜後端 / 因果：確認流程、順序、資料流、依賴與失敗影響。
- B｜邊界 / 行為：確認可讀取、可寫入、可呼叫、可停止的範圍。
- K｜依據 / 風格：確認參考資料、風格、模型依據與來源可信度。
- R｜回放 / 簽名：確認驗收條件、回放紀錄、入庫選項與簽名狀態。

只有使用者確認後，模型才可以生成。

P12 目前保留「一鍵確認責任鏈」操作，但底層不再只是設定單一 `confirmed` boolean。一鍵確認會批次確認 S / C / B / K / R 五個維度，並為每一維封存 `confirmed_at`、`confirmed_by`、`snapshot_hash` 與 `confirmed_snapshot`，讓當時確認的五維責任鏈版本可回放、可審計。generate 前也必須通過五維全部 confirmed 的安全閘門，且 live dimension payload 必須仍與封存 snapshot 相符；確認後若 S/C/B/K/R 任一業務內容被修改，舊 seal 會失效並拒絕 generate。

---

三、核心流程

SCBKR 的固定流程是：

使用者輸入任務
→ 系統建立 task
→ 系統產生 SCBKR 五維確認單
→ 使用者修改或確認
→ confirmed 後模型才可執行
→ 模型依照已確認責任鏈生成
→ 使用者驗收
→ 驗收通過後才可詢問是否入庫
→ 使用者二次確認
→ 產生入庫計畫
→ 回放紀錄保留流程軌跡

MVP 版目前以 in-memory runtime 跑通本地流程。
正式 SQLite、ChromaDB、ledger JSONL、memory physical write 仍屬於後續階段。

---

四、功能概覽

目前 MVP 可跑功能：

- 本地 FastAPI 後端
- React + Vite + TypeScript 前端
- 任務建立
- SCBKR 五維確認單生成
- 使用者確認後才允許生成
- 模型設定
- LM Studio / Ollama / OpenAI-compatible API 接入
- 模型連線測試
- 權限鎖
- 生成安全閘門
- 驗收 pass / fail / rollback
- 入庫計畫
- 驗收失敗報告草案
- 使用者明確觸發的失敗規則草案
- 使用者簽名後的 memory rule confirmed plan
- API key 遮罩
- 手機同 Wi-Fi 連線使用

---

五、SCBKR 如何降低成本

SCBKR 的成本優化不是靠壓低模型能力，而是靠減少無效生成。

一般 AI 使用常見浪費：

- 任務沒講清楚就生成。
- 模型答錯後反覆重問。
- 每次都重新解釋背景。
- 沒有驗收標準，導致生成結果不可用。
- 同類任務無法複用已確認流程。
- 大模型被拿去處理本來可以先被規則分流的小任務。

SCBKR 透過責任鏈降低浪費：

1. 減少無效 token

模型在生成前，先經過 SCBKR 確認單。
任務目的、輸出形式、邊界、依據、驗收條件先被整理清楚。
這可以降低「模型猜錯方向後大量輸出廢內容」的機率。

2. 減少重複生成

已確認過的任務結構可以被保存為責任鏈案例。
未來相似任務可以參考既有 S / C / B / K / R，不必每次從零開始。

3. 降低電費與運算浪費

本地 LLM 或外部 API 都有成本。
每一次無效生成，都代表額外 token、額外推理時間、額外電力、額外等待時間。
SCBKR 的流程控制讓模型在更明確的條件下執行，減少盲目試錯。

4. 小模型也能參與工作流

SCBKR 把「任務確認、權限、驗收、回放」放在模型外層。
因此部分工作不必全部丟給大模型。
使用者可以用較小的本地模型跑流程測試，再依任務需求切換更強模型。

5. 錯誤不污染記憶

驗收失敗不會自動進入記憶庫。
失敗只會形成 failure report draft。
只有使用者明確判定錯因、寫出規則、並簽名確認後，才會形成 memory rule confirmed plan。
這避免系統把錯誤答案當成長期知識，降低後續修正成本。

---

六、權限與安全邊界

SCBKR 的核心原則是：

«工具未啟用，不得宣稱已執行。
模型未測通，不得宣稱可用。
使用者未確認，不得生成。
驗收未通過，不得入庫。
失敗輸出不得污染記憶。»

目前權限鎖包含：

- "model_generate"
- "external_api"
- "dangerous_operation_confirmed"
- "storage_write"
- "ledger_write"
- "sqlite_runtime"
- "chromadb_runtime"
- "embedding_create"
- "memory_write"

external / hybrid mode 使用外部 API 時，必須同時通過：

external_api = true
dangerous_operation_confirmed = true

否則不得呼叫外部 API。

---

七、MVP 邊界

目前可跑：

- FastAPI health / status
- 模型設定與連線測試
- 權限設定
- 任務建立
- SCBKR 草案
- 使用者確認
- 生成閘門
- 驗收
- 入庫計畫
- P11 失敗報告草案
- 使用者明確觸發的失敗規則草案與確認計畫

目前仍為 MVP in-memory：

- 任務 runtime
- 模型設定 runtime
- 權限設定 runtime

目前仍 pending：

- 正式 SQLite 持久化
- 正式 ChromaDB / embedding runtime
- 正式 ledger append runtime
- 正式 memory physical write
- 桌面安裝包
- 雲端 SaaS 版
- 手機外網遠端連線

---

八、固定端口

後端 API：http://localhost:8787
前端 Web：http://localhost:5500

---

九、快速開始

python -m pip install -e .
npm --prefix apps/web install --package-lock=false
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787
npm --prefix apps/web run dev

打開：

http://localhost:5500

---

十、模型接入

預設適合 LM Studio：

http://localhost:1234/v1

Ollama OpenAI-compatible endpoint 可使用：

http://localhost:11434/v1

外部 API 可使用 OpenAI-compatible endpoint。
API key 在讀取設定時只會遮罩，不會明文回傳。

---

十一、手機同 Wi-Fi 使用

若前端開發伺服器改用區網 host 啟動，手機與電腦在同一個 Wi-Fi 下，可用手機打開：

http://{電腦區網IP}:5500

P12 不自動設定外網 tunnel，也不提供手機原生 App。

---

十二、產品階段

目前版本定位：

SCBKR 本地責任鏈模型｜自接入 MVP App

下一階段可選：

- 桌面封裝：Electron / Tauri
- 本地主機手機連線
- SQLite / ledger / ChromaDB / memory 持久化 runtime
- 雲端收費版
- 固化規則庫裁決服務

---

十三、簽名

語意防火牆創辦人
許文耀 / 沈耀888π

---

English Version

1. Product Positioning

SCBKR Local Responsibility Chain Model is a local AI workflow control layer.

It is not a general chatbot.
It is not a simple RAG tool.
It is not a large model company.
It is not a tool that lets the model directly decide and answer for the user.

The core of SCBKR is not “answer immediately.”
The core of SCBKR is “declare the responsibility chain before generation.”

SCBKR allows users to run a local AI responsibility-chain workspace on their own computer and connect their own:

- LM Studio
- Ollama
- OpenAI-compatible API
- Custom model endpoint

The system guides every task through a five-dimensional confirmation process before generation.

Core principle:

«The model does not answer first. It explains first.
The model does not generate first. It confirms first.
Do not let the model decide what is right or wrong for you.
Build your own responsibility-chain model.»

---

2. What SCBKR Solves

Common problems in regular AI tools:

- The model generates immediately after user input.
- The task goal is unclear, but the model still answers.
- Permissions, data sources, style, and acceptance criteria are not confirmed first.
- When the output is wrong, users can only ask again.
- Every task starts from zero.
- Cost is wasted on invalid tokens, repeated generation, failed outputs, and unverified results.

SCBKR changes this process.

Before generation, SCBKR creates a five-dimensional confirmation sheet:

- S｜Subject / Interface: task name, subject, input, output format.
- C｜Causality / Backend: process, order, data flow, dependencies, failure impact.
- B｜Boundary / Behavior: read scope, write scope, permissions, stop conditions.
- K｜Knowledge / Style: references, style, model basis, source credibility.
- R｜Replay / Signature: acceptance criteria, replay record, storage options, signature status.

Only after the user confirms the responsibility chain can the model generate.

---

3. Core Workflow

User enters a task
→ System creates a task
→ System generates the SCBKR five-dimensional confirmation sheet
→ User modifies or confirms it
→ Model can only generate after confirmation
→ Model generates according to the confirmed responsibility chain
→ User reviews the output
→ Storage can only be requested after review passes
→ User confirms storage again
→ System creates a storage plan
→ Replay trail preserves the process

The current MVP uses an in-memory runtime to validate the local workflow.
Formal SQLite, ChromaDB, JSONL ledger, and memory physical write are still pending stages.

---

4. Feature Overview

Current MVP features:

- Local FastAPI backend
- React + Vite + TypeScript frontend
- Task creation
- SCBKR five-dimensional draft generation
- Generation only after user confirmation
- Model settings
- LM Studio / Ollama / OpenAI-compatible API connection
- Model connection test
- Permission lock
- Generation safety gate
- Review: pass / fail / rollback
- Storage planning
- Failure report draft
- User-triggered failed-memory rule draft
- User-signed memory rule confirmed plan
- API key masking
- Same Wi-Fi mobile access

---

5. How SCBKR Reduces Cost

SCBKR does not reduce cost by weakening the model.
It reduces cost by reducing invalid generation.

Typical AI cost waste comes from:

- Generating before the task is clear.
- Repeatedly asking again after wrong answers.
- Re-explaining the same background every time.
- No acceptance criteria, causing unusable outputs.
- No reusable task structure.
- Using large models for tasks that should first be filtered by rules.

SCBKR reduces waste through responsibility-chain control.

1. Fewer wasted tokens

Before generation, the task goal, output format, boundaries, references, and acceptance criteria are clarified.
This reduces the chance of the model generating a large but unusable answer.

2. Less repeated generation

Confirmed task structures can become reusable responsibility-chain cases.
Similar future tasks can refer to existing S / C / B / K / R structures instead of starting from zero.

3. Lower electricity and compute waste

Local LLMs and external APIs both have cost.
Every invalid generation consumes tokens, inference time, electricity, and user attention.
SCBKR helps the model run under clearer conditions, reducing blind trial-and-error.

4. Smaller models can be useful

SCBKR places task confirmation, permissions, review, and replay outside the model.
This means not every workflow must rely entirely on a large model.
Users can test the flow with smaller local models and switch to stronger models only when needed.

5. Failed outputs do not pollute memory

A failed review does not automatically enter memory.
Failure only creates a failure report draft.
Only when the user explicitly defines the failure judgment, rule statement, scope, and signature can it become a memory rule confirmed plan.
This prevents wrong outputs from becoming long-term knowledge.

---

6. Permission and Safety Boundaries

SCBKR follows these rules:

«If a tool is not enabled, the system must not claim it was used.
If the model test fails, the model must not be treated as available.
If the user has not confirmed the responsibility chain, generation is not allowed.
If the review has not passed, storage is not allowed.
Failed outputs must not pollute memory.»

Permission locks include:

- "model_generate"
- "external_api"
- "dangerous_operation_confirmed"
- "storage_write"
- "ledger_write"
- "sqlite_runtime"
- "chromadb_runtime"
- "embedding_create"
- "memory_write"

For external / hybrid API mode, both must be true:

external_api = true
dangerous_operation_confirmed = true

Otherwise, external API calls are not allowed.

---

7. MVP Boundaries

Currently runnable:

- FastAPI health / status
- Model settings and connection test
- Permission settings
- Task creation
- SCBKR draft
- User confirmation
- Generation gate
- Review
- Storage plan
- P11 failure report draft
- User-triggered failed-rule draft and confirmed plan

Currently MVP in-memory only:

- Task runtime
- Model settings runtime
- Permission settings runtime

Still pending:

- Formal SQLite persistence
- Formal ChromaDB / embedding runtime
- Formal JSONL ledger append runtime
- Formal memory physical write
- Desktop installer
- Cloud SaaS version
- Mobile external-network remote access

---

8. Fixed Ports

Backend API: http://localhost:8787
Frontend Web: http://localhost:5500

---

9. Quick Start

python -m pip install -e .
npm --prefix apps/web install --package-lock=false
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787
npm --prefix apps/web run dev

Open:

http://localhost:5500

---

10. Model Connection

Default LM Studio endpoint:

http://localhost:1234/v1

Ollama OpenAI-compatible endpoint:

http://localhost:11434/v1

External OpenAI-compatible APIs can also be used.
API keys are masked when settings are read and are not returned in plain text.

---

11. Same Wi-Fi Mobile Use

If the frontend dev server is started with a LAN host, a phone on the same Wi-Fi can open:

http://{computer_lan_ip}:5500

P12 does not automatically configure external tunnels and does not provide a native mobile app.

---

12. Product Stage

Current version:

SCBKR Local Responsibility Chain Model｜Self-Connected MVP App

Possible next stages:

- Desktop packaging: Electron / Tauri
- Local host + mobile access
- SQLite / ledger / ChromaDB / memory persistent runtime
- Cloud paid version
- Fixed-rule adjudication service

---

13. Signature

Founder of Semantic Firewall
Wen-Yao Hsu / ShenYao888π
### P12 sealed SCBKR generation boundary

- Model generation reads only the sealed `confirmed_snapshot.payload` business payload for S/C/B/K/R.
- Confirmation metadata such as `confirmation_statement`, `confirmed_at`, `snapshot_hash`, and `confirmed_snapshot` is audit/replay state and is not sent into the model prompt.
- If a confirmed dimension's business payload is modified after sealing, generation is rejected until the dimension is reconfirmed.
- If only confirmation metadata is modified after sealing, the model-visible payload remains unchanged.
- `schemas/scbkr.schema.json` recognizes confirmed dimensions and their seal fields while preserving the original business-field schemas.
- Desktop packaging is not designed yet and remains pending; this Web MVP does not add Electron, Tauri, or an installer.

### P13-A SQLite + JSONL persistence runtime

P13-A now supports local workflow persistence without expanding into P13-B/P13-C storage runtimes:

- Tasks are saved to `data/scbkr.sqlite3` with Python's standard `sqlite3` runtime.
- Flow events are appended to `data/ledger/audit-log.jsonl`, which is the replay source of record and must not be overwritten.
- SQLite `ledger_index` stores query/index metadata and can be rebuilt from the JSONL ledger.
- `GET /api/tasks/{task_id}` can recover a task from SQLite after the in-memory `TASKS` cache is cleared.
- P13-A does not add ChromaDB, embeddings, memory physical write, corpus/logic/vector physical write, desktop packaging, Electron, Tauri, or installers.

### P13-A data-safety fixes

- New API tasks use collision-resistant IDs in the form `task-{UTC timestamp}-{uuid8}` so a process restart cannot reset the in-memory counter and overwrite an older persisted task.
- Tests and local isolated runs can set `SCBKR_DATA_DIR` to redirect SQLite and JSONL runtime files away from the default `data/` directory; the integration tests use this to avoid deleting production-like repo data.
- `ledger_index` rebuild first clears the SQLite index, then recreates it from JSONL so dirty rows not present in the append-only ledger are removed.

### P13-B physical storage layer

- P13-B supports local JSON physical writes after `review_passed` plus explicit storage confirmation (`storage_confirmed=true`, `confirmed_by="user"`, and a non-empty signature): successful content is written to `data/corpus`, responsibility-chain logic to `data/logic`, and replay/export bundles to `data/exports`.
- Signed memory rules are written to `data/memory` only after `memory_rule_confirmed_plan` is created with a user `reviewer_signature`.
- `physical_write_performed=true` appears only after a legal storage commit succeeds.
- `vector_db`, ChromaDB, embeddings, and vector search remain P13-C pending; P13-B does not create `data/vector_db`.
- P13-B does not include desktop packaging, Electron, Tauri, or installers.

### P13-C similar-case retrieval runtime

P13-C now supports advisory retrieval over legally committed local content without adding desktop packaging:

- `storage_committed` tasks can be indexed as retrieval cases after review pass, storage confirmation, physical write, and signature.
- Signed memory rules can be indexed as retrieval cases; unsigned memory-rule drafts are not indexed.
- Similarity queries return deterministic `A` / `B` / `C` / `none` routes.
- Retrieval results are hints only: `requires_user_confirmation=true`, `auto_confirmed=false`, and `generation_allowed=false`.
- ChromaDB is optional. If local ChromaDB is unavailable, SCBKR uses deterministic pure-Python fallback retrieval or reports the backend as unavailable without crashing.
- P13-C does not include desktop packaging. Tauri, Electron, installers, and sandbox mode remain P14 scope.
