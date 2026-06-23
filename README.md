SCBKR 本地責任鏈模型｜自接入 MVP App

SCBKR Local Responsibility Chain Model｜Self-Connected MVP App

---

一、產品定位

SCBKR 本地責任鏈模型是一套本地 AI 工作流控制層。

它不是一般聊天機器人。
它不是單純 RAG。
它不是大模型公司。
它不是直接替使用者決定答案的工具。

SCBKR 的核心不是讓模型「立刻回答」，而是讓模型在回答之前，先交代任務、邊界、依據、驗收與責任鏈。

使用者可以在自己的電腦上，自行接入：

- LM Studio
- Ollama
- OpenAI-compatible API
- 其他自訂模型 endpoint

並透過 SCBKR 五維確認流程，建立一套可確認、可驗收、可回放、可入庫、可持續累積的本地 AI 工作台。

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
- 模型生成錯誤後，使用者只能反覆重問。
- 每次任務都從零開始，無法累積有效判準。
- 大量成本浪費在無效 token、重複生成、錯誤修正與無責任輸出上。

SCBKR 改變這個流程。

SCBKR 不讓模型直接衝出去回答，而是先建立一份 SCBKR 五維確認單：

- S｜介面 / 主體：確認任務名稱、主體、輸入內容、輸出形式與操作介面。
- C｜後端 / 因果：確認流程、順序、資料流、依賴、測試條件與失敗影響。
- B｜邊界 / 行為：確認可讀取、可寫入、可呼叫、可停止、可入庫的範圍。
- K｜依據 / 風格：確認參考資料、風格、模型依據、來源可信度與歷史案例。
- R｜回放 / 簽名：確認驗收條件、回放紀錄、入庫選項、簽名狀態與審計資料。

只有使用者確認後，模型才可以生成。

---

三、核心流程

SCBKR 的固定流程是：

使用者輸入任務
→ 系統建立 task
→ 系統查詢 Data Center / 四庫
→ 模型根據使用者輸入與已確認規則產生 SCBKR 五維草案
→ 使用者修改或確認
→ confirmed 後模型才可正式生成
→ 模型依照已確認責任鏈輸出結果
→ 使用者驗收
→ 驗收通過後才可產生入庫建議
→ 使用者選擇寫入哪些庫
→ 使用者二次確認
→ 寫入本地 Data Center / 四庫
→ ledger / hash / replay 保留完整軌跡
→ 下次任務可再次引用已確認規則

SCBKR 的目標不是讓模型自由猜，而是：

«有已確認規則，就必須引用。
有相似案例，就必須標示沿用或調整。
有衝突，就必須交給使用者確認。
沒有命中資料時，模型才可以產生待確認草案。»

---

四、四庫與 Data Center

SCBKR 的 Data Center 不是展示頁，而是模型未來工作的規則來源層。

四庫包含：

1. 向量庫｜Vector Store

用於相似任務檢索、責任鏈案例索引、降低重複推理。

用途：

- 找相似任務
- 引用已驗收案例
- 降低重複 token
- 提供未來任務的參考路徑

2. 語料庫｜Corpus Store

用於保存使用者確認過的原始資料、文件、內容依據。

用途：

- 保存外部文件
- 保存原始文本
- 保存任務依據
- 避免模型憑空編造來源

3. 程式邏輯庫｜Logic Store

用於保存可重用流程、API 邏輯、UI 狀態機、測試條件與規則模板。

用途：

- 保存流程設計
- 保存產品邏輯
- 保存工程規則
- 保存可重用工作流

4. 記憶庫｜Memory Store

用於保存使用者確認過的長期偏好、禁止規則、判斷標準與個人化規則。

用途：

- 保存長期偏好
- 保存禁止行為
- 保存使用者判準
- 防止模型反覆犯同樣錯誤

---

五、SCBKR 如何降低成本

SCBKR 的成本優化不是靠壓低模型能力，而是靠減少無效生成。

一般 AI 成本浪費來自：

- 任務沒講清楚就生成。
- 模型答錯後反覆重問。
- 每次都重新解釋背景。
- 沒有驗收標準，導致結果不可用。
- 同類任務無法複用已確認流程。
- 大模型被拿去處理本來可以先被規則分流的小任務。

SCBKR 透過責任鏈降低浪費：

1. 減少無效 token

模型生成前，先確認任務目的、輸出形式、邊界、依據、驗收條件。
這可以降低模型猜錯方向後大量輸出廢內容的機率。

2. 減少重複生成

已確認過的任務結構可以保存為責任鏈案例。
未來相似任務可以參考既有 S / C / B / K / R，不必每次從零開始。

