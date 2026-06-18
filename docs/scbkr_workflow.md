# SCBKR Workflow

狀態：P9 responsibility-chain retrieval route structure

本文件定義 Task、SCBKR、狀態枚舉、狀態轉移，並記錄 P2 回放帳本結構邊界。

## P1 範圍

P1 建立以下結構：

- Task JSON Schema：任務欄位、任務類型、任務狀態、三層硬鎖與結果欄位。
- SCBKR JSON Schema：S / C / B / K / R 五維確認單欄位。
- Task status enum：固定任務狀態列表。
- Allowed transitions：任務狀態轉移白名單。
- Pure Python constants：五維欄位對照與狀態 helper。

## Task 三層硬鎖

- `confirmed = false` 時不得 generate。
- `review_passed = false` 時不得標準入庫。
- `storage_confirmed = false` 時不得寫入四庫。

## SCBKR 五維

- S｜介面 / 主體：任務名稱、使用者指令、任務主體、輸入內容、輸出形式、介面與平台。
- C｜後端 / 因果：流程拆解、執行順序、資料流、事件流、核心邏輯、依賴、失敗影響與測試條件。
- B｜邊界 / 行為：資料讀寫範圍、本地與外部操作範圍、權限開關、停止條件、錯誤處理、敏感操作確認與入庫條件。
- K｜依據 / 風格：參考資料、技術文件、語料來源、風格設定、框架選擇、模型依據、歷史案例與來源可信度。
- R｜回放 / 簽名：預期輸出、驗收條件、ledger 要求、入庫選項、簽名狀態、review 狀態、replay 要求與是否產生 memory rule。

## P2 回放帳本範圍

P2 建立 ledger event schema、event constants、hash helper、append-only JSONL helper。

ledger 是 SCBKR 的回放時間軸，只保存事件記錄：

- ledger 不是資料庫。
- ledger 不是模型記憶。
- ledger 不是四庫。
- ledger 不判定任務成功。

P2 保留三層硬鎖語義，讓 ledger 能記錄 `user_confirmed`、`review_passed`、`review_failed`、`storage_requested`、`storage_confirmed` 等狀態事件；但 P2 不實作這三層鎖的執行流程。

## P2 尚未接入

- P2 尚未接入 task workflow。
- P2 尚未接入 API route。
- P2 尚未接入 DB。
- P2 尚未寫入正式 `data/ledger/audit-log.jsonl`。

## P3 前端主畫面範圍

P3 建立前端主畫面 skeleton。

- P3 使用 mock state。
- P3 尚未接入 API。
- P3 尚未建立 task。
- P3 尚未寫 ledger。
- P3 尚未呼叫 model gateway。
- P3 尚未寫入四庫。

P3 UI 是本地責任鏈工作台，不是聊天框；畫面只展示頂部狀態列、任務輸入區、目前任務卡片、SCBKR 五維確認區、四庫狀態區與三層硬鎖按鈕狀態。

## P4 SCBKR 生成器範圍

P4 建立純函式 SCBKR 草案生成器。

- P4 根據 raw_input / task_type 產生 S / C / B / K / R 草案。
- P4 產物只是 waiting user confirmation 的草案。
- P4 尚未接入 API。
- P4 尚未接入 UI。
- P4 尚未寫 ledger。
- P4 尚未接入 model gateway。
- P4 尚未做向量檢索。
- P4 尚未建立 embedding。
- P4 尚未進入正式 task workflow runtime。

P4 的 A / B / C / none 相似路徑只作欄位標註，不代表已執行 RAG、向量搜尋、資料庫查詢或模型生成。

## P5 模型接口範圍

P5 建立模型接口安全結構。

- P5 只建立設定驗證、request builder、response parser、connection test helper。
- P5 尚未接入 task workflow。
- P5 尚未接入 API route。
- P5 尚未接入 UI。
- P5 尚未執行真模型呼叫。
- P5 尚未產生正式任務答案。
- P5 尚未寫 ledger。
- P5 尚未寫 DB。
- P5 尚未寫四庫。

P5 只是模型插座結構，不代表 LM Studio、Ollama、OpenAI-compatible 或 custom provider 已可用；只有呼叫方明確提供 success 測試狀態時，後續階段才可考慮啟用生成。

## P6 任務生成流程安全閘門範圍

P6 建立任務生成流程安全閘門。

- P6 只處理 confirmed task → model request → caller-supplied response → generation_result → waiting_review。
- P6 不執行真模型呼叫。
- P6 不寫 ledger。
- P6 不寫 DB。
- P6 不寫四庫。
- P6 不接 API route。
- P6 不接 UI。
- P6 不自動驗收。
- P6 不自動入庫。

