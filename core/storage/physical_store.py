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

from core.storage.runtime_paths import REPO_ROOT
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
        "vector": base / "vector",
        "corpus": base / "corpus",
        "logic": base / "logic",
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


def _relative_posix(path: Path, base: Path | None = None) -> str:
    """Return metadata paths with stable POSIX separators on every OS."""
    return path.relative_to(base or _active_data_dir()).as_posix()


def _relative(path: Path) -> str:
    return _relative_posix(path)


def _sealed_scbkr(task: dict[str, Any]) -> dict[str, Any]:
    scbkr = task.get("scbkr", {})
    return sanitize_payload(
        {
            "confirmed_snapshot": scbkr.get("confirmed_snapshot"),
            "confirmed_snapshot_hash": scbkr.get("confirmed_snapshot_hash"),
            "confirmation_status": scbkr.get("confirmation_status"),
            "signature_status": scbkr.get("signature_status"),
            "owner_signature_required": scbkr.get("owner_signature_required"),
            "model_signature_allowed": scbkr.get("model_signature_allowed"),
            "signature_metadata": {"confirmed_by": scbkr.get("confirmed_by"), "signature_hash": hash_payload(scbkr.get("signature") or "") if scbkr.get("signature") else None},
        }
    )


def _generation_text(task: dict[str, Any]) -> str:
    result = task.get("generation_result") or {}
    return str(result.get("content") or result.get("generated_text") or result.get("text") or "")


def _title(task: dict[str, Any]) -> str:
    return str(task.get("task_name") or task.get("scbkr", {}).get("S", {}).get("task_name") or task.get("raw_input") or "SCBKR storage item")[:80]


def _summary(task: dict[str, Any]) -> str:
    text = _generation_text(task) or str(task.get("raw_input") or "")
    return text[:300]


def prepare_storage_payloads(task: dict[str, Any], selected_targets: list[str], ledger_id: str | None = None) -> dict[str, dict[str, Any]]:
    """Build structured payloads for storage layer; never writes files or mutates task state."""
    now = task.get("created_at") or f"system_storage:{task.get('task_id') or 'unknown-task'}"
    scbkr = task.get("scbkr", {})
    generation = task.get("generation_result") or {}
    gen_text = _generation_text(task)
    snapshot_hash = scbkr.get("confirmed_snapshot_hash") or hash_payload(scbkr.get("confirmed_snapshot") or scbkr)
    base = {
        "task_id": task.get("task_id"),
        "trace_id": task.get("trace_id"),
        "ledger_id": ledger_id or task.get("ledger_id"),
        "title": _title(task),
        "summary": _summary(task),
        "content": f"{gen_text}\n\nSCBKR: {json.dumps(_sealed_scbkr(task), ensure_ascii=False, sort_keys=True)}".strip(),
        "source_task_id": task.get("task_id"),
        "source_generation_id": generation.get("generation_id") or task.get("trace_id"),
        "raw_input": task.get("raw_input"),
        "task_type": task.get("task_type"),
        "scbkr_snapshot": _sealed_scbkr(task),
        "scbkr_snapshot_hash": snapshot_hash,
        "confirmed_snapshot_hash": snapshot_hash,
        "generation_result": generation,
        "review_result": task.get("review_result"),
        "review_passed": task.get("review_passed") is True or (task.get("review_result") or {}).get("review_passed") is True,
        "signature_status": scbkr.get("signature_status"),
        "owner_signature": {"signature_hash": hash_payload(scbkr.get("signature") or "") if scbkr.get("signature") else None, "confirmed_by": scbkr.get("confirmed_by")},
        "relation_metadata": task.get("data_center_context", {}),
        "confirmed_at": scbkr.get("confirmed_at") or task.get("confirmed_at"),
        "reviewed_at": (task.get("review_result") or {}).get("reviewed_at") or task.get("accepted_at"),
        "written_at": now,
        "stored_at": now,
        "created_at": now,
    }
    payloads: dict[str, dict[str, Any]] = {}
    if "vector" in selected_targets:
        payloads["vector"] = {**base, "target": "vector", "case_id": f"vector:{task.get('task_id')}", "S": scbkr.get("S"), "C": scbkr.get("C"), "B": scbkr.get("B"), "K": scbkr.get("K"), "R": scbkr.get("R"), "embedding_status": "pending", "embedding": None, "status": "metadata_saved_embedding_pending"}
    if "corpus" in selected_targets:
        payloads["corpus"] = {**base, "target": "corpus", "source_id": f"corpus:{task.get('task_id')}", "type": "review_passed_generation", "tags": [str(task.get("task_type") or "general"), "corpus"], "source_origin": "user_confirmed_storage"}
    if "logic" in selected_targets:
        payloads["logic"] = {**base, "target": "logic", "logic_id": f"logic:{task.get('task_id')}", "name": _title(task), "purpose": _summary(task), "flow_steps": scbkr.get("C", {}).get("flow_steps", []), "boundary_rules": scbkr.get("B", {}).get("storage_conditions", []), "test_rules": scbkr.get("C", {}).get("test_conditions", []), "dependencies": scbkr.get("C", {}).get("dependencies", []), "status": "active"}
    if "memory" in selected_targets:
        payloads["memory"] = {**base, "target": "memory", "memory_id": f"memory:{task.get('task_id')}", "category": str(task.get("task_type") or "general"), "reason": "使用者二次確認後保存為本地記憶資料。", "source_task": task.get("task_id"), "confirmed_by_user": True, "status": "active"}
    for target, payload in payloads.items():
        payload["hash"] = hash_payload(payload)
    return payloads

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


