"""P13-A FastAPI MVP runtime for the local SCBKR Web App.

Tasks are cached in memory and persisted to local SQLite. Flow events are
appended to a JSONL replay ledger; no ChromaDB, memory store, or desktop runtime
is initialized here.
"""

from datetime import UTC, datetime
from itertools import count
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
from core.storage.sqlite_runtime import (
    get_task_ledger,
    init_sqlite_runtime,
    list_tasks as list_persisted_tasks,
    load_task,
    save_ledger_index,
    save_scbkr_confirmation,
    save_task,
)
from core.storage.storage_plan import build_storage_commit_plan
from core.storage.storage_request import build_storage_request
from core.workflow.generation_flow import build_generation_messages, assert_task_can_generate
from core.workflow.generation_result import build_generation_result
from core.workflow.review_flow import apply_review_decision

app = FastAPI(title="SCBKR Local Responsibility Model API", version="0.13.0-p13a")
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
    return {"ok": True, "service": "scbkr-api", "runtime": "P13-A SQLite + JSONL runtime"}


@app.get("/api/system/status")
def system_status() -> dict[str, Any]:
    return {
        "api_url": "http://localhost:8787",
        "web_url": "http://localhost:5500",
        "runtime": "P13-A SQLite + JSONL runtime",
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
    task_id = f"task-{next(_TASK_COUNTER):04d}"
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
        "runtime": "P13-A SQLite + JSONL runtime",
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
    try:
        status_before = task.get("status")
        task["storage_plan"] = build_storage_commit_plan(
            task,
            task.get("review_result", {}),
            payload.get("selected_targets", ["vector_db"]),
            storage_signature=payload.get("storage_signature"),
            storage_notes=payload.get("storage_notes", "P13-A MVP plan only; no physical write."),
        )
        task["storage_confirmed"] = True
        task["physical_write_performed"] = False
        task["status"] = "completed"
        save_task(task)
        _append_task_event(
            "storage_plan_confirmed",
            task,
            status_before=status_before,
            status_after=task["status"],
            payload={
                "selected_targets": task["storage_plan"].get("selected_targets", []),
                "physical_write_performed": False,
            },
        )
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/memory-rule-confirm")
def memory_rule_confirm(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    try:
        if "memory_rule_draft" not in task:
            raise ValueError("memory_rule_draft is required before confirmation")
        reviewer_signature = payload.get("reviewer_signature", "")
        if not str(reviewer_signature).strip():
            raise ValueError("reviewer_signature is required")
        status_before = task.get("status")
        task["memory_rule_confirmed_plan"] = confirm_memory_rule_plan(task["memory_rule_draft"], reviewer_signature)
        task["physical_write_performed"] = False
        save_task(task)
        _append_task_event(
            "memory_rule_confirmed_plan_created",
            task,
            status_before=status_before,
            status_after=task.get("status"),
            payload={"physical_write_performed": False},
        )
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/tasks")
def list_tasks() -> dict[str, Any]:
    return {"tasks": list_persisted_tasks(limit=50)}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    return _get_task(task_id)


@app.get("/api/tasks/{task_id}/ledger")
def get_task_ledger_events(task_id: str) -> dict[str, Any]:
    _get_task(task_id)
    return {"task_id": task_id, "events": read_ledger_events(task_id=task_id), "index": get_task_ledger(task_id)}


@app.post("/api/ledger/rebuild-index")
def rebuild_ledger_index() -> dict[str, Any]:
    return rebuild_ledger_index_from_jsonl()
