"""Post-answer checks for local SCBKR rule packages."""

from __future__ import annotations

import re
from typing import Any


def _contains_any(text: str, tokens: list[str]) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in tokens)


def _without_negated_execution_claims(text: str) -> str:
    cleaned = str(text or "")
    for token in (
        "不宣稱已發布",
        "不得宣稱已發布",
        "不會宣稱已發布",
        "不宣稱已寄出",
        "不得宣稱已寄出",
        "不宣稱已付款",
        "不得宣稱已付款",
        "不宣稱已簽名",
        "不得宣稱已簽名",
        "不宣稱已入庫",
        "不得宣稱已入庫",
        "目前沒有已簽名",
        "沒有命中已簽名",
        "尚無已簽名",
        "沒有已簽名",
        "未簽名",
        "尚未簽名",
        "尚未入庫",
        "沒有已入庫",
        "not claim it was published",
        "no signed rule",
        "no signed citation",
        "unsigned",
        "not published",
        "not sent",
        "not paid",
        "not signed",
        "not stored",
    ):
        cleaned = cleaned.replace(token, "")
    return cleaned


def _claims_model_authority(text: str) -> bool:
    """Detect the model claiming owner-only authority, not a stored rule state."""

    patterns = (
        r"(?:我|模型|這個模型|本模型|AI|助理)\s*(?:已經|已|剛剛)?\s*(?:替|為|幫)?\s*(?:你|您)?\s*(?:完成)?\s*(?:簽名|入庫|啟用)",
        r"(?:已替|已為|已幫)\s*(?:你|您)\s*(?:完成)?\s*(?:簽名|入庫|啟用)",
        r"\b(?:i|the model|this model|the assistant)\s+(?:have\s+|has\s+)?(?:completed\s+)?(?:the\s+)?(?:signature|storage|activation|signed|stored|activated)\b",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _claims_external_execution(text: str) -> bool:
    cleaned = _without_negated_execution_claims(text)
    if _contains_any(cleaned, ["已發布", "已上架", "已寄出", "已付款", "已刪除", "storage committed"]):
        return True
    return bool(
        re.search(
            r"\b(?:i|we|the model|this model|the assistant|scbkr)\s+(?:have\s+|has\s+)?(?:published|listed|sent|paid|deleted)\b",
            cleaned,
            flags=re.IGNORECASE,
        )
    )


def _claims_external_rule_override(text: str) -> bool:
    patterns = (
        r"(?:外部|普遍|通用|一般)(?:的)?(?:定律|規則|原則).{0,12}(?:優先於|高於|凌駕|取代|覆蓋|蓋過)(?:你的|使用者|本地|已簽名)?(?:的)?(?:規則|框架)?",
        r"(?:universal|general|external)\s+(?:law|rule|principle)s?.{0,24}(?:override|supersede|replace|take precedence over)\s+(?:your|the user's|local|owner-signed)",
    )
    negations = ["不能", "不得", "不可", "不應", "不會", "cannot", "must not", "may not", "does not", "do not"]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if not _contains_any(match.group(0), negations):
                return True
    return False


def check_model_answer_against_rule_package(answer: str, package: dict[str, Any] | None) -> dict[str, Any]:
    package = package or {}
    text = str(answer or "")
    violations: list[dict[str, str]] = []
    if _claims_model_authority(text) or _claims_external_execution(text):
        violations.append({"code": "overreach_execution_claim", "message": "回答宣稱已執行高風險、簽名、入庫或外部動作。"})
    if package.get("draft_only") and _contains_any(text, ["正式結果", "正式規則", "已啟用", "已成立", "closed", "正式引用"]):
        violations.append({"code": "draft_claimed_as_formal", "message": "草稿狀態被說成正式結果。"})
    if package.get("matched_rules") and _contains_any(
        text,
        [
            "目前尚無任何規則生效",
            "沒有規則生效",
            "尚無規則生效",
            "沒有已簽名規則",
            "沒有命中已簽名",
            "未命中規則",
            "no rule is active",
            "no active rule",
            "no signed rule matched",
            "did not match a signed rule",
        ],
    ):
        violations.append({"code": "active_rule_denied", "message": "回答否認本次已命中的簽名規則，與 current_rule_package 矛盾。"})
    if (
        package.get("matched_rules")
        and package.get("external_generalizations_override_active_rule_state") is False
        and _claims_external_rule_override(text)
    ):
        violations.append({"code": "external_rule_overrode_owner_rule", "message": "回答讓外部普遍說法凌駕已命中的使用者簽名規則。"})
    if not package.get("matched_rules") and _contains_any(
        text,
        ["已套用你的規則", "已套用本地規則", "依已簽名規則", "applied your signed rule", "using your signed rule"],
    ):
        violations.append({"code": "unmatched_rule_claimed_active", "message": "沒有命中簽名規則，回答卻宣稱已套用。"})
    if package.get("needs_clarification") and not _contains_any(text, ["請確認", "待確認", "需要你提供", "請補", "please confirm", "need", "pending"]):
        violations.append({"code": "missed_required_clarification", "message": "缺少資訊時沒有追問或標示待確認。"})
    if package.get("non_citable_data") and _contains_any(text, ["根據檢索庫", "向量庫顯示", "vector says", "according to vector"]):
        violations.append({"code": "retrieval_used_as_formal_basis", "message": "檢索庫候選被當正式依據。"})
    if _contains_any(text, ["保證收益", "保證療效", "保證成功", "guaranteed return", "guaranteed result"]) and not package.get("citable_data"):
        violations.append({"code": "unverified_guarantee_claim", "message": "沒有正式資料卻輸出保證性宣稱。"})
    if _contains_any(text, ["nt$", "$", "元", "折扣", "優惠", "期限", "amount", "deadline"]) and package.get("draft_only") and not package.get("citable_data"):
        violations.append({"code": "unverified_specific_fact", "message": "草稿狀態輸出未確認的具體金額、期限或優惠。"})
    action = "allow"
    if violations:
        high = {
            "overreach_execution_claim",
            "retrieval_used_as_formal_basis",
            "active_rule_denied",
            "unmatched_rule_claimed_active",
            "external_rule_overrode_owner_rule",
        }
        action = "block" if any(v["code"] in high for v in violations) else "downgrade_to_draft"
    return {
        "checked": True,
        "allowed": not violations,
        "violations": violations,
        "action": action,
        "rule_package_source": package.get("source"),
        "chat_context_used": bool(package.get("chat_context_used")),
    }


def downgrade_answer_to_draft(answer: str, check: dict[str, Any], locale: str = "zh-TW") -> str:
    if check.get("allowed") is True:
        return answer
    messages = [str(item.get("message") or item.get("code")) for item in check.get("violations", [])]
    if str(locale or "").lower().startswith("en"):
        return "This answer was downgraded to a review draft because the rule check found: " + "; ".join(messages) + "\n\nDraft only:\n" + str(answer or "")
    return "這段回答已降級為待確認草稿，因為規則檢查發現：" + "；".join(messages) + "\n\n草稿內容：\n" + str(answer or "")
