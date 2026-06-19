# P12｜本地 App 自接入 MVP 總驗收

## 驗收項目

- 後端可啟動於 `http://localhost:8787`。
- 前端可啟動於 `http://localhost:5500`。
- 前端可顯示 API health、任務輸入、SCBKR 五維、模型狀態、權限狀態。
- 任務流程遵守：create → scbkr → confirm → generate → review → storage-request → storage-confirm。
- 生成必須受 confirmed、P5 model settings、P10 permission lock 限制。
- 一鍵 confirm 後 S/C/B/K/R 必須全部 confirmed，但 UI 不新增五個確認頁，避免大重構。
- 每一維都必須有 `snapshot_hash`。
- 每一維都必須有 `confirmed_snapshot`。
- generate 前必須檢查 S/C/B/K/R 五維全 confirmed。
- confirm 後若任一維 live payload 與 `confirmed_snapshot` 不一致，必須拒絕 generate。
- `snapshot_hash` 必須等於 `confirmed_snapshot` 的穩定 hash，竄改 hash 或 snapshot 都必須失效。
- 測試環境必須優先使用真 FastAPI `TestClient`；只有真 TestClient import 失敗時才可 fallback shim。
- 入庫只產生 plan，`physical_write_performed = false`。
- review_failed 只產生 `failure_report_draft`；不得自動建立 `memory_rule_draft`。
- `memory_rule_draft` 只能由 `POST /api/tasks/{task_id}/memory-rule-draft` 在使用者明確提供判詞、規則與 scope 後建立。
- `memory_rule_confirmed_plan` 只能由 `POST /api/tasks/{task_id}/memory-rule-confirm` 在 reviewer_signature 非空白後建立，不寫 memory。

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
- external / hybrid mode 必須通過 P10 `external_api_call`，也就是 `external_api = true` 且 `dangerous_operation_confirmed = true`，否則不得呼叫外部 API。
- storage、ledger、SQLite、ChromaDB、embedding、memory 權限不會造成 P12 實體寫入。

## 任務流程檢查

1. `POST /api/tasks/create`
2. `POST /api/tasks/{task_id}/scbkr`
3. `POST /api/tasks/{task_id}/confirm`
4. `POST /api/tasks/{task_id}/generate`
5. `POST /api/tasks/{task_id}/review`
6. `POST /api/tasks/{task_id}/storage-request`
7. `POST /api/tasks/{task_id}/storage-confirm`
8. review failed 時只能檢查 `failure_report_draft`，不得自動產生 `memory_rule_draft` 或 `memory_rule_stored`。
9. 如需建立記憶規則草案，呼叫 `POST /api/tasks/{task_id}/memory-rule-draft` 並明確提供 `user_failure_judgement`、`rule_statement`、`applies_to_task_types`、`trigger_conditions`、`forbidden_patterns`、`required_behavior`。
10. 如需確認記憶規則計畫，呼叫 `POST /api/tasks/{task_id}/memory-rule-confirm` 並提供非空白 `reviewer_signature`。

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

### P12 sealed snapshot acceptance updates

- The sealed `confirmed_snapshot.payload` is the only model-visible source for the confirmed S/C/B/K/R responsibility chain.
- The live dimension dictionaries are runtime state containers and must not be passed directly into generation prompts.
- Schema validation must accept confirmed SCBKR payloads, including per-dimension seal metadata such as `confirmed`, `snapshot_hash`, and `confirmed_snapshot`.
- P12 remains a Web MVP boundary and does not include desktop packaging, Electron, Tauri, installers, or new local database/vector/ledger runtimes.

### P13-A persistence acceptance updates

- Creating a task persists the task in `data/scbkr.sqlite3`.
- Creating a task appends `task_created` to `data/ledger/audit-log.jsonl`.
- SCBKR draft and confirm steps save the task and latest SCBKR confirmation to SQLite.
- Confirm appends `scbkr_confirmed` with `confirmed_snapshot_hash` payload metadata.
- Clearing the in-memory `TASKS` cache must not lose tasks; `GET /api/tasks/{task_id}` can restore from SQLite.
- `GET /api/tasks/{task_id}/ledger` reads task events from JSONL.
- `POST /api/ledger/rebuild-index` rebuilds SQLite `ledger_index` from JSONL without modifying JSONL.
- P13-A storage confirmation was plan-only; P13-B supersedes this with signed corpus/logic/exports physical commits.
- P13-A memory rule confirmation was plan-only; P13-B supersedes this with signed memory-rule physical writes.

## P13-A correction acceptance

- After API restart or cache loss, creating a task must generate a collision-resistant ID and must not collide with or overwrite old SQLite tasks.
- Automated tests must use an isolated runtime data directory such as `SCBKR_DATA_DIR`; they must not unlink repository-root `data/scbkr.sqlite3` or `data/ledger/audit-log.jsonl`.
- Rebuilding `ledger_index` must clear the old SQLite index first and rebuild only from JSONL, removing dirty rows that are not present in the JSONL replay ledger.

## P13-B physical storage acceptance

- Storage commit is allowed only after `review_passed`, explicit `storage_confirmed=true`, `confirmed_by="user"`, and a non-empty signature.
- A successful storage commit creates JSON files in `data/corpus`, `data/logic`, and `data/exports`, sets `physical_write_performed=true`, and records storage item indexes.
- Failed outputs must not enter `data/corpus`.
- Memory rules require `memory_rule_draft` plus signed `memory_rule_confirmed_plan`; unsigned drafts must not create `data/memory` files.
- `data/vector_db` must not be created in P13-B; ChromaDB, embeddings, and vector search remain out of scope.

## P13-C retrieval acceptance

- A `storage_committed` task with review pass and physical writes can be indexed as a success retrieval case.
- A `review_failed` task cannot be indexed as a `success_case`.
- A signed memory rule can be indexed as `signed_memory_rule`; an unsigned memory-rule draft cannot be indexed.
- Retrieval queries return candidates with `A` / `B` / `C` / `none` route semantics.
- Retrieval requires user confirmation and never auto-confirms, auto-generates, or auto-commits storage.
- ChromaDB unavailable must not crash the app; deterministic fallback retrieval remains available or the unavailable backend is reported clearly.

### P13-C retrieval fallback acceptance

- ChromaDB unavailable, corrupted, or unwritable states must not crash the app.
- Retrieval indexing must still save SQLite `retrieval_cases` when optional ChromaDB upsert fails.
- Fallback retrieval must remain usable from SQLite `retrieval_cases`.
- Retrieval output remains advisory and must keep user confirmation and P12/P13-B gates intact.
