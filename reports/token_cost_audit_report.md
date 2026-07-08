# Token / Cost Audit Report

## Test Input
- Rule creation: 以後凡是朋友要求我先墊錢，我要先判斷這是不是風險轉嫁，把這個寫成我的本地規則。
- Follow-up: 朋友說月底還我，要我今天先墊三萬，可以嗎？

## Used Rules
- 以後凡是朋友要求我先墊錢，我要先判斷這是不是風險轉嫁，寫成我的本地規則規則草稿: active

## Token Estimate
- Full Context: 107394 tokens (214788 chars)
- Rule Package: 2257 tokens (4514 chars)
- Compression Ratio: 0.021016
- Compression: 97.9%
- Threshold: 98.06%
- Status: NEEDS_OPTIMIZATION

## Formal Basis
- Formal basis: signed_active_four_store_rules_only
- Chat context used as formal basis: No
- Matched LOGIC rules: 2
- Citable CORPUS data: 2
- MEMORY preferences: 1
- VECTOR candidates: 0
- VECTOR recall only: Yes

## Excluded
- raw_chat_history
- unreviewed_drafts
- unsigned_rules
- archived_or_superseded_rules
- vector_records_as_formal_basis
- full_memory_dump

## Retained
- signed_active_logic_rules
- reviewed_active_corpus_items
- owner_signed_memory_preferences
- vector_retrieval_candidates_recall_only
- rule_boundaries_and_post_check_policy

## Why Four Stores Replace Long Context
Signed Active LOGIC, reviewed CORPUS, and owner-signed MEMORY records carry formal authority. VECTOR is retained only as recall metadata, so the model receives a minimal rule package instead of a full chat transcript or full memory dump.

## Context Pollution
No unnecessary chat context was used as formal basis.
