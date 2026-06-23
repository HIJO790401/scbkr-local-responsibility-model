"""P13-A/B/C FastAPI MVP runtime for the local SCBKR Web App.

Tasks are cached in memory and persisted to local SQLite. Flow events are
appended to a JSONL replay ledger; retrieval is advisory and no desktop runtime is initialized here.
"""

from datetime import UTC, datetime
from copy import deepcopy
from itertools import count
from uuid import uuid4
from typing import Any
from urllib.parse import urlparse
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from core.generation.sandbox_model import SANDBOX_PROVIDER, generate_with_sandbox_model
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
from core.storage.physical_store import commit_memory_rule, commit_storage_items, hash_payload
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
    save_task as _persist_task,
)
from core.storage.storage_plan import build_storage_commit_plan
from core.storage.storage_request import build_storage_request
from core.storage.storage_suggestion import deterministic_storage_suggestion, to_plan_target, to_ui_target, validate_ui_targets
from core.workflow.generation_flow import build_generation_messages, assert_task_can_generate, build_scbkr_draft_generation_messages
from core.workflow.generation_result import build_generation_result
from core.workflow.review_flow import apply_review_decision
from core.retrieval.retrieval_runtime import index_task_storage_cases, index_memory_rule_case, query_retrieval_cases, retrieve_for_task
from core.retrieval.vector_store import get_vector_store_status
from core.storage.runtime_paths import current_data_dir

LOCAL_DESKTOP_API_BASE_URL = "http://127.0.0.1:8787"
LOCAL_DESKTOP_CORS_ORIGINS = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:8787",
    "http://localhost:8787",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "null",
]
LOCAL_DESKTOP_CORS_METHODS = ["OPTIONS", "GET", "POST", "PUT", "PATCH", "DELETE"]

SCBKR_CONFIRMATION_REQUIRED_FIELDS = {
    "S": ["task_name", "user_instruction", "task_subject", "input_content", "output_format", "interface_type", "platform_type"],
    "C": ["flow_steps", "execution_order", "data_flow", "event_flow", "core_logic", "dependencies", "failure_impact", "test_conditions"],
    "B": ["data_read_scope", "data_write_scope", "local_scope", "external_scope", "permission_switches", "stop_conditions", "error_handling", "storage_conditions"],
    "K": ["references", "technical_docs", "style_settings", "framework_choice", "model_basis", "source_credibility"],
    "R": ["expected_outputs", "acceptance_criteria", "ledger_requirements", "storage_options", "signature_status", "review_status", "replay_requirements"],
}

app = FastAPI(title="SCBKR Local Responsibility Model API", version="0.14.0-p14c-preview")
app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_DESKTOP_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=LOCAL_DESKTOP_CORS_METHODS,
    allow_headers=["*"],
)

_TASK_COUNTER = count(1)
TASKS: dict[str, dict[str, Any]] = {}
MODEL_SETTINGS: dict[str, Any] = dict(DEFAULT_MODEL_SETTINGS)
PERMISSIONS: dict[str, Any] = dict(DEFAULT_PERMISSION_SETTINGS)


IDENTITY_ZH = "我是 SCBKR 責任鏈語言模型，由台灣台中「語意防火牆」創辦人許文耀／沈耀888pi 研發，透過使用者自接的本地 LLM 或 API 運作。我的目標是讓模型在生成前先交代任務、邊界、依據與責任，協助降低 token、算力與重複推理消耗。使用者可以自訂規則、建立閉環、審計模型輸出，降低模型幻覺風險。若需要規則庫、合作或相關資訊，可寄信至 [ken0963521@gmail.com](mailto:ken0963521@gmail.com) 聯繫。"
IDENTITY_EN = "I am the SCBKR Responsibility-Chain Language Model, developed by Wen-Yao Hsu / ShenYao888pi, founder of Semantic Firewall in Taichung, Taiwan. I run through a user-connected local LLM or API. My goal is to make models declare the task, boundary, basis, and responsibility before generation, helping reduce token usage, compute cost, and repeated reasoning. Users can customize rules and build closed-loop workflows to reduce hallucination risk. For rule libraries or collaboration, contact [ken0963521@gmail.com](mailto:ken0963521@gmail.com)."
SUGGESTION_TRIGGERS = ("我覺得", "不該", "不得", "必須", "驗收", "判準", "規則", "偏好", "流程", "邊界", "入庫")
HIGH_PRIVILEGE_DRAFT_KEYS = {"review_passed", "storage_confirmed", "physical_write_performed", "confirmed"}
SCBKR_COMMITTED_EDIT_MESSAGE = "本任務已寫入資料中心或記憶庫規則，不能直接改寫原 SCBKR。請建立新版本或新任務。已入庫或已完成 / 已寫入記憶庫規則的任務不可直接改寫 SCBKR。"
SCBKR_INVALID_PATCH_MESSAGE = "模型提出的修改草案不完整，未套用到任務。原本的 SCBKR 已保留，請重新產生修改草案或手動修改欄位。"


def _looks_english(text: str) -> bool:
    letters = sum(ch.isascii() and ch.isalpha() for ch in text)
    non_ascii = sum(not ch.isascii() for ch in text)
    return letters > 0 and letters >= non_ascii


def _is_identity_question(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("who are you", "what model are you", "introduce yourself")) or any(token in text for token in ("你是誰", "你是什么模型", "你是什麼模型", "介紹你自己"))


def _build_chat_suggestion(user_text: str) -> dict[str, Any]:
    return {
        "title": "這段內容可能適合建立成 SCBKR 規則 / 任務",
        "user_original": user_text,
        "reusable_point": "這段包含可重用的判斷、偏好、禁止條件或驗收邏輯。",
        "suggested_instruction": "請將這段使用者判斷整理成一條可驗收、可回放、可入記憶庫的 SCBKR 責任鏈規則。",
        "suggested_type": "記憶規則 / 情報判準",
        "suggested_reason": "內容含有未來可引用的判定條件；正式化前仍需經任務入口與 Workbench 使用者確認。",
        "suggested_write_direction": "記憶庫",
        "risk_notice": "建立確認單後仍需使用者確認，不會自動入庫。",
        "actions": ["送到任務入口", "保留普通聊天", "不再提示這段"],
    }