def _payload_for_target(task: dict[str, Any], target: str, prepared: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    prepared = prepared or {}
    if target in prepared:
        return prepared[target]
    if target == "vector":
        return prepare_storage_payloads(task, ["vector"], task.get("ledger_id"))["vector"]
    if target == "corpus":
        return prepared.get("corpus") or build_success_corpus_payload(task)
    if target == "logic":
        return prepared.get("logic") or build_logic_payload(task)
    if target == "memory":
        return prepared.get("memory") or prepare_storage_payloads(task, ["memory"], task.get("ledger_id"))["memory"]
    raise ValueError(f"unsupported physical storage target: {target}")


def _governance_metadata(now: str) -> dict[str, Any]:
    return {
        "status": "active",
        "version": 1,
        "parent_item_id": None,
        "superseded_by": None,
        "user_event_date": None,
        "event_date_source": "unset",
        "event_date_confirmed": False,
        "created_at": now,
        "stored_at": now,
        "updated_at": None,
        "archived_at": None,
        "revoked_at": None,
    }


def build_storage_item(task: dict[str, Any], target: str, payload: dict[str, Any], source_event_id: str | None = None) -> dict[str, Any]:
    supported_targets = set(SUCCESS_STORAGE_TARGETS)
    if target not in supported_targets:
        raise ValueError(f"unsupported physical storage target: {target}")
    now = str(payload.get("created_at") or payload.get("stored_at") or task.get("created_at") or f"system_storage:{task.get('task_id') or 'unknown-task'}")
    governed_payload = {**payload, **_governance_metadata(now)}
    content_hash = hash_payload(governed_payload)
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
        **_governance_metadata(now),
        "payload": governed_payload,
    }


def commit_storage_items(task: dict[str, Any], storage_plan: dict[str, Any], source_event_id: str | None = None) -> list[dict[str, Any]]:
    if task.get("review_passed") is not True or task.get("review_result", {}).get("review_passed") is not True:
        raise ValueError("storage commit requires review_passed task")
    requested = set(storage_plan.get("selected_targets") or []) | {item.get("target") for item in storage_plan.get("storage_items", [])}
    # Accept old plans as input only; all new records are written with target=vector.
    if "vector_db" in requested:
        requested.remove("vector_db")
        requested.add("vector")
    supported_targets = ["vector", "corpus", "logic", "memory"]
    targets = [target for target in supported_targets if target in requested]
    if storage_plan.get("allow_vector_metadata") is not True:
        targets = [target for target in targets if target != "vector"]
    if not targets and not requested:
        targets = ["corpus", "logic"]
    prepared = prepare_storage_payloads(task, targets, task.get("ledger_id")) if storage_plan.get("p15d_structured_payloads") is True else {}
    items: list[dict[str, Any]] = []
    for target in targets:
        payload = _payload_for_target(task, target, prepared)
        item = build_storage_item(task, target, payload, source_event_id=source_event_id)
        write_json_atomic(_active_data_dir() / item["relative_path"], item["payload"])
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
