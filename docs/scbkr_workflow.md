# SCBKR Workflow

狀態：P2 ledger structure

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

## 尚未實作

- 尚未實作正式任務流程 ledger writer。
- 尚未實作 generate。
- 尚未實作 API route。
- 尚未實作 DB table。
- 尚未實作 model gateway。
- 尚未實作四庫寫入。
- 尚未實作 RAG similarity route。
