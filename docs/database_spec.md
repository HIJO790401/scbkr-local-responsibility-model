# Database Spec

狀態：P2 ledger boundary

## P2 ledger 邊界

SCBKR ledger 是回放帳本，不是資料庫。

- 真正原始帳本是 append-only JSONL。
- SQLite `ledger_index` 之後只是索引，用於輔助查詢原始 JSONL 帳本。
- P2 不建立 SQLite table。
- P2 不做 migration。
- P2 不寫正式資料庫。
- P2 不寫入正式 `data/ledger/audit-log.jsonl`。

P2 只建立 ledger event schema、event constants、hash helper、append-only JSONL helper，以及使用 temporary directory 的單元測試。

## P8 storage plan 邊界

P8 不建立 SQLite tables。
P8 不執行 migration。
P8 不寫 `data/scbkr.sqlite3`。
P8 不寫 ChromaDB。
P8 不寫 `data/vector_db`。
P8 只建立 storage plan。
實體 storage runtime 尚未實作。

## P9 retrieval route 邊界

P9 不建立 ChromaDB collection。
P9 不初始化 ChromaDB。
P9 不寫 `data/vector_db`。
P9 不建立 embedding。
P9 不寫 SQLite。
P9 不建立 SQLite table。
P9 只建立 responsibility-chain retrieval route structure。
實體 ChromaDB runtime 與 embedding runtime 尚未實作。

## P10 permission lock 邊界

P10 不建立 SQLite tables。
P10 不執行 migration。
P10 不寫 `data/scbkr.sqlite3`。
P10 不初始化 ChromaDB。
P10 不寫 `data/vector_db`。
P10 不寫 ledger。
P10 只建立 permission settings schema 與 pure permission checker。
SQLite / ChromaDB runtime 仍未實作。

## P13-A SQLite + JSONL persistence runtime

P13-A adds a minimal local persistence runtime:

- SQLite path: `data/scbkr.sqlite3`.
- JSONL ledger path: `data/ledger/audit-log.jsonl`.
- JSONL is the original append-only replay ledger.
- SQLite stores mutable task state and query indexes; it is not the immutable source of truth.
- `ledger_index` can be rebuilt from JSONL by `POST /api/ledger/rebuild-index`.

SQLite tables:

- `tasks`: current task state and full `task_json` snapshot.
- `scbkr_confirmations`: latest SCBKR confirmation JSON and `confirmed_snapshot_hash`.
- `ledger_index`: event metadata, JSONL line number, and payload hash for lookup.
- `system_events`: minimal system event table reserved for local runtime notes.

P13-A intentionally did not write four-library physical stores before the P13-B physical storage layer:

- No `data/vector_db`.
- No `data/corpus`.
- No `data/logic`.
- No `data/memory`.
- No ChromaDB, embeddings, or memory physical write.

## P13-A safety boundaries

- JSONL is the only replay source for ledger recovery. The SQLite `ledger_index` table is a rebuildable index, not the authoritative ledger.
- `ledger_index` may be cleared and rebuilt from JSONL; rebuild must not rewrite, truncate, delete, or otherwise mutate the JSONL ledger file.
- SQLite task upsert remains valid for saving mutable task snapshots, but new task creation must use collision-resistant task IDs so an API restart cannot overwrite an existing persisted task through ID collision.
- `SCBKR_DATA_DIR` can redirect runtime data for tests or local isolation. When it is unset, runtime data continues to default to the repository `data/` directory.

## P13-B physical storage and indexes

- `storage_items` indexes physical JSON writes with `item_id`, `task_id`, `target`, `relative_path`, `content_hash`, `source_event_id`, `physical_write_performed`, `created_at`, and sanitized `item_json`.
- `memory_rules` indexes signed memory-rule JSON writes with `rule_id`, `task_id`, `rule_hash`, `relative_path`, `reviewer_signature`, `scope`, `created_at`, and sanitized `rule_json`.
- Physical store JSON files live under `data/corpus`, `data/logic`, `data/exports`, and `data/memory`; each filename includes the task ID and the first 12 characters of the content hash.
- `data/corpus` stores only review-passed generation payloads; `data/logic` stores sealed SCBKR responsibility logic and review/storage context; `data/exports` stores sanitized replay bundles; `data/memory` stores only signed `memory_rule_confirmed_plan` rules.
- JSONL remains the workflow replay ledger and records physical-write request/completion/failure events. SQLite remains an index for tasks, ledger rows, storage items, and memory rules; the JSON physical files are the content store.

## P13-C retrieval indexes and optional vector backend

P13-C adds two SQLite index tables while keeping JSONL as the workflow replay ledger:

- `retrieval_cases`: indexes committed success cases and signed memory-rule retrieval cases with `case_id`, `task_id`, `case_type`, `source_target`, `relative_path`, `content_hash`, `retrieval_text_hash`, `embedding_status`, `backend`, `created_at`, and sanitized `case_json`.
- `retrieval_queries`: stores advisory query results with `query_id`, `task_id`, `query_text_hash`, `backend`, `route`, `top_k`, `created_at`, and sanitized `result_json`.

`data/vector_db` is reserved for the optional local ChromaDB backend and is created lazily only by retrieval indexing/vector runtime when ChromaDB is actually used. ChromaDB is optional, local-only, and must not call cloud services or external embedding APIs. When ChromaDB is unavailable, SQLite retrieval cases plus deterministic JSON/Python similarity provide fallback retrieval.

JSONL remains the main append-only process ledger. P13-C appends retrieval request/completion/failure and fallback events, while SQLite remains an index/result cache for `retrieval_cases` and `retrieval_queries`.

### P13-C optional vector store and fallback source

`vector_db` / ChromaDB is an optional local acceleration store, not the source of truth for retrieval. SQLite `retrieval_cases` is the fallback query source and must remain usable when ChromaDB is unavailable, corrupted, or unwritable. JSONL ledger events record optional backend unavailability and fallback use with `retrieval_backend_unavailable` and `retrieval_fallback_used`, while completed indexing still records `retrieval_case_index_completed` when SQLite cases are saved.