3. 降低電費與運算浪費

本地 LLM 或外部 API 都有成本。
每一次無效生成，都代表額外 token、額外推理時間、額外電力與額外等待時間。
SCBKR 讓模型在更明確的條件下執行，減少盲目試錯。

4. 小模型也能參與工作流

SCBKR 把任務確認、權限、驗收、回放放在模型外層。
部分工作不必全部丟給大模型。
使用者可以先用較小的本地模型跑流程，再依任務需求切換更強模型。

5. 錯誤不污染記憶

驗收失敗不會自動進入記憶庫。
失敗只會形成 failure report draft。
只有使用者明確判定錯因、寫出規則、並簽名確認後，才會形成 memory rule confirmed plan。
這避免系統把錯誤答案當成長期知識。

---

六、權限與安全邊界

SCBKR 的核心安全原則是：

«工具未啟用，不得宣稱已執行。
模型未測通，不得宣稱可用。
使用者未確認，不得生成。
驗收未通過，不得入庫。
失敗輸出不得污染記憶。
非本機模型網址不得假裝成本地模型。»

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

外部 API / hybrid 模式必須同時通過：

external_api = true
dangerous_operation_confirmed = true

否則不得呼叫外部 API。

模型網址安全規則：

- "127.0.0.1"
- "localhost"
- "[::1]"

以上 loopback URL 可視為本機模型。

任何非 loopback URL，例如：

- "192.168.x.x"
- 區網另一台電腦
- 公網 API
- 遠端 OpenAI-compatible endpoint

即使 provider 顯示為 LM Studio / Ollama / local mode，也必須視為外部模型呼叫，必須經過 "external_api=true" 授權。

---

七、目前版本階段

目前版本定位：

SCBKR 本地責任鏈模型｜自接入 MVP App
SCBKR Local Responsibility Chain Model｜Self-Connected MVP App

目前階段：

P15-G 已完成，準備進入 P15-H 最終 UI 對齊。

已完成重點：

- FastAPI 本地後端
- React + Vite + TypeScript 前端
- Windows Desktop Preview workflow
- Sandbox Mode
- 任務建立
- SCBKR 五維確認單
- P12 sealed SCBKR generation boundary
- confirmed gate
- review gate
- storage_confirm gate
- SQLite task persistence
- JSONL ledger replay
- physical storage layer
- Data Center read-back
- activeBackendUrl routing
- Connection Center
- Model Settings
- LM Studio / Ollama / OpenAI-compatible API 接入
- 模型連線測試
- Chat real model gateway
- Workbench model-authored SCBKR draft
- fallback 草案明確標示
- four-store retrieval context
- external_api guard
- 非 loopback model URL 安全阻擋
- API key masking
- same Wi-Fi / remote backend URL 操作基礎

目前剛完成：

P15-G P1 Model URL External Permission Guard

此階段已確認：

- 只有 sandbox / loopback model URL 可免 external_api。
- LM Studio / Ollama 若使用 LAN IP 或遠端 URL，必須 external_api=true。
- Chat / SCBKR draft / confirmed generation / model test 共用同一安全 guard。
- external_api=false 時，不會外傳 user_text / raw task。
- Windows Desktop Preview workflow 已成功。

下一階段：

P15-H UI Reference Lock｜最終產品介面對齊

P15-H 目標：

- 桌面版對齊：左 Chat / 右 Workbench / 左側導覽 / 上方狀態列。
- 手機版對齊：Chat 全螢幕 / Drawer / Workbench 任務視圖。
- Connection Center 可見可用。
- Workbench 顯示模型草案來源、四庫引用、S/C/B/K/R 摘要卡。
- Data Center / 四庫 / Audit 入口完整。
- 不再把 Chat、Workbench、日期、patch、入庫全部塞成一頁長表單。

---

八、目前可跑功能

目前 MVP 可跑功能：

- 本地 FastAPI API
- React Web UI
- Windows Desktop Preview
- Sandbox 測試模式
- 後端 API 連線測試
- 模型 Provider 設定
- LM Studio / Ollama / OpenAI-compatible API 設定
- API Key 遮罩與清除
- 模型連線測試
- 一般 Chat 入口
- Chat-to-Workbench 建議卡
- 任務建立
- SCBKR 五維草案生成
- 使用者修改 / 確認
- confirmed 後才可 generate
- 模型正式生成
- 驗收 pass / fail / rollback
- 入庫建議
- 使用者二次確認入庫
- Data Center 讀回
- ledger / hash / audit
- 四庫引用 context
- 手機同 Wi-Fi 連線使用基礎

---

九、MVP 邊界

目前已支援：

