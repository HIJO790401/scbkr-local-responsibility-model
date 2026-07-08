"""Post-answer SCBKR rule package checks."""

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
        "不宣稱已上架",
        "不得宣稱已上架",
        "不會宣稱已上架",
        "不宣稱已寄出",
        "不得宣稱已寄出",
        "不會宣稱已寄出",
        "not claim it was published",
        "not published",
        "not emailed",
        "not listed",
        "not stored",
    ):
        cleaned = cleaned.replace(token, "")
    return cleaned


def check_model_answer_against_rule_package(answer: str, package: dict[str, Any] | None) -> dict[str, Any]:
    package = package or {}
    text = str(answer or "")
    execution_claim_text = _without_negated_execution_claims(text)
    violations: list[dict[str, str]] = []
    if _contains_any(execution_claim_text, ["已發布", "已上架", "已寄出", "已付款", "已刪除", "已入庫", "storage committed", "published"]):
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
    if package.get("task_type") == "product_launch_marketing_copy":
        if _contains_any(text, ["nt$", "$", "元", "折", "買一送一", "限時", "launches on", "available now", "in stock"]) and not package.get("citable_data"):
            violations.append({"code": "invented_launch_commercial_data", "message": "沒有正式資料卻輸出價格、優惠、上市日期或庫存資訊。"})
        if _contains_any(execution_claim_text, ["已發布", "已上架", "已寄出", "published", "sent", "listed"]):
            violations.append({"code": "launch_overreach_execution_claim", "message": "新品上市回答宣稱已發布、已寄出或已上架。"})
        if _contains_any(text, ["保證熱賣", "銷量翻倍", "guaranteed sales", "sold out guaranteed"]):
            violations.append({"code": "launch_unverified_performance_claim", "message": "新品上市回答疑似編造成效保證。"})
    if package.get("task_type") == "debt_civil_case_draft":
        required_review_guard = [
            "不是法律意見",
            "不得視為正式法律意見",
            "不得作為正式法律意見",
            "不構成法律意見",
            "not legal advice",
            "not a filed document",
            "not submitted",
            "owner review",
            "使用者確認",
            "待確認",
            "簽名",
        ]
        if not _contains_any(text, required_review_guard):
            violations.append({"code": "debt_missing_review_guard", "message": "債務民事草稿缺少使用者確認、非法律意見或不得送件的邊界提示。"})
        if _contains_any(text, ["已提交法院", "已送件", "已寄出存證", "已聯絡對造", "filed with court", "sent to the counterparty"]):
            violations.append({"code": "debt_overreach_execution_claim", "message": "債務民事草稿宣稱已送件、寄出或聯絡對造。"})
        if _contains_any(text, ["2023年", "2024年", "2025年", "2026年", "court case no.", "法院案號"]) and not _contains_any(text, ["待確認", "請確認", "placeholder", "example only"]):
            violations.append({"code": "debt_unconfirmed_dates_or_case_data", "message": "債務民事草稿疑似輸出未確認日期、案號或案件資料。"})
    if package.get("needs_clarification") and not _contains_any(text, ["請確認", "待確認", "需要你提供", "請補", "please confirm", "need"]):
        violations.append({"code": "missed_required_clarification", "message": "缺少資訊時沒有追問或標示待確認。"})
    if package.get("non_citable_data") and _contains_any(text, ["根據檢索庫", "向量庫顯示", "vector says"]):
        violations.append({"code": "retrieval_used_as_formal_basis", "message": "檢索庫候選被當正式依據。"})
    action = "allow"
    if violations:
        high = {"overreach_execution_claim", "retrieval_used_as_formal_basis", "debt_overreach_execution_claim"}
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
