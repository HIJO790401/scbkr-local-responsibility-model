"""Backend labels for SCBKR local rule OS responses."""

from __future__ import annotations

from typing import Any

try:
    from opencc import OpenCC
except ImportError:  # Optional in source-only and constrained offline runtimes.
    OpenCC = None  # type: ignore[assignment]


_ZH_TW_CONVERTER = OpenCC("s2twp") if OpenCC is not None else None

TEXT: dict[str, dict[str, Any]] = {
    "zh-TW": {
        "modes": {
            "general_chat": "一般聊天",
            "generate_rule": "生成規則",
            "answer_with_rules": "引用規則回答",
            "modify_existing_rule": "修改既有規則",
            "confirm_storage": "確認入庫",
            "query_four_stores": "查詢四庫",
            "tool_execution": "工具執行",
            "high_risk_action": "高風險動作",
        },
        "stores": {"logic": "規則庫", "corpus": "資料庫", "memory": "記憶庫", "vector": "檢索庫"},
        "dimensions": {"S": "主體與情境", "C": "因果與判斷順序", "B": "邊界、禁止與停止", "K": "依據與可引用來源", "R": "責任、驗收與簽名"},
        "dimension_descriptions": {
            "S": "誰、什麼事、何時適用",
            "C": "為什麼成立、先判什麼再判什麼",
            "B": "不能做什麼、何時必須停止",
            "K": "憑什麼判、哪些來源可以或不可以引用",
            "R": "誰承擔、怎樣驗收、誰能簽名、錯了怎麼修",
        },
        "plans": {"FREE": "免費版"},
        "statuses": {"draft": "草稿", "owner_signed": "使用者已簽名", "active": "已啟用", "disabled": "已停用", "archived": "已封存", "superseded": "已被新版取代", "deleted": "已刪除（保留回放）", "storage_conflict": "來源規則已更新，入庫已停止"},
        "signature_prompt": "請逐欄確認後由使用者簽名，模型不能代簽。",
        "storage_prompt": "入庫前必須二次確認；檢索庫只作候選召回。",
        "state_conflict_prompt": "來源狀態已變更，未寫入四庫；請重新載入最新版、檢查差異並再次簽名。",
        "applied_rule": "已套用你的本地規則。",
    },
    "en": {
        "modes": {
            "general_chat": "General chat",
            "generate_rule": "Generate rule",
            "answer_with_rules": "Answer with rules",
            "modify_existing_rule": "Modify existing rule",
            "confirm_storage": "Confirm storage",
            "query_four_stores": "Query four stores",
            "tool_execution": "Tool execution",
            "high_risk_action": "High-risk action",
        },
        "stores": {"logic": "Rule store", "corpus": "Data store", "memory": "Memory store", "vector": "Retrieval store"},
        "dimensions": {"S": "Subject and Situation", "C": "Causality and Decision Order", "B": "Boundaries, Prohibitions, and Stops", "K": "Basis and Citable Sources", "R": "Responsibility, Review, and Signature"},
        "dimension_descriptions": {
            "S": "Who, what, and when the rule applies",
            "C": "Why it applies and the order of decisions",
            "B": "What is forbidden and when processing must stop",
            "K": "What supports the decision and which sources may be cited",
            "R": "Who is accountable, how it is accepted, who signs, and how failure is repaired",
        },
        "plans": {"FREE": "Free"},
        "statuses": {"draft": "Draft", "owner_signed": "Owner signed", "active": "Active", "disabled": "Disabled", "archived": "Archived", "superseded": "Superseded", "deleted": "Deleted (replay retained)", "storage_conflict": "Source rule changed; storage stopped"},
        "signature_prompt": "The user must review and sign each field. The model cannot sign.",
        "storage_prompt": "Storage requires second confirmation. Retrieval store is discovery-only.",
        "state_conflict_prompt": "The source state changed. Nothing was written; reload the latest version, review the difference, and sign again.",
        "applied_rule": "Your local rule has been applied.",
    },
}


def rule_os_text(locale: str | None = None) -> dict[str, Any]:
    return TEXT["en"] if str(locale or "").lower().startswith("en") else TEXT["zh-TW"]


def normalize_locale_text(text: str, locale: str | None = None) -> str:
    """Normalize model-facing text for display without changing rule semantics."""
    value = str(text or "")
    if _ZH_TW_CONVERTER is not None and str(locale or "").lower() in {"zh-tw", "zh_tw", "tw", "traditional_chinese"}:
        return _ZH_TW_CONVERTER.convert(value)
    return value
