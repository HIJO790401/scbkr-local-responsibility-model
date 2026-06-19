"""Build sanitized retrieval case documents from committed storage and signed memory rules."""
from __future__ import annotations
from datetime import UTC, datetime
import hashlib, json, re
from typing import Any
from core.storage.physical_store import sanitize_payload

SENSITIVE_WORDS = re.compile(r"api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|secret", re.I)

def _now(): return datetime.now(UTC).isoformat()
def _hash(v: Any) -> str: return hashlib.sha256(json.dumps(sanitize_payload(v), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def hash_retrieval_text(text: str) -> str: return hashlib.sha256((text or "").encode("utf-8")).hexdigest()
def _safe_text(value: Any) -> str:
    text = json.dumps(sanitize_payload(value), ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    return SENSITIVE_WORDS.sub("[REDACTED_KEY]", text)

def build_retrieval_text(case: dict[str, Any]) -> str:
    keys = ["case_type","task_type","raw_input","generation_summary","review_summary","acceptance_criteria","sealed_scbkr_payload","scope","rule_statement","user_failure_judgment","required_behavior","forbidden_patterns"]
    return "\n".join(f"{k}: {_safe_text(case.get(k))}" for k in keys if case.get(k) not in (None, "", [], {}))

def build_success_case_from_storage_item(task: dict[str, Any], storage_item: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if task.get("status") != "storage_committed" or task.get("review_passed") is not True or task.get("physical_write_performed") is not True:
        raise ValueError("success_case requires storage_committed, review_passed task with physical writes")
    if storage_item.get("target") not in ("corpus", "logic", "exports"):
        raise ValueError("success_case only supports corpus/logic/exports")
    review = payload.get("review_result") or task.get("review_result") or {}
    if review.get("review_passed") is not True:
        raise ValueError("review_failed output cannot become success_case")
    generation = payload.get("generation_result") or task.get("generation_result") or {}
    scbkr = payload.get("sealed_scbkr_payload") or task.get("scbkr", {})
    case = sanitize_payload({
        "case_id": f"case:success:{storage_item.get('target')}:{task.get('task_id')}:{(storage_item.get('content_hash') or _hash(payload))[:12]}",
        "case_type": "success_case", "task_id": task.get("task_id"), "source_target": storage_item.get("target"),
        "relative_path": storage_item.get("relative_path"), "content_hash": storage_item.get("content_hash") or _hash(payload),
        "sealed_scbkr_payload": scbkr, "task_type": task.get("task_type"), "raw_input": task.get("raw_input"),
        "generation_summary": generation.get("summary") or generation.get("output") or generation.get("content"),
        "review_summary": review.get("review_message") or review.get("message") or review.get("status"),
        "acceptance_criteria": task.get("scbkr", {}).get("R", {}).get("acceptance_criteria"), "created_at": _now(),
    })
    case["retrieval_text"] = build_retrieval_text(case); case["retrieval_text_hash"] = hash_retrieval_text(case["retrieval_text"])
    return case

def build_memory_rule_case(memory_rule: dict[str, Any]) -> dict[str, Any]:
    payload = memory_rule.get("payload") or memory_rule.get("memory_rule_confirmed_plan") or {}
    plan = payload.get("memory_rule_confirmed_plan") or payload
    if plan.get("memory_rule_status") != "confirmed_plan":
        raise ValueError("memory_rule_status must be confirmed_plan")
    if not str(memory_rule.get("reviewer_signature") or "").strip():
        raise ValueError("reviewer_signature is required")
    if not memory_rule.get("relative_path") or not memory_rule.get("rule_hash"):
        raise ValueError("relative_path and rule_hash are required")
    scope = payload.get("scope") or plan.get("scope") or {"applies_to_task_types": plan.get("applies_to_task_types", []), "trigger_conditions": plan.get("trigger_conditions", []), "forbidden_patterns": plan.get("forbidden_patterns", []), "required_behavior": plan.get("required_behavior", [])}
    case = sanitize_payload({"case_id": f"case:memory:{memory_rule.get('task_id')}:{memory_rule.get('rule_hash')[:12]}", "case_type": "signed_memory_rule", "task_id": memory_rule.get("task_id"), "rule_hash": memory_rule.get("rule_hash"), "relative_path": memory_rule.get("relative_path"), "scope": scope, "rule_statement": plan.get("rule_statement") or payload.get("rule_statement"), "user_failure_judgment": plan.get("user_failure_judgement") or payload.get("user_failure_judgment"), "required_behavior": scope.get("required_behavior"), "forbidden_patterns": scope.get("forbidden_patterns"), "created_at": memory_rule.get("created_at") or _now()})
    case["retrieval_text"] = build_retrieval_text(case); case["retrieval_text_hash"] = hash_retrieval_text(case["retrieval_text"])
    return case
