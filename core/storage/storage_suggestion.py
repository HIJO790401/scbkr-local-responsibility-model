"""P15-C deterministic review-to-storage suggestion helpers.

Builds advisory suggestions only; never writes physical storage.
"""

from __future__ import annotations

from typing import Any

UI_TARGETS = ("vector", "corpus", "logic", "memory")
PLAN_TARGET_ALIASES = {"vector": "vector", "corpus": "corpus", "logic": "logic", "memory": "memory"}
STORE_PURPOSES = {
    "vector": "檢索庫只保存相似案例索引與召回文字，用來找相似任務；不得單獨當正式判準。",
    "corpus": "資料庫保存使用者確認的正式資料、原文素材、生成成品或可引用文本。",
    "logic": "規則庫保存規則、流程、邊界、成立/失效條件、驗收與責任判準。",
    "memory": "記憶庫保存使用者簽名後要長期影響未來任務的偏好、禁止事項與固定提醒。",
}


def to_plan_target(target: str) -> str:
    if target not in PLAN_TARGET_ALIASES:
        raise ValueError("寫入目標只能是 vector / corpus / logic / memory。")
    return PLAN_TARGET_ALIASES[target]


def to_ui_target(target: str) -> str:
    # Read compatibility for records written before the 2.0 canonical target migration.
    return "vector" if target == "vector_db" else target


def validate_ui_targets(targets: Any) -> list[str]:
    if not isinstance(targets, list):
        raise ValueError("selected_targets 必須是陣列。")
    normalized: list[str] = []
    for target in targets:
        ui = to_ui_target(str(target))
        if ui not in UI_TARGETS:
            raise ValueError("寫入目標只能是 vector / corpus / logic / memory。")
        if ui not in normalized:
            normalized.append(ui)
    return normalized


def deterministic_storage_suggestion(task: dict[str, Any], user_preference: str | None = None) -> dict[str, Any]:
    raw = " ".join(str(task.get(k, "")) for k in ("raw_input", "task_name", "task_type"))
    scbkr = str(task.get("scbkr", {}))
    generation = str(task.get("generation_result", {}))
    text = f"{raw} {scbkr} {generation}".lower()
    has_docs = any(token in text for token in ("pdf", "docx", "markdown", "網頁", "文件", "報告", "文章", "url", "http", "資料來源", "外部資料"))
    has_long_term = any(token in text for token in ("長期偏好", "固定規則", "禁止", "不得", "未來任務", "記憶規則", "驗收失敗", "以後", "判準"))
    is_logic = any(token in text for token in ("api", "ui", "workflow", "流程", "測試", "權限", "規則", "程式", "邏輯", "scbkr", "邊界", "後果", "查證", "條件"))
    suggestions = {
        "vector": {
            "recommended": True,
            "reason": "本次任務已完成 SCBKR 確認與驗收，具備可重用責任鏈，可供未來相似任務檢索。",
            "planned_summary": "寫入相似案例索引、任務摘要、核心邏輯與停止條件；只作檢索候選，不作正式判準。",
            "store_role": "retrieval_index",
            "store_purpose": STORE_PURPOSES["vector"],
            "model_write_logic": "模型只能把任務摘要與可召回片段放進向量索引；引用時必須再回查 corpus/logic/memory 正式資料。",
        },
        "corpus": {
            "recommended": bool(has_docs),
            "reason": "本次任務包含外部文件、網頁或原始資料，可作為後續生成依據。" if has_docs else "本次任務未提供外部文件或原始資料，因此不建議寫入資料庫。",
            "planned_summary": "寫入使用者提供或驗收後的原文文本、生成成品與素材內容。" if has_docs else "",
            "store_role": "source_material",
            "store_purpose": STORE_PURPOSES["corpus"],
            "model_write_logic": "模型只能把已驗收正式資料、原文或成品放入資料庫；不得把推論規則塞進資料庫冒充原文。",
        },
        "logic": {
            "recommended": True if is_logic else False,
            "reason": "本次任務包含流程、權限、驗收與入庫邏輯，可作為後續任務的可重用流程模板。" if is_logic else "本次任務未明確產生可重用工程流程或規則，因此不優先寫入規則庫。",
            "planned_summary": "寫入 SCBKR 規則、流程、邊界、成立條件、失效條件、驗收與責任判準。" if is_logic else "",
            "store_role": "rule_logic",
            "store_purpose": STORE_PURPOSES["logic"],
            "model_write_logic": "模型若產生規則/流程/判準，只能建議寫入規則庫；正式入庫需使用者簽名與驗收。",
        },
        "memory": {
            "recommended": bool(has_long_term),
            "reason": "本次任務包含長期偏好、禁止規則或未來任務需要提醒的基準，可由使用者選擇寫入記憶庫。" if has_long_term else "本次任務未產生新的長期偏好或驗收失敗判定規則，因此不建議寫入記憶庫。",
            "planned_summary": "寫入使用者確認的長期偏好、固定規則、禁止行為與未來提醒。" if has_long_term else "",
            "store_role": "long_term_user_memory",
            "store_purpose": STORE_PURPOSES["memory"],
            "model_write_logic": "模型只能建議長期記憶候選；沒有使用者簽名不得影響未來任務。",
        },
    }
    recommended_targets = [target for target, item in suggestions.items() if item["recommended"]]
    return {
        "task_id": task.get("task_id"),
        "review_passed": True,
        "suggestions": suggestions,
        "recommended_targets": recommended_targets,
        "model_assisted": False,
        "fallback_used": True,
        "user_preference": user_preference or "",
        "next_required_action": "user_select_storage_targets",
    }
