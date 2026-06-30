# SCBKR 責任鏈模型總計畫書｜最終完整嚴格版  
# Local Responsibility Chain Model Master Plan｜FINAL STRICT VERSION

版本：`SCBKR-MASTER-PLAN-v1.0-FINAL`  
產品路線：`SCBKR 1.0 → SCBKR 2.0`  
目前工程階段：`P15-Q Release Candidate + PATCH-1`  
目前產品階段：`SCBKR 1.0 上線基礎整理前`  
未來產品階段：`SCBKR 2.0 規則驅動 AI 引擎作業系統`  
主軸：`本地責任鏈工作台 → 規則驅動 AI 引擎 → 工具權限 Gate → 可商用規則包`

---

# 0. 本文件用途

本文件是 SCBKR 後續所有工程、UI、後端、商業化、上架、公告、Codex 任務的總主檔。

後續所有修改必須以本文件為基準。

本文件用途：

1. 鎖定 SCBKR 的產品核心。
2. 鎖定 1.0 上線基礎。
3. 鎖定 2.0 最終設計方向。
4. 鎖定 UI 結構。
5. 鎖定後端模組。
6. 鎖定工具權限邊界。
7. 鎖定手機端定位。
8. 鎖定規則包商業方向。
9. 鎖定不可破壞鐵律。
10. 防止 Codex / 工程 / UI / 模型把系統改歪。

本文件不是概念稿。

本文件是施工規範。

---

# 1. 總定位

SCBKR 不是一般聊天機器人。

SCBKR 不是單純 RAG。

SCBKR 不是單純 Agent。

SCBKR 不是模型公司。

SCBKR 不是讓模型自由決策的自動化玩具。

SCBKR 是一套本地 AI 責任鏈模型。

它的核心不是讓模型直接回答，而是讓模型在回答、生成、入庫、引用、工具執行、記憶更新、資料封存之前，先通過一條可簽名、可驗收、可回放、可審計、可追責的責任鏈。

SCBKR 的核心產品命題：

模型可以參與，但不能越權。

使用者可以定義，但必須簽名。

資料可以入庫，但必須驗收。

工具可以執行，但必須受規則控制。

AI 可以自動化，但必須回到責任鏈。

SCBKR 的最終目標：

建立一套本地運行、可連本地模型、可用手機操作、可接工具、可簽名、可驗收、可審計、可回放、可版本化規則、可商用規則包的 AI 作業系統。

---

# 2. 核心總原則

以下原則是 SCBKR 的母原則，不得被任何 UX、測試、上架、Demo、商業合作、模型能力、工具能力覆蓋。

## 2.1 模型定位

模型可以：

- 理解使用者輸入
- 整理任務
- 生成草案
- 編譯確認單
- 依確認單生成內容
- 協助比對資料
- 協助整理依據
- 協助生成候選方案
- 協助執行已授權工具流程

模型不能：

- 自己簽名
- 自己驗收
- 自己二次確認入庫
- 自己把草案變成規則
- 自己把輸出變成長期記憶
- 自己更改 Data Center
- 自己封存資料
- 自己取代資料
- 自己刪除資料
- 自己繞過使用者確認
- 自己繞過 Rule Match Gate
- 自己繞過 Tool Permission Gate

## 2.2 使用者定位

使用者可以：

- 發起任務
- 修改確認單
- 簽名確認責任鏈
- 驗收模型輸出
- 二次確認入庫
- 更改 Data Center 資料
- 封存資料
- 取代資料
- 啟用規則
- 停用規則
- 採用規則包
- 選擇模型 Runtime
- 選擇工具權限

使用者必須承擔：

- 自己簽名後成立的規則
- 自己驗收後通過的資料
- 自己二次確認入庫的資料
- 自己採用的規則包
- 自己啟用的工具權限

## 2.3 責任鏈定位

責任鏈不是裝飾。

責任鏈是模型執行前的成立條件。

沒有責任鏈，模型只能做低風險整理。

沒有簽名，責任鏈不成立。

沒有驗收，資料不能入庫。

沒有二次確認，資料不能寫入四庫。

沒有有效規則，工具不能執行高風險動作。

---

# 3. 目前已完成狀態

目前工程狀態：

`P15-Q Release Candidate + PATCH-1`

目前已完成：

1. P15-Q Release Candidate 主流程完成。
2. P15-Q PATCH-1 完成。
3. Windows Desktop Preview workflow 已跑通。
4. 核心責任鏈閉環已成立。
5. 四庫入庫目標已收束為正式四庫。
6. Data Center 簽名 Gate 已補上。
7. Windows smoke selected_targets 已修正。
8. 可進入 SCBKR 1.0 上線整理階段。

目前已完成的 1.0 核心能力：

1. Chat 對話入口
2. Chat-to-Workbench 任務建立
3. Workbench 工作台
4. SCBKR S / C / B / K / R 草案
5. 模型輔助草案整理
6. 使用者修改確認單
7. 修改後舊簽名作廢
8. 使用者簽名 Gate
9. 模型不能簽名
10. confirmed gate
11. generation gate
12. user review gate
13. storage request
14. second confirmation storage gate
15. Data Center
16. 四庫寫入
17. 四庫引用條件
18. Data Center 更改 / 封存 / 取代簽名 Gate
19. SQLite task persistence
20. JSONL ledger replay
21. physical local storage
22. FastAPI 本地後端
23. React + TypeScript 前端
24. Tauri desktop shell
25. LM Studio / Ollama / OpenAI-compatible API 接入基礎
26. activeBackendUrl
27. same-Wi-Fi / mobile companion operation foundation
28. Release Candidate metadata
29. Windows build / smoke workflow
30. 四庫 UI targets 收束為 `vector / corpus / logic / memory`

---

# 4. 正式四庫定義

SCBKR 正式四庫只有四個：

1. `vector`
2. `corpus`
3. `logic`
4. `memory`

## 4.1 vector｜向量庫

用途：

- 相似任務檢索
- 語意索引
- 責任鏈案例查詢
- 任務相似度比對

## 4.2 corpus｜語料庫

用途：

- 保存原始文本
- 保存文件內容
- 保存外部資料
- 保存任務依據
- 保存可回放文字材料

## 4.3 logic｜邏輯庫

用途：

- 保存流程規則
- 保存判準
- 保存測試條件
- 保存工程邏輯
- 保存任務因果
- 保存責任鏈結構

## 4.4 memory｜記憶庫

用途：

- 保存使用者確認過的長期偏好
- 保存長期規則
- 保存禁止事項
- 保存已成立判斷標準
- 保存可再引用的穩定記憶

## 4.5 禁止事項

`exports` 不是正式四庫入庫目標。

正式 UI 入庫目標不得包含 `exports`。