- SQLite task persistence
- JSONL ledger append
- 本地 physical JSON storage
- corpus / logic / memory / vector metadata 寫入
- Data Center read-back
- advisory retrieval context
- Windows preview packaging workflow

目前仍非最終產品：

- 非正式 production installer
- 尚未 code signing
- 尚未 auto-update
- 尚未 bundle model
- 尚未 bundle API key
- 尚未正式雲端 SaaS
- 手機原生 App 尚未提供
- 外網 tunnel 不自動設定
- macOS / Linux package 尚未完成

---

十、固定端口

後端 API：

http://localhost:8787

前端 Web：

http://localhost:5500

LM Studio 常見本機 endpoint：

http://localhost:1234/v1

Ollama OpenAI-compatible endpoint：

http://localhost:11434/v1

注意：

"localhost" / "127.0.0.1" 表示同一台電腦本機。
如果使用 "192.168.x.x" 或遠端網址，即使是 LM Studio / Ollama，也會被視為外部模型連線，需要 external_api 授權。

---

十一、快速開始

安裝 Python package：

python -m pip install -e .

安裝前端依賴：

npm --prefix apps/web install --package-lock=false

啟動後端：

python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787

啟動前端：

npm --prefix apps/web run dev

打開：

http://localhost:5500

---

十二、模型接入

使用者可自行接入：

- Sandbox
- LM Studio
- Ollama
- OpenAI-compatible API
- 自訂 endpoint

模型設定包含：

- Provider
- Mode
- Base URL
- Model Name
- API Key
- Temperature
- Max Tokens
- Timeout

API Key 在讀取設定時只會遮罩，不會明文回傳。

---

十三、手機同 Wi-Fi 使用

若前端開發伺服器使用 LAN host 啟動，手機與電腦在同一個 Wi-Fi 下，可用手機打開：

http://{電腦區網IP}:5500

手機可以作為操作入口：

- 聊天
- 打開 Workbench
- 設定 Backend API URL
- 設定模型
- 建立工單
- 確認 S/C/B/K/R
- 驗收
- 二次確認入庫
- 查看 Data Center

但手機不是內建 LLM。
手機端資料仍透過 activeBackendUrl 連回使用者指定的本地後端 / desktop sidecar / API。

---

十四、產品階段

目前版本：

SCBKR 本地責任鏈模型｜自接入 MVP App

目前技術階段：

P15-G Complete → P15-H Final UI Reference Lock Pending

下一階段可選：

- P15-H：最終 UI 對齊
- 桌面封裝強化：Electron / Tauri
- 本地主機手機連線強化
- SQLite / ledger / ChromaDB / memory persistent runtime 強化
- 正式 installer
- code signing
- auto-update
- macOS / Linux package
- 雲端收費版
- 固化規則庫裁決服務

---

十五、English Summary

SCBKR Local Responsibility Chain Model is a self-connected local AI workflow control layer.

It is not a general chatbot.
It is not a simple RAG tool.
It is not a large model company.
It is not a tool that lets the model decide and answer directly for the user.

SCBKR makes the model declare the task, boundary, basis, acceptance criteria, and responsibility chain before generation.

Users can connect their own:

- LM Studio
- Ollama
- OpenAI-compatible API
- Custom model endpoint

The system guides each task through a five-dimensional confirmation process:

- S｜Subject / Interface
- C｜Causality / Backend
- B｜Boundary / Behavior
- K｜Knowledge / Style
- R｜Replay / Signature

Only after user confirmation can the model generate.

SCBKR reduces invalid tokens, repeated generation, compute waste, and memory pollution by forcing responsibility-chain confirmation before output and storage.

The current stage is:

Self-Connected MVP App
P15-G completed
P15-H final UI alignment pending

Current capabilities include:

- Local FastAPI backend
- React / Vite / TypeScript frontend
- Windows Desktop Preview workflow
- Connection Center
- Active backend URL routing
- Real model gateway
- LM Studio / Ollama / OpenAI-compatible API support
- SCBKR five-dimensional draft
- User confirmation gate
- Generation gate
- Review gate
- Storage confirmation gate
- SQLite task persistence
- JSONL ledger
- Physical local storage
- Data Center read-back
- Four-store retrieval context
- External API permission guard
- Non-loopback model URL protection
- API key masking
- Same-Wi-Fi mobile operation foundation

SCBKR principle:

«The model does not answer first.
It explains first.
The model does not generate first.
It confirms first.
Build your own responsibility-chain model.»

---

十六、簽名

語意防火牆創辦人
許文耀 / 沈耀888π

Founder of Semantic Firewall
Wen-Yao Hsu / ShenYao888π