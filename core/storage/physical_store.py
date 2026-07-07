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
FOUR_STORE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "vector": {
        "store_label": "向量庫",
        "store_role": "相似案例索引",
        "store_purpose": "讓系統找到相似任務、路由候選資料與召回案例；不得單獨當正式判準。",
        "can_be_used_for": ["相似任務搜尋", "候選資料召回", "RAG 前置索引"],
        "cannot_be_used_for": ["單獨作為正式引用", "取代邏輯庫判準", "取代使用者簽名"],
        "citation_policy": "discovery_index_only_not_formal_basis",
    },
    "corpus": {
        "store_label": "語料庫",
        "store_role": "原文素材庫",
        "store_purpose": "保存使用者確認過的原始文本、生成成品或可供引用的素材內容。",
        "can_be_used_for": ["引用原文素材", "保存已驗收輸出", "提供後續生成語料"],
        "cannot_be_used_for": ["自動推導規則成立", "取代邏輯庫流程", "取代長期記憶"],
        "citation_policy": "signed_reviewed_source_material_can_be_formal_basis",
    },
    "logic": {
        "store_label": "邏輯庫",
        "store_role": "規則與流程判準庫",
        "store_purpose": "保存 SCBKR 五鏈、成立條件、失效條件、流程、邊界、驗收與責任規則。",
        "can_be_used_for": ["規則引用", "流程判準", "邊界與驗收檢查", "CLOSE_CANDIDATE 審計"],
        "cannot_be_used_for": ["保存大量原文素材", "取代向量搜尋", "未簽名時宣稱正式規則"],
        "citation_policy": "signed_reviewed_logic_can_be_formal_rule_basis",
    },
    "memory": {
        "store_label": "記憶庫",
        "store_role": "長期偏好與使用者規則記憶",
        "store_purpose": "保存使用者簽名確認後要長期影響未來任務的偏好、禁止事項與固定提醒。",
        "can_be_used_for": ["長期偏好提醒", "固定禁止條款", "未來任務預設提醒"],
        "cannot_be_used_for": ["保存一次性輸出成品", "取代語料原文", "未簽名時影響未來任務"],
        "citation_policy": "signed_user_memory_can_guide_future_tasks",
    },
}


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


def _store_contract(target: str) -> dict[str, Any]:
    return dict(FOUR_STORE_DEFINITIONS[target])


def _compact_json(value: Any) -> str:
    return json.dumps(sanitize_payload(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _list_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value if item not in (None, ""))
    if isinstance(value, dict):
        return _compact_json(value)
    return str(value or "")


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
        s = scbkr.get("S", {})
        c = scbkr.get("C", {})
        b = scbkr.get("B", {})
        r = scbkr.get("R", {})
        retrieval_text = "\n".join(
            part for part in [
                f"任務：{task.get('raw_input')}",
                f"主體：{s.get('task_subject') or s.get('task_name')}",
                f"摘要：{_summary(task)}",
                f"核心邏輯：{_list_text(c.get('core_logic'))}",
                f"停止條件：{_list_text(b.get('stop_conditions'))}",
                f"驗收：{_list_text(r.get('acceptance_criteria'))}",
            ] if part.strip()
        )
        payloads["vector"] = {
            **base,
            **_store_contract("vector"),
            "target": "vector",
            "case_id": f"vector:{task.get('task_id')}",
            "item_type": "retrieval_case_index",
            "content": retrieval_text,
            "retrieval_text": retrieval_text,
            "index_fields": {
                "S": s,
                "C_core_logic": c.get("core_logic", []),
                "B_stop_conditions": b.get("stop_conditions", []),
                "R_acceptance_criteria": r.get("acceptance_criteria", []),
            },
            "embedding_status": "pending",
            "embedding": None,
            "status": "metadata_saved_embedding_pending",
        }
    if "corpus" in selected_targets:
        source_material = gen_text or str(task.get("raw_input") or "")
        payloads["corpus"] = {
            **base,
            **_store_contract("corpus"),
            "target": "corpus",
            "source_id": f"corpus:{task.get('task_id')}",
            "item_type": "review_passed_source_material",
            "type": "review_passed_generation",
            "content": source_material,
            "source_material": source_material,
            "source_material_kind": "review_passed_generation" if gen_text else "owner_raw_input",
            "tags": [str(task.get("task_type") or "general"), "corpus"],
            "source_origin": "user_confirmed_storage",
        }
    if "logic" in selected_targets:
        c = scbkr.get("C", {})
        b = scbkr.get("B", {})
        k = scbkr.get("K", {})
        r = scbkr.get("R", {})
        logic_content = "\n".join([
            f"規則/流程：{_title(task)}",
            f"目的：{_summary(task)}",
            f"流程：\n{_list_text(c.get('flow_steps'))}",
            f"核心邏輯：\n{_list_text(c.get('core_logic'))}",
            f"邊界/停止條件：\n{_list_text(b.get('stop_conditions') or b.get('storage_conditions'))}",
            f"成立條件：\n{_list_text(b.get('formation_conditions') or r.get('formation_conditions'))}",
            f"失效條件：\n{_list_text(b.get('failure_conditions') or r.get('failure_conditions'))}",
            f"依據政策：\n{_list_text(k.get('source_credibility'))}",
            f"驗收：\n{_list_text(r.get('acceptance_criteria'))}",
        ]).strip()
        payloads["logic"] = {
            **base,
            **_store_contract("logic"),
            "target": "logic",
            "logic_id": f"logic:{task.get('task_id')}",
            "item_type": "scbkr_rule_logic",
            "name": _title(task),
            "purpose": _summary(task),
            "content": logic_content,
            "flow_steps": c.get("flow_steps", []),
            "core_logic": c.get("core_logic", []),
            "boundary_rules": b.get("stop_conditions") or b.get("storage_conditions", []),
            "formation_conditions": b.get("formation_conditions") or r.get("formation_conditions", []),
            "failure_conditions": b.get("failure_conditions") or r.get("failure_conditions", []),
            "test_rules": c.get("test_conditions", []),
            "dependencies": c.get("dependencies", []),
            "acceptance_criteria": r.get("acceptance_criteria", []),
            "status": "active",
        }
    if "memory" in selected_targets:
        b = scbkr.get("B", {})
        r = scbkr.get("R", {})
        memory_statement = (
            str(task.get("raw_input") or "").strip()
            or _summary(task)
            or _title(task)
        )
        memory_content = "\n".join([
            f"長期記憶：{memory_statement}",
            f"觸發條件：\n{_list_text(b.get('stop_conditions') or b.get('failure_conditions'))}",
            f"必須提醒：\n{_list_text(r.get('acceptance_criteria'))}",
            "限制：這不是一次性生成成品；只有使用者簽名確認後才影響未來任務。",
        ]).strip()
        payloads["memory"] = {
            **base,
            **_store_contract("memory"),
            "target": "memory",
            "memory_id": f"memory:{task.get('task_id')}",
            "item_type": "user_confirmed_long_term_memory",
            "category": str(task.get("task_type") or "general"),
            "content": memory_content,
            "memory_statement": memory_statement,
            "trigger_conditions": b.get("stop_conditions") or b.get("failure_conditions", []),
            "required_behavior": r.get("acceptance_criteria", []),
            "reason": "使用者二次確認後保存為本地長期記憶資料。",
            "source_task": task.get("task_id"),
            "confirmed_by_user": True,
            "status": "active",
        }
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
