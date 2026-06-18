# SCBKR 本地責任鏈模型｜自接入 MVP App

SCBKR 是本地責任鏈流程控制層：模型只是執行單元，使用者才是最終決策者。P12 將 P0–P11 收束為本地 Web App MVP，讓使用者可自行接入 LM Studio、Ollama 或 OpenAI-compatible API，先建立 SCBKR 五維確認單，確認後才允許模型生成，再進入驗收與入庫計畫。

## 它不是

- 不是雲端 SaaS。
- 不是桌面安裝包（Electron / Tauri 尚未完成）。
- 不是直接聊天模型。
- 不是大模型公司。
- 不宣稱正式 SQLite、ChromaDB / embedding、ledger runtime 或 memory 實體寫入已完成。

## 固定端口

- 後端 API：`http://localhost:8787`
- 前端 Web：`http://localhost:5500`

## 快速開始

```sh
python -m pip install -e .
npm --prefix apps/web install --package-lock=false
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787
npm --prefix apps/web run dev
```

打開 `http://localhost:5500` 後：

1. 設定 LM Studio / Ollama / OpenAI-compatible API（`GET/POST /api/settings/model`）。
2. 呼叫 `POST /api/model/test` 測試連線；`model_name` 未填或服務沒開會失敗，不會假裝成功。
3. 開啟必要權限（至少 `model_generate`；external / hybrid mode 測試或生成外部 API 另需通過 P10 `external_api_call`，即 `external_api` 與 `dangerous_operation_confirmed` 皆為 true）。
4. 建立任務。
5. 產生 SCBKR 五維確認單。
6. 使用者確認。
7. 權限與模型測試成功後才可生成。
8. 進入驗收。
9. 通過後產生入庫計畫；P12 不做實體寫入，回傳 `physical_write_performed = false`。
10. 失敗後只保留 `failure_report_draft`；若使用者另行明確提供判詞、規則與 scope，才可建立 P11 `memory_rule_draft`，再以非空白簽名建立 `memory_rule_confirmed_plan`，但不寫 memory。

## scripts

- `scripts/setup.sh`：安裝 Python 與前端依賴。
- `scripts/dev.sh`：啟動 API 8787 與 Web 5500。
- `scripts/test.sh`：執行 pytest 與前端 build。

## 模型接入

預設設定適合 LM Studio：`http://localhost:1234/v1`。Ollama 可使用 OpenAI-compatible 端點，例如 `http://localhost:11434/v1`。外部 API 使用 `openai_compatible` / `external` 或 `hybrid` 時，模型測試與生成都必須通過 P10 `external_api_call`；該操作同時要求 `external_api = true` 與 `dangerous_operation_confirmed = true`。API key 在讀取設定時只會遮罩，不明文回傳。

## 權限鎖

P10 控制准不准用：`model_generate` 未開不得生成；external / hybrid 模式下必須通過 `external_api_call`，缺少 `external_api` 或 `dangerous_operation_confirmed` 都不得呼叫外部 API；storage、ledger、SQLite、ChromaDB、embedding、memory 權限不會被 P12 自動開啟。

## MVP 邊界

可跑：FastAPI health / status、模型設定與連線測試、權限設定、任務建立、SCBKR 草案、確認、生成閘門、驗收、入庫計畫、P11 失敗報告草案，以及使用者明確觸發的失敗規則草案與確認計畫。

仍為 MVP in-memory：任務 runtime、模型設定 runtime、權限設定 runtime。

仍 pending：正式 SQLite 持久化、正式 ChromaDB / embedding runtime、正式 ledger append runtime、正式 memory physical write、桌面安裝包、雲端版、手機外網遠端連線。

## 手機同 Wi‑Fi 使用

前端開發伺服器若改用區網 host 啟動，可在同 Wi‑Fi 手機打開：`http://{電腦區網IP}:5500`。P12 不自動設定外網 tunnel，也不提供手機原生 App。
