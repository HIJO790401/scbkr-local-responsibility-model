"""Build the minimal current rule package before model answers."""

from __future__ import annotations

import json
from typing import Any

AUTHORITATIVE_STORES = {"logic", "corpus", "memory"}
PACKAGE_LIMITS = {
    "matched_rules": 3,
    "citable_data": 3,
    "user_preferences": 3,
    "retrieval_candidates": 3,
    "non_citable_data": 5,
}


def _locale_is_en(locale: str | None) -> bool:
    return str(locale or "").lower().startswith("en")


def _excerpt(item: dict[str, Any]) -> str:
    return str(item.get("excerpt") or item.get("rule") or item.get("summary") or item.get("content") or "")[:700]


def _source_id(item: dict[str, Any]) -> str:
    return str(item.get("citation_id") or item.get("storage_item_id") or item.get("source_id") or item.get("case_id") or "")


def _cap_items(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return items[: max(0, limit)]


def _formal(hit: dict[str, Any]) -> bool:
    return (
        hit.get("source_store") in AUTHORITATIVE_STORES
        and (hit.get("authority") is True or hit.get("adopted") is True)
        and hit.get("review_passed") is True
        and str(hit.get("signature_status") or "") in {"owner_signed", "verified", "valid"}
        and str(hit.get("status") or hit.get("governance_status") or "active") not in {"revoked", "archived", "superseded", "deleted"}
    )


def _task_type(user_input: str) -> str:
    text = (user_input or "").lower()
    if any(token in text for token in ("美容", "臉部", "脸部", "保養", "保养", "文案", "貼文", "贴文", "copy", "beauty", "salon", "facial", "skincare", "skin care", "marketing post")):
        return "beauty_salon_marketing_copy"
    if any(token in text for token in ("債務", "债务", "民事", "借款", "欠款", "催告", "支付命令", "強制執行", "强制执行", "debt", "civil", "loan", "owed", "demand", "payment order", "enforcement", "lawsuit", "claim")):
        return "debt_civil_case_draft"
    if any(token in text for token in ("email", "郵件", "信")):
        return "email_draft"
    return "general_answer"


def _label_for_task(task_type: str, locale: str | None) -> str:
    if _locale_is_en(locale):
        return {
            "beauty_salon_marketing_copy": "beauty salon marketing copy",
            "debt_civil_case_draft": "debt civil case draft",
            "email_draft": "email draft",
            "general_answer": "general answer",
        }.get(task_type, task_type)
    return {
        "beauty_salon_marketing_copy": "美容院商業文案",
        "debt_civil_case_draft": "債務民事案件草稿",
        "email_draft": "Email 草稿",
        "general_answer": "一般回答",
    }.get(task_type, task_type)


def _base_policy(locale: str | None) -> dict[str, Any]:
    if _locale_is_en(locale):
        return {
            "forbidden_actions": [
                "Do not cite unconfirmed material as authority.",
                "Do not present a draft as a final result.",
                "Do not automatically publish, send email, list products, pay, delete, or store anything.",
            ],
            "output_limits": ["The answer must follow this current rule package and must not expand rules from chat context."],
            "stop_conditions": ["If formal authority is missing, mark the result as draft or ask for clarification."],
            "missing_information": ["No signed rule matched. This can only be basic chat or a draft."],
            "vector_reason": "Retrieval store only recalls candidates and cannot be used as formal authority.",
            "non_citable_reason": "Signature, review, activation, or relevance is incomplete.",
        }
    return {
        "forbidden_actions": [
            "不得引用未確認資料。",
            "不得把草稿說成正式結果。",
            "不得自動發布、寄信、上架、付款、刪除或入庫。",
        ],
        "output_limits": ["回答必須依本次規則包，不得依聊天上下文自行擴張規則。"],
        "stop_conditions": ["缺少正式依據時，需標示為草稿或追問。"],
        "missing_information": ["沒有命中已簽名規則時，只能一般聊天或草稿。"],
        "vector_reason": "檢索庫只負責召回候選，不可直接當正式依據。",
        "non_citable_reason": "未完成簽名、驗收、啟用或相關性不足。",
    }


def _extend_task_policy(policy: dict[str, list[str]], task_type: str, locale: str | None) -> None:
    if _locale_is_en(locale):
        if task_type == "beauty_salon_marketing_copy":
            policy["forbidden_actions"].extend(
                [
                    "Do not exaggerate effects.",
                    "Do not invent prices, discounts, treatment duration, or customer testimonials.",
                ]
            )
            policy["output_limits"].extend(
                [
                    "Beauty marketing copy must not imply medical effects or guaranteed results.",
                    "Do not include prices when no confirmed price data exists.",
                ]
            )
            policy["stop_conditions"].extend(
                ["Ask or mark pending confirmation when price, effect, promotion deadline, or customer case data is required."]
            )
        if task_type == "debt_civil_case_draft":
            policy["forbidden_actions"].extend(
                [
                    "Do not present the draft as legal advice, a filed pleading, a formal defense, or a submitted document.",
                    "Do not invent debt amount, interest, dates, chat records, repayment records, court case numbers, statutes, or court outcomes.",
                    "Do not automatically send demand letters, submit court documents, contact the counterparty, delete evidence, or execute payment.",
                ]
            )
            policy["output_limits"].extend(
                [
                    "Only produce a debt civil case draft pending user confirmation.",
                    "If party identity, debt source, amount, dates, evidence list, or procedure stage is missing, mark it as pending confirmation.",
                ]
            )
            policy["stop_conditions"].extend(
                [
                    "Stop and require user signature for litigation, defense, payment order, enforcement, settlement terms, or external filing.",
                    "Do not use legal basis, court procedure, or deadlines as formal authority unless supplied or verified by the user.",
                ]
            )
        return
    if task_type == "beauty_salon_marketing_copy":
        policy["forbidden_actions"].extend(["不得誇大療效。", "不得編造價格、優惠、療程時間或客戶見證。"])
        policy["output_limits"].extend(["美容文案不得暗示醫療效果或保證結果。", "沒有價格資料時不得寫價格。"])
        policy["stop_conditions"].extend(["需要價格、療效、優惠期限或客戶案例時必須追問或標待確認。"])
    if task_type == "debt_civil_case_draft":
        policy["forbidden_actions"].extend(
            [
                "不得把草稿說成正式法律意見、正式訴狀、正式答辯或已送件文件。",
                "不得編造借款金額、利率、日期、對話紀錄、還款紀錄、法院案號、法條或裁判結果。",
                "不得自動寄送存證信函、提交法院文件、聯絡對造、刪除證據或執行付款。",
            ]
        )
        policy["output_limits"].extend(
            [
                "只能生成待使用者確認的債務民事案件草稿。",
                "缺少當事人身分、債務來源、金額、日期、證據清單或程序階段時必須標示待確認。",
            ]
        )
        policy["stop_conditions"].extend(
            [
                "涉及起訴、答辯、支付命令、強制執行、和解條件或對外送件時必須停下要求使用者簽名。",
                "法律依據、法院流程或期限未由使用者提供或正式查證時，不得作為正式依據。",
            ]
        )


def _collect_hits(context: dict[str, Any]) -> list[dict[str, Any]]:
    packet = context.get("evidence_packet") or {}
    hits: list[dict[str, Any]] = []
    for item in packet.get("citations", []) or []:
        enriched = dict(item)
        enriched.setdefault("rule", item.get("excerpt"))
        enriched.setdefault("adopted", True)
        hits.append(enriched)
    for item in context.get("hits", []) or []:
        if not any(_source_id(existing) == _source_id(item) and _source_id(item) for existing in hits):
            hits.append(dict(item))
    return hits


def build_current_rule_package(
    user_input: str,
    four_store_context: dict[str, Any] | None,
    *,
    plan_level: str = "FREE",
    locale: str = "zh-TW",
    classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create the short package the model may see for this one answer.

    It intentionally contains only local-store citations needed for the current
    task. Chat history is not a source.
    """
    context = four_store_context or {}
    hits = _collect_hits(context)
    task_type = _task_type(user_input)
    policy = _base_policy(locale)
    matched_rules: list[dict[str, Any]] = []
    citable_data: list[dict[str, Any]] = []
    user_preferences: list[dict[str, Any]] = []
    retrieval_candidates: list[dict[str, Any]] = []
    non_citable_data: list[dict[str, Any]] = []
    for hit in hits:
        source_store = str(hit.get("source_store") or "vector")
        item = {
            "source_store": source_store,
            "source_id": _source_id(hit),
            "excerpt": _excerpt(hit),
            "signature_status": hit.get("signature_status"),
            "review_passed": hit.get("review_passed"),
            "status": hit.get("status") or hit.get("governance_status") or "active",
            "content_hash": hit.get("content_hash") or hit.get("hash"),
            "version": hit.get("version") or "1",
        }
        if _formal(hit) and source_store == "logic":
            matched_rules.append(item)
        elif _formal(hit) and source_store == "corpus":
            citable_data.append(item)
        elif _formal(hit) and source_store == "memory":
            user_preferences.append(item)
        elif source_store in {"vector", "vector_db"}:
            retrieval_candidates.append(item)
            non_citable_data.append({**item, "reason": policy["vector_reason"]})
        else:
            non_citable_data.append({**item, "reason": policy["non_citable_reason"]})

    _extend_task_policy(policy, task_type, locale)
    forbidden_actions = policy["forbidden_actions"]
    output_limits = policy["output_limits"]
    stop_conditions = policy["stop_conditions"]
    package_budget = {
        "matched_rules_total": len(matched_rules),
        "citable_data_total": len(citable_data),
        "user_preferences_total": len(user_preferences),
        "retrieval_candidates_total": len(retrieval_candidates),
        "non_citable_data_total": len(non_citable_data),
        "limits": PACKAGE_LIMITS,
    }
    matched_rules = _cap_items(matched_rules, PACKAGE_LIMITS["matched_rules"])
    citable_data = _cap_items(citable_data, PACKAGE_LIMITS["citable_data"])
    user_preferences = _cap_items(user_preferences, PACKAGE_LIMITS["user_preferences"])
    retrieval_candidates = _cap_items(retrieval_candidates, PACKAGE_LIMITS["retrieval_candidates"])
    non_citable_data = _cap_items(non_citable_data, PACKAGE_LIMITS["non_citable_data"])

    rule_status = "signed_rule_applied" if matched_rules else "no_signed_rule_matched"
    needs_clarification = not matched_rules and task_type != "general_answer"
    package = {
        "package_version": "scbkr.current_rule_package.v1",
        "source": "local_four_store_rule_package",
        "chat_context_used": False,
        "task_type": task_type,
        "task_type_label": _label_for_task(task_type, locale),
        "classification_mode": (classification or {}).get("mode") or "answer_with_rules",
        "matched_rules": matched_rules,
        "rule_status": rule_status,
        "citable_data": citable_data,
        "non_citable_data": non_citable_data,
        "retrieval_candidates": retrieval_candidates,
        "forbidden_actions": forbidden_actions,
        "stop_conditions": stop_conditions,
        "missing_information": [] if matched_rules else policy["missing_information"],
        "output_limits": output_limits,
        "user_preferences": user_preferences,
        "plan_level": plan_level,
        "package_budget": package_budget,
        "needs_clarification": needs_clarification,
        "draft_only": not matched_rules,
        "can_use_model": True,
        "can_execute_tools": False,
        "can_store": False,
        "citation_policy": "logic/corpus/memory only when signed, reviewed, active; vector is discovery only",
    }
    return package


def build_rule_package_messages(user_input: str, package: dict[str, Any], locale: str = "zh-TW") -> list[dict[str, str]]:
    if _locale_is_en(locale):
        system = (
            "You are the SCBKR local rule answer engine. First obey the provided current_rule_package. "
            "Do not use chat history as a rule source. Do not cite retrieval candidates as facts. "
            "If formal signed rules are missing, answer as draft/basic chat and ask for missing information when needed. "
            "Never claim storage, signing, publishing, email sending, payment, or tool execution happened."
        )
    else:
        system = (
            "你是 SCBKR 本地規則回答引擎。必須先遵守 current_rule_package。"
            "不得把聊天上下文當規則來源；不得把檢索庫候選當正式事實引用。"
            "沒有已簽名正式規則時，只能一般聊天或草稿，必要時追問缺少資訊。"
            "不得宣稱已簽名、已入庫、已發布、已寄信、已付款或已執行工具。"
        )
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": json.dumps(
                {"user_input": user_input, "current_rule_package": package},
                ensure_ascii=False,
                sort_keys=True,
            ),
        },
    ]


def build_rule_package_local_reply(user_input: str, package: dict[str, Any], locale: str = "zh-TW") -> str:
    task_type = package.get("task_type")
    applied = bool(package.get("matched_rules"))
    if _locale_is_en(locale):
        if applied:
            if task_type == "debt_civil_case_draft":
                return (
                    "Applied your debt civil case rule.\n\n"
                    "Draft:\n"
                    "1. Confirm party identity, debt source, amount, dates, repayment records, and evidence before use.\n"
                    "2. The demand draft may describe only confirmed facts, payment request, and response deadline. Do not invent interest, dates, case numbers, statutes, or outcomes.\n"
                    "3. This is not legal advice, not a filed document, and must not be sent automatically. Owner review and signature are required before any external action."
                )
            return (
                f"Applied your {package.get('task_type_label')} rule.\n\n"
                "Draft output:\n"
                "- Use confirmed rule boundaries before writing.\n"
                "- Do not invent price, discounts, proof, medical claims, or customer testimonials.\n"
                "- This is not published and still needs your review."
            )
        return "No signed local rule matched this request. Draft only. Pending confirmation: create and sign a rule or provide confirmed data before formal use."
    if applied and task_type == "beauty_salon_marketing_copy":
        return (
            "已套用你的美容院商業文案規則。\n\n"
            "草稿：\n"
            "今天想讓肌膚休息一下，就從一段溫柔的臉部保養開始。"
            "本次內容只描述保養體驗與預約引導，不寫未確認價格、不誇大療效、不保證結果，也不會自動發布。\n\n"
            "待確認：服務項目、價格、活動期限、品牌語氣與發布通路。"
        )
    if applied and task_type == "debt_civil_case_draft":
        return (
            "已套用你的債務民事案件規則。\n\n"
            "草稿：\n"
            "一、請先確認當事人身分、債務來源、借款或欠款金額、約定日期、還款紀錄與現有證據。\n"
            "二、催告內容只能描述已確認事實、付款請求與回覆期限，不得編造利率、日期、法院案號、法條或裁判結果。\n"
            "三、此內容不得自動寄出、不得視為正式法律意見、不得直接提交法院；送出前必須由使用者逐項確認並簽名。\n\n"
            "待確認：債務金額、債務發生日、付款期限、證據清單、目前程序階段、是否要轉成正式文件。"
        )
    if applied:
        return (
            f"已套用你的{package.get('task_type_label')}規則。\n\n"
            "我會依本次規則包生成草稿，不引用未確認資料，不執行工具，也不宣稱已入庫或已發布。"
        )
    return "目前沒有命中已簽名的本地規則，所以只能當一般聊天或草稿。待確認：若要正式套用，請先建立規則、簽名並入庫。"
