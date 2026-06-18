"""Pure P8 storage target constants and validation helpers."""

STORAGE_TARGETS = ("vector_db", "corpus", "logic", "memory")
MEMORY_REQUIRES_SIGNATURE = True
TARGET_DESCRIPTIONS = {
    "vector_db": "保存已驗收通過的任務案例與 SCBKR 責任鏈摘要，不保存失敗輸出。",
    "corpus": "保存材料來源，不代表判定成立。",
    "logic": "保存可重用流程、工程邏輯、測試規則、API 流程。",
    "memory": "保存使用者確認過的偏好、判定規則、禁用規則、驗收標準；必須使用者簽名。",
}


def validate_storage_target(target):
    """Validate one storage target."""
    if target not in STORAGE_TARGETS:
        raise ValueError("storage target must be one of: vector_db, corpus, logic, memory")
    return True


def validate_storage_targets(targets):
    """Validate a list of storage targets."""
    if not isinstance(targets, list):
        raise ValueError("storage targets must be a list")
    for target in targets:
        validate_storage_target(target)
    return True