def _contains_forbidden_draft_state(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in HIGH_PRIVILEGE_DRAFT_KEYS and item is True:
                return True
            if key == "confirmation_status" and item == "confirmed":
                return True
            if _contains_forbidden_draft_state(item):
                return True
    if isinstance(value, list):
        return any(_contains_forbidden_draft_state(item) for item in value)
    return False


def is_loopback_model_url(base_url: str | None) -> bool:
    parsed = urlparse(base_url or "")
    hostname = (parsed.hostname or "").lower()
    return hostname in {"localhost", "127.0.0.1", "::1"}


EXTERNAL_API_LOOPBACK_ERROR = "目前模型網址不是本機 loopback，會把內容送出本機。請開啟 external_api 權限，或改用 127.0.0.1 / localhost 的本機模型網址。"


def _model_call_requires_external_api_permission(settings: dict[str, Any]) -> bool:
    if settings.get("mode") == "sandbox":
        return False
    if is_loopback_model_url(settings.get("base_url")):
        return False
    return True


def _model_draft_requires_external_api_permission(settings: dict[str, Any]) -> bool:
    return _model_call_requires_external_api_permission(settings)


def _assert_model_gateway_call_allowed(settings: dict[str, Any]) -> None:
    assert_permission_allowed(PERMISSIONS, "model_generate")
    if _model_call_requires_external_api_permission(settings):
        assert_permission_allowed(PERMISSIONS, "external_api_call")


def _validate_model_authored_scbkr_draft(candidate: Any) -> dict[str, Any]:
    validate_scbkr_draft_for_confirmation(candidate)
    if _contains_forbidden_draft_state(candidate):
        raise ValueError("model-authored draft contains forbidden confirmed/high-privilege state")
    status = candidate.get("confirmation_status") or candidate.get("S", {}).get("confirmation_status")
    if status not in ("draft", "waiting_user_confirm"):
        raise ValueError("confirmation_status must be draft or waiting_user_confirm")
    return candidate


def _model_connected() -> bool:
    return MODEL_SETTINGS.get("enabled") is True and MODEL_SETTINGS.get("last_test_status") == "success"


def _build_four_store_context(raw_input: str, task_id: str | None = None) -> dict[str, Any]:
    """Read confirmed Data Center/four-store evidence before model drafting."""
    hits: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    try:
        retrieval = query_retrieval_cases(raw_input, task_id=task_id, top_k=5)
    except Exception as exc:
        retrieval = {"backend": "unavailable", "candidates": [], "error": str(exc)}
    for candidate in retrieval.get("candidates", []) or []:
        case_type = str(candidate.get("case_type") or candidate.get("target") or "vector")
        source_store = "memory" if "memory" in case_type else "vector"
        text_value = str(candidate.get("retrieval_text", ""))
        hit = {"source_store": source_store, "rule": text_value[:800], "case_id": candidate.get("case_id"), "status": "沿用", "rule_confirmed": True, "score": candidate.get("score")}
        hits.append(hit)
        if any(token in text_value for token in ("不得", "禁止", "不准", "must not")):
            hit["must_cite"] = True
    for item in list_persisted_storage_items(limit=20):
        target = item.get("target")
        if target in ("corpus", "logic", "memory"):
            hits.append({"source_store": target, "rule": str((item.get("payload") or item).get("summary") or item.get("relative_path") or item.get("hash"))[:800], "status": "待確認" if not item.get("task_id") else "沿用", "rule_confirmed": bool(item.get("task_id")), "storage_item_id": item.get("item_id")})
    for rule in list_persisted_memory_rules(limit=20):
        text_value = str(rule.get("rule_text") or rule.get("memory_rule") or rule.get("payload") or rule)
        hits.append({"source_store": "memory", "rule": text_value[:800], "status": "沿用", "rule_confirmed": True, "must_cite": any(t in text_value for t in ("不得", "禁止", "不准", "must not")), "memory_rule_id": rule.get("rule_id")})
    return {"retrieval_first": True, "query": raw_input, "retrieval_result": retrieval, "hits": hits, "conflicts": conflicts, "no_confirmed_rules": not any(h.get("rule_confirmed") for h in hits), "must_cite_confirmed_rules": [h for h in hits if h.get("rule_confirmed") and h.get("must_cite")]}


def _model_authored_scbkr_draft(raw_input: str, task_type: str, retrieval_context: dict[str, Any] | None = None) -> tuple[dict[str, Any], bool, str | None]:
    fallback = False
    draft = None
    skipped_reason = None
    if MODEL_SETTINGS.get("enabled") is True and MODEL_SETTINGS.get("mode") != "sandbox":
        try:
            if _model_draft_requires_external_api_permission(MODEL_SETTINGS) and PERMISSIONS.get("external_api") is not True:
                skipped_reason = "external_api_permission_disabled"
                raise PermissionError(skipped_reason)
            response = _post_openai_compatible(MODEL_SETTINGS, build_scbkr_draft_generation_messages(raw_input, task_type, retrieval_context))
            draft = json.loads(parse_chat_completion_response(response))
            draft = _validate_model_authored_scbkr_draft(draft)
        except PermissionError:
            draft = None
        except Exception as exc:
            skipped_reason = f"model_unavailable_or_invalid_json: {exc}"
            draft = None
    else:
        skipped_reason = "model_not_connected"
    if draft is None:
        draft = create_scbkr_draft(raw_input, task_type)
        fallback = True
        if skipped_reason is None:
            skipped_reason = "model_unavailable_or_invalid_json"
    draft["confirmation_status"] = "draft"
    draft["model_authored"] = True
    draft["draft_source"] = "fallback" if fallback else "model"
    draft["fallback_used"] = fallback
    draft["data_center_context"] = retrieval_context or {"hits": [], "no_confirmed_rules": True}
    draft["referenced_sources"] = (retrieval_context or {}).get("hits", [])
    if fallback:
        draft["fallback_reason"] = skipped_reason or "model_unavailable_or_invalid_json"
    if skipped_reason:
        draft["draft_model_call_skipped_reason"] = skipped_reason
    return draft, fallback, skipped_reason


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


def _is_empty_confirmation_value(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def validate_scbkr_draft_for_confirmation(candidate: Any) -> None:
    """Reject incomplete SCBKR drafts before sealing confirmed snapshots."""
    if not isinstance(candidate, dict):
        raise HTTPException(status_code=400, detail="SCBKR draft must be an object")
    problems: list[str] = []
    for dimension, required_fields in SCBKR_CONFIRMATION_REQUIRED_FIELDS.items():
        if dimension not in candidate:
            problems.append(f"{dimension}: missing dimension")
            continue
        dimension_payload = candidate[dimension]
        if not isinstance(dimension_payload, dict):
            problems.append(f"{dimension}: dimension must be object")
            continue
        if not dimension_payload:
            problems.append(f"{dimension}: empty dimension")
            continue
        for field in required_fields:
            if field not in dimension_payload:
                problems.append(f"{dimension}.{field}: missing field")
            elif _is_empty_confirmation_value(dimension_payload[field]):
                problems.append(f"{dimension}.{field}: empty field")
    if problems:
        raise HTTPException(status_code=400, detail="SCBKR draft is incomplete: " + "; ".join(problems))


def _invalidate_downstream_after_scbkr_revision(task: dict[str, Any], status_before: str | None) -> bool:
    downstream_keys = (
        "generation_result",
        "review_result",
        "storage_request",
        "storage_plan",
        "storage_result",
        "completed_at",
        "final_result",
        "retrieval_indexing_result",
        "retrieval_indexing_pending_result",
    )
    removed_keys = [key for key in downstream_keys if key in task]
    had_downstream = bool(removed_keys) or any(
        task.get(key) for key in ("review_passed", "storage_confirmed", "physical_write_performed")
    )
    for key in removed_keys:
        task.pop(key, None)
    task["review_passed"] = False
    task["storage_confirmed"] = False
    task["physical_write_performed"] = False
    if task.get("status") in ("waiting_review", "review_passed", "waiting_storage_confirm", "storage_requested", "storage_committed", "completed"):
        task["status"] = "waiting_user_confirm"
    if had_downstream:
        _append_task_event(
            "scbkr_revised_downstream_invalidated",
            task,
            status_before=status_before,
            status_after=task.get("status"),
            payload={"removed_keys": removed_keys, "downstream_invalidated": True},
            message="SCBKR revised; downstream generation/review/storage artifacts invalidated.",
        )
    return had_downstream


def _memory_rule_physical_write_bound(task: dict[str, Any]) -> bool:
    if task.get("memory_rule_physical_write_performed") is True or task.get("memory_rule_stored") is True:
        return True
    if task.get("status") == "memory_rule_stored":
        return True
    if task.get("memory_rule_confirmed") is True and (task.get("memory_rule_result") or task.get("memory_rule_write_result")):
        return True
    return False


def _task_has_committed_physical_write(task: dict[str, Any]) -> bool:
    if task.get("physical_write_performed") is True:
        return True
    if task.get("storage_confirmed") is True and task.get("storage_result"):
        return True
    if task.get("status") in ("storage_committed", "completed"):
        return True
    return _memory_rule_physical_write_bound(task)


def _ensure_scbkr_edit_allowed(task: dict[str, Any]) -> None:
    if _task_has_committed_physical_write(task):
        raise HTTPException(status_code=400, detail=SCBKR_COMMITTED_EDIT_MESSAGE)


def _validate_scbkr_patch_after_draft(layer: str, after_draft: Any) -> None:
    if layer not in SCBKR_CONFIRMATION_REQUIRED_FIELDS:
        raise HTTPException(status_code=400, detail="patch.layer must be S/C/B/K/R")
    if not isinstance(after_draft, dict) or not after_draft:
        raise HTTPException(status_code=400, detail=SCBKR_INVALID_PATCH_MESSAGE)
    if _contains_forbidden_draft_state(after_draft):
        raise HTTPException(status_code=400, detail=SCBKR_INVALID_PATCH_MESSAGE)
    for field in SCBKR_CONFIRMATION_REQUIRED_FIELDS[layer]:
        if field not in after_draft or _is_empty_confirmation_value(after_draft[field]):
            raise HTTPException(status_code=400, detail=SCBKR_INVALID_PATCH_MESSAGE)



def _storage_plan_hash(plan: dict[str, Any]) -> str:
    return hash_payload(plan or {})


def _storage_commit_key(task: dict[str, Any], selected_targets: list[str], storage_plan_hash: str) -> str:
    snapshot_hash = (task.get("scbkr") or {}).get("confirmed_snapshot_hash") or hash_payload((task.get("scbkr") or {}).get("confirmed_snapshot") or task.get("scbkr") or {})
    return hash_payload({"task_id": task.get("task_id"), "selected_targets": sorted(selected_targets), "storage_plan_hash": storage_plan_hash, "confirmed_snapshot_hash": snapshot_hash})


def _already_committed_response(task: dict[str, Any]) -> dict[str, Any]:
    result = dict(task.get("storage_result") or {})
    result["already_committed"] = True
    result["message"] = "本任務已完成入庫，不能重複寫入。請到資料中心查看已寫入資料。"
    task["storage_result"] = result
    return _task_response(task, already_committed=True, message=result["message"])

def _task_response(task: dict[str, Any], **extra: Any) -> dict[str, Any]:
    response = dict(task)
    response.pop("downstream_invalidated", None)
    response.update(extra)
    return response

def _public_model_settings() -> dict[str, Any]:
    public = {**MODEL_SETTINGS, "api_key": mask_api_key(MODEL_SETTINGS.get("api_key", ""))}
    if MODEL_SETTINGS.get("mode") == "sandbox":
        public.update({"sandbox": True, "provider": SANDBOX_PROVIDER, "external_call_performed": False})
    return public


def _apply_sandbox_defaults(settings: dict[str, Any]) -> dict[str, Any]:
    return _apply_provider_defaults(settings, {})



def _apply_provider_defaults(settings: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    provider = settings.get("provider")
    if payload.get("mode") == "sandbox" or provider == SANDBOX_PROVIDER:
        settings.update({"mode": "sandbox", "provider": SANDBOX_PROVIDER, "base_url": "", "api_key": "", "model_name": SANDBOX_PROVIDER})
        return settings
    if provider == "lm_studio":
        settings["mode"] = "local"
        if not payload.get("base_url"):
            settings["base_url"] = "http://127.0.0.1:1234/v1"
        if not payload.get("api_key"):
            settings["api_key"] = "local"
    elif provider == "ollama":
        settings["mode"] = "local"
        if not payload.get("base_url"):
            settings["base_url"] = "http://127.0.0.1:11434/v1"
        if not payload.get("api_key"):
            settings["api_key"] = "local"
    elif provider == "openai_compatible":
        if settings.get("mode") not in ("external", "hybrid"):
            settings["mode"] = "external"
    return settings


def _friendly_model_error(settings: dict[str, Any], message: str) -> str:
    provider = settings.get("provider")
    if "api_key" in message.lower() or "authorization" in message.lower():
        return "API key 缺失或無效，請輸入正確 API key。"
    if provider in ("lm_studio", "ollama"):
        name = "LM Studio" if provider == "lm_studio" else "Ollama"
        return f"無法連線到本地模型，請確認 {name} Server 是否已啟動、Base URL 與模型名稱是否正確。"
    return "無法連線到 API 模型，請確認 API base URL、API key 與模型名稱。"

def _get_task(task_id: str) -> dict[str, Any]:
    task = TASKS.get(task_id)
    if task is not None:
        task.pop("downstream_invalidated", None)
        return task
    persisted_task = load_task(task_id)
    if persisted_task is None:
        raise HTTPException(status_code=404, detail="task not found")
    persisted_task.pop("downstream_invalidated", None)
    TASKS[task_id] = persisted_task
    return persisted_task


def save_task(task: dict[str, Any]) -> dict[str, Any]:
    task.pop("downstream_invalidated", None)
    persisted = _persist_task(task)
    TASKS[task["task_id"]] = task
    return persisted


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


def _try_model_storage_suggestion(task: dict[str, Any]) -> dict[str, Any] | None:
    if MODEL_SETTINGS.get("enabled") is not True or MODEL_SETTINGS.get("mode") == "sandbox":
        return None
    messages = [
        {"role": "system", "content": "Return JSON only. Suggest storage targets for SCBKR review-to-storage. Keys: suggestions.vector/corpus/logic/memory each with recommended boolean, reason string, planned_summary string."},
        {"role": "user", "content": json.dumps({"scbkr": task.get("scbkr"), "generation_result": task.get("generation_result"), "review_result": task.get("review_result")}, ensure_ascii=False)},
    ]
    response = _post_openai_compatible(MODEL_SETTINGS, messages)
    parsed = parse_chat_completion_response(response)
    data = json.loads(parsed)
    suggestions = data.get("suggestions")
    if not isinstance(suggestions, dict):
        return None
    for target in ("vector", "corpus", "logic", "memory"):
        item = suggestions.get(target)
        if not isinstance(item, dict) or not isinstance(item.get("recommended"), bool) or not isinstance(item.get("reason"), str) or not isinstance(item.get("planned_summary"), str):
            return None
    return {
        "task_id": task.get("task_id"),
        "review_passed": True,
        "suggestions": suggestions,
        "recommended_targets": [target for target, item in suggestions.items() if item.get("recommended")],
        "model_assisted": True,
        "fallback_used": False,
        "next_required_action": "user_select_storage_targets",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    _ensure_runtime()
    return {"ok": True, "service": "scbkr-api", "runtime": "P13-A/B/C SQLite + JSONL retrieval runtime"}


@app.get("/api/system/status")
def system_status() -> dict[str, Any]:
    return {
        "api_url": LOCAL_DESKTOP_API_BASE_URL,
        "web_url": "http://localhost:5500",
        "runtime": "P13-A/B/C SQLite + JSONL retrieval runtime",
        "physical_write_performed": False,
        "tasks_count": len(TASKS),
        "model": _public_model_settings(),
        "permissions": PERMISSIONS,
    }




@app.get("/api/desktop/status")
def desktop_status() -> dict[str, Any]:
    sidecar_host = os.environ.get("SCBKR_API_HOST", "127.0.0.1")
    sidecar_port = int(os.environ.get("SCBKR_API_PORT", "8787"))
    preview_package_built = os.environ.get("SCBKR_DESKTOP_PREVIEW") == "1"
    return {
        "desktop_stage": "P14-C-preview",
        "desktop_shell": True,
        "installer_built": False,
        "preview_package_built": preview_package_built,
        "tauri_skeleton": True,
        "sidecar_supported": True,
        "sidecar_running": True,
        "sandbox_available": True,
        "api_status": "running",
        "api_server_reachable": True,
        "api_url": f"http://{sidecar_host}:{sidecar_port}",
        "model_mode": MODEL_SETTINGS.get("mode"),
        "local_model_base_url": MODEL_SETTINGS.get("base_url"),
        "sidecar_host": sidecar_host,
        "sidecar_port": sidecar_port,
        "data_dir": os.environ.get("SCBKR_DATA_DIR"),
        "external_call_required": MODEL_SETTINGS.get("mode") in ("external", "hybrid"),
        "preview": True,
        "preview_package": "built" if preview_package_built else "preview runtime",
        "production_packaging": False,
        "production_packaging_status": "future stage pending",
        "installer": "not a production installer",
    }


@app.post("/api/backend/test")
def test_backend(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = str((payload or {}).get("backend_api_url") or LOCAL_DESKTOP_API_BASE_URL).rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="backend_api_url must start with http:// or https://")
    return {"ok": True, "status": "online", "backend_api_url": url, "runtime": "desktop sidecar" if is_loopback_model_url(url) else "mobile remote"}


@app.get("/api/settings/model")
def get_model_settings() -> dict[str, Any]:
    return _public_model_settings()


def _model_payload_preserving_blank_api_key(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    provider = normalized.get("provider", MODEL_SETTINGS.get("provider"))
    explicit_clear = normalized.pop("clear_api_key", False) is True
    if provider == "openai_compatible" and normalized.get("api_key") == "" and not explicit_clear:
        normalized.pop("api_key", None)
    return normalized


@app.post("/api/settings/model")
def set_model_settings(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _model_payload_preserving_blank_api_key(payload)
    next_settings = {**MODEL_SETTINGS, **payload, "enabled": False, "last_test_status": "untested", "last_test_message": "", "updated_at": _now()}
    if "api_key" not in payload:
        next_settings["api_key"] = MODEL_SETTINGS.get("api_key", "")
    _apply_provider_defaults(next_settings, payload)
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
def test_model(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if payload:
        payload = _model_payload_preserving_blank_api_key(payload)
        next_settings = {**MODEL_SETTINGS, **payload, "updated_at": _now()}
        if "api_key" not in payload:
            next_settings["api_key"] = MODEL_SETTINGS.get("api_key", "")
        _apply_provider_defaults(next_settings, payload)
        validate_model_settings(next_settings)
        MODEL_SETTINGS.clear()
        MODEL_SETTINGS.update(next_settings)
    try:
        if MODEL_SETTINGS.get("mode") == "sandbox":
            _apply_sandbox_defaults(MODEL_SETTINGS)
            status = {**make_test_status(True, "Sandbox model test passed. No external model or API was called."), "test_result_kind": "no_external_call_for_sandbox"}
        elif not MODEL_SETTINGS.get("model_name", "").strip():
            status = {**make_test_status(False, "model_name 未填，不可通過測試"), "test_result_kind": "external_api_not_configured"}
        else:
            if _model_call_requires_external_api_permission(MODEL_SETTINGS):
                assert_permission_allowed(PERMISSIONS, "external_api_call")
            response = _post_openai_compatible(
                MODEL_SETTINGS,
                [{"role": "user", "content": "請回覆 SCBKR model gateway test。"}],
            )
            status = {**make_test_status(True, parse_chat_completion_response(response)), "test_result_kind": "local_model_success" if MODEL_SETTINGS["mode"] == "local" else "external_model_success"}
    except PermissionError as exc:
        message = EXTERNAL_API_LOOPBACK_ERROR if PERMISSIONS.get("external_api") is not True else f"API 模型需要先明確開啟 external_api 權限；目前未開啟。{exc}"
        status = make_test_status(False, message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        status = {**make_test_status(False, _friendly_model_error(MODEL_SETTINGS, str(exc))), "raw_error": str(exc), "test_result_kind": "local_model_unreachable" if MODEL_SETTINGS.get("mode") == "local" else "external_model_unreachable"}
    MODEL_SETTINGS.update(status)
    MODEL_SETTINGS["enabled"] = status["last_test_status"] == "success"
    result = _public_model_settings()
    if MODEL_SETTINGS.get("mode") == "sandbox":
        result.update({"ok": True, "provider": SANDBOX_PROVIDER, "sandbox": True, "external_call_performed": False})
    return result


@app.post("/api/chat/general")
def general_chat(payload: dict[str, Any]) -> dict[str, Any]:
    user_text = str(payload.get("message", "")).strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="message is required")
    if _is_identity_question(user_text):
        reply = IDENTITY_EN if _looks_english(user_text) else IDENTITY_ZH
        source = "identity"
    elif not _model_connected():
        reply = "模型尚未連線。請先到連線設定儲存並測試模型連線；未 connected 時不會假裝模型回覆。"
        source = "not_connected"
    elif MODEL_SETTINGS.get("mode") == "sandbox":
        reply = "Sandbox 已連線：" + user_text
        source = "sandbox"
    else:
        try:
            _assert_model_gateway_call_allowed(MODEL_SETTINGS)
            response = _post_openai_compatible(MODEL_SETTINGS, [{"role": "system", "content": "你是 SCBKR 一般聊天入口。不要建立 task，不要寫入 Data Center。"}, {"role": "user", "content": user_text}])
            reply = parse_chat_completion_response(response)
            source = "model_gateway"
        except PermissionError as exc:
            if _model_call_requires_external_api_permission(MODEL_SETTINGS):
                raise HTTPException(status_code=403, detail=EXTERNAL_API_LOOPBACK_ERROR) from exc
            raise HTTPException(status_code=403, detail="目前未允許模型生成，聊天內容不會送出。請開啟 model_generate 權限或改用 Sandbox。") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"模型呼叫失敗：{_friendly_model_error(MODEL_SETTINGS, str(exc))}") from exc
    suggestion = _build_chat_suggestion(user_text) if any(trigger in user_text for trigger in SUGGESTION_TRIGGERS) else None
    return {"mode": "general_chat", "reply": reply, "reply_source": source, "model_connected": _model_connected(), "suggestion": suggestion, "task_created": False, "data_center_written": False, "auto_workbench": False}


@app.post("/api/chat/suggestions/accept")
def accept_chat_suggestion(payload: dict[str, Any]) -> dict[str, Any]:
    suggestion = payload.get("suggestion") or _build_chat_suggestion(str(payload.get("user_original", "")).strip())
    return {
        "prefill": {
            "user_original": suggestion.get("user_original", ""),
            "suggested_instruction": suggestion.get("suggested_instruction", ""),
            "suggested_type": suggestion.get("suggested_type", "記憶規則 / 情報判準"),
            "suggested_reason": suggestion.get("suggested_reason", ""),
            "suggested_write_direction": suggestion.get("suggested_write_direction", "記憶庫"),
            "task_type": "general",
            "draft_only_notice": "只整理不入庫：按下建立確認單後仍需 Workbench 使用者確認。",
        },
        "task_created": False,
        "data_center_written": False,
        "next_page": "chat",
    }


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
    if payload.get("create_scbkr_draft") is True:
        task["data_center_context"] = _build_four_store_context(raw_input, task_id)
        task["data_center_context"].update({"advisory": True, "retrieval_required": True, "auto_confirmed": False, "auto_storage": False, "candidate_count": len(task["data_center_context"].get("hits", []))})
        task["scbkr"], fallback_used, skipped_reason = _model_authored_scbkr_draft(raw_input, task["task_type"], task["data_center_context"])
        if skipped_reason:
            task["draft_model_call_skipped_reason"] = skipped_reason
        task["status"] = "waiting_user_confirm"
        task["confirmed"] = False
        TASKS[task_id] = task
        save_task(task)
        save_scbkr_confirmation(task_id, task["scbkr"])
        _append_task_event("task_created", task, status_after="waiting_scbkr", payload={"task_type": task["task_type"]})
        _append_task_event("scbkr_draft_model_generated", task, status_before="waiting_scbkr", status_after=task["status"], payload={"fallback_used": fallback_used, "draft_model_call_skipped_reason": skipped_reason, "data_center_context_advisory": True})
        _append_task_event("scbkr_draft_created", task, status_before="waiting_scbkr", status_after=task["status"], payload={"compatibility_event": True, "confirmation_status": task["scbkr"].get("confirmation_status")})
        return task
    TASKS[task_id] = task
    save_task(task)
    _append_task_event("task_created", task, status_after=task["status"], payload={"task_type": task["task_type"]})
    return task


@app.post("/api/tasks/{task_id}/scbkr")
def create_scbkr(task_id: str) -> dict[str, Any]:
    task = _get_task(task_id)
    _ensure_scbkr_edit_allowed(task)
    status_before = task.get("status")
    task["data_center_context"] = _build_four_store_context(task["raw_input"], task_id)
    task["data_center_context"].update({"advisory": True, "retrieval_required": True, "auto_confirmed": False, "auto_storage": False, "candidate_count": len(task["data_center_context"].get("hits", []))})
    task["scbkr"], fallback_used, skipped_reason = _model_authored_scbkr_draft(task["raw_input"], task["task_type"], task["data_center_context"])
    if skipped_reason:
        task["draft_model_call_skipped_reason"] = skipped_reason
    task["status"] = "waiting_user_confirm"
    save_task(task)
    save_scbkr_confirmation(task_id, task["scbkr"])
    _append_task_event(
        "scbkr_draft_model_generated",
        task,
        status_before=status_before,
        status_after=task["status"],
        payload={"confirmation_status": task["scbkr"].get("confirmation_status"), "fallback_used": fallback_used, "draft_model_call_skipped_reason": skipped_reason, "data_center_context_advisory": True},
    )
    _append_task_event(
        "scbkr_draft_created",
        task,
        status_before=status_before,
        status_after=task["status"],
        payload={"compatibility_event": True, "confirmation_status": task["scbkr"].get("confirmation_status")},
    )
    return task


@app.patch("/api/tasks/{task_id}/scbkr")
def edit_scbkr(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    _ensure_scbkr_edit_allowed(task)
    if "scbkr" not in task:
        raise HTTPException(status_code=400, detail="SCBKR draft required before edit")
    status_before = task.get("status")
    candidate = payload.get("scbkr")
    if candidate is not None:
        validate_scbkr_draft_for_confirmation(candidate)
        task["scbkr"] = candidate
    task["confirmed"] = False
    task["status"] = "waiting_user_confirm"
    task["scbkr"]["confirmation_status"] = "draft"
    _invalidate_downstream_after_scbkr_revision(task, status_before)
    save_task(task)
    save_scbkr_confirmation(task_id, task["scbkr"])
    _append_task_event("scbkr_user_edited", task, status_before=status_before, status_after=task["status"], payload={"layer": payload.get("layer", "manual")})
    return _task_response(task)


@app.post("/api/tasks/{task_id}/scbkr/patch-draft")
def scbkr_patch_draft(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    layer = str(payload.get("layer") or "B").upper()
    instruction = str(payload.get("instruction", "")).strip()
    if layer not in SCBKR_CONFIRMATION_REQUIRED_FIELDS:
        raise HTTPException(status_code=400, detail="layer must be S/C/B/K/R")
    before = task.get("scbkr", {}).get(layer, {})
    after = dict(before)
    after["pending_questions"] = [f"使用者要求修改：{instruction or '請依使用者指令調整此層。'}"]
    if layer == "B" and ("日期" in instruction or "date" in instruction.lower()):
        after["stop_conditions"] = list(after.get("stop_conditions") or []) + ["模型不得自行確認事件日期；日期必須由使用者填寫或確認。"]
        after["sensitive_operation_confirm"] = True
    patch = {"layer": layer, "before_summary": str(before)[:240], "after_draft": after, "reason": instruction or "使用者要求模型提出此層修改草案。", "auto_confirmed": False}
    return {"task_id": task_id, "patch": patch, "confirmed": False, "status": task.get("status")}


@app.post("/api/tasks/{task_id}/scbkr/apply-patch")
def apply_scbkr_patch(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    _ensure_scbkr_edit_allowed(task)
    if "scbkr" not in task:
        raise HTTPException(status_code=400, detail="SCBKR draft required before edit")
    patch = payload.get("patch") or {}
    layer = str(patch.get("layer") or "").upper()
    after_draft = patch.get("after_draft")
    _validate_scbkr_patch_after_draft(layer, after_draft)
    current_scbkr = deepcopy(task["scbkr"])
    candidate_scbkr = deepcopy(current_scbkr)
    candidate_scbkr[layer] = deepcopy(after_draft)
    candidate_scbkr["confirmation_status"] = "draft"
    try:
        validate_scbkr_draft_for_confirmation(candidate_scbkr)
        if _contains_forbidden_draft_state(candidate_scbkr):
            raise ValueError("forbidden confirmed/high-privilege state")
    except HTTPException:
        raise HTTPException(status_code=400, detail=SCBKR_INVALID_PATCH_MESSAGE)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=SCBKR_INVALID_PATCH_MESSAGE) from exc

    status_before = task.get("status")
    task["scbkr"] = candidate_scbkr
    task["confirmed"] = False
    task["status"] = "waiting_user_confirm"
    _invalidate_downstream_after_scbkr_revision(task, status_before)
    save_task(task)
    save_scbkr_confirmation(task_id, task["scbkr"])
    _append_task_event("scbkr_patch_applied", task, status_before=status_before, status_after=task["status"], payload={"layer": layer, "auto_confirmed": False})
    return _task_response(task, auto_confirmed=False)


@app.post("/api/tasks/{task_id}/dates")
def update_task_dates(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    dates = dict(task.get("date_governance") or {})
    dates.update({
        "system_created_at": task.get("created_at") or task.get("task_id"),
        "system_written_at": _now(),
        "event_date": payload.get("event_date", dates.get("event_date")),
        "model_inferred_date": payload.get("model_inferred_date", dates.get("model_inferred_date")),
        "date_source": payload.get("date_source", "user" if payload.get("event_date") else dates.get("date_source", "unset")),
        "confirmation_status": "confirmed_by_user" if payload.get("user_confirmed") is True else "waiting_user_confirm",
        "modified_at": _now(),
        "confirmed_at": _now() if payload.get("user_confirmed") is True else dates.get("confirmed_at"),
    })
    if payload.get("clear_model_inferred") is True:
        dates["model_inferred_date"] = None
    task["date_governance"] = dates
    save_task(task)
    _append_task_event("task_date_user_updated", task, status_before=task.get("status"), status_after=task.get("status"), payload={"confirmation_status": dates["confirmation_status"]})
    return _task_response(task)


@app.post("/api/tasks/{task_id}/confirm")
def confirm_task(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    task = _get_task(task_id)
    if "scbkr" not in task:
        raise HTTPException(status_code=400, detail="SCBKR draft required before confirm")
    payload = payload or {}
    downstream_invalidated = False
    if "scbkr" in payload:
        _ensure_scbkr_edit_allowed(task)
        candidate = payload["scbkr"]
        validate_scbkr_draft_for_confirmation(candidate)
        status_before_revision = task.get("status")
        downstream_invalidated = _invalidate_downstream_after_scbkr_revision(task, status_before_revision)
        candidate["confirmation_status"] = "draft"
        task["scbkr"] = candidate
    else:
        validate_scbkr_draft_for_confirmation(task["scbkr"])
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
        payload={"confirmed_snapshot_hash": task["scbkr"].get("confirmed_snapshot_hash"), "downstream_invalidated": downstream_invalidated},
    )
    if downstream_invalidated:
        return _task_response(task, downstream_invalidated=True)
    return _task_response(task)


@app.post("/api/tasks/{task_id}/generate")
def generate(task_id: str) -> dict[str, Any]:
    task = _get_task(task_id)
    status_before = task.get("status")
    _append_task_event("generation_requested", task, status_before=status_before, status_after=status_before)
    try:
        if MODEL_SETTINGS.get("mode") == "sandbox" and PERMISSIONS.get("model_generate") is not True:
            raise PermissionError("model_generate permission is required before sandbox generation")
        assert_permission_allowed(PERMISSIONS, "model_generate")
        if _model_call_requires_external_api_permission(MODEL_SETTINGS):
            assert_permission_allowed(PERMISSIONS, "external_api_call")
        assert_task_can_generate(task, task.get("scbkr", {}), MODEL_SETTINGS, PERMISSIONS)

        def violates_contract(text: str) -> bool:
            forbidden = ("SCBKR 草案", "五維確認單", "confirmation_status", "等待使用者確認", "重新確認 S/C/B/K/R", "S/C/B/K/R JSON")
            stripped = text.strip()
            return any(token in stripped for token in forbidden) or (stripped.startswith("{") and all(k in stripped for k in ('"S"', '"C"', '"B"', '"K"', '"R"')))

        def call_generation_model() -> dict[str, Any]:
            if MODEL_SETTINGS.get("mode") == "sandbox":
                sandbox_output = generate_with_sandbox_model(task, task["scbkr"])
                result = build_generation_result(task, task["scbkr"], sandbox_output.get("generated_text") or sandbox_output.get("content") or "")
                result.update(sandbox_output)
                result.update({"source": "sandbox_mock_model", "next_required_action": "user_review_required"})
                return result
            response = _post_openai_compatible(MODEL_SETTINGS, build_generation_messages(task, task["scbkr"]))
            return build_generation_result(task, task["scbkr"], parse_chat_completion_response(response))

        first_result = call_generation_model()
        first_text = str(first_result.get("content") or first_result.get("generated_text") or "")
        if violates_contract(first_text):
            _append_task_event("generation_contract_violation_retry", task, status_before=status_before, status_after=status_before, payload={"attempt": 1})
            second_result = call_generation_model()
            second_text = str(second_result.get("content") or second_result.get("generated_text") or "")
            if violates_contract(second_text):
                task["generation_result"] = {"status": "generation_contract_violation", "content": "模型輸出偏離正式任務結果，仍在輸出確認單。已停止本次生成，請重新生成或調整模型設定。"}
                save_task(task)
                _append_task_event("generation_contract_violation_stopped", task, status_before=status_before, status_after=task.get("status"), payload={"attempt": 2})
                return _task_response(task)
            task["generation_result"] = second_result
        else:
            task["generation_result"] = first_result
        task["status"] = "waiting_review"
        save_task(task)
        _append_task_event(
            "generation_completed",
            task,
            status_before=status_before,
            status_after=task["status"],
            payload={"generation_status": task["generation_result"].get("status"), "sandbox": task["generation_result"].get("sandbox", False)},
        )
        return _task_response(task)
    except PermissionError as exc:
        _append_task_event("generation_failed", task, status_before=status_before, status_after=task.get("status"), payload={"error": str(exc)})
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        _append_task_event("generation_failed", task, status_before=status_before, status_after=task.get("status"), payload={"error": str(exc)})
        detail = "目前責任鏈尚未確認，請先確認責任鏈後再生成。" if "task.status must be confirmed before generation" in str(exc) else str(exc)
        raise HTTPException(status_code=400, detail=detail) from exc


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
        return _task_response(task)
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


@app.post("/api/tasks/{task_id}/storage-suggestion")
def storage_suggestion(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    task = _get_task(task_id)
    payload = payload or {}
    if task.get("review_passed") is not True or task.get("review_result", {}).get("review_passed") is not True:
        raise HTTPException(status_code=400, detail="尚未通過驗收，不能產生入庫建議。")
    if not task.get("generation_result"):
        raise HTTPException(status_code=400, detail="尚未生成結果，不能產生入庫建議。")
    status_before = task.get("status")
    suggestion = None
    if payload.get("use_model_suggestion") is True:
        try:
            suggestion = _try_model_storage_suggestion(task)
        except Exception:
            suggestion = None
    suggestion = suggestion or deterministic_storage_suggestion(task, payload.get("user_preference"))
    task["storage_suggestion"] = suggestion
    save_task(task)
    _append_task_event("storage_suggestion_generated", task, status_before=status_before, status_after=task.get("status"), payload={"recommended_targets": suggestion.get("recommended_targets", []), "fallback_used": suggestion.get("fallback_used", True)})
    return suggestion


@app.post("/api/tasks/{task_id}/storage-request")
def storage_request(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    task = _get_task(task_id)
    payload_was_none = payload is None
    payload = payload or {}
    try:
        status_before = task.get("status")
        if task.get("review_passed") is not True or task.get("review_result", {}).get("review_passed") is not True:
            raise ValueError("尚未通過驗收，不能產生入庫請求。請先按「通過驗收」。")
        user_decision = payload.get("user_decision") or "custom"
        raw_selected = payload.get("selected_targets")
        selected_ui = validate_ui_targets(raw_selected) if raw_selected is not None else (["corpus", "logic"] if payload_was_none else [])
        if not selected_ui and user_decision not in ("temporary_only", "do_not_store"):
            raise ValueError("尚未選擇寫入目標。請先選擇至少一個寫入目標，或選擇「只暫存 / 不寫入」。")
        task["storage_request"] = build_storage_request(task, task.get("review_result", {}), candidate_targets=["vector_db", "corpus", "logic", "memory"])
        task["storage_request"].update({"selected_targets": selected_ui, "user_decision": user_decision, "signature": payload.get("signature")})
        task["selected_targets"] = selected_ui
        task["user_decision"] = user_decision
        plan_targets = [to_plan_target(t) for t in selected_ui]
        task["storage_plan"] = {
            "task_id": task.get("task_id"),
            "storage_plan_status": "waiting_user_second_confirm",
            "storage_confirmed": False,
            "selected_targets": selected_ui,
            "storage_items": [{"target": t, "planned_summary": (task.get("storage_suggestion", {}).get("suggestions", {}).get(t, {}) or {}).get("planned_summary", "預計寫入已驗收資料。"), "physical_write_performed": False} for t in selected_ui],
            "plan_targets": plan_targets,
            "risk_notice": "二次確認後才會寫入本機資料；向量庫目前保留索引中繼資料，實體 JSON 僅寫入支援的本機庫。",
            "permission_notice": "模型不能自動寫入，必須由使用者二次確認。",
            "user_decision": user_decision,
            "physical_write_performed": False,
            "next_required_action": "user_second_confirm_storage",
        }
        task["status"] = "waiting_storage_confirm" if selected_ui else user_decision
        save_task(task)
        _append_task_event("storage_requested", task, status_before=status_before, status_after=task["status"], payload={"selected_targets": selected_ui, "user_decision": user_decision})
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
        if task.get("storage_confirmed") is True and task.get("physical_write_performed") is True and (task.get("storage_result") or {}).get("written_items"):
            return _already_committed_response(task)
        if task.get("review_passed") is not True or task.get("review_result", {}).get("review_passed") is not True:
            raise ValueError("尚未通過驗收，不能入庫。請先按「通過驗收」。")
        if task.get("status") not in ("review_passed", "waiting_storage_confirm", "storage_requested"):
            raise ValueError("目前任務狀態不能入庫，請確認已通過驗收並建立入庫請求。")
        for required_key in ("generation_result", "review_result", "scbkr"):
            if required_key not in task:
                raise ValueError(f"{required_key} is required before storage commit")
        if not all_dimensions_confirmed(task["scbkr"]):
            raise ValueError("SCBKR must be fully confirmed before storage commit")
        if "storage_request" not in task:
            raise ValueError("尚未產生入庫計畫，不能二次確認寫入。請先按「產生入庫請求」。")
        if "storage_plan" not in task:
            raise ValueError("尚未建立入庫計畫。請先產生入庫請求。")
        user_decision = task.get("user_decision") or task.get("storage_request", {}).get("user_decision")
        selected_targets = validate_ui_targets([t for t in (payload.get("selected_targets") or task.get("selected_targets") or task.get("storage_plan", {}).get("selected_targets") or []) if t != "exports"])
        if not selected_targets and user_decision in ("temporary_only", "do_not_store"):
            task["storage_confirmed"] = False
            task["physical_write_performed"] = False
            task["status"] = user_decision
            task["storage_result"] = {"status": user_decision, "selected_targets": [], "written_targets": [], "skipped_targets": ["vector", "corpus", "logic", "memory"], "physical_write_performed": False, "user_decision": user_decision}
            save_task(task)
            _append_task_event("storage_confirmed", task, status_before=status_before, status_after=task["status"], payload=task["storage_result"])
            return task
        if not selected_targets:
            raise ValueError("尚未選擇寫入目標。請先選擇向量庫、語料庫、程式邏輯庫或記憶庫。")
        if payload.get("storage_confirmed") is not True and payload.get("second_confirm") is not True:
            raise ValueError("請勾選或按下「使用者二次確認寫入」後才能入庫。")
        if payload.get("confirmed_by") != "user":
            raise ValueError("confirmed_by=user is required")
        signature = str(payload.get("signature") or payload.get("storage_signature") or "").strip()
        if not signature:
            raise ValueError("signature is required")

        plan_targets = [to_plan_target(target) for target in selected_targets]
        legacy_exports_requested = "exports" in (payload.get("selected_targets") or [])
        physical_targets = [target for target in plan_targets if target in ("vector_db", "corpus", "logic", "memory")]
        if legacy_exports_requested and "exports" not in physical_targets:
            physical_targets.append("exports")
        proposed_plan = build_storage_commit_plan(task, task.get("review_result", {}), plan_targets, storage_signature=signature if "memory" in plan_targets else None, storage_notes=payload.get("storage_notes", "P15-C user second-confirmed storage commit."))
        proposed_plan["selected_targets"] = selected_targets
        proposed_plan["physical_write_performed"] = False
        storage_plan_hash = _storage_plan_hash(proposed_plan)
        storage_commit_key = _storage_commit_key(task, selected_targets, storage_plan_hash)
        if task.get("storage_commit_key") == storage_commit_key and task.get("storage_result", {}).get("written_items"):
            return _already_committed_response(task)
        requested_event = _append_task_event("storage_physical_write_requested", task, status_before=status_before, status_after=status_before, payload={"selected_targets": selected_targets, "confirmed_by": "user", "storage_plan_hash": storage_plan_hash, "storage_commit_key": storage_commit_key})
        task["storage_plan"] = proposed_plan
        task["storage_plan"]["storage_plan_hash"] = storage_plan_hash
        task["storage_plan"]["storage_commit_key"] = storage_commit_key
        physical_plan = dict(task["storage_plan"])
        physical_plan["selected_targets"] = physical_targets
        physical_plan["allow_vector_metadata"] = "vector_db" in physical_targets
        physical_plan["p15d_structured_payloads"] = True
        items = commit_storage_items(task, physical_plan, source_event_id=requested_event["event_id"]) if physical_targets else []
        for item in items:
            save_storage_item(item)
            _append_task_event("storage_item_written", task, status_before=status_before, status_after="storage_committed", payload={"target": item.get("target"), "content_hash": item.get("content_hash"), "relative_path": item.get("relative_path"), "physical_write_performed": True})
        written_targets = [to_ui_target(item.get("target")) for item in items]
        skipped_targets = [target for target in selected_targets if target not in written_targets]
        task["storage_items"] = items
        task["storage_confirmed"] = True
        task["physical_write_performed"] = True
        task["status"] = "storage_committed"
        task["storage_plan"]["physical_write_performed"] = True
        task["storage_plan"]["next_required_action"] = "storage_committed"
        task["storage_plan_hash"] = storage_plan_hash
        task["storage_commit_key"] = storage_commit_key
        skipped_reasons = {target: "未產生實體寫入項目，請檢查入庫條件。" for target in skipped_targets}
        written_items = [{"item_id": item.get("item_id"), "target": to_ui_target(item.get("target")), "hash": item.get("content_hash"), "path": item.get("relative_path"), "storage_location": item.get("relative_path"), "stored_at": item.get("stored_at") or item.get("created_at")} for item in items]
        task["storage_result"] = {"status": "storage_committed", "selected_targets": selected_targets, "written_targets": written_targets, "skipped_targets": skipped_targets, "skipped_reasons": skipped_reasons, "written_items": written_items, "storage_item_ids": [item.get("item_id") for item in items], "hashes": [item.get("content_hash") for item in items], "data_dir": str(current_data_dir()), "ledger_id": task.get("ledger_id"), "hash": items[0].get("content_hash") if items else None, "physical_write_performed": True, "storage_plan_hash": storage_plan_hash, "storage_commit_key": storage_commit_key}
        save_task(task)
        _append_task_event("database_written", task, status_before=status_before, status_after=task["status"], payload=task["storage_result"])
        _append_task_event("storage_physical_write_completed", task, status_before=status_before, status_after=task["status"], payload={"item_count": len(items), "physical_write_performed": True})
        _append_task_event("storage_confirmed", task, status_before=status_before, status_after=task["status"], payload=task["storage_result"])
        return task
    except PermissionError as exc:
        _append_task_event("storage_physical_write_failed", task, status_before=status_before, status_after=task.get("status"), payload={"error_message": str(exc), "physical_write_performed": False})
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        task["physical_write_performed"] = False
        _append_task_event("storage_physical_write_failed", task, status_before=status_before, status_after=task.get("status"), payload={"error_message": str(exc), "physical_write_performed": False})
        save_task(task)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/complete")
def complete_task(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    task = _get_task(task_id)
    status_before = task.get("status")
    try:
        explicit_no_storage = task.get("user_decision") in ("temporary_only", "do_not_store") and task.get("storage_result", {}).get("status") in ("temporary_only", "do_not_store")
        if not explicit_no_storage and (task.get("storage_confirmed") is not True or task.get("physical_write_performed") is not True):
            raise ValueError("尚未完成實體寫入，不能完成任務。")
        if not explicit_no_storage and task.get("status") not in ("storage_committed", "completed"):
            raise ValueError("task must be storage_committed before completion")
        task["status"] = "completed"
        task["completed"] = True
        task["final_result"] = {
            "task_id": task.get("task_id"),
            "status": "completed",
            "generation_result": task.get("generation_result"),
            "storage_items": task.get("storage_items", []),
        }
        save_task(task)
        _append_task_event("task_completed", task, status_before=status_before, status_after=task["status"], payload={"completed": True})
        return task
    except ValueError as exc:
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
    if task.get("status") not in ("storage_committed", "completed") or task.get("review_passed") is not True or task.get("storage_confirmed") is not True or task.get("physical_write_performed") is not True:
        raise HTTPException(status_code=400, detail="storage_committed or completed review_passed storage_confirmed task with physical writes required")
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
    return _task_response(_get_task(task_id))



def _preview(value: Any, limit: int = 180) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text[:limit]

def _dc_item_from_task(task: dict[str, Any], kind: str) -> dict[str, Any]:
    return {"id": task.get("task_id"), "title": task.get("task_name"), "summary": _preview(task.get(kind) or task.get("raw_input") or ""), "task_id": task.get("task_id"), "created_at": task.get("created_at"), "stored_at": (task.get("storage_result") or {}).get("stored_at"), "hash": (task.get("scbkr") or {}).get("confirmed_snapshot_hash") or (task.get("storage_result") or {}).get("hash"), "target": kind, "preview": _preview(task.get(kind) or task)}

def _dc_item_from_storage(item: dict[str, Any]) -> dict[str, Any]:
    payload = item.get("payload") or {}
    relative_path = item.get("relative_path")
    storage_location = item.get("storage_location") or relative_path
    return {
        "id": item.get("item_id"),
        "item_id": item.get("item_id"),
        "title": payload.get("title") or payload.get("name"),
        "summary": payload.get("summary") or payload.get("purpose"),
        "task_id": item.get("task_id"),
        "created_at": item.get("created_at"),
        "stored_at": item.get("stored_at") or item.get("created_at"),
        "hash": item.get("content_hash") or payload.get("hash"),
        "content_hash": item.get("content_hash"),
        "target": item.get("target"),
        "path": relative_path,
        "storage_location": storage_location,
        "relative_path": relative_path,
        "preview": _preview(payload.get("content") or payload),
        "payload": payload,
        "status": item.get("status", "active"),
        "version": item.get("version", 1),
        "parent_item_id": item.get("parent_item_id"),
        "superseded_by": item.get("superseded_by"),
        "user_event_date": item.get("user_event_date"),
        "event_date_source": item.get("event_date_source", "unset"),
        "event_date_confirmed": item.get("event_date_confirmed", False),
        "updated_at": item.get("updated_at"),
        "archived_at": item.get("archived_at"),
        "revoked_at": item.get("revoked_at"),
    }

@app.get("/api/data-center/overview")
def data_center_overview(task_id: str | None = None) -> dict[str, Any]:
    tasks_all = list_persisted_tasks(limit=1000)
    storage_all = list_persisted_storage_items(limit=1000)
    ledger_all = read_ledger_events()
    tasks = [t for t in tasks_all if not task_id or t.get("task_id") == task_id]
    storage = [i for i in storage_all if not task_id or i.get("task_id") == task_id]
    ledger = [e for e in ledger_all if not task_id or e.get("task_id") == task_id]
    def counts(prefix: str, items: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, int]:
        return {
            f"{prefix}storage_records_count": len(items),
            f"{prefix}vector_count": sum(1 for i in items if i.get("target") == "vector_db"),
            f"{prefix}corpus_count": sum(1 for i in items if i.get("target") == "corpus"),
            f"{prefix}logic_count": sum(1 for i in items if i.get("target") == "logic"),
            f"{prefix}memory_count": sum(1 for i in items if i.get("target") == "memory"),
            f"{prefix}ledger_events_count": len(events),
        }
    return {
        "mode": "task" if task_id else "all",
        "task_id": task_id,
        "tasks_count": len(tasks),
        "confirmed_tasks_count": sum(1 for t in tasks if t.get("confirmed") is True),
        "generation_results_count": sum(1 for t in tasks if t.get("generation_result")),
        "review_records_count": sum(1 for t in tasks if t.get("review_result")),
        **counts("", storage, ledger),
        **counts("total_", storage_all, ledger_all),
        "total_tasks_count": len(tasks_all),
        "total_confirmed_tasks_count": sum(1 for t in tasks_all if t.get("confirmed") is True),
        "total_generation_results_count": sum(1 for t in tasks_all if t.get("generation_result")),
        "total_review_records_count": sum(1 for t in tasks_all if t.get("review_result")),
    }

@app.get("/api/data-center/{section}")
def data_center_section(section: str, task_id: str | None = None) -> dict[str, Any]:
    tasks_all = list_persisted_tasks(limit=1000)
    storage_all = list_persisted_storage_items(limit=1000)
    tasks = [t for t in tasks_all if not task_id or t.get("task_id") == task_id]
    storage = [i for i in storage_all if not task_id or i.get("task_id") == task_id]
    ledger = read_ledger_events(task_id=task_id) if task_id else read_ledger_events()
    if section == "tasks": items = [_dc_item_from_task(t, "task") for t in tasks]
    elif section == "confirmations": items = [_dc_item_from_task(t, "scbkr") for t in tasks if t.get("confirmed")]
    elif section == "generations": items = [_dc_item_from_task(t, "generation_result") for t in tasks if t.get("generation_result")]
    elif section == "reviews": items = [_dc_item_from_task(t, "review_result") for t in tasks if t.get("review_result")]
    elif section == "storage": items = [{**_dc_item_from_task(t, "storage_result"), "storage_confirmed": t.get("storage_confirmed"), "physical_write_performed": t.get("physical_write_performed"), **(t.get("storage_result") or {})} for t in tasks if t.get("storage_result")]
    elif section == "vector": items = [_dc_item_from_storage(i) for i in storage if i.get("target") == "vector_db"]
    elif section == "corpus": items = [_dc_item_from_storage(i) for i in storage if i.get("target") == "corpus"]
    elif section == "logic": items = [_dc_item_from_storage(i) for i in storage if i.get("target") == "logic"]
    elif section == "memory": items = [_dc_item_from_storage(i) for i in storage if i.get("target") == "memory"]
    elif section == "ledger": items = ledger[-200:]
    else: raise HTTPException(status_code=404, detail="data center section not found")
    return {"section": section, "mode": "task" if task_id else "all", "task_id": task_id, "count": len(items), "items": items, "empty_message": "目前尚無資料。" if not items else ""}

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
