# P11 驗收失敗記憶規則草案與簽名確認

## P11 定位

P11 建立「驗收失敗記憶規則草案與簽名確認」的純流程。它只把 `review_failed` 的來源資料、使用者判詞、規則陳述與規則 scope 整理成 `memory_rule_draft`，並在使用者簽名後整理成 `memory_rule_confirmed_plan`。

P11 不是 memory runtime，不做 physical write，不寫記憶庫，不寫 `data/memory`，不寫 SQLite，不寫 ChromaDB，不寫 ledger，不自動套用規則，也不自動重新 generate。

## P11 輸入

P11 的輸入包含：

- `task`
- `review_result`
- `user_failure_judgement`
- `rule_statement`
- `applies_to_task_types`
- `trigger_conditions`
- `forbidden_patterns`
- `required_behavior`
- optional `reviewer_signature`

`review_result` 必須是 `review_failed`，且 `review_passed = false`、`storage_confirmed = false`，並包含 `failure_report_draft`。

## P11 輸出

P11 輸出分兩階段：

1. `memory_rule_draft`
2. `memory_rule_confirmed_plan`

`memory_rule_draft` 只代表：「使用者提供的失敗判詞已被整理成規則草案，仍需簽名確認。」

`memory_rule_confirmed_plan` 只代表：「使用者已簽名確認這條規則計畫。」它仍不代表已寫入記憶庫、不代表已寫 `data/memory`、不代表已寫 SQLite、也不代表已寫 ledger。

## memory_rule_draft 欄位

`memory_rule_draft` 包含：

- `rule_id`
- `source_task_id`
- `source_trace_id`
- `source_ledger_id`
- `source_review_status = review_failed`
- `failure_summary`
- `failure_report_draft`
- `user_failure_judgement`
- `rule_statement`
- `applies_to_task_types`
- `trigger_conditions`
- `forbidden_patterns`
- `required_behavior`
- `reviewer_signature = null`
- `memory_rule_status = draft`
- `requires_user_signature = true`
- `physical_write_performed = false`
- `next_required_action = user_sign_memory_rule`

## memory_rule_confirmed_plan 欄位

`memory_rule_confirmed_plan` 保留 draft 的來源與規則欄位，並更新：

- `reviewer_signature = 使用者簽名`
- `memory_rule_status = confirmed_plan`
- `requires_user_signature = false`
- `physical_write_performed = false`
- `next_required_action = memory_runtime_pending`

## 失敗輸出不得入庫

驗收失敗不等於可入記憶。失敗輸出本身不得入庫，也不得被直接轉成規則。失敗內容只能作為後續使用者判詞與規則草案的來源證據。

## failure_report_draft 不是規則

`failure_report_draft` 只能當來源，不是規則本身。系統不得把 `failure_report_draft` 原文直接當成 `rule_statement`，也不得自行宣稱它已成為記憶規則。

## 使用者判詞必要性

失敗原因是否成立，必須由使用者判詞確認。沒有 `user_failure_judgement`，不得建立 `memory_rule_draft`。系統不得自行判定失敗原因成立，模型也不得自行判定失敗原因成立。

## 使用者簽名必要性

沒有使用者簽名，不得建立 `memory_rule_confirmed_plan`。`reviewer_signature` 必須是非空白字串。

## 不得 physical write

P11 不得 physical write。`physical_write_performed` 必須保持 `false`。P11 不寫 `data/memory`、不寫 SQLite、不寫 ChromaDB、不寫 ledger、不寫四庫。

## 不得 memory_rule_stored

P11 不得產生 `memory_rule_stored`，不得宣稱已寫入記憶庫，也不得宣稱規則已被正式套用。

## 後續 memory runtime pending

`memory_rule_confirmed_plan` 的 `next_required_action` 必須是 `memory_runtime_pending`。實體 memory runtime 尚未實作，後續階段仍需另行確認與施工。
