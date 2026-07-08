"""Backend labels for SCBKR local rule OS responses."""

from __future__ import annotations

from typing import Any

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
        "dimensions": {"S": "主體", "C": "因果", "B": "邊界", "K": "依據", "R": "責任"},
        "plans": {"FREE": "免費版", "NT690": "NT$690 責任鏈結構輔助", "NT3300": "NT$3,300 規則書閉環"},
        "statuses": {"draft": "草稿", "owner_signed": "使用者已簽名", "active": "已啟用"},
        "signature_prompt": "請逐欄確認後由使用者簽名，模型不能代簽。",
        "storage_prompt": "入庫前必須二次確認；檢索庫只作候選召回。",
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
        "dimensions": {"S": "Subject", "C": "Causality", "B": "Boundary", "K": "Key/Basis", "R": "Responsibility"},
        "plans": {"FREE": "Free", "NT690": "NT$690 responsibility-chain assist", "NT3300": "NT$3,300 rulebook closure"},
        "statuses": {"draft": "Draft", "owner_signed": "Owner signed", "active": "Active"},
        "signature_prompt": "The user must review and sign each field. The model cannot sign.",
        "storage_prompt": "Storage requires second confirmation. Retrieval store is discovery-only.",
        "applied_rule": "Your local rule has been applied.",
    },
}


def rule_os_text(locale: str | None = None) -> dict[str, Any]:
    return TEXT["en"] if str(locale or "").lower().startswith("en") else TEXT["zh-TW"]
