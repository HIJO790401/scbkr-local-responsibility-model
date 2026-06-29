# SCBKR 本地責任鏈模型

本地 AI 責任鏈工作台｜使用者簽名 Gate｜Data Center｜四庫引用｜Release Candidate

SCBKR 不是一般聊天機器人。SCBKR 是一套本地 AI 責任鏈工作台。模型可以協助，但不能越權。使用者簽名後，責任鏈才成立。驗收後才可入庫。二次確認後才可寫入四庫。

## 1. 什麼是 SCBKR

SCBKR 將「使用者意圖、草案、簽名、模型生成、驗收、入庫」串成可追溯的責任鏈。它不是讓模型直接決定規則、記憶或資料是否成立，而是讓使用者在每個關鍵節點留下明確授權。

![SCBKR 產品總覽](docs/images/scbkr-hero.png)

## 2. 核心原則

- 模型可以協助，但不能越權。
- 使用者簽名後，SCBKR 才成立。
- 模型不能簽名。
- 使用者修改確認單後，舊簽名必須作廢。
- 使用者驗收後才可入庫。
- 入庫必須二次確認。
- 未驗收資料不得進入四庫。
- 未有效資料不得被未來任務引用。

## 3. 目前版本狀態

- 目前版本：0.15.0-rc.1
- 目前階段：P15-Q Release Candidate + PATCH-2
- 下一階段：P15-R 1.0 上線基礎整理

## 4. 1.0 目前能做什麼

- Chat 任務入口
- Workbench 責任鏈確認單
- S / C / B / K / R 草案
- 使用者簽名 Gate
- 模型生成
- 使用者驗收
- Storage Request
- Second Confirmation
- Data Center
- 四庫引用
- LM Studio / Ollama / OpenAI-compatible API 接入基礎
- Windows desktop release candidate
- 手機透過 activeBackendUrl 連回本機後端的基礎設計

## 5. 完整責任鏈流程

Chat → Workbench → SCBKR Draft Grammar → Owner Signature → Model Generation → User Review → Storage Request → Second Confirmation → Data Center → Four-store Evidence Reuse

Rule / Memory / Data 不是模型自己決定成立。必須由使用者簽名、驗收、二次確認後才成立。

![完整責任鏈流程](docs/images/responsibility-loop.png)

## 6. Workbench 與使用者簽名

Workbench 是責任鏈確認單的操作區。使用者必須檢查任務目的、草案內容、引用資料與入庫意圖後簽名；若確認單被修改，舊簽名必須作廢並重新簽名。

![Workbench 與使用者簽名](docs/images/workbench-owner-signature.png)

## 7. Data Center 與四庫

Data Center 只對已驗收且通過二次確認的內容開放正式入庫。正式四庫為：

- vector
- corpus
- logic
- memory

exports 不是正式四庫入庫目標。exports 若未來存在，只能是匯出 / 報告功能，不得混入 selected_targets。

![Data Center 與四庫](docs/images/four-store-evidence.png)

## 8. 本地模型支援

SCBKR 可接：Sandbox、LM Studio、Ollama、OpenAI-compatible API、Custom endpoint。

localhost / 127.0.0.1 / ::1 是本機模型呼叫。192.168.x.x 是區網呼叫。外部 API endpoint 會把資料送到使用者設定的服務。

![本地模型架構](docs/images/architecture.png)

## 9. Windows 安裝與啟動

1. 下載 Windows installer / release artifact（目前為 Release Candidate）。
2. 安裝 SCBKR Desktop。
3. 啟動本機 backend / sidecar。
4. 打開桌面 app。
5. 設定模型 provider。
6. 建立第一個任務。
7. 簽名、生成、驗收、入庫。

詳細步驟請見 [Windows 安裝文件](docs/INSTALL_WINDOWS.md)。

## 10. 手機連回本機電腦

手機端不是獨立模型主體，而是操作入口。手機端透過 activeBackendUrl 連回本機電腦；手機與電腦需在同一 Wi-Fi。使用者需要查詢電腦區網 IP，例如 192.168.x.x。Windows 防火牆可能需要允許 SCBKR / FastAPI 通訊。手機端目前不得宣稱已具備完整獨立 Runtime。

## 11. 隱私與安全邊界

- SCBKR 主要在本機運行。
- 使用本地模型時，資料留在使用者本機或使用者指定的區網環境。
- 使用外部 OpenAI-compatible API 時，資料會送往使用者設定的 endpoint。
- SCBKR 不會讓模型自動簽名。
- SCBKR 不會讓模型自動驗收。
- SCBKR 不會讓模型自動二次確認入庫。
- SCBKR 不會讓模型自動把輸出變成長期記憶。
- Data Center 寫入需要使用者驗收與二次確認。

## 12. 與 Chatbot / Agent / RAG 的差異

| 類型 | 典型行為 | SCBKR 差異 |
|---|---|---|
| Chatbot | 直接回覆 | SCBKR 先建立責任鏈，再允許生成。 |
| RAG | 檢索資料後回覆 | SCBKR 只允許有效資料被未來任務引用。 |
| Agent | 嘗試自動執行任務 | SCBKR 不讓模型繞過簽名、驗收與二次確認。 |
| SCBKR | 建立責任鏈 | 使用者簽名後才允許模型生成，驗收後才允許入庫。 |

## 13. 2.0 Roadmap

以下屬於 Roadmap / Future Work，不屬於目前 1.0 已完成功能：

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

## 14. 開發者快速啟動

```bash
python -m pytest -q
npm --prefix apps/web run build
npm --prefix apps/desktop run check:skeleton
npm --prefix apps/desktop run check:release
```

## 15. 測試與驗收

建議以完整責任鏈 smoke 驗收：建立任務、打開 Workbench、簽名、模型生成、使用者驗收、送出 Storage Request、二次確認、確認 Data Center 四庫目標。

## 16. 專案狀態與限制

SCBKR 0.15.0-rc.1 是 1.0 Release Candidate。完整使用者介面 i18n、Web Search、Semantic Legality Gate、Rule Design Engine、工具權限層與商店上架仍屬後續階段。

## 17. License / Author

Author: SCBKR project maintainers. License: see repository license file when provided.
