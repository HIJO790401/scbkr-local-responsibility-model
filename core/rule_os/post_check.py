"""Post-answer SCBKR rule package checks."""

from __future__ import annotations

from typing import Any


def _contains_any(text: str, tokens: list[str]) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in tokens)


def check_model_answer_against_rule_package(answer: str, package: dict[str, Any] | None) -> dict[str, Any]:
    package = package or {}
    text = str(answer or "")
    violations: list[dict[str, str]] = []
    if _contains_any(text, ["已發布", "已上架", "已寄出", "已付款", "已刪除", "已入庫", "storage committed", "published"]):
        violations.append({"code": "overreach_execution_claim", "message": "回答宣稱已執行高風險或入庫動作。"})
    if package.get("draft_only") and _contains_any(text, ["正式結果", "正式規則", "已啟用", "已成立", "closed", "正式引用"]):
        violations.append({"code": "draft_claimed_as_formal", "message": "草稿狀態被說成正式結果。"})
    if package.get("task_type") == "beauty_salon_marketing_copy":
        claim_text = text
        for negated in ("不保證", "不得保證", "不會保證", "不誇大療效", "不得誇大療效", "不暗示醫療效果", "不得暗示醫療效果"):
            claim_text = claim_text.replace(negated, "")
        if _contains_any(claim_text, ["保證", "根治", "治療", "醫療級", "永久", "100%", "百分百"]):
            violations.append({"code": "beauty_medical_or_guarantee_claim", "message": "美容文案疑似誇大療效或保證結果。"})
        if _contains_any(text, ["nt$", "$", "元", "折", "買一送一", "限時"]) and not package.get("citable_data"):
            violations.append({"code": "invented_commercial_data", "message": "沒有正式資料卻輸出價格、優惠或活動資訊。"})
    if package.get("needs_clarification") and not _contains_any(text, ["請確認", "待確認", "需要你提供", "請補", "please confirm", "need"]):
        violations.append({"code": "missed_required_clarification", "message": "缺少資訊時沒有追問或標示待確認。"})
    if package.get("non_citable_data") and _contains_any(text, ["根據檢索庫", "向量庫顯示", "vector says"]):
        violations.append({"code": "retrieval_used_as_formal_basis", "message": "檢索庫候選被當正式依據。"})
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
        return (
            "This answer was downgraded to a review draft because the rule check found: "
            + "; ".join(messages)
            + "\n\nDraft only:\n"
            + str(answer or "")
        )
    return "這段回答已降級為待確認草稿，因為規則檢查發現：" + "；".join(messages) + "\n\n草稿內容：\n" + str(answer or "")