`exports` 不得被加回正式四庫 UI targets。

若需要匯出功能，必須獨立定義為 Export / Download / Report，不得混入正式四庫。

---

# 5. SCBKR 1.0 產品定義

SCBKR 1.0 定位：

本地責任鏈基礎版。

1.0 不是最終完整 AI 引擎。

1.0 的任務是把責任鏈基底打穩，讓使用者能下載、安裝、連模型、建立確認單、簽名、生成、驗收、入庫、查 Data Center、回放紀錄。

## 5.1 1.0 核心流程

使用者輸入任務  
→ Chat 判斷是否送入 Workbench  
→ Workbench 建立 SCBKR 草案  
→ 使用者修改確認單  
→ 使用者簽名  
→ 模型依確認單生成  
→ 使用者驗收  
→ 使用者建立入庫請求  
→ 使用者二次確認入庫  
→ 寫入 Data Center / 四庫  
→ 未來任務只能引用有效資料

## 5.2 1.0 產品價值

1.0 解決：

- AI 輸出不再直接變成規則
- AI 草稿不會自動污染記憶
- 每次任務都有責任鏈
- 使用者簽名後，模型才依照確認單生成
- 資料入庫前必須驗收與二次確認
- 未來引用有明確來源與狀態
- 本地模型輸出有可回放審計路徑

## 5.3 1.0 不承諾內容

1.0 不承諾完整自動 Agent。

1.0 不承諾全自動 Email。

1.0 不承諾完整 Code Workspace。

1.0 不承諾規則商城。

1.0 不承諾完整語音助手。

1.0 不承諾所有平台一次完整商店上架。

1.0 的定位必須清楚：

本地責任鏈基礎版。

---

# 6. SCBKR 1.0 不可破壞鐵律

以下規則不得為了 UX、測試、上架、展示、Demo、商業合作而放鬆。

## 6.1 使用者簽名鐵律

使用者簽名後，SCBKR 才成立。

模型不能簽名。

system 不能簽名。

assistant 不能簽名。

測試可以使用明確測試簽名，但不得把測試簽名硬塞進產品 UI。

產品 UI 不得存在 fallback signature。

不得使用以下字串作為替代簽名：

- `owner-signature-required`
- `storage-owner-signature`
- `user`
- `model`
- `assistant`
- `system`

## 6.2 修改後重簽鐵律

確認單內容只要改動，舊簽名必須作廢。

這不是 UX 缺陷。

這是責任一致性 Gate。

原因：

簽名只對當下那份內容有效。

內容改動後，責任內容已變更。

舊簽名不能代表新內容。

若保留舊簽名，模型可透過偷改確認單越權。

因此以下動作後必須清空 `ownerSignature`：

- createTask
- createConfirmationFromChat
- acceptSuggestion
- duplicateTask
- updateField
- saveFields
- applyPatch
- regenerateDraft
- returnToRevision
- resetWorkbench

同時必須提示：

草案已修改，請重新輸入使用者簽名後再確認責任鏈。

UX 可優化：

- 顯示修改前後 diff
- 顯示受影響欄位
- 顯示為何需要重簽
- 提供快速重新簽名欄位
- 提供修改摘要
- 提供變更紀錄

UX 不得做：

- 自動保留舊簽名
- 自動代簽
- 背景重簽
- 模型重簽
- 修改後仍保留 confirmed
- 修改後仍保留 review_passed
- 修改後仍保留 storage_confirmed
- 修改後仍讓舊生成結果有效

## 6.3 驗收鐵律

模型生成後，必須由使用者驗收。

未驗收通過，不得入庫。

`review_passed` 必須由使用者操作成立。

模型不得替使用者驗收。

## 6.4 入庫鐵律

入庫必須同時滿足：

- `review_passed=true`
- `storage_confirmed=true`
- `second_confirm=true`
- `confirmed_by=user`
- `signature` 不可空
- `signature_status=owner_signed`
- `physical_write_performed=true`

缺少 `second_confirm` 必須失敗。

缺少 `signature` 必須失敗。

`confirmed_by` 不是 `user` 必須失敗。

模型不得自動入庫。

## 6.5 Data Center 鐵律

Data Center 更改、封存、取代，必須使用 Data Center 自己的使用者簽名欄位。

Data Center 不得沿用 Workbench `ownerSignature`。

Data Center 不得 fallback signature。

Data Center 空簽名不得送出 confirm。

Data Center delete 不得做不可逆硬刪作為預設操作。

正式操作應以以下狀態為主：

- archive
- revoke
- supersede

## 6.6 四庫引用鐵律

未來任務不可亂引用資料。

SCBKR 只允許引用符合以下條件的資料：

- owner_signed
- review_passed
- storage_confirmed
- not revoked
- not archived
- not superseded
- 與目前任務相關

不可作為正式依據：

- 未簽名資料
- 未驗收資料
- revoked 資料
- archived 資料
- superseded 資料
- similar_grammar 但未明確採用的資料
- 模型臨時草案
- 外部搜尋但未驗收資料

---

# 7. SCBKR 1.0 上線前必補基礎能力

1.0 上線目標是讓一般使用者可以下載、安裝、理解、使用。

上線前必補：

1. 中英文切換
2. 語言包
3. 基礎網路搜尋
4. 模型設定
5. Windows 安裝與版本資訊
6. 隱私與安全說明
7. README / README_EN
8. Release Notes
9. 1.0 功能公告
10. 2.0 Roadmap 公告
11. 手機連本機說明
12. GitHub About / Topics
13. 基礎 onboarding
14. 基礎錯誤訊息整理

---

# 8. 1.0 中英文切換與語言包

必須支援：

- 繁體中文
- 英文

UI 文案不得硬寫死在元件內。

必須建立語言包。

建議結構：

apps/web/src/i18n/zh-TW.ts  
apps/web/src/i18n/en.ts  
apps/web/src/i18n/index.ts

所有 UI label、button、error message、status chip、empty state、onboarding text 必須逐步移入語言包。

1.0 先完成主要 UI：

- Chat
- Workbench
- Signature Gate
- Review
- Storage
- Data Center
- Model Settings
- Backend URL
- Error messages
- Onboarding
- Release notes

語言切換不得影響：

- 內部資料 key
- API schema
- storage targets
- signature status
- rule status
- ledger
- 四庫名稱內部代碼

內部 key 繼續使用英文穩定代碼。

UI 顯示再轉譯。

---

# 9. 1.0 基礎網路搜尋

1.0 可加入基礎 Web Search。

但 Web Search 在 1.0 僅能作為候選資料來源。

Web Search 結果不得自動入庫。

Web Search 結果不得自動成為 memory。

Web Search 結果不得自動成為 logic。

