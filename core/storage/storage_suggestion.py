"""P15-C deterministic review-to-storage suggestion helpers.

Builds advisory suggestions only; never writes physical storage.
"""

from __future__ import annotations

from typing import Any

UI_TARGETS = ("vector", "corpus", "logic", "memory")
PLAN_TARGET_ALIASES = {"vector": "vector", "corpus": "corpus", "logic": "logic", "memory": "memory"}


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
            "planned_summary": "寫入已驗收任務案例、責任鏈摘要與生成結果索引。",
        },
        "corpus": {
            "recommended": bool(has_docs),
            "reason": "本次任務包含外部文件、網頁或原始資料，可作為後續生成依據。" if has_docs else "本次任務未提供外部文件或原始資料，因此不建議寫入語料庫。",
            "planned_summary": "寫入使用者提供或整理後的文本資料。" if has_docs else "",
        },
        "logic": {
            "recommended": True if is_logic else False,
            "reason": "本次任務包含流程、權限、驗收與入庫邏輯，可作為後續任務的可重用流程模板。" if is_logic else "本次任務未明確產生可重用工程流程或規則，因此不優先寫入程式邏輯庫。",
            "planned_summary": "寫入流程、API、UI 狀態機、測試與錯誤處理規則。" if is_logic else "",
        },
        "memory": {
            "recommended": bool(has_long_term),
            "reason": "本次任務包含長期偏好、禁止規則或未來任務需要提醒的基準，可由使用者選擇寫入記憶庫。" if has_long_term else "本次任務未產生新的長期偏好或驗收失敗判定規則，因此不建議寫入記憶庫。",
            "planned_summary": "寫入使用者確認的長期規則或禁止行為。" if has_long_term else "",
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
