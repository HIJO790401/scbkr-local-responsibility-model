# SCBKR Workflow

狀態：P6 generation gate structure

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

## 尚未實作

- 尚未實作正式任務流程 ledger writer。
- 尚未實作 generate。
- 尚未實作 API route。
- 尚未實作 DB table。
- 尚未實作 model gateway runtime / 真模型呼叫。
- 尚未實作四庫寫入。
- 尚未實作 RAG similarity route。
