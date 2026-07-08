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
    if any(token in text for token in ("刪除", "移除", "delete", "remove", "script", "腳本", "程式", "code")):
        return "generate_code"
    if any(token in text for token in ("公告", "文案", "copy", "announcement", "post", "對外")):
        return "generate_copy"
    if any(token in text for token in ("可以嗎", "該不該", "判斷", "風險", "should i", "judge", "risk")):
        return "judgement"
    if any(token in text for token in ("email", "郵件", "信")):
        return "email_draft"
    return "general_answer"


def _label_for_task(task_type: str, locale: str | None) -> str:
    if _locale_is_en(locale):
        return {
            "generate_code": "code draft",
            "generate_copy": "copy draft",
            "judgement": "judgement",
            "email_draft": "email draft",
            "general_answer": "general answer",
        }.get(task_type, task_type)
    return {
        "generate_code": "程式草稿",
        "generate_copy": "文案草稿",
        "judgement": "判斷",
        "email_draft": "Email 草稿",
        "general_answer": "一般回答",
    }.get(task_type, task_type)


def _base_policy(locale: str | None) -> dict[str, Any]:
    if _locale_is_en(locale):
        return {
            "forbidden_actions": [
                "Do not cite unconfirmed material as authority.",
                "Do not present a draft as a final result.",
                "Do not automatically publish, send email, list, pay, delete, sign, activate, or store anything.",
            ],
            "output_limits": ["The answer must follow this current rule package and must not expand rules from chat context."],
            "stop_conditions": ["If formal authority is missing, mark the result as draft, OWNER_REVIEW, or NEED_DEFINITION."],
            "missing_information": ["No signed active local rule matched. This can only be basic chat or a draft."],
            "vector_reason": "VECTOR only recalls candidates and cannot be used as formal authority.",
            "non_citable_reason": "Signature, review, activation, or relevance is incomplete.",
        }
    return {
        "forbidden_actions": [
            "不得引用未確認資料作為正式依據。",
            "不得把草稿說成正式結果。",
            "不得自動發布、寄信、上架、付款、刪除、簽名、啟用或入庫。",
        ],
        "output_limits": ["回答必須依本次最小規則包，不得依聊天上下文自行擴張規則。"],
        "stop_conditions": ["缺少正式依據時，需標示 DRAFT / OWNER_REVIEW / NEED_DEFINITION。"],
        "missing_information": ["沒有命中已簽名 Active 規則時，只能一般聊天或草稿。"],
        "vector_reason": "VECTOR 只負責召回候選，不可直接當正式依據。",
        "non_citable_reason": "未完成簽名、驗收、啟用或相關性不足。",
    }