Web Search 結果若要成為未來引用資料，必須經過：

Workbench  
→ 使用者簽名  
→ 模型整理  
→ 使用者驗收  
→ 二次確認入庫  
→ Data Center 寫入

Web Search 基礎能力：

- 搜尋
- 摘要
- 列出來源
- 提供候選引用
- 送入 Workbench
- 等待使用者確認

Web Search 不得：

- 自動決策
- 自動入庫
- 自動覆蓋規則
- 自動更新 memory
- 自動取代 Data Center 資料

---

# 10. 1.0 模型設定

1.0 必須清楚支援：

- Sandbox
- LM Studio
- Ollama
- OpenAI-compatible API
- Custom endpoint

設定欄位：

- provider
- mode
- baseUrl
- modelName
- apiKey
- temperature
- maxTokens
- timeout
- contextLength

API Key 讀取時必須遮罩。

不得明文回傳 API Key。

不得把 API Key 寫入前端可見 log。

`activeBackendUrl` 不得破壞。

手機端必須能設定 `activeBackendUrl` 連回本機電腦。

只有 loopback URL 可視為本機模型：

127.0.0.1  
localhost  
[::1]

非 loopback URL，例如：

192.168.x.x  
區網另一台電腦  
公網 API  
遠端 OpenAI-compatible endpoint

即使 provider 顯示為 LM Studio / Ollama，也必須視為外部模型呼叫。

外部模型呼叫必須經過 external API guard。

---

# 11. 1.0 安裝與版本資訊

必須整理：

- Windows installer
- Windows Release Candidate build
- Windows smoke 驗收說明
- 版本號
- Release Notes
- Known Issues
- 更新機制說明
- 資料保留說明
- 本地資料位置說明
- 如何備份 Data Center
- 如何重設設定

1.0 可先主打：

Windows 下載版  
GitHub Release  
本地開發啟動  
桌面 Release Candidate  

Apple / iOS / Android / Microsoft Store 可列 Roadmap，不得假裝已完成。

---

# 12. 1.0 隱私與安全說明

1.0 上架前必須寫清楚：

SCBKR 主要在本機運行。

手機端是操作入口，不是獨立模型主體。

手機端透過 `activeBackendUrl` 連回使用者指定的本機後端。

使用 LM Studio / Ollama 時，模型由使用者本機或使用者指定 endpoint 提供。

使用 OpenAI-compatible API 時，資料會送到使用者自己設定的 API endpoint。

Web Search 會連外搜尋。

SCBKR 不會在未經使用者確認下自動寄信、付款、刪除、發布、入庫。

Data Center 寫入需要使用者驗收與二次確認。

Data Center 更改、封存、取代需要資料中心使用者簽名。

---

# 13. 1.0 UI 定義

1.0 UI 主要目標：

讓使用者看懂責任鏈閉環。

1.0 不需要完整 2.0 規則中心與 AI 引擎。

1.0 必須清楚呈現：

- Chat
- Workbench
- S / C / B / K / R
- 使用者簽名
- 模型生成
- 使用者驗收
- 二次確認入庫
- Data Center
- 四庫
- 審計回放
- 模型設定
- 手機連線

## 13.1 1.0 桌面 UI

1.0 桌面 UI 基本布局：

左側：導航  
中間：Chat / Workbench 主內容  
右側：任務狀態 / 簽名狀態 / 入庫狀態  
Data Center 頁：四庫資料與回放

導航包含：

- 聊天
- 工作台
- 資料中心
- 模型設定
- 審計資料
- 說明

Workbench 必須顯示：

- S 主體
- C 因果
- B 邊界
- K 依據
- R 回放
- 使用者簽名欄
- 確認責任鏈
- 模型生成
- 驗收通過
- 建立入庫請求
- 二次確認入庫

## 13.2 1.0 手機 UI

手機定位：

手機不是內建 LLM。

手機是連回本機 SCBKR Runtime 的操作入口。

手機可做：

- 聊天
- 查看任務
- 查看 S / C / B / K / R
- 輸入使用者簽名
- 確認責任鏈
- 驗收
- 二次確認入庫
- 查看 Data Center
- 設定 Backend URL

手機 UI 以 Chat 為主入口。

Workbench 與 Data Center 使用卡片式呈現。

手機端不得獨立規則判定。

手機端不得獨立工具執行。

手機端所有需要規則判斷、工具權限、資料寫入、入庫、封存、取代、刪除的行為，都必須送回桌面端 / 本機 Runtime Gate 驗證。

---

# 14. SCBKR 2.0 產品定義

SCBKR 2.0 定位：

規則驅動 AI 引擎作業系統。

2.0 不是重做 1.0。

2.0 是在 1.0 責任鏈基底上加入：

- 設定規則層
- 半自動 / 全自動 AI 引擎層
- 工具權限 Gate
- 規則包系統
- 規則版本系統
- 規則採用 Gate
- 規則商業化
- 更多 AI 工具

2.0 核心一句話：

模型沒看到已成立規則，不執行決策。

模型可以搜尋、整理、草擬。

但涉及判斷、入庫、寄信、刪除、封存、發布、付款、長期記憶、工具執行、外部傳送時，必須回到規則層與責任鏈 Gate。

---

# 15. 2.0 兩大主層

## 15.1 設定規則層

設定規則層負責定義模型能依照什麼規則工作。

規則來源分為：

- 使用者自定義規則
- 沈耀簽名規則包
- 企業內部規則
- 外部第三方規則
- 模型草案規則

規則狀態分為：

- draft
- waiting_owner_signature
- owner_signed
- active
- disabled
- revoked
- archived
- superseded

每條規則必須包含：

- rule_id
- rule_name
- rule_author
- rule_source
- rule_version
- rule_scope
- allowed_tools
- denied_tools
- automation_level
- risk_level
- activation_status
- created_at
- updated_at
- signed_at
- signature
- adopted_by
- adoption_scope
- supersedes
- superseded_by
- changelog
- hash

規則來源必須明確。

沈耀簽名規則包不得被說成使用者自定義規則。

使用者啟用沈耀簽名規則包時，必須明確記錄：

規則作者：許文耀 / 沈耀888π  
啟用者：使用者  
規則版本：vX.X.X  
啟用範圍：指定任務 / 指定工具 / 指定工作流

## 15.2 半自動 / 全自動 AI 引擎層

AI 引擎層負責讓模型使用工具。

工具包含：

- Web Search
- Email Read
- Email Draft
- Code Workspace
- Git / Repo
- Image Generation
- Voice Input
- Voice Output
- Local Files
- API Tools
- Scheduler
- Data Center Query
- Rule Registry Query

AI 引擎不得自由執行。

