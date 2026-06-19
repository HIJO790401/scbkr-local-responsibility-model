"""P13-A/B/C FastAPI MVP runtime for the local SCBKR Web App.

Tasks are cached in memory and persisted to local SQLite. Flow events are
appended to a JSONL replay ledger; retrieval is advisory and no desktop runtime is initialized here.
"""

from datetime import UTC, datetime
from itertools import count
from uuid import uuid4
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from core.model_gateway.connection_test import make_test_status
from core.model_gateway.openai_compatible import build_chat_completion_payload, build_headers
from core.model_gateway.response_parser import parse_chat_completion_response
from core.model_gateway.settings import DEFAULT_MODEL_SETTINGS, mask_api_key, validate_model_settings
from core.permissions.permission_checker import assert_permission_allowed, validate_permission_settings
from core.permissions.permission_flags import DEFAULT_PERMISSION_SETTINGS
from core.ledger.ledger_event import build_ledger_event
from core.ledger.jsonl_ledger import append_ledger_event, read_ledger_events, rebuild_ledger_index_from_jsonl
from core.review_rules.rule_confirmation import confirm_memory_rule_plan
from core.review_rules.rule_draft import build_memory_rule_draft
from core.scbkr.confirmation import all_dimensions_confirmed, confirm_all_dimensions
from core.scbkr.generator import create_scbkr_draft
from core.storage.physical_store import commit_memory_rule, commit_storage_items
from core.storage.sqlite_runtime import (
    get_task_ledger,
    init_sqlite_runtime,
    list_tasks as list_persisted_tasks,
    load_task,
    list_memory_rules as list_persisted_memory_rules,
    list_storage_items as list_persisted_storage_items,
    save_ledger_index,
    save_memory_rule,
    save_scbkr_confirmation,
    save_storage_item,
    save_task,
)
from core.storage.storage_plan import build_storage_commit_plan
from core.storage.storage_request import build_storage_request
from core.workflow.generation_flow import build_generation_messages, assert_task_can_generate
from core.workflow.generation_result import build_generation_result
from core.workflow.review_flow import apply_review_decision
from core.retrieval.retrieval_runtime import index_task_storage_cases, index_memory_rule_case, query_retrieval_cases, retrieve_for_task
from core.retrieval.vector_store import get_vector_store_status

app = FastAPI(title="SCBKR Local Responsibility Model API", version="0.13.0-p13c")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_TASK_COUNTER = count(1)
TASKS: dict[str, dict[str, Any]] = {}
MODEL_SETTINGS: dict[str, Any] = dict(DEFAULT_MODEL_SETTINGS)
PERMISSIONS: dict[str, Any] = dict(DEFAULT_PERMISSION_SETTINGS)


def _now() -> str:
    return datetime.now(UTC).isoformat()



def _ensure_runtime() -> None:
    init_sqlite_runtime()


def _generate_task_id() -> str:
    """Generate a persisted-task ID that does not collide with memory or SQLite."""
    for _ in range(5):
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        task_id = f"task-{timestamp}-{uuid4().hex[:8]}"
        if task_id not in TASKS and load_task(task_id) is None:
            return task_id
    raise RuntimeError("failed to generate unique task_id after 5 attempts")


def _append_task_event(
    event_type: str,
    task: dict[str, Any],
    status_before: str | None = None,
    status_after: str | None = None,
    payload: dict[str, Any] | None = None,
    message: str | None = None,
    layer: str = "SYSTEM",
) -> dict[str, Any]:
    _ensure_runtime()
    event = build_ledger_event(
        event_type,
        task_id=task.get("task_id"),
        trace_id=task.get("trace_id"),
        ledger_id=task.get("ledger_id"),
        status_before=status_before,
        status_after=status_after,
        layer=layer,
        payload=payload or {},
        message=message,
    )
    append_result = append_ledger_event(event)
    save_ledger_index(event, line_number=append_result["line_number"], jsonl_path=append_result["ledger_path"])
    return event

def _public_model_settings() -> dict[str, Any]:
    return {**MODEL_SETTINGS, "api_key": mask_api_key(MODEL_SETTINGS.get("api_key", ""))}


def _get_task(task_id: str) -> dict[str, Any]:
    task = TASKS.get(task_id)
    if task is not None:
        return task
    persisted_task = load_task(task_id)
    if persisted_task is None:
        raise HTTPException(status_code=404, detail="task not found")
    TASKS[task_id] = persisted_task
    return persisted_task