P6 的狀態上限是 `waiting_review`；模型回覆仍須使用者驗收，不得自動變成 `review_passed`、`waiting_storage_request`、`storage_confirmed` 或 `completed`。

## P7 驗收與回退範圍

P7 建立使用者驗收與回退判定。

- P7 只處理 waiting_review → review_passed / review_failed / rollback_requested。
- P7 通過後只進入 ask_user_storage_request。
- P7 失敗後只產生 failure_report_draft。
- P7 回退後只標記 rollback_layer。
- P7 不自動入庫。
- P7 不自動寫四庫。
- P7 不自動寫記憶。
- P7 不自動重生。
- P7 不寫 ledger。
- P7 不寫 DB。
- P7 不接 API route。
- P7 不接 UI。

失敗可以被報告，但不能被定義成規則。
失敗原因是否可入庫，必須由使用者後續明確簽名確認。
驗收失敗入記憶規則屬於 P11，不屬於 P7。

## P8 四庫寫入計畫與二次確認範圍

P8 建立四庫寫入計畫與二次確認。

- P8 只處理 review_passed → storage_request → storage_commit_plan。
- P8 不做實體寫入。
- P8 不寫 SQLite。
- P8 不寫 ChromaDB。
- P8 不寫 data/*。
- P8 不寫 ledger。
- P8 不接 API route。
- P8 不接 UI。

驗收通過不等於自動入庫。
入庫必須二次確認。
memory 目標必須使用者簽名。
失敗內容不得入庫。
failure_report_draft 不得入庫。
驗收失敗入記憶規則屬於 P11。
ChromaDB 實體向量檢索與寫入屬於 P9 或後續 storage runtime。
SQLite table / migration 屬於後續 database runtime。

## P9 責任鏈相似路由範圍

P9 建立責任鏈相似路由結構。

- P9 只處理 caller-supplied candidate cases。
- P9 不讀 ChromaDB。
- P9 不寫 ChromaDB。
- P9 不建立 embedding。
- P9 不寫 data/vector_db。
- P9 不寫 SQLite。
- P9 不寫 ledger。
- P9 不接 API route。
- P9 不接 UI。
- P9 不自動沿用舊案例。
- P9 不跳過使用者確認。

P9 找的是責任鏈基因相似度，不是單純文字相似度。
A / B / C / none 都只是路由建議。
任何檢索結果都不得跳過 SCBKR 使用者確認。
ChromaDB 實體 runtime 尚未實作。
embedding runtime 尚未實作。

## 尚未實作

- 尚未實作正式任務流程 ledger writer。
- 尚未實作 generate。
- 尚未實作 API route。
- 尚未實作 DB table。
- 尚未實作 model gateway runtime / 真模型呼叫。
- 尚未實作四庫寫入。
- 尚未實作 RAG similarity route。

## P10 權限鎖與高風險操作確認範圍

狀態：P10 permission lock and high-risk confirmation structure

P10 建立權限鎖與高風險操作確認。

- P10 只判定 operation 是否被授權。
- P10 不執行 operation。
- P10 不呼叫模型。
- P10 不呼叫外部 API。
- P10 不搜尋網路。
- P10 不讀本地檔案。
- P10 不寫 SQLite。
- P10 不寫 ChromaDB。
- P10 不寫 ledger。
- P10 不寫四庫。
- P10 不接 API route。
- P10 不接 UI。

P5 確認能不能連。
P10 確認准不准用。

所有權限預設關閉。
權限未開，不得宣稱已執行。
高風險操作必須使用者確認。
P10 只是 permission gate，不是 runtime executor。

## P11 驗收失敗記憶規則草案與簽名確認範圍

狀態：P11 review failed memory rule draft and signature structure

P11 建立驗收失敗記憶規則草案與簽名確認。

- P11 只處理 review_failed → memory_rule_draft → memory_rule_confirmed_plan。
- P11 不寫記憶庫。
- P11 不寫 data/memory。
- P11 不寫 SQLite。
- P11 不寫 ChromaDB。
- P11 不寫 ledger。
- P11 不接 API route。
- P11 不接 UI。
- P11 不自動套用規則。
- P11 不自動重新 generate。

失敗輸出本身不得入庫。
failure_report_draft 只能當來源，不是規則本身。
失敗原因是否成立，必須由使用者判詞確認。
沒有使用者簽名，不得建立 confirmed plan。
P11 不產生 memory_rule_stored。
實體 memory runtime 尚未實作。