每次工具呼叫前必須經過：

- Rule Match Gate
- Tool Permission Gate
- Risk Gate
- Execution Trace
- User Confirmation Gate

若沒有命中有效規則：

模型只能搜尋、整理、草擬。

不得做決策。

不得入庫。

不得外部傳送。

不得寄信。

不得刪除。

不得封存。

不得寫入記憶。

不得全自動執行。

---

# 16. 2.0 UI 最終版鎖定

2.0 UI 不得再改成單純 Chat App。

2.0 UI 不得只做成規則後台。

2.0 UI 不得把 Workbench 藏起來。

2.0 UI 固定為四區：

左側：規則設定層  
中間：Chat 對話入口  
右側：Workbench / AI 引擎工具權限  
底部：Data Center / 四庫 / 回放紀錄

## 16.1 左側：規則設定層

左側不是普通選單。

左側是規則主權區。

必須包含：

- 規則中心
- 使用者自定義規則
- 沈耀簽名規則包
- 企業內部規則
- 第三方規則包
- 規則版本
- 規則啟用範圍
- 規則更新 / 回滾
- 規則衝突
- 規則購買 / 訂閱

必須顯示目前啟用規則：

- 規則來源
- 規則作者
- 規則版本
- 適用範圍
- 啟用狀態
- 自動化等級
- 允許工具
- 禁止工具

## 16.2 中間：Chat 對話入口

中間是使用者主要入口。

必須像一般 AI 產品一樣可以自然對話。

但必須常駐顯示規則狀態。

Chat 必須包含：

- 使用者訊息
- 模型回覆
- 工具動作
- 搜尋結果摘要
- 引用規則提示
- 任務建議卡
- 送到 Workbench
- 建立規則
- 依規則執行

輸入框必須包含：

- 文字輸入
- 麥克風
- 小喇叭 / 語音朗讀
- 網頁搜尋
- 附件
- 工具箱
- 模型選擇
- 送出

Chat 狀態提示範例：

目前未命中已簽名規則：僅允許搜尋、整理、草稿，不允許決策。

或：

已命中規則：沈耀簽名規則包 v2.0.7，本次允許半自動執行。

## 16.3 右側：Workbench / AI 引擎工具權限

右側分成兩段。

第一段：Workbench

包含：

- S 主體
- C 因果
- B 邊界
- K 依據
- R 回放
- 使用者簽名 Gate
- 確認責任鏈
- 模型生成
- 使用者驗收
- 二次確認入庫

第二段：AI 引擎工具層

包含工具：

- 網頁搜尋
- Email
- 程式碼工作台
- 圖像生成
- 語音
- 本機檔案
- Git
- API
- Data Center

每個工具要顯示權限：

- 可觀察
- 可草稿
- 可半自動
- 可全自動
- 需確認
- 禁止執行

## 16.4 底部：Data Center / 四庫 / 回放

底部是資料證據層。

包含：

- Data Center
- vector
- corpus
- logic
- memory
- 引用紀錄
- 入庫狀態
- 撤銷
- 封存
- 取代
- 回放紀錄
- 資料中心使用者簽名
- 確認更改
- 確認封存
- 確認取代

Data Center 不得共用 Workbench 簽名。

---

# 17. 2.0 手機 UI 最終鎖定

手機端不是獨立模型主體。

手機端不是獨立規則裁判。

手機端不是獨立工具執行器。

手機端是：

- 操作入口
- 簽名入口
- 驗收入口
- 二次確認入口
- 顯示入口
- 遠端控制入口

手機端所有工具調用與決策行為，必須回桌面端 / 本機 Runtime 的以下 Gate 驗證：

- Rule Match Gate
- Tool Permission Gate
- Risk Gate
- Execution Trace
- Data Center Gate
- Storage Gate

手機端不得繞過：

- activeBackendUrl
- Rule Registry
- Tool Registry
- Execution Trace
- Data Center Gate
- Storage Gate
- Signature Gate
- Review Gate
- Second Confirmation Gate

手機端語音指令不得跳過：

- 使用者簽名 Gate
- 驗收 Gate
- 二次確認入庫 Gate
- Tool Permission Gate

手機端可以發起請求，但不能本地獨立判定是否允許。

正確流程：

手機端輸入任務  
→ 送回 activeBackendUrl  
→ 本機 Runtime 查 Rule Match Gate  
→ 本機 Runtime 查 Tool Permission Gate  
→ 本機 Runtime 回傳允許 / 拒絕 / 需確認  
→ 手機端顯示結果  
→ 使用者在手機端簽名 / 驗收 / 確認  
→ 本機 Runtime 執行  
→ Execution Trace 記錄  

---

# 18. 2.0 後端對接設計

2.0 後端必須在 1.0 基礎上新增以下核心模組。

---

## 18.1 Rule Registry

目的：

保存所有規則。

資料表 / 儲存內容：

- rules
- rule_versions
- rule_adoptions
- rule_changelog
- rule_hashes
- rule_conflicts

必要 API：

GET /api/rules  
POST /api/rules  
GET /api/rules/{rule_id}  
POST /api/rules/{rule_id}/sign  
POST /api/rules/{rule_id}/activate  
POST /api/rules/{rule_id}/disable  
POST /api/rules/{rule_id}/revoke  
POST /api/rules/{rule_id}/supersede  
GET /api/rules/{rule_id}/history  
POST /api/rules/match

Rule Registry 不得取代 1.0 的使用者簽名 Gate。

Rule Registry 是規則管理層。

簽名 Gate 仍然是成立條件。

---

## 18.2 Rule Match Gate

目的：

任務執行前先查規則。

輸入：

- task_id
- user_input
- task_context
- requested_tools
- automation_request
- data_center_context

輸出：

- matched_rules
- match_level
- rule_source
- rule_author
- rule_version
- allowed_tools
- denied_tools
- automation_level
- requires_user_confirmation
- requires_owner_signature
- reason

match_level：

- none
- candidate
- same_domain
- direct_match
- explicit_adopted_rule

只有以下 match_level 可進入半自動 / 全自動：

- direct_match
- explicit_adopted_rule

candidate / same_domain 只能提示使用者確認，不得自動決策。

---

## 18.3 Tool Registry

目的：

保存工具定義。

工具欄位：

- tool_id
- tool_name
- tool_type
- risk_level
- read_permission
- write_permission
- external_network
- local_file_access
- requires_confirmation
- supports_dry_run
- supports_audit_log
- default_enabled

工具類型：

- read_only
- draft_only
- write_action
- external_action
- high_risk_action

必要 API：

GET /api/tools  
GET /api/tools/{tool_id}  
POST /api/tools/{tool_id}/enable  
POST /api/tools/{tool_id}/disable  
POST /api/tools/check-permission

