# P12｜本地 App 自接入 MVP 總驗收

## 驗收項目

- 後端可啟動於 `http://localhost:8787`。
- 前端可啟動於 `http://localhost:5500`。
- 前端可顯示 API health、任務輸入、SCBKR 五維、模型狀態、權限狀態。
- 任務流程遵守：create → scbkr → confirm → generate → review → storage-request → storage-confirm。
- 生成必須受 confirmed、P5 model settings、P10 permission lock 限制。
- 入庫只產生 plan，`physical_write_performed = false`。
- review_failed 只產生 P11 draft / confirmed plan，不寫 memory。

## 測試指令

```sh
python -m pytest -q
npm --prefix apps/web install --package-lock=false
npm --prefix apps/web run build
```

## 啟動指令

```sh
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787
npm --prefix apps/web run dev
```

或使用：

```sh
scripts/setup.sh
scripts/dev.sh
scripts/test.sh
```

## API 檢查

```sh
curl http://localhost:8787/health
curl http://localhost:8787/api/system/status
curl http://localhost:8787/api/settings/model
curl http://localhost:8787/api/settings/permissions
```

## 前端檢查

- 打開 `http://localhost:5500`。
- 確認 health 顯示 online。
- 建立任務並產生 SCBKR 五維確認單。
- 確認 UI 明確標示 MVP in-memory runtime。

## 模型接入檢查

- LM Studio：`base_url = http://localhost:1234/v1`。
- Ollama：`base_url = http://localhost:11434/v1`（OpenAI-compatible）。
- OpenAI-compatible API：設定 provider / mode / base_url / api_key / model_name。
- `model_name` 未填必須測試失敗。
- 服務未開必須測試失敗，不得宣稱可用。
- API key 讀取時必須遮罩。

## 權限鎖檢查

- `model_generate = false` 時不得 generate。
- external / hybrid mode 且 `external_api = false` 時不得呼叫外部 API。
- storage、ledger、SQLite、ChromaDB、embedding、memory 權限不會造成 P12 實體寫入。

## 任務流程檢查

1. `POST /api/tasks/create`
2. `POST /api/tasks/{task_id}/scbkr`
3. `POST /api/tasks/{task_id}/confirm`
4. `POST /api/tasks/{task_id}/generate`
5. `POST /api/tasks/{task_id}/review`
6. `POST /api/tasks/{task_id}/storage-request`
7. `POST /api/tasks/{task_id}/storage-confirm`
8. review failed 時檢查 `memory_rule_draft`，不得產生 `memory_rule_stored`。

## MVP 已完成項

- FastAPI MVP app 與固定 8787 啟動方式。
- Vite Web MVP 與固定 5500 啟動方式。
- In-memory task runtime。
- 模型設定、模型連線測試、權限設定 route。
- SCBKR 基本流程 route。
- README 與 scripts 啟動說明。

## MVP 尚未完成項

- 桌面安裝包尚未完成。
- 雲端版尚未完成。
- 正式 SQLite 持久化尚未完成。
- 正式 ChromaDB / embedding runtime 尚未完成。
- 正式 ledger append runtime 尚未完成。
- 正式 memory physical write 尚未完成。
- 手機外網遠端連線尚未完成。

## 下一階段

P13 可在「桌面封裝 / 本地主機手機連線 / 持久化 runtime」三選一。