def _post_openai_compatible(settings: dict[str, Any], messages: list[dict[str, str]]) -> dict[str, Any]:
    payload = build_chat_completion_payload(messages, settings)
    url = settings["base_url"].rstrip("/") + "/chat/completions"
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=build_headers(settings),
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings["timeout"]) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"model http error: {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"model connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("model connection timed out") from exc


@app.get("/health")
def health() -> dict[str, Any]:
    _ensure_runtime()
    return {"ok": True, "service": "scbkr-api", "runtime": "P13-A/B/C SQLite + JSONL retrieval runtime"}


@app.get("/api/system/status")
def system_status() -> dict[str, Any]:
    return {
        "api_url": "http://localhost:8787",
        "web_url": "http://localhost:5500",
        "runtime": "P13-A/B/C SQLite + JSONL retrieval runtime",
        "physical_write_performed": False,
        "tasks_count": len(TASKS),
        "model": _public_model_settings(),
        "permissions": PERMISSIONS,
    }


@app.get("/api/settings/model")
def get_model_settings() -> dict[str, Any]:
    return _public_model_settings()


@app.post("/api/settings/model")
def set_model_settings(payload: dict[str, Any]) -> dict[str, Any]:
    next_settings = {**MODEL_SETTINGS, **payload, "last_test_status": "untested", "updated_at": _now()}
    if "api_key" not in payload:
        next_settings["api_key"] = MODEL_SETTINGS.get("api_key", "")
    validate_model_settings(next_settings)
    MODEL_SETTINGS.clear()
    MODEL_SETTINGS.update(next_settings)
    return _public_model_settings()


@app.get("/api/settings/permissions")
def get_permissions() -> dict[str, Any]:
    return PERMISSIONS


@app.post("/api/settings/permissions")
def set_permissions(payload: dict[str, Any]) -> dict[str, Any]:
    next_permissions = {**PERMISSIONS, **payload, "updated_at": _now()}
    validate_permission_settings(next_permissions)
    PERMISSIONS.clear()
    PERMISSIONS.update(next_permissions)
    return PERMISSIONS