新增工具後，預設不得全自動啟用。

新增工具必須先進 Tool Registry。

新增工具必須受 Tool Permission Gate 控制。

---

## 18.4 Tool Permission Gate

目的：

模型呼叫工具前必須檢查權限。

輸入：

- task_id
- tool_id
- requested_action
- matched_rule_id
- automation_level
- user_signature_status
- risk_level

輸出：

- allowed
- denied_reason
- requires_confirmation
- requires_second_confirm
- requires_dry_run
- allowed_scope
- audit_required

規則：

沒有命中規則，不得執行高風險工具。

沒有使用者簽名，不得執行 write action。

沒有驗收，不得入庫。

沒有二次確認，不得寫入四庫。

工具新增後預設不得自動取得全自動權限。

---

## 18.5 Risk Gate

目的：

依工具風險分級決定是否需要確認。

風險等級：

- low
- medium
- high
- critical

low：

可觀察、可整理、可草稿。

medium：

需要使用者確認。

high：

需要使用者簽名 + 明確確認。

critical：

需要使用者簽名 + 二次確認 + Execution Trace。

critical 類型包含：

- 寄出 Email
- 刪除資料
- 封存資料
- 取代資料
- 寫入 Data Center
- 修改規則
- 啟用全自動
- 修改本地檔案
- 執行程式碼
- 外部發布
- 金流相關動作

---

## 18.6 Execution Trace

目的：

記錄每次 AI 引擎行動。

資料包含：

- trace_id
- task_id
- rule_id
- rule_version
- tool_id
- requested_action
- permission_result
- model_output
- tool_input
- tool_output
- user_confirmation
- storage_result
- created_at
- hash

必要 API：

GET /api/traces  
GET /api/traces/{trace_id}  
GET /api/tasks/{task_id}/traces

Execution Trace 不得被模型刪除。

Execution Trace 修改必須進 Data Center Gate。

---

# 19. 2.0 工具設計

## 19.1 Web Search Tool

1.0 可做基礎版。

2.0 進入工具層。

Web Search 規則：

可以搜尋。  
可以整理。  
可以產生候選依據。  
不得自動入庫。  
不得自動成為 memory。  
不得自動成為 logic。  
入庫必須走 Workbench / 驗收 / 二次確認。

## 19.2 Email Tool

2.0 才做。

Email 初期只允許：

- 讀取
- 摘要
- 分類
- 草稿

不得預設允許：

- 自動寄出
- 自動刪信
- 自動封存
- 自動標記法律 / 財務高風險結果
- 自動新增聯絡人

寄出必須使用者確認。

高風險信件必須二次確認。

## 19.3 Code Workspace Tool

2.0 才做。

初期允許：

- 讀 repo
- 產生 patch
- 解釋 diff
- 跑測試
- 提出修改建議

不得預設允許：

- 直接 push
- 直接刪檔
- 直接改主分支
- 直接修改 Data Center
- 直接覆蓋重要設定

寫入檔案必須經過工具權限 Gate。

高風險操作必須使用者確認。

## 19.4 Image Generation Tool

2.0 才做。

允許：

- 生成圖片
- 生成 prompt
- 修改圖片草案

不得自動：

- 發布
- 入庫為正式品牌素材
- 覆蓋原檔
- 外部傳送

## 19.5 Voice Tool

1.0 可先做語音輸入 / 朗讀基礎。

2.0 再做完整語音助手。

語音指令不得跳過簽名 Gate。

語音確認高風險動作必須轉為明確 UI 確認。

## 19.6 Local File Tool

2.0 才做。

初期允許：

- 讀取使用者指定檔案
- 讀取使用者指定資料夾
- 摘要檔案
- 建立草稿
- 產生修改建議

不得預設允許：

- 刪除檔案
- 覆蓋檔案
- 移動檔案
- 修改 Data Center 檔案
- 修改設定檔
- 修改密鑰檔
- 遞迴掃描整台電腦

所有寫入必須經過 Tool Permission Gate。

---

# 20. 關於 Sandbox 的正式定義

SCBKR 1.0 不是雲端多租戶 Agent 平台。

SCBKR 1.0 是本地責任鏈工作台。

因此「防爆沙盒」不是 1.0 阻塞點。

但 2.0 要接工具時，必須建立工具權限隔離層。

正式名稱不用空泛叫防爆沙盒。

正式名稱：

- Tool Permission Gate
- Tool Runtime Boundary
- Execution Scope Guard

定義：

SCBKR 規則層決定可不可以做。

Tool Permission Gate 決定就算可以做，也只能在允許範圍內做。

例如：

Web Search 可搜尋，不可自動入庫。

Email 可草稿，不可自動寄出。

Code 可產生 patch，不可自動 push。

File 可讀指定資料夾，不可刪 Data Center。

Data Center 可封存，不可硬刪。

這不是否定本地模型。

這是把責任鏈規則落到工具執行層。

---

# 21. 資料與版本更新策略

SCBKR 更新必須分層。

不能把所有東西混成一包。

更新層：

1. App 更新
2. Backend 更新
3. 規則包更新
4. 模型 Runtime 更新
5. 工具更新

## 21.1 App 更新

更新：

- UI
- Workbench
- Data Center
- 桌面殼
- 手機操作
- 語言包

## 21.2 Backend 更新

更新：

- FastAPI
- 資料庫 schema
- 四庫邏輯
- Rule Registry
- Tool Registry
- Execution Trace

## 21.3 規則包更新

更新：

- 使用者規則
- 沈耀簽名規則包
- 企業規則包
- 第三方規則包

規則包更新必須可查看、可採用、可停用、可回滾。

## 21.4 模型 Runtime 更新

支援：

- LM Studio
- Ollama
- OpenAI-compatible endpoint
- 本地模型切換
- 外部 API endpoint

新模型不得自動取得舊規則沒有授權的工具能力。

## 21.5 工具更新

新增工具後，預設不得全自動啟用。

新增工具必須進入 Tool Registry。

新增工具必須受 Tool Permission Gate 控制。

## 21.6 更新流程

檢查更新  
→ 下載新版  
→ 驗證 hash / signature  
→ 備份本地資料  
→ 停止舊版 runtime  
→ 替換 App / Backend  
→ 執行資料 migration  
→ 檢查責任鏈相容性  
→ 啟動新版  
→ 成功則完成  
→ 失敗則回滾

更新不得破壞：

- 使用者簽名紀錄
- Data Center
- 四庫
- ledger
- hash
- 回放資料
- revoked / archived / superseded 狀態
- 使用者啟用的規則包狀態

---

# 22. 商業方向

SCBKR 商業方向分兩階段。

## 22.1 1.0 商業方向

