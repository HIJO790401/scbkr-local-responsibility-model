"""P13-B local JSON physical storage helpers.

This module writes only local JSON files for confirmed P13-B storage targets. It
never writes ChromaDB/vector stores, calls models/APIs, or mutates JSONL.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from core.storage.runtime_paths import CORPUS_DIR, EXPORTS_DIR, LOGIC_DIR, MEMORY_DIR, REPO_ROOT
from core.storage.storage_manifest import SUCCESS_STORAGE_TARGETS

SENSITIVE_KEYS = {"api_key", "apikey", "authorization", "access_token", "refresh_token", "token", "secret"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _active_data_dir() -> Path:
    import os

    return Path(os.environ.get("SCBKR_DATA_DIR", REPO_ROOT / "data")).expanduser()


def _target_dir(target: str) -> Path:
    base = _active_data_dir()
    return {
        "corpus": base / "corpus",
        "logic": base / "logic",
        "exports": base / "exports",
        "memory": base / "memory",
    }[target]


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = sanitize_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    return value


def hash_payload(payload: Any) -> str:
    safe_payload = sanitize_payload(payload)
    encoded = json.dumps(safe_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_json_atomic(path: str | Path, payload: Any) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_payload = sanitize_payload(payload)
    content_hash = hash_payload(safe_payload)
    data = json.dumps(safe_payload, sort_keys=True, ensure_ascii=False, indent=2)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        try:
            if json.loads(existing) == safe_payload:
                return {"path": str(path), "content_hash": content_hash, "idempotent": True}
        except json.JSONDecodeError:
            pass
        raise FileExistsError(f"refusing to overwrite different JSON content: {path}")
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as file:
            file.write(data)
            file.write("\n")
            file.flush()
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return {"path": str(path), "content_hash": content_hash, "idempotent": False}


def _relative(path: Path) -> str:
    return str(path.relative_to(_active_data_dir()))


def _sealed_scbkr(task: dict[str, Any]) -> dict[str, Any]:
    scbkr = task.get("scbkr", {})
    return sanitize_payload(
        {
            "confirmed_snapshot": scbkr.get("confirmed_snapshot"),
            "confirmed_snapshot_hash": scbkr.get("confirmed_snapshot_hash"),
            "confirmation_status": scbkr.get("confirmation_status"),
        }
    )


def build_success_corpus_payload(task: dict[str, Any]) -> dict[str, Any]:
    if task.get("review_passed") is not True or task.get("review_result", {}).get("review_passed") is not True:
        raise ValueError("corpus physical write requires review_passed content")
    return sanitize_payload(
        {
            "task_id": task.get("task_id"),
            "trace_id": task.get("trace_id"),
            "task_type": task.get("task_type"),
            "raw_input": task.get("raw_input"),
            "generation_result": task.get("generation_result"),
            "review_result": task.get("review_result"),
            "sealed_scbkr_payload": _sealed_scbkr(task),
            "accepted_at": task.get("accepted_at") or task.get("review_result", {}).get("reviewed_at") or "review_passed",
            "source": "review_passed_generation",
        }
    )


def build_logic_payload(task: dict[str, Any]) -> dict[str, Any]:
    scbkr = task.get("scbkr", {})
    return sanitize_payload(
        {
            "task_id": task.get("task_id"),
            "sealed_scbkr_payload": _sealed_scbkr(task),
            "confirmed_snapshot_hash": scbkr.get("confirmed_snapshot_hash"),
            "acceptance_criteria": scbkr.get("R", {}).get("acceptance_criteria") or scbkr.get("confirmed_snapshot", {}).get("R"),
            "review_result": task.get("review_result"),
            "storage_plan": task.get("storage_plan"),
            "responsibility_chain_version": "P13-B",
            "source": "sealed_scbkr_logic",
        }
    )


def build_export_payload(task: dict[str, Any]) -> dict[str, Any]:
    return sanitize_payload(
        {
            "task": {key: value for key, value in task.items() if key not in {"memory_rule_draft"}},
            "scbkr": task.get("scbkr"),
            "generation_result": task.get("generation_result"),
            "review_result": task.get("review_result"),
            "storage_plan": task.get("storage_plan"),
            "ledger_hint": {"task_id": task.get("task_id"), "trace_id": task.get("trace_id"), "ledger_id": task.get("ledger_id")},
            "source": "export_bundle",
        }
    )


def _payload_for_target(task: dict[str, Any], target: str) -> dict[str, Any]:
    if target == "corpus":
        return build_success_corpus_payload(task)
    if target == "logic":
        return build_logic_payload(task)
    if target == "exports":
        return build_export_payload(task)
    raise ValueError(f"unsupported physical storage target: {target}")


def build_storage_item(task: dict[str, Any], target: str, payload: dict[str, Any], source_event_id: str | None = None) -> dict[str, Any]:
    if target not in SUCCESS_STORAGE_TARGETS:
        raise ValueError(f"unsupported physical storage target: {target}")
    content_hash = hash_payload(payload)
    task_id = task.get("task_id") or "unknown-task"
    filename = f"{task_id}-{content_hash[:12]}.json"
    path = _target_dir(target) / filename
    return {
        "item_id": f"storage:{target}:{task_id}:{content_hash[:12]}",
        "task_id": task_id,
        "target": target,
        "relative_path": _relative(path),
        "content_hash": content_hash,
        "source_event_id": source_event_id,
        "physical_write_performed": True,
        "created_at": _now(),
        "payload": payload,
    }


def commit_storage_items(task: dict[str, Any], storage_plan: dict[str, Any], source_event_id: str | None = None) -> list[dict[str, Any]]:
    if task.get("review_passed") is not True or task.get("review_result", {}).get("review_passed") is not True:
        raise ValueError("storage commit requires review_passed task")
    requested = set(storage_plan.get("selected_targets") or []) | {item.get("target") for item in storage_plan.get("storage_items", [])}
    targets = [target for target in SUCCESS_STORAGE_TARGETS if target in requested or not requested]
    if not targets:
        targets = list(SUCCESS_STORAGE_TARGETS)
    items: list[dict[str, Any]] = []
    for target in targets:
        payload = _payload_for_target(task, target)
        item = build_storage_item(task, target, payload, source_event_id=source_event_id)
        write_json_atomic(_active_data_dir() / item["relative_path"], payload)
        items.append(item)
    return items


def commit_memory_rule(task: dict[str, Any], source_event_id: str | None = None) -> dict[str, Any]:
    plan = task.get("memory_rule_confirmed_plan")
    if not isinstance(plan, dict) or plan.get("memory_rule_status") != "confirmed_plan":
        raise ValueError("confirmed memory rule plan is required")
    signature = str(plan.get("reviewer_signature") or "").strip()
    if not signature:
        raise ValueError("reviewer_signature is required")
    payload = sanitize_payload(
        {
            "task_id": task.get("task_id"),
            "memory_rule_confirmed_plan": plan,
            "reviewer_signature": signature,
            "user_failure_judgment": plan.get("user_failure_judgement"),
            "rule_statement": plan.get("rule_statement"),
            "scope": {
                "applies_to_task_types": plan.get("applies_to_task_types", []),
                "trigger_conditions": plan.get("trigger_conditions", []),
                "forbidden_patterns": plan.get("forbidden_patterns", []),
                "required_behavior": plan.get("required_behavior", []),
            },
            "created_at": task.get("memory_rule_confirmed_plan", {}).get("created_at") or "signed_memory_rule",
            "source": "signed_memory_rule",
        }
    )
    rule_hash = hash_payload(payload)
    task_id = task.get("task_id") or "unknown-task"
    path = _target_dir("memory") / f"{task_id}-{rule_hash[:12]}.json"
    write_json_atomic(path, payload)
    return {
        "rule_id": f"memory:{task_id}:{rule_hash[:12]}",
        "task_id": task_id,
        "rule_hash": rule_hash,
        "relative_path": _relative(path),
        "reviewer_signature": signature,
        "scope": json.dumps(payload["scope"], sort_keys=True, ensure_ascii=False),
        "created_at": payload["created_at"],
        "payload": payload,
        "source_event_id": source_event_id,
    }
