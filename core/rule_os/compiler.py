"""Compile signed SCBKR records into executable local-rule metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, "", {}):
        return []
    return [value]


def compile_executable_rule(task: dict[str, Any], storage_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Create a compact executable local-rule record after signed storage."""
    scbkr = task.get("scbkr") or {}
    s = scbkr.get("S") or {}
    c = scbkr.get("C") or {}
    b = scbkr.get("B") or {}
    k = scbkr.get("K") or {}
    r = scbkr.get("R") or {}
    storage_items = storage_items or []
    return {
        "compiled_rule_version": "scbkr.local_rule.v1",
        "compiled_at": _now(),
        "rule_id": f"local-rule:{task.get('task_id')}",
        "task_id": task.get("task_id"),
        "title": s.get("task_name") or task.get("task_name") or task.get("raw_input"),
        "active": task.get("storage_confirmed") is True and scbkr.get("signature_status") == "owner_signed",
        "signature_status": scbkr.get("signature_status"),
        "review_passed": task.get("review_passed") is True,
        "version": 1,
        "match_conditions": {
            "task_subject": s.get("task_subject"),
            "task_type": task.get("task_type"),
            "keywords": _as_list(s.get("task_subject")) + _as_list(s.get("task_name")) + _as_list(task.get("raw_input")),
        },
        "execution_logic": {
            "flow_steps": _as_list(c.get("flow_steps")),
            "core_logic": _as_list(c.get("core_logic")),
            "forbidden_actions": _as_list(b.get("stop_conditions")) + _as_list(b.get("failure_conditions")),
            "stop_conditions": _as_list(b.get("stop_conditions")),
            "formation_conditions": _as_list(b.get("formation_conditions")) + _as_list(r.get("formation_conditions")),
            "failure_conditions": _as_list(b.get("failure_conditions")) + _as_list(r.get("failure_conditions")),
            "basis_policy": _as_list(k.get("source_credibility")) + _as_list(k.get("references")),
            "acceptance_criteria": _as_list(r.get("acceptance_criteria")),
            "repair_path": _as_list(r.get("repair_path")),
            "replay_requirements": _as_list(r.get("replay_requirements")),
        },
        "four_store_bindings": [
            {
                "target": item.get("target"),
                "item_id": item.get("item_id"),
                "content_hash": item.get("content_hash"),
                "status": item.get("status"),
            }
            for item in storage_items
        ],
        "citation_policy": "formal answers may cite only active owner-signed reviewed logic/corpus/memory records; retrieval/vector is discovery only",
    }