1.0 重點是可下載、可安裝、可用。

可做：

- GitHub Release
- Windows installer
- 開源展示
- 技術媒體曝光
- 本地 AI 社群曝光
- AI governance 社群曝光
- 早期使用者收集
- 顧問合作
- 企業 PoC

1.0 不要過度銷售全自動。

1.0 賣點：

- 本地責任鏈
- 使用者簽名
- 模型不能越權
- 驗收後入庫
- 四庫引用
- Data Center
- 可回放審計

## 22.2 2.0 商業方向

2.0 開始建立規則商品。

可做：

- Personal Rule Pack
- Pro Rule Engine
- Custom Rule Design
- Team / Enterprise Governance
- Rule Marketplace
- 規則包訂閱
- 規則版本更新
- 工具權限套件
- 企業內部 AI 審計

核心商品不是模型。

核心商品是：

可簽名、可版本化、可更新、可引用、可審計的規則判準。

## 22.3 沈耀簽名規則包

沈耀簽名規則包必須明確標示：

- 規則作者：許文耀 / 沈耀888π
- 規則版本
- 適用範圍
- 禁止範圍
- 更新紀錄
- 使用者採用狀態
- 授權範圍

使用者購買或啟用後，不代表該規則變成使用者自定義規則。

正確語意：

規則作者是沈耀。

使用者是採用者。

模型依照該規則執行時，必須標明規則來源。

---

# 23. 工程階段路線

## 23.1 P15-Q 已完成

完成內容：

- Release Candidate 主流程
- 使用者簽名 Gate
- 入庫 Gate
- Data Center Gate
- 四庫收束
- Windows workflow

## 23.2 P15-R：1.0 上線基礎整理

目標：

- 中英文語言包
- README / README_EN
- Release Notes
- Windows 安裝說明
- 隱私政策草案
- 1.0 功能公告
- 2.0 Roadmap 公告
- 基礎 Web Search 設計
- 手機連線說明
- GitHub Topics / About

不可改弱：

- 簽名 Gate
- 修改後重簽 Gate
- 入庫 Gate
- Data Center Gate

## 23.3 P16-A：Rule Registry

目標：

建立規則註冊中心。

支援使用者規則、沈耀簽名規則包、企業規則。

支援版本、啟用、停用、撤銷、取代。

## 23.4 P16-B：Rule Match Gate

目標：

任務執行前查規則。

輸出命中規則、版本、來源、允許工具、自動化等級。

## 23.5 P16-C：Tool Registry

目標：

建立工具註冊中心。

每個工具有風險等級、可讀、可寫、是否外部連線、是否需要確認。

## 23.6 P16-D：Tool Permission Gate

目標：

所有工具呼叫前檢查規則。

沒有規則不執行決策。

高風險動作需要確認。

## 23.7 P16-E：Web Search Tool

目標：

接入網頁搜尋。

搜尋結果為候選資料。

入庫仍走責任鏈。

## 23.8 P16-F：Voice I/O

目標：

語音輸入。

語音朗讀。

語音不得跳過簽名 Gate。

## 23.9 P16-G：Email Draft Tool

目標：

Email 讀取與草稿。

不得自動寄出。

寄出需使用者確認。

## 23.10 P16-H：Code Workspace

目標：

讀 repo。

生成 patch。

跑測試。

產生 diff。

不得自動 push。

## 23.11 P16-I：Rule Pack Subscription

目標：

規則包購買 / 啟用 / 更新 / 回滾。

沈耀簽名規則包正式產品化。

---

# 24. 給 Codex / 工程的不可矛盾規則

任何工程修改必須遵守：

1. 不得放鬆使用者簽名 Gate。
2. 不得保留修改前舊簽名。
3. 不得讓模型簽名。
4. 不得讓模型驗收。
5. 不得讓模型二次確認入庫。
6. 不得讓未驗收資料入庫。
7. 不得讓缺 `second_confirm` 的 `storage-confirm` 成功。
8. 不得恢復 fallback signature。
9. 不得恢復 preview-only 假閉環。
10. 不得把 `exports` 加回正式四庫 UI targets。
11. 不得讓 Data Center 共用 Workbench 簽名。
12. 不得讓 Data Center 更改 / 封存 / 取代在空簽名時送出。
13. 不得把沈耀簽名規則包說成使用者自定義規則。
14. 不得讓新增工具自動取得全自動權限。
15. 不得讓手機成為獨立模型主體。
16. 不得破壞 `activeBackendUrl`。
17. 不得讓 Web Search 結果自動入庫。
18. 不得讓 Email 工具預設自動寄信。
19. 不得讓 Code Workspace 預設自動 push。
20. 不得讓更新流程破壞 Data Center / 四庫 / ledger / 簽名紀錄。
21. 手機端不得獨立執行規則判定。
22. 手機端所有工具調用、決策行為、半自動 / 全自動請求，必須回到桌面端 / 本機 Runtime 的 Rule Match Gate 與 Tool Permission Gate 驗證。
23. 手機端只能作為操作入口、簽名入口、驗收入口、確認入口與顯示入口，不得成為獨立模型主體或獨立規則裁判。
24. 手機端不得繞過 `activeBackendUrl`、Rule Registry、Tool Registry、Execution Trace 與 Data Center Gate。
25. 手機端語音指令不得跳過使用者簽名 Gate、驗收 Gate 或二次確認入庫 Gate。
26. 不得讓新增模型 Runtime 自動獲得舊規則未授權的工具能力。
27. 不得讓語言切換改變內部 key、ledger、storage targets 或 signature status。
28. 不得讓基礎網路搜尋繞過 Workbench / 驗收 / 二次確認入庫。
29. 不得讓 Rule Registry 取代使用者簽名 Gate。
30. 不得讓 Tool Permission Gate 取代使用者驗收 Gate。
31. 不得讓模型生成內容直接寫入 memory。
32. 不得讓 archived / revoked / superseded 資料重新成為有效引用來源。
33. 不得在產品 UI 內使用測試簽名。
34. 不得讓 Data Center 預設硬刪資料。
35. 不得把手機 App 描述成獨立本地模型主體。
36. 不得把 SCBKR 1.0 宣傳成完整全自動 Agent。
37. 不得把 SCBKR 2.0 做成單純 Chat App。
38. 不得把 Workbench 藏在次要入口。
39. 不得把規則來源混淆。
40. 不得讓商業規則包無版本、無作者、無採用紀錄。

---

# 25. 1.0 公告方向

公告標題：

SCBKR 1.0 Release Candidate：本地責任鏈模型正式進入實機驗收階段

公告重點：

SCBKR 不是聊天機器人。

SCBKR 是本地 AI 責任鏈工作台。

模型可以協助，但不能越權。

