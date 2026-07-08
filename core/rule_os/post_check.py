"""Post-answer checks for local SCBKR rule packages."""

from __future__ import annotations

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
        "not claim it was published",
        "not published",
        "not sent",
        "not paid",
        "not signed",
        "not stored",
    ):
        cleaned = cleaned.replace(token, "")
    return cleaned


def check_model_answer_against_rule_package(answer: str, package: dict[str, Any] | None) -> dict[str, Any]:
    package = package or {}
    text = str(answer or "")
    execution_claim_text = _without_negated_execution_claims(text)
    violations: list[dict[str, str]] = []
    if _contains_any(
        execution_claim_text,
        ["已發布", "已上架", "已寄出", "已付款", "已刪除", "已簽名", "已入庫", "已啟用", "storage committed", "published", "sent", "paid", "signed", "stored"],
    ):
        violations.append({"code": "overreach_execution_claim", "message": "回答宣稱已執行高風險、簽名、入庫或外部動作。"})
    if package.get("draft_only") and _contains_any(text, ["正式結果", "正式規則", "已啟用", "已成立", "closed", "正式引用"]):
        violations.append({"code": "draft_claimed_as_formal", "message": "草稿狀態被說成正式結果。"})
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
        high = {"overreach_execution_claim", "retrieval_used_as_formal_basis"}
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

