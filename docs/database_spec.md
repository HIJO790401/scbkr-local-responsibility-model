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

P13-A intentionally does not write four-library physical stores:

- No `data/vector_db`.
- No `data/corpus`.
- No `data/logic`.
- No `data/memory`.
- No ChromaDB, embeddings, or memory physical write.