使用者簽名後責任鏈才成立。

驗收後才可入庫。

二次確認後才可寫入四庫。

未來任務只能引用有效資料。

目前支援本地後端、Data Center、四庫、LM Studio / Ollama / OpenAI-compatible API 接入基礎。

下一階段 2.0 將加入規則中心、工具權限、半自動 / 全自動 AI 引擎與規則包訂閱。

---

# 26. 2.0 公告方向

公告標題：

SCBKR 2.0 Roadmap：規則驅動 AI 引擎作業系統

公告重點：

2.0 不只是 UI 更新。

2.0 是規則層控制 AI 引擎。

模型沒有命中已成立規則，不執行決策。

工具能力包含 Web Search、Email、Code Workspace、Image、Voice、API。

所有工具受 Rule Match Gate 與 Tool Permission Gate 控制。

未來將支援使用者自定義規則、沈耀簽名規則包、企業規則與規則訂閱。

SCBKR 的目標是讓 AI 能接近巨頭模型工具能力，但所有判斷與行動都回到使用者或創作者簽名規則。

---

# 27. 最終產品一句話

SCBKR 1.0：

本地 AI 責任鏈確認單工作台。

SCBKR 2.0：

規則驅動 AI 引擎作業系統。

完整產品閉環：

使用者定義任務  
→ 模型整理確認單  
→ 使用者修改  
→ 使用者簽名  
→ 模型依確認單生成  
→ 使用者驗收  
→ 使用者二次確認入庫  
→ Data Center 寫入四庫  
→ 未來任務引用有效證據  
→ 2.0 規則層控制 AI 工具執行

核心總結：

模型可以參與，但不能越權。  
規則可以成立，但必須簽名。  
資料可以入庫，但必須驗收。  
工具可以執行，但必須受規則控制。  
AI 可以自動化，但必須回到責任鏈。

---

# 28. 最終裁決

目前方向固定如下。

先把 1.0 基底打穩。

1.0 先完成：

- 中英文切換
- 語言包
- 基礎網路搜尋
- 模型設定
- Windows installer
- 手機連本機說明
- README / README_EN
- Release Notes
- 隱私政策
- 1.0 功能公告
- 2.0 Roadmap 公告

2.0 再完成：

- 規則中心
- 規則包
- 規則命中
- 工具註冊
- 工具權限
- Web Search 進階
- Email
- Code Workspace
- Image Generation
- Voice I/O
- 半自動 AI 引擎
- 全自動 AI 引擎
- Rule Marketplace
- 訂閱制
- 企業治理

最終不再偏移。

所有後續 UI、後端、工具、商業、上架、公告、Codex 指令，都以本計畫書為準。
29. Codex 防漂移施工協議｜Anti-Drift Build Protocol

本章是給 Codex / 工程代理 / 自動化修復工具使用的施工協議。

SCBKR 總計畫書是產品主藍圖，不代表每次任務都要實作所有內容。

任何 Codex 任務都必須只執行當前指定階段與指定範圍。

若任務沒有明確要求，不得自行實作未來 Roadmap。

---

29.1 文件優先級

SCBKR 工程文件優先級如下：

第一優先級：不可破壞鐵律
第二優先級：當前任務指令
第三優先級：當前階段目標
第四優先級：總計畫書 Roadmap
第五優先級：Codex 自行推測

若發生衝突，必須依照高優先級文件執行。

Codex 不得用 Roadmap 內容覆蓋當前任務指令。

Codex 不得用未來 2.0 目標改動 1.0 基礎架構。

Codex 不得自行推測產品意圖。

---

29.2 總計畫書不是一次性實作清單

總計畫書用途：

- 定義產品方向
- 定義不可破壞鐵律
- 定義 1.0 與 2.0 分層
- 定義後續施工路線
- 定義工程紅線

總計畫書不是：

- 一次性全部實作清單
- 自由重構授權
- UI 全面改版授權
- 工具層自動啟用授權
- 規則商城立即實作授權
- 2.0 全功能同時開工授權

Codex 每次只能依照當次任務指定的 phase / files / goals / tests 執行。

---

29.3 任務切片原則

每次 Codex 任務必須切成小片。

不得一次要求 Codex 同時處理：

- UI redesign
- backend schema
- storage gate
- Web Search
- i18n
- mobile
- rule registry
- tool registry
- release scripts

除非任務明確指定，否則每次只處理一個主題。

標準任務切片格式：

Phase:
Scope:
Allowed files:
Forbidden files:
Goal:
Non-goals:
Must preserve:
Implementation requirements:
Tests:
Final report format:

Codex 不得超出 "Scope"。

Codex 不得修改 "Forbidden files"。

Codex 不得實作 "Non-goals"。

---

29.4 當前階段鎖定

目前階段為：

P15-R：1.0 上線基礎整理

P15-R 允許處理：

- README / README_EN
- Release Notes
- GitHub About / Topics
- 中英文語言包
- UI 文案整理
- 基礎 Web Search 設計
- 模型設定說明
- Windows 安裝說明
- 手機連本機說明
- 隱私與安全說明
- 1.0 功能公告
- 2.0 Roadmap 公告

P15-R 不得處理：

- Rule Registry 正式實作
- Rule Match Gate 正式實作
- Tool Registry 正式實作
- Tool Permission Gate 正式實作
- Email Tool 正式實作
- Code Workspace 正式實作
- Image Generation Tool 正式實作
- Rule Marketplace
- Subscription payment
- 全自動 AI 引擎
- 手機端獨立 Runtime
- 大規模重構
- 改弱任何 Gate

若 Codex 需要做上述內容，必須停止並回報：

「此內容屬於 P16 或 2.0，不屬於目前 P15-R 範圍。」

---

29.5 不可碰觸區域

除非任務明確要求，Codex 不得修改以下核心 Gate：

- 使用者簽名 Gate
- 修改後重簽 Gate
- review_passed Gate
- storage_confirmed Gate
- second_confirm Gate
- confirmed_by=user Gate
- Data Center signature Gate
- 四庫 selected_targets Gate
- external_api guard
- activeBackendUrl
- physical write gate
- ledger replay
- revoked / archived / superseded 狀態判定

若修改任何 Gate，必須在回報中逐項說明：

- 修改了哪個 Gate
- 為什麼必須修改
- 是否降低安全性
- 哪個測試證明沒有降低
- 缺少測試時不得宣稱完成

---

29.6 不可自行新增能力

Codex 不得自行新增以下能力：

- 自動寄信
- 自動刪信
- 自動封存信件
- 自動 push code
- 自動刪檔
- 自動寫入 Data Center
- 自動把搜尋結果寫入 memory
- 自動把模型輸出寫入 logic
- 自動啟用全自動模式
- 自動建立商業規則包
- 自動新增付款功能
- 自動把手機端變成獨立模型 Runtime

