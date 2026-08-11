# Token / Cost Audit Report

Edition: SCBKR FREE
Status: VERIFIED for this bounded benchmark only

## Method

- Provider: LM Studio
- Model: `qwen2.5-3b-instruct`
- Variant A: bounded full history and full rule context
- Variant B: minimal `current_rule_package`
- Calls: one real model call per variant
- Measurement: provider-reported prompt, completion, and total usage
- Formal authority: signed active LOGIC, reviewed CORPUS, and owner-signed MEMORY
- Recall only: VECTOR
- Chat history as formal authority: no

## Result

| Metric | A full context | B rule package | Saved |
| --- | ---: | ---: | ---: |
| Prompt tokens | 5,658 | 1,723 | 3,935 (69.55%) |
| Completion tokens | 51 | 57 | -6 |
| Total tokens | 5,709 | 1,780 | 3,929 (68.82%) |

This is one reproducible model-and-task measurement, not a universal savings
guarantee. SCBKR displays `VERIFIED` only when the same provider and exact model
complete both real calls and return usage data. Otherwise, the interface labels
the result as an estimate or as not yet measured.

Machine-readable evidence, timestamps, latency, and prompt hashes are stored in
[`token_ab_verified_free.json`](token_ab_verified_free.json).
