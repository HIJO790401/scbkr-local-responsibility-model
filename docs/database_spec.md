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
