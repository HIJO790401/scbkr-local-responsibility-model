"""SCBKR 2.2 workflow-card contract shared by chat, rules, and workbench."""

from __future__ import annotations

from typing import Any
from uuid import uuid4


def _items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        return [f"{key}: {item}" for key, item in value.items()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value)]


def _dimension(draft: dict[str, Any], key: str) -> dict[str, Any]:
    value = draft.get(key)
    return value if isinstance(value, dict) else {}


def _suggested_stores(object_type: str, draft: dict[str, Any]) -> list[str]:
    candidates = _items(_dimension(draft, "R").get("storage_options"))
    if object_type == "rule":
        return ["logic"]
    if object_type in {"memory", "decision"}:
        return ["memory"]
    if object_type in {"source", "corpus"}:
        return ["corpus"]
    return [store for store in candidates if store in {"corpus", "logic", "memory"}] or ["logic", "memory"]


def build_scbkr_draft_object(
    *,
    user_request_raw: str,
    scbkr: dict[str, Any],
    intent: str = "create_confirmation",
    object_type: str = "task",
    draft_id: str | None = None,
    evidence_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the non-authoritative 2.2 draft shown as a workflow card."""
    s = _dimension(scbkr, "S")
    b = _dimension(scbkr, "B")
    k = _dimension(scbkr, "K")
    r = _dimension(scbkr, "R")
    context = evidence_context or {}
    citations = context.get("evidence_packet", {}).get("citations", []) or []
    required_citations = [
        str(item.get("citation_id"))
        for item in citations
        if isinstance(item, dict) and item.get("citation_id")
    ]
    pending = []
    for key in "SCBKR":
        pending.extend(_items(_dimension(scbkr, key).get("pending_questions")))
    suggested_store = _suggested_stores(object_type, scbkr)
    return {
        "draft_id": draft_id or f"draft:{uuid4().hex}",
        "state": "DRAFT_FAILED" if scbkr.get("draft_source") == "draft_failed" else "DRAFTING",
        "intent": intent,
        "object_type": object_type,
        "user_request_raw": user_request_raw.strip(),
        "proposed_title": str(s.get("task_name") or user_request_raw[:48] or "SCBKR 草案"),
        "summary": str(s.get("task_subject") or user_request_raw),
        "S_subject": _dimension(scbkr, "S"),
        "C_causality": _dimension(scbkr, "C"),
        "B_boundary": b,
        "K_basis": k,
        "R_responsibility": r,
        "suggested_store": suggested_store,
        "suggested_store_reason": "模型僅依內容類型提出候選；最終入庫需 OwnerReview、簽名與二次確認。",
        "forbidden_store": ["vector_only"],
        "required_inputs": pending,
        "required_citations": required_citations,
        "assumptions": _items(scbkr.get("compiler_report", {}).get("errors")),
        "missing_definitions": pending,
        "validity_conditions": _items(r.get("acceptance_criteria")),
        "failure_conditions": _items(b.get("stop_conditions")),
        "risk_flags": ["unsigned", "not_storage_confirmed"],
        "allowed_actions_before_signature": ["edit_draft", "request_model_patch", "cancel"],
        "blocked_actions_before_signature": ["activate", "formal_generate", "store", "claim_as_citation"],
        "allowed_actions_after_signature": ["generate", "owner_review", "request_storage_plan"],
        "owner_review_required": True,
        "signature_required": True,
        "confirmed_by": None,
        "signed_at": None,
        "storage_confirmed": False,
        "final_store": None,
    }


def build_rule_draft_object(rule: dict[str, Any]) -> dict[str, Any]:
    """Represent an unsigned user rule using the same workflow-card contract."""
    scope = rule.get("rule_scope") if isinstance(rule.get("rule_scope"), dict) else {}
    text = str(rule.get("rule_text") or rule.get("rule_name") or "")
    return {
        "draft_id": str(rule.get("rule_id") or f"draft:{uuid4().hex}"),
        "state": "DRAFTING",
        "intent": "create_new_rule_confirmation",
        "object_type": "rule",
        "user_request_raw": text,
        "proposed_title": str(rule.get("rule_name") or "User Rule draft"),
        "summary": text,
        "S_subject": {"rule_author": rule.get("rule_author"), "applies_to": scope.get("task_types", ["*"])},
        "C_causality": {"reason": "使用者要求建立可重用規則。"},
        "B_boundary": {"scope": scope, "denied_tools": rule.get("denied_tools", [])},
        "K_basis": {"source": rule.get("rule_source"), "keywords": scope.get("keywords", [])},
        "R_responsibility": {"required_signer": "user", "activation_status": rule.get("activation_status")},
        "suggested_store": ["logic"],
        "suggested_store_reason": "可重用規則屬於 logic 候選；尚未簽名，不得視為有效依據。",
        "forbidden_store": ["vector_only", "memory_without_review"],
        "required_inputs": [],
        "required_citations": [],
        "assumptions": [],
        "missing_definitions": [],
        "validity_conditions": ["OwnerReview 完成", "使用者簽名", "使用者啟用"],
        "failure_conditions": ["規則被撤銷、封存或取代", "簽名缺失"],
        "risk_flags": ["unsigned"],
        "allowed_actions_before_signature": ["edit_draft", "request_model_patch", "cancel"],
        "blocked_actions_before_signature": ["activate", "store", "claim_as_citation"],
        "allowed_actions_after_signature": ["activate", "owner_review"],
        "owner_review_required": True,
        "signature_required": True,
        "confirmed_by": None,
        "signed_at": None,
        "storage_confirmed": False,
        "final_store": None,
    }
