"""P12 FastAPI MVP runtime for the local SCBKR Web App.

This module intentionally uses an in-memory store. It does not write SQLite,
ChromaDB, ledger JSONL, memory, or the four storage targets.
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
from core.review_rules.rule_confirmation import confirm_memory_rule_plan
from core.review_rules.rule_draft import build_memory_rule_draft
from core.scbkr.generator import create_scbkr_draft
from core.storage.storage_plan import build_storage_commit_plan
from core.storage.storage_request import build_storage_request
from core.workflow.generation_flow import build_generation_messages, assert_task_can_generate
from core.workflow.generation_result import build_generation_result
from core.workflow.review_flow import apply_review_decision

app = FastAPI(title="SCBKR Local Responsibility Model API", version="0.12.0-mvp")
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


def _public_model_settings() -> dict[str, Any]:
    return {**MODEL_SETTINGS, "api_key": mask_api_key(MODEL_SETTINGS.get("api_key", ""))}


def _get_task(task_id: str) -> dict[str, Any]:
    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


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
    return {"ok": True, "service": "scbkr-api", "runtime": "MVP in-memory runtime"}


@app.get("/api/system/status")
def system_status() -> dict[str, Any]:
    return {
        "api_url": "http://localhost:8787",
        "web_url": "http://localhost:5500",
        "runtime": "MVP in-memory runtime",
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
        "runtime": "MVP in-memory runtime",
    }
    TASKS[task_id] = task
    return task


@app.post("/api/tasks/{task_id}/scbkr")
def create_scbkr(task_id: str) -> dict[str, Any]:
    task = _get_task(task_id)
    task["scbkr"] = create_scbkr_draft(task["raw_input"], task["task_type"])
    task["status"] = "waiting_user_confirm"
    return task


@app.post("/api/tasks/{task_id}/confirm")
def confirm_task(task_id: str) -> dict[str, Any]:
    task = _get_task(task_id)
    if "scbkr" not in task:
        raise HTTPException(status_code=400, detail="SCBKR draft required before confirm")
    task["confirmed"] = True
    task["status"] = "confirmed"
    task["scbkr"]["confirmation_status"] = "confirmed"
    for key in ("S", "C", "B", "K", "R"):
        task["scbkr"][key]["confirmation_status"] = "confirmed"
    return task


@app.post("/api/tasks/{task_id}/generate")
def generate(task_id: str) -> dict[str, Any]:
    task = _get_task(task_id)
    try:
        assert_permission_allowed(PERMISSIONS, "model_generate")
        if MODEL_SETTINGS["mode"] in ("external", "hybrid"):
            assert_permission_allowed(PERMISSIONS, "external_api_call")
        assert_task_can_generate(task, task.get("scbkr", {}), MODEL_SETTINGS, PERMISSIONS)
        response = _post_openai_compatible(MODEL_SETTINGS, build_generation_messages(task, task["scbkr"]))
        task["generation_result"] = build_generation_result(task, task["scbkr"], parse_chat_completion_response(response))
        task["status"] = "waiting_review"
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
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
        task["review_result"] = result
        task["review_passed"] = result.get("review_passed", False)
        task["status"] = result["status"]
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
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/storage-request")
def storage_request(task_id: str) -> dict[str, Any]:
    task = _get_task(task_id)
    try:
        task["storage_request"] = build_storage_request(task, task.get("review_result", {}))
        task["status"] = "waiting_storage_confirm"
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/storage-confirm")
def storage_confirm(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    try:
        task["storage_plan"] = build_storage_commit_plan(
            task,
            task.get("review_result", {}),
            payload.get("selected_targets", ["vector_db"]),
            storage_signature=payload.get("storage_signature"),
            storage_notes=payload.get("storage_notes", "P12 MVP plan only; no physical write."),
        )
        task["storage_confirmed"] = True
        task["status"] = "completed"
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
        task["memory_rule_confirmed_plan"] = confirm_memory_rule_plan(task["memory_rule_draft"], reviewer_signature)
        return task
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    return _get_task(task_id)