@app.post("/api/model/test")
def test_model() -> dict[str, Any]:
    try:
        if not MODEL_SETTINGS.get("model_name", "").strip():
            status = make_test_status(False, "model_name 未填，不可通過測試")
        else:
            if MODEL_SETTINGS["mode"] in ("external", "hybrid"):
                assert_permission_allowed(PERMISSIONS, "external_api_call")
            response = _post_openai_compatible(
                MODEL_SETTINGS,
                [{"role": "user", "content": "請回覆 SCBKR model gateway test。"}],
            )
            status = make_test_status(True, parse_chat_completion_response(response))
    except PermissionError as exc:
        status = make_test_status(False, f"external_api_call 權限或高風險確認未通過: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        status = make_test_status(False, str(exc))
    MODEL_SETTINGS.update(status)
    MODEL_SETTINGS["enabled"] = status["last_test_status"] == "success"
    return _public_model_settings()


@app.post("/api/tasks/create")
def create_task(payload: dict[str, Any]) -> dict[str, Any]:
    raw_input = str(payload.get("raw_input", "")).strip()
    if not raw_input:
        raise HTTPException(status_code=400, detail="raw_input is required")
    task_id = _generate_task_id()
    task = {
        "task_id": task_id,
        "trace_id": f"trace-{task_id}",
        "ledger_id": f"ledger-{task_id}-in-memory",
        "task_name": payload.get("task_name") or raw_input[:40],
        "task_type": payload.get("task_type", "general"),
        "raw_input": raw_input,
        "status": "waiting_scbkr",
        "confirmed": False,
        "review_passed": False,
        "storage_confirmed": False,
        "physical_write_performed": False,
        "runtime": "P13-A/B/C SQLite + JSONL retrieval runtime",
    }
    TASKS[task_id] = task
    save_task(task)
    _append_task_event("task_created", task, status_after=task["status"], payload={"task_type": task["task_type"]})
    return task


@app.post("/api/tasks/{task_id}/scbkr")
def create_scbkr(task_id: str) -> dict[str, Any]:
    task = _get_task(task_id)
    status_before = task.get("status")
    task["scbkr"] = create_scbkr_draft(task["raw_input"], task["task_type"])
    task["status"] = "waiting_user_confirm"
    save_task(task)
    save_scbkr_confirmation(task_id, task["scbkr"])
    _append_task_event(
        "scbkr_draft_created",
        task,
        status_before=status_before,
        status_after=task["status"],
        payload={"confirmation_status": task["scbkr"].get("confirmation_status")},
    )
    return task


@app.post("/api/tasks/{task_id}/confirm")
def confirm_task(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    task = _get_task(task_id)
    if "scbkr" not in task:
        raise HTTPException(status_code=400, detail="SCBKR draft required before confirm")
    payload = payload or {}
    confirm_all_dimensions(
        task["scbkr"],
        confirmed_by=payload.get("confirmed_by", "user"),
        confirmation_statement=payload.get("confirmation_statement"),
        signature=payload.get("signature"),
    )
    status_before = task.get("status")
    if all_dimensions_confirmed(task["scbkr"]):
        task["confirmed"] = True
        task["status"] = "confirmed"
    save_task(task)
    save_scbkr_confirmation(task_id, task["scbkr"])
    _append_task_event(
        "scbkr_confirmed",
        task,
        status_before=status_before,
        status_after=task["status"],
        payload={"confirmed_snapshot_hash": task["scbkr"].get("confirmed_snapshot_hash")},
    )
    return task


@app.post("/api/tasks/{task_id}/generate")
def generate(task_id: str) -> dict[str, Any]:
    task = _get_task(task_id)
    status_before = task.get("status")
    _append_task_event("generation_requested", task, status_before=status_before, status_after=status_before)
    try:
        assert_permission_allowed(PERMISSIONS, "model_generate")
        if MODEL_SETTINGS["mode"] in ("external", "hybrid"):
            assert_permission_allowed(PERMISSIONS, "external_api_call")
        assert_task_can_generate(task, task.get("scbkr", {}), MODEL_SETTINGS, PERMISSIONS)
        response = _post_openai_compatible(MODEL_SETTINGS, build_generation_messages(task, task["scbkr"]))
        task["generation_result"] = build_generation_result(task, task["scbkr"], parse_chat_completion_response(response))
        task["status"] = "waiting_review"
        save_task(task)
        _append_task_event(
            "generation_completed",
            task,
            status_before=status_before,
            status_after=task["status"],
            payload={"generation_status": task["generation_result"].get("status")},
        )
        return task
    except PermissionError as exc:
        _append_task_event("generation_failed", task, status_before=status_before, status_after=task.get("status"), payload={"error": str(exc)})
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _append_task_event("generation_failed", task, status_before=status_before, status_after=task.get("status"), payload={"error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/review")
def review(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    try:
        result = apply_review_decision(
            task,
            task.get("generation_result", {}),
            payload.get("review_decision", "pass"),
            payload.get("review_message", "P12 MVP user review"),
            rollback_layer=payload.get("rollback_layer"),
            reviewer_signature=payload.get("reviewer_signature"),
        )
        status_before = task.get("status")
        task["review_result"] = result
        task["review_passed"] = result.get("review_passed", False)
        task["status"] = result["status"]
        save_task(task)
        event_type = "rollback_requested" if result.get("status") == "rollback_requested" else result.get("status", "review_failed")
        if event_type not in ("review_passed", "review_failed", "rollback_requested"):
            event_type = "review_failed"
        _append_task_event(event_type, task, status_before=status_before, status_after=task["status"], payload={"review_passed": task["review_passed"]})
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _require_payload_fields(payload: dict[str, Any], fields: list[str]) -> None:
    missing = [field for field in fields if field not in payload or payload[field] in (None, "")]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing required fields: {', '.join(missing)}")


@app.post("/api/tasks/{task_id}/memory-rule-draft")
def memory_rule_draft(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    required_fields = [
        "user_failure_judgement",
        "rule_statement",
        "applies_to_task_types",
        "trigger_conditions",
        "forbidden_patterns",
        "required_behavior",
    ]
    _require_payload_fields(payload, required_fields)
    try:
        if task.get("review_result", {}).get("status") != "review_failed":
            raise ValueError("task review_result.status must be review_failed before memory rule draft")
        status_before = task.get("status")
        task["memory_rule_draft"] = build_memory_rule_draft(
            task,
            task["review_result"],
            payload["user_failure_judgement"],
            payload["rule_statement"],
            payload["applies_to_task_types"],
            payload["trigger_conditions"],
            payload["forbidden_patterns"],
            payload["required_behavior"],
        )
        save_task(task)
        _append_task_event("memory_rule_draft_created", task, status_before=status_before, status_after=task.get("status"), payload={"rule_status": task["memory_rule_draft"].get("rule_status")})
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/storage-request")
def storage_request(task_id: str) -> dict[str, Any]:
    task = _get_task(task_id)
    try:
        status_before = task.get("status")
        task["storage_request"] = build_storage_request(task, task.get("review_result", {}))
        task["status"] = "waiting_storage_confirm"
        save_task(task)
        _append_task_event("storage_request_created", task, status_before=status_before, status_after=task["status"], payload={"candidate_targets": task["storage_request"].get("candidate_targets", [])})
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/storage-confirm")
def storage_confirm(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    status_before = task.get("status")
    requested_event: dict[str, Any] | None = None
    try:
        if task.get("review_passed") is not True or task.get("review_result", {}).get("review_passed") is not True:
            raise ValueError("storage commit requires review_passed task")
        if task.get("status") not in ("review_passed", "waiting_storage_confirm", "storage_requested"):
            raise ValueError("task status must allow storage commit")
        for required_key in ("generation_result", "review_result", "scbkr"):
            if required_key not in task:
                raise ValueError(f"{required_key} is required before storage commit")
        if not all_dimensions_confirmed(task["scbkr"]):
            raise ValueError("SCBKR must be fully confirmed before storage commit")
        if "storage_request" not in task and "storage_plan" not in task:
            raise ValueError("storage_request or storage_plan is required before storage commit")
        if payload.get("storage_confirmed") is not True:
            raise ValueError("storage_confirmed=true is required")
        if payload.get("confirmed_by") != "user":
            raise ValueError("confirmed_by=user is required")
        signature = str(payload.get("signature") or payload.get("storage_signature") or "").strip()
        if not signature:
            raise ValueError("signature is required")

        selected_targets = payload.get("selected_targets") or ["corpus", "logic", "exports"]
        plan_targets = [target for target in selected_targets if target in ("vector_db", "corpus", "logic", "memory")]
        if not plan_targets:
            plan_targets = ["corpus", "logic"]
        requested_event = _append_task_event(
            "storage_physical_write_requested",
            task,
            status_before=status_before,
            status_after=status_before,
            payload={"selected_targets": selected_targets, "confirmed_by": "user"},
        )
        task["storage_plan"] = build_storage_commit_plan(
            task,
            task.get("review_result", {}),
            plan_targets,
            storage_signature=signature if "memory" in plan_targets else None,
            storage_notes=payload.get("storage_notes", "P13-B physical storage commit."),
        )
        task["storage_plan"]["selected_targets"] = list(dict.fromkeys([*selected_targets, "corpus", "logic", "exports"]))
        task["storage_plan"]["physical_write_performed"] = False
        items = commit_storage_items(task, task["storage_plan"], source_event_id=requested_event["event_id"])
        for item in items:
            save_storage_item(item)
            _append_task_event(
                "storage_item_written",
                task,
                status_before=status_before,
                status_after="storage_committed",
                payload={
                    "target": item.get("target"),
                    "content_hash": item.get("content_hash"),
                    "relative_path": item.get("relative_path"),
                    "physical_write_performed": True,
                },
            )
        task["storage_items"] = items
        task["storage_confirmed"] = True
        task["physical_write_performed"] = True
        task["status"] = "storage_committed"
        task["storage_plan"]["physical_write_performed"] = True
        task["storage_plan"]["next_required_action"] = "storage_committed"
        save_task(task)
        _append_task_event(
            "storage_physical_write_completed",
            task,
            status_before=status_before,
            status_after=task["status"],
            payload={"item_count": len(items), "physical_write_performed": True},
        )
        return task
    except PermissionError as exc:
        _append_task_event("storage_physical_write_failed", task, status_before=status_before, status_after=task.get("status"), payload={"error_message": str(exc), "physical_write_performed": False})
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        task["physical_write_performed"] = False
        _append_task_event("storage_physical_write_failed", task, status_before=status_before, status_after=task.get("status"), payload={"error_message": str(exc), "physical_write_performed": False})
        save_task(task)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/memory-rule-confirm")
def memory_rule_confirm(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    status_before = task.get("status")
    try:
        if task.get("review_passed") is not False and task.get("status") != "review_failed":
            raise ValueError("memory rule storage requires review_failed task")
        if "failure_report_draft" not in task.get("review_result", {}) and task.get("review_result", {}).get("status") != "review_failed":
            raise ValueError("review_failed result or failure_report_draft is required")
        if "memory_rule_draft" not in task:
            raise ValueError("memory_rule_draft is required before confirmation")
        reviewer_signature = str(payload.get("reviewer_signature", "")).strip()
        if not reviewer_signature:
            raise ValueError("reviewer_signature is required")
        requested_event = _append_task_event(
            "memory_rule_physical_write_requested",
            task,
            status_before=status_before,
            status_after=status_before,
            payload={"physical_write_performed": False},
        )
        task["memory_rule_confirmed_plan"] = confirm_memory_rule_plan(task["memory_rule_draft"], reviewer_signature)
        rule = commit_memory_rule(task, source_event_id=requested_event["event_id"])
        save_memory_rule(rule)
        task["memory_rule_stored"] = True
        task["memory_rule_physical_write_performed"] = True
        task["physical_write_performed"] = task.get("physical_write_performed", False)
        save_task(task)
        _append_task_event(
            "memory_rule_written",
            task,
            status_before=status_before,
            status_after=task.get("status"),
            payload={"rule_hash": rule.get("rule_hash"), "relative_path": rule.get("relative_path")},
        )
        _append_task_event(
            "memory_rule_physical_write_completed",
            task,
            status_before=status_before,
            status_after=task.get("status"),
            payload={"physical_write_performed": True, "rule_hash": rule.get("rule_hash")},
        )
        return task
    except PermissionError as exc:
        _append_task_event("memory_rule_physical_write_failed", task, status_before=status_before, status_after=task.get("status"), payload={"error_message": str(exc)})
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        task["memory_rule_stored"] = False
        task["memory_rule_physical_write_performed"] = False
        save_task(task)
        _append_task_event("memory_rule_physical_write_failed", task, status_before=status_before, status_after=task.get("status"), payload={"error_message": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/retrieval/index")
def index_task_retrieval(task_id: str) -> dict[str, Any]:
    task = _get_task(task_id)
    if task.get("status") != "storage_committed" or task.get("physical_write_performed") is not True or task.get("review_passed") is not True:
        raise HTTPException(status_code=400, detail="storage_committed review_passed task with physical writes required")
    try:
        return index_task_storage_cases(task)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/memory-rules/index")
def index_memory_rules() -> dict[str, Any]:
    indexed = []
    for rule in list_persisted_memory_rules(limit=200):
        try:
            indexed.append(index_memory_rule_case(rule))
        except ValueError:
            continue
    return {"indexed_cases": indexed, "backend_status": get_vector_store_status()}


@app.post("/api/retrieval/query")
def retrieval_query(payload: dict[str, Any]) -> dict[str, Any]:
    case_type = payload.get("case_type")
    if case_type == "any":
        case_type = None
    try:
        return query_retrieval_cases(str(payload.get("query_text", "")), top_k=int(payload.get("top_k", 3)), case_type=case_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/retrieval/query")
def task_retrieval_query(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    task = _get_task(task_id)
    try:
        result = retrieve_for_task(task, top_k=int((payload or {}).get("top_k", 3)))
        TASKS[task_id] = task
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/tasks")
def list_tasks() -> dict[str, Any]:
    return {"tasks": list_persisted_tasks(limit=50)}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    return _get_task(task_id)


@app.get("/api/tasks/{task_id}/storage-items")
def get_task_storage_items(task_id: str) -> dict[str, Any]:
    _get_task(task_id)
    return {"storage_items": list_persisted_storage_items(task_id=task_id, limit=50)}


@app.get("/api/memory-rules")
def get_memory_rules() -> dict[str, Any]:
    return {"memory_rules": list_persisted_memory_rules(limit=50)}


@app.get("/api/tasks/{task_id}/ledger")
def get_task_ledger_events(task_id: str) -> dict[str, Any]:
    _get_task(task_id)
    return {"task_id": task_id, "events": read_ledger_events(task_id=task_id), "index": get_task_ledger(task_id)}


@app.post("/api/ledger/rebuild-index")
def rebuild_ledger_index() -> dict[str, Any]:
    return rebuild_ledger_index_from_jsonl()