這些能力只能在對應 Phase 明確開啟。

---

29.7 UI 防漂移規則

Codex 不得把 SCBKR 改成單純 Chat App。

Codex 不得把 Workbench 藏起來。

Codex 不得把 Data Center 藏起來。

Codex 不得把使用者簽名欄改成可省略。

Codex 不得把二次確認入庫改成自動流程。

Codex 不得為了 UX 減少責任鏈確認步驟。

允許的 UX 優化：

- 顯示 diff
- 顯示修改摘要
- 顯示為何需要重新簽名
- 顯示 Gate 狀態
- 顯示錯誤原因
- 顯示下一步可操作項目
- 改善排版
- 改善 onboarding

不允許的 UX 優化：

- 保留舊簽名
- 自動確認責任鏈
- 自動驗收
- 自動二次確認
- 自動入庫
- 隱藏 Gate
- 將 Gate 改成背景流程

---

29.8 i18n 防漂移規則

語言包只能影響 View 層顯示。

語言切換不得改變：

- API schema
- internal key
- storage target
- task status
- signature status
- ledger field
- rule status
- database field
- JSONL replay field
- vector / corpus / logic / memory 內部代碼

中文 UI 可以顯示：

- 向量庫
- 語料庫
- 邏輯庫
- 記憶庫

但內部 key 必須固定為：

vector
corpus
logic
memory

Codex 不得因翻譯而修改內部資料結構。

---

29.9 Web Search 防漂移規則

P15-R 若實作基礎 Web Search，只能作為候選資料來源。

Web Search 資料流只能進入：

- Chat 顯示
- 搜尋摘要
- 候選引用
- Workbench 草案

Web Search 不得直接寫入：

- vector
- corpus
- logic
- memory
- Data Center 正式資料
- long-term memory
- rule registry

Web Search 結果若要入庫，必須走完整責任鏈：

Search
→ Candidate
→ Workbench
→ Owner Signature
→ Generation / Summary
→ User Review
→ Storage Request
→ Second Confirmation
→ Data Center
→ Four Stores

Codex 不得偷寫捷徑。

---

29.10 Mobile 防漂移規則

手機端不是獨立模型主體。

手機端不是獨立規則裁判。

手機端不是獨立工具執行器。

手機端只能作為：

- 操作入口
- 顯示入口
- 簽名入口
- 驗收入口
- 二次確認入口
- 遠端控制入口

手機端所有決策行為必須回到：

- activeBackendUrl
- 本機 Runtime
- Rule Match Gate
- Tool Permission Gate
- Data Center Gate
- Storage Gate

Codex 不得在手機端建立獨立判定邏輯。

Codex 不得讓手機端繞過桌面端 / 本機 Runtime。

---

29.11 測試優先規則

每次修改必須附帶最小驗收測試。

若是文件修改，必須至少確認：

- Markdown link 正常
- 圖片路徑正常
- README 不含過期語意
- 版本號一致

若是 UI 修改，必須至少確認：

- web build 通過
- 沒有破壞 Gate 文案
- 空簽名不得送出
- 修改草案後簽名清空

若是後端修改，必須至少確認：

- python tests 通過
- storage-confirm 缺 second_confirm 仍失敗
- confirmed_by 不是 user 仍失敗
- signature 空值仍失敗

若是 Windows / desktop 修改，必須至少確認：

- desktop check 通過
- release check 通過
- Windows smoke 通過或明確回報環境限制

不得在未跑測試時宣稱「已完成」。

只能說：

「程式修改完成，但尚未通過指定測試。」

---

29.12 Codex 停止條件

遇到以下情況，Codex 必須停止，不得繼續自行發揮：

1. 任務要求與不可破壞鐵律衝突。
2. 任務需要修改 Gate，但沒有明確授權。
3. 任務需要實作 2.0 功能，但目前 phase 是 P15-R。
4. 任務需要新增工具權限，但沒有 Tool Registry 規格。
5. 任務需要改資料庫 schema，但沒有 migration 要求。
6. 任務需要改手機端獨立判定邏輯。
7. 任務需要自動入庫搜尋結果。
8. 任務需要自動寄信、刪檔、push、發布。
9. 任務缺少必要檔案或測試環境。
10. 任務範圍過大，無法在單一 PR 內安全完成。

停止時必須回報：

未完成，原因：
阻塞點：
需要使用者確認：
建議拆分任務：

---

29.13 Codex 最終回報格式

Codex 每次完成後只能用以下格式回報。

Summary:
- 實際修改了什麼
- 沒有修改什麼
- 是否碰到核心 Gate
- 是否符合當前 Phase

Files changed:
- path 1
- path 2

Gate preservation:
- 使用者簽名 Gate：未降低 / 有修改，說明
- 修改後重簽 Gate：未降低 / 有修改，說明
- 驗收 Gate：未降低 / 有修改，說明
- 二次確認入庫 Gate：未降低 / 有修改，說明
- Data Center Gate：未降低 / 有修改，說明
- 四庫 Gate：未降低 / 有修改，說明

Tests:
- 已執行：
- 結果：
- 未執行：
- 未執行原因：

Non-goals not touched:
- 是否未實作 2.0 未授權功能
- 是否未新增自動寄信 / 自動刪檔 / 自動入庫
- 是否未改動手機端獨立判定

Final verdict:
A. 完成，可進下一步
或
B. 未完成，列出最小阻塞點

Codex 不得只回「done」。

Codex 不得只回「all tests passed」。

Codex 必須明確說明 Gate 是否被保留。

---

29.14 給 Codex 的標準任務模板

每次給 Codex 任務時，必須使用以下模板。

任務名稱：

Phase：

本次目標：

允許修改檔案：

禁止修改檔案：

必須保留：

不得實作：

工程要求：

測試要求：

完成回報格式：

最終裁決只能輸出：
A. 完成，可進下一步
或
B. 未完成，列出最小阻塞點

---

29.15 最終防漂移裁決

SCBKR 總計畫書是方向。

Codex 任務卡才是當次施工範圍。

Codex 不得把方向當成一次性全量實作。

Codex 不得因為看到 2.0 Roadmap 就提前實作 2.0。

Codex 不得為了 UX 改弱責任鏈。

Codex 不得為了測試通過改弱 Gate。

Codex 不得為了商業化混淆規則來源。

Codex 不得為了手機便利繞過本機 Runtime。

每次施工只做當次任務。

所有施工都必須回到：

使用者簽名
→ 模型生成
→ 使用者驗收
→ 二次確認入庫
→ Data Center
→ 四庫
→ 回放審計

最終不漂移。