def _extend_task_policy(policy: dict[str, list[str]], task_type: str, locale: str | None) -> None:
    if _locale_is_en(locale):
        if task_type == "generate_code":
            policy["forbidden_actions"].extend(["Do not claim files were deleted, changed, pushed, paid, sent, or executed."])
            policy["stop_conditions"].extend(["Destructive scripts require owner confirmation and formal local rules when available."])
        elif task_type == "generate_copy":
            policy["forbidden_actions"].extend(["Do not claim an announcement or copy was published or sent."])
            policy["stop_conditions"].extend(["Formal external claims require citable local data; otherwise mark pending confirmation."])
        elif task_type == "judgement":
            policy["stop_conditions"].extend(["Formal judgement requires signed active LOGIC/CORPUS/MEMORY basis."])
        return
    if task_type == "generate_code":
        policy["forbidden_actions"].extend(["不得宣稱已刪除、已修改、已推送、已付款、已寄出或已執行。"])
        policy["stop_conditions"].extend(["破壞性腳本需使用者確認；若四庫有相關規則必須引用。"])
    elif task_type == "generate_copy":
        policy["forbidden_actions"].extend(["不得宣稱公告或文案已發布、已寄出或已上架。"])
        policy["stop_conditions"].extend(["正式對外宣稱需要可引用本地資料；缺資料時標待確認。"])
    elif task_type == "judgement":
        policy["stop_conditions"].extend(["正式判斷必須以 signed / reviewed / active 的 LOGIC/CORPUS/MEMORY 為準。"])


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
            "active": str(hit.get("status") or hit.get("governance_status") or "active") == "active",
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
    rule_status = "signed_rule_applied" if matched_rules else "no_signed_rule_matched"
    needs_clarification = not matched_rules and task_type != "general_answer"
    return {
        "package_version": "scbkr.current_rule_package.v2",
        "source": "local_four_store_rule_package",
        "chat_context_used": False,
        "task_type": task_type,
        "task_type_label": _label_for_task(task_type, locale),
        "classification_mode": (classification or {}).get("mode") or "answer_with_rules",
        "matched_rules": matched_rules[: PACKAGE_LIMITS["matched_rules"]],
        "rule_status": rule_status,
        "citable_data": citable_data[: PACKAGE_LIMITS["citable_data"]],
        "non_citable_data": non_citable_data[: PACKAGE_LIMITS["non_citable_data"]],
        "retrieval_candidates": retrieval_candidates[: PACKAGE_LIMITS["retrieval_candidates"]],
        "forbidden_actions": policy["forbidden_actions"],
        "stop_conditions": policy["stop_conditions"],
        "missing_information": [] if matched_rules else policy["missing_information"],
        "output_limits": policy["output_limits"],
        "user_preferences": user_preferences[: PACKAGE_LIMITS["user_preferences"]],
        "plan_level": plan_level,
        "package_budget": {
            "matched_rules_total": len(matched_rules),
            "citable_data_total": len(citable_data),
            "user_preferences_total": len(user_preferences),
            "retrieval_candidates_total": len(retrieval_candidates),
            "non_citable_data_total": len(non_citable_data),
            "limits": PACKAGE_LIMITS,
        },
        "needs_clarification": needs_clarification,
        "draft_only": not matched_rules,
        "can_use_model": True,
        "can_execute_tools": False,
        "can_store": False,
        "citation_policy": "LOGIC/CORPUS/MEMORY only when signed, reviewed, active; VECTOR is recall only",
    }


def build_rule_package_messages(user_input: str, package: dict[str, Any], locale: str = "zh-TW") -> list[dict[str, str]]:
    if _locale_is_en(locale):
        system = (
            "You are the SCBKR local rule answer engine. Obey current_rule_package. "
            "Chat history is non-authoritative. VECTOR candidates are recall only. "
            "Never claim storage, signing, publishing, sending, payment, deletion, or tool execution happened."
        )
    else:
        system = (
            "你是 SCBKR 本地規則回答引擎。必須遵守 current_rule_package。"
            "聊天上下文只能作非正式對話脈絡；VECTOR 只能召回。"
            "不得宣稱已簽名、已入庫、已發布、已寄信、已付款、已刪除或已執行工具。"
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps({"user_input": user_input, "current_rule_package": package}, ensure_ascii=False, sort_keys=True)},
    ]


def build_rule_package_local_reply(user_input: str, package: dict[str, Any], locale: str = "zh-TW") -> str:
    applied = bool(package.get("matched_rules"))
    task_type = package.get("task_type")
    if _locale_is_en(locale):
        if not applied:
            return "No signed active local rule matched. Draft only. Use this as non-authoritative conversation context until a local rule is signed and stored."
        return (
            f"Answered with your local {package.get('task_type_label')} rule package.\n\n"
            "Draft:\n"
            "- Follow the signed local rule boundaries.\n"
            "- Treat missing formal basis as pending confirmation.\n"
            "- No publishing, sending, payment, deletion, signing, storage, or external execution was performed."
        )
    if not applied:
        return "目前沒有命中已簽名 Active 的本地規則，所以只能當一般聊天或待確認草稿；正式判斷需先建立、簽名並入庫。"
    if task_type == "generate_code":
        return "已套用本地規則包回答。以下只能作程式草稿；未執行、未刪除、未修改任何本地資料。涉及破壞性動作前必須由使用者確認。"
    if task_type == "generate_copy":
        return "已套用本地規則包回答。以下只能作文案草稿；未發布、未寄出、未上架。缺正式資料處維持待確認。"
    if task_type == "judgement":
        return "已套用本地規則包回答。此判斷只引用 signed / reviewed / active 的本地規則；VECTOR 未作正式依據。"
    return "已套用本地規則包回答。未執行工具、未簽名、未入庫；若缺正式依據，維持草稿或 OWNER_REVIEW。"
