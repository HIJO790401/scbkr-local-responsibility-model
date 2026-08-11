"""FastAPI runtime for the local-first SCBKR product.

Tasks are cached in memory and persisted to local SQLite. Flow events are
appended to a JSONL replay ledger; retrieval is advisory and no desktop runtime is initialized here.
"""

from datetime import UTC, datetime
from copy import deepcopy
from functools import wraps
from itertools import count
from threading import RLock
from uuid import uuid4
from typing import Any
from urllib.parse import urlparse
from urllib.error import URLError, HTTPError
from urllib.request import Request as UrlRequest, urlopen
import json
import os
import hashlib
import secrets
import socket
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core.generation.sandbox_model import SANDBOX_PROVIDER, generate_with_sandbox_model
from core.model_gateway.connection_test import make_test_status
from core.model_gateway.openai_compatible import build_chat_completion_payload, build_headers
from core.model_gateway.response_parser import parse_chat_completion_response
from core.model_gateway.settings import DEFAULT_MODEL_SETTINGS, mask_api_key, validate_model_settings
from core.metrics.token_efficiency import build_token_efficiency_metrics, summarize_metrics
from core.metrics.token_ab_benchmark import run_token_ab_benchmark, write_token_ab_report
from core.metrics.token_meter import DEFAULT_PRICING, normalize_pricing
from core.permissions.permission_checker import assert_permission_allowed, validate_permission_settings
from core.permissions.permission_flags import DEFAULT_PERMISSION_SETTINGS
from core.product_manifest import (
    build_product_reply,
    detect_explanation_depth,
    detect_product_topic,
    localized_product_manifest,
    load_product_manifest,
)
from core.evidence.contracts import build_evidence_packet
from core.ledger.ledger_event import build_ledger_event
from core.ledger.jsonl_ledger import append_ledger_event, read_ledger_events, rebuild_ledger_index_from_jsonl
from core.review_rules.rule_confirmation import confirm_memory_rule_plan
from core.review_rules.rule_draft import build_memory_rule_draft
from core.scbkr.confirmation import all_dimensions_confirmed, confirm_all_dimensions, strip_confirmation_metadata
from core.scbkr.generator import create_scbkr_draft
from core.scbkr.draft_grammar import (
    build_task_understanding_messages,
    build_scbkr_from_understanding,
    classify_evidence_relation,
    normalize_task_understanding,
    ADOPTABLE_RELATIONS,
)
from core.scbkr.compiler import (
    build_compiler_report,
    build_repair_messages,
    task_understanding_response_format,
    validate_task_understanding_strict,
)
from core.scbkr.draft_object import build_rule_draft_object, build_scbkr_draft_object
from core.scbkr.model_rulebook_author import (
    ModelRulebookAuthoringError,
    apply_model_dimension_patch,
    authoring_to_scbkr_draft,
    build_authoring_failure,
    build_context_audit,
    build_model_capability_assessment,
    build_model_basis_selection_messages,
    build_model_dimension_explanation_messages,
    build_model_dimension_patch_messages,
    build_model_rulebook_messages,
    build_semantic_repair_instruction,
    compile_kernel_required_clauses,
    compile_model_basis_selection_candidate,
    enforce_kernel_authority_boundary,
    merge_model_dimension_explanation_candidate,
    model_dimension_explanation_response_format,
    model_dimension_patch_response_format,
    model_dimension_repair_instruction,
    model_rulebook_response_format,
    model_rulebook_repair_targets,
    merge_model_dimension_patch_candidate,
    parse_model_basis_selection_output,
    parse_model_dimension_explanation_output,
    parse_model_dimension_patch_output,
    parse_model_rulebook_candidate,
    parse_model_rulebook_output,
    refresh_model_rulebook_support_fields,
    validate_model_rulebook_semantics,
)
from core.scbkr.plan_depth_compiler import apply_plan_depth
from core.scbkr.validity_failure_validator import validate_validity_failure
from core.storage.physical_store import commit_memory_rule, commit_storage_items, hash_payload
from core.storage.sqlite_runtime import (
    get_task_ledger,
    init_sqlite_runtime,
    list_active_stored_tasks,
    list_task_summaries as list_persisted_task_summaries,
    list_tasks as list_persisted_tasks,
    load_task,
    list_memory_rules as list_persisted_memory_rules,
    list_retrieval_cases as list_persisted_retrieval_cases,
    list_storage_items as list_persisted_storage_items,
    save_ledger_index,
    save_memory_rule,
    save_retrieval_case,
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
from core.rules.registry import RuleRegistry
from core.rule_state.manager import RuleStateManager
from core.rule_state.runtime import RuleStateRuntime
from core.rule_state.schemas import RuleStateEnum
from core.tools.registry import ToolGateEngine, list_tool_definitions
from core.tools.state_precondition import compare_evidence_state, evidence_state_hash
from core.tools.web_runtime import WebRuntime
from core.launch.readiness import launch_readiness, load_launch_settings, public_launch_settings, save_launch_settings
from core.kernel.local_kernel_cache import ensure_local_kernel_cache
from core.storage.runtime_paths import current_data_dir
from core.runtime_settings import load_runtime_section, persistence_enabled, save_runtime_section
from core.rule_assist import (
    DEFAULT_RULE_ASSIST_SETTINGS,
    apply_rule_assist_to_scbkr,
    build_scbkr_layer_patch,
    build_local_rule_assist_reply,
    build_rule_assist_prompt,
    evaluate_rule_assist,
    plan_catalog,
    public_settings as public_rule_assist_settings,
    validate_settings_update as validate_rule_assist_settings_update,
)
from core.rule_os import (
    apply_plan_depth_to_draft,
    build_current_rule_package,
    build_rule_package_local_reply,
    build_rule_package_messages,
    check_model_answer_against_rule_package,
    classify_user_input,
    compile_executable_rule,
    downgrade_answer_to_draft,
    normalize_locale_text,
    rule_os_text,
)
from core.audit.token_cost_audit import measure_context_compression

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

app = FastAPI(title="SCBKR Local Responsibility Model API", version="2.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_DESKTOP_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=LOCAL_DESKTOP_CORS_METHODS,
    allow_headers=["*"],
)

_TASK_COUNTER = count(1)
TASKS: dict[str, dict[str, Any]] = {}
RULE_STATE_COMMIT_LOCK = RLock()
MODEL_SETTINGS: dict[str, Any] = load_runtime_section("model", DEFAULT_MODEL_SETTINGS)
# A successful connection test is evidence for the current API process only.
# Persisted credentials remain available, but a restarted desktop must verify
# that the configured model still exists before generation is enabled.
_MODEL_SESSION_VERIFIED = not persistence_enabled()
PERMISSIONS: dict[str, Any] = load_runtime_section("permissions", DEFAULT_PERMISSION_SETTINGS)
RULE_ASSIST_SETTINGS: dict[str, Any] = load_runtime_section("rule_assist", DEFAULT_RULE_ASSIST_SETTINGS)
PRICING_SETTINGS: dict[str, Any] = load_runtime_section("pricing", DEFAULT_PRICING)
COMPANION_PAIRINGS: dict[str, dict[str, Any]] = {}
COMPANION_TOKENS: dict[str, dict[str, Any]] = {}


def _serialized_rule_state_change(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        with RULE_STATE_COMMIT_LOCK:
            return func(*args, **kwargs)

    return wrapped


def lan_companion_enabled() -> bool:
    return os.environ.get("SCBKR_LAN_COMPANION_ENABLED") == "1"


def _client_is_loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in {"127.0.0.1", "::1", "localhost"}


def _companion_token_valid(request: Request) -> bool:
    expected = os.environ.get("SCBKR_COMPANION_TOKEN", "")
    supplied = request.headers.get("X-SCBKR-Companion-Token") or request.query_params.get("companion_token")
    if bool(expected) and supplied == expected:
        return True
    if not supplied:
        return False
    token_hash = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
    record = COMPANION_TOKENS.get(token_hash)
    return bool(record and record.get("revoked") is not True and float(record.get("expires_at", 0)) > time.time())


def _is_public_companion_asset_path(path: str) -> bool:
    return (
        path in {
            "/",
            "/index.html",
            "/health",
            "/favicon.ico",
            "/favicon.png",
            "/manifest.json",
            "/robots.txt",
            "/vite.svg",
            "/api/companion/pairing/redeem",
        }
        or path.startswith("/assets/")
    )


@app.middleware("http")
async def require_companion_token_for_lan_requests(request: Request, call_next):
    if lan_companion_enabled() and not _client_is_loopback(request):
        if _is_public_companion_asset_path(request.url.path):
            return await call_next(request)
        if not _companion_token_valid(request):
            return JSONResponse(status_code=401, content={"detail": "LAN Companion Mode requires a valid companion token"})
    return await call_next(request)


def _lan_ipv4() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"


def _pairing_cleanup() -> None:
    now = time.time()
    for code_hash, record in list(COMPANION_PAIRINGS.items()):
        if float(record.get("expires_at", 0)) <= now or record.get("used") is True:
            COMPANION_PAIRINGS.pop(code_hash, None)
    for token_hash, record in list(COMPANION_TOKENS.items()):
        if float(record.get("expires_at", 0)) <= now:
            COMPANION_TOKENS.pop(token_hash, None)


@app.get("/api/companion/status")
def companion_status(request: Request) -> dict[str, Any]:
    desktop_request = _client_is_loopback(request)
    if not desktop_request and not _companion_token_valid(request):
        raise HTTPException(status_code=403, detail="valid companion token required")
    _pairing_cleanup()
    host = _lan_ipv4()
    port = int(os.environ.get("SCBKR_API_PORT") or os.environ.get("SCBKR_SIDECAR_PORT", "8787"))
    return {
        "lan_companion_enabled": lan_companion_enabled(),
        "lan_host": host,
        "port": port,
        "base_url": f"http://{host}:{port}",
        "active_devices": sum(1 for item in COMPANION_TOKENS.values() if item.get("revoked") is not True) if desktop_request else None,
        "pairing_ttl_seconds": 600,
    }


@app.post("/api/companion/pairing/start")
def companion_pairing_start(request: Request) -> dict[str, Any]:
    if not _client_is_loopback(request):
        raise HTTPException(status_code=403, detail="pairing can only be started on the desktop")
    if not lan_companion_enabled():
        raise HTTPException(status_code=400, detail="LAN Companion Mode is disabled")
    _pairing_cleanup()
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = time.time() + 600
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    COMPANION_PAIRINGS[code_hash] = {"expires_at": expires_at, "used": False, "created_at": _now() if "_now" in globals() else datetime.now(UTC).isoformat()}
    status = companion_status(request)
    return {
        "pairing_code": code,
        "expires_at": datetime.fromtimestamp(expires_at, UTC).isoformat(),
        "base_url": status["base_url"],
        "redeem_url": f"{status['base_url']}/api/companion/pairing/redeem",
    }


@app.post("/api/companion/pairing/redeem")
def companion_pairing_redeem(payload: dict[str, Any]) -> dict[str, Any]:
    if not lan_companion_enabled():
        raise HTTPException(status_code=400, detail="LAN Companion Mode is disabled")
    _pairing_cleanup()
    code = str(payload.get("pairing_code") or "").strip()
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    pairing = COMPANION_PAIRINGS.get(code_hash)
    if not pairing or pairing.get("used") is True or float(pairing.get("expires_at", 0)) <= time.time():
        raise HTTPException(status_code=401, detail="invalid or expired pairing code")
    pairing["used"] = True
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = time.time() + 30 * 24 * 60 * 60
    COMPANION_TOKENS[token_hash] = {
        "device_name": str(payload.get("device_name") or "mobile companion")[:80],
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": expires_at,
        "revoked": False,
    }
    return {"companion_token": token, "expires_at": datetime.fromtimestamp(expires_at, UTC).isoformat()}


@app.post("/api/companion/pairing/revoke-all")
def companion_pairing_revoke_all(request: Request) -> dict[str, Any]:
    if not _client_is_loopback(request):
        raise HTTPException(status_code=403, detail="device revocation is available on the desktop only")
    for record in COMPANION_TOKENS.values():
        record["revoked"] = True
    return {"revoked": True, "device_count": len(COMPANION_TOKENS)}



SUGGESTION_TRIGGERS = ("我覺得", "不該", "不得", "必須", "驗收", "判準", "規則", "偏好", "流程", "邊界", "入庫")
HIGH_PRIVILEGE_DRAFT_KEYS = {"review_passed", "storage_confirmed", "physical_write_performed", "confirmed"}
SCBKR_COMMITTED_EDIT_MESSAGE = "本任務已寫入資料中心或記憶庫規則，不能直接改寫原 SCBKR。請建立新版本或新任務。已入庫或已完成 / 已寫入記憶庫規則的任務不可直接改寫 SCBKR。"
SCBKR_INVALID_PATCH_MESSAGE = "模型提出的修改草案不完整，未套用到任務。原本的 SCBKR 已保留，請重新產生修改草案或手動修改欄位。"

SCBKR_WORKBENCH_CAPABILITY_ZH = """可以，我可以協助編輯 SCBKR 工作台。

但我不能繞過使用者直接改寫，也不能自動套用修改。正確流程是：使用者在 Workbench 選擇 S / C / B / K / R 層級，輸入自然語言修改指令，按「產生修改草案」，系統只產生人話摘要與欄位差異，不會自動套用。使用者按「套用修改」後，才會寫回 task.scbkr。套用後 confirmed=false，舊 generation / review / storage plan 會作廢，必須重新確認責任鏈後，才能再次生成。

驗收通過後，我可以產生入庫建議，建議是否寫入檢索庫、資料庫、規則庫、記憶庫。模型只能建議，不能自動入庫；必須由使用者二次確認後才會 physical write。寫入後，後續任務可以從 Data Center 與四庫引用已確認資料，Workbench 也會顯示引用證據。"""

def _normalize_scbkr_terms(text: str) -> str:
    return (text or "").lower().replace("sckr", "scbkr").replace("工作檯", "工作台")

def _is_scbkr_product_question(text: str) -> bool:
    normalized = _normalize_scbkr_terms(text)
    has_term = any(token in normalized for token in ("scbkr", "workbench", "data center", "四庫", "s/c/b/k/r", "工作台"))
    asks_identity = any(token in normalized for token in ("什麼是", "是什么", "介紹", "定義", "是什麼", "what is"))
    return has_term and asks_identity

def _is_workbench_capability_question(text: str) -> bool:
    normalized = _normalize_scbkr_terms(text)
    has_workbench = any(token in normalized for token in ("scbkr", "workbench", "工作台", "s/c/b/k/r"))
    asks_capability = any(token in normalized for token in ("能編輯", "可以編輯", "修改", "怎麼編輯", "如何編輯", "edit", "update", "revise"))
    return has_workbench and asks_capability


def _looks_english(text: str) -> bool:
    if any("\u3400" <= ch <= "\u9fff" for ch in text):
        return False
    letters = sum(ch.isascii() and ch.isalpha() for ch in text)
    non_ascii = sum(not ch.isascii() for ch in text)
    return letters > 0 and letters >= non_ascii


def _response_locale(text: str, requested: str | None = None) -> str:
    if any("\u3040" <= ch <= "\u30ff" for ch in text):
        return "ja"
    if any("\uac00" <= ch <= "\ud7af" for ch in text):
        return "ko"
    if _looks_english(text):
        return "en"
    if requested in {"en", "ja", "ko", "zh-TW"}:
        return str(requested)
    return "zh-TW"


def _zh_tw_output_guard(text: str) -> str:
    replacements = {
        "什么": "什麼", "么": "麼", "这里": "這裡", "这": "這", "个": "個", "请": "請",
        "说": "說", "为": "為", "与": "與", "应": "應", "后": "後", "关": "關",
        "时": "時", "对": "對", "发": "發", "写": "寫", "义": "義", "态": "態",
        "规": "規", "则": "則", "库": "庫", "认": "認", "证": "證", "权": "權",
        "启": "啟", "帮": "幫", "问": "問", "资": "資", "测": "測", "试": "試",
        "输": "輸", "层": "層", "责": "責", "链": "鏈", "语": "語", "构": "構",
        "标": "標", "签": "簽", "验": "驗", "审": "審", "计": "計", "广": "廣",
    }
    guarded = normalize_locale_text(text, "zh-TW")
    for simplified, traditional in replacements.items():
        guarded = guarded.replace(simplified, traditional)
    return guarded


def _is_identity_question(text: str) -> bool:
    return detect_product_topic(text) == "identity"


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




CHAT_INTENTS = {
    "normal_chat", "suggest_create_confirmation", "create_confirmation",
    "suggest_new_rule_confirmation", "create_new_rule_confirmation", "data_center_query",
    "suggest_data_center_update_confirmation", "create_data_center_update_confirmation",
    "suggest_data_center_delete_confirmation", "create_data_center_delete_confirmation",
}

def _normalize_chat_intent_text(text: str) -> str:
    value = _normalize_scbkr_terms(text)
    replacements = {
        "責任練": "責任鏈", "工作檯": "工作台", "work bench": "workbench",
        "sckr": "scbkr", "任務確認單": "確認單", "責任確認單": "確認單",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    for ch in " ，,。！？!?:：；;（）()[]【】\n\t":
        value = value.replace(ch, "")
    return value

def route_chat_intent(message: str) -> dict[str, Any]:
    raw = (message or "").strip()
    rule_os_classification = classify_user_input(raw)
    normalized = _normalize_chat_intent_text(raw)
    def has_any(tokens: tuple[str, ...]) -> bool:
        return any(token in normalized for token in tokens)
    delete_terms = ("刪除", "移除", "封存", "不要再引用", "取消引用", "revoke", "archive")
    update_terms = ("幫我改", "更新", "更改", "修改那筆", "修改某", "改那條", "update")
    query_terms = ("幫我查", "幫我找", "找到哪天", "哪個計畫", "上週那個", "某個任務", "某筆資料", "資料中心")
    citation_terms = ("引用我們之前", "引用之前", "照我之前的判準", "照之前的規則", "之前聊過的規則", "過去規則", "previousrule", "citeprevious")
    rule_terms = ("建立規則", "生成規則", "整理成規則", "變成規則", "規則化", "以後凡是", "createrule", "newrule")
    memory_terms = ("幫我記住", "記住", "寫入記憶", "存起來", "以後照這樣做", "之後遇到類似情況", "這個判斷要入庫", "放進四庫", "當依據")
    audit_terms = ("幫我審計", "建立流程", "產生任務單", "生成任務單", "auditthis", "createworkflow")
    create_terms = (
        "生成確認單", "建立確認單", "生成責任鏈", "建立責任鏈", "責任鏈任務確認單", "責任鏈確認單",
        "工作台草案", "開工作台", "幫我建確認單", "幫我做責任鏈", "你能生成責任鏈確認單嗎",
        "workbench草案", "scbkr確認單", "scbkr任務", "確認單草案",
    )
    suggest_terms = (
        "以後要重用", "想固定這個做法", "這個判斷想重用", "下次也要照這樣",
        "規劃一個可重用流程", "make this reusable", "reuse this decision", "use this next time",
    )
    rule_os_mode = str(rule_os_classification.get("mode") or "")
    if str(rule_os_classification.get("reason") or "").startswith("explicit_chat_only"):
        intent = "normal_chat"
    elif rule_os_mode == "generate_rule":
        intent = "create_new_rule_confirmation"
    elif rule_os_mode == "query_four_stores":
        intent = "data_center_query"
    elif rule_os_mode == "answer_with_rules":
        # Continue to /api/chat/general so that it can build the current rule
        # package, call the model, post-check the answer, and record token use.
        intent = "normal_chat"
    elif rule_os_mode == "modify_existing_rule":
        intent = "normal_chat"
    elif rule_os_mode == "confirm_storage":
        intent = "normal_chat"
    elif rule_os_mode in {"tool_execution", "high_risk_action"} and has_any(memory_terms):
        intent = "create_confirmation"
    elif rule_os_mode in {"tool_execution", "high_risk_action"}:
        intent = "normal_chat"
    elif has_any(delete_terms):
        intent = "create_data_center_delete_confirmation" if has_any(("確認單", "建立", "生成")) else "suggest_data_center_delete_confirmation"
    elif has_any(update_terms):
        intent = "create_data_center_update_confirmation" if has_any(("確認單", "建立", "生成")) else "suggest_data_center_update_confirmation"
    elif has_any(query_terms) or has_any(citation_terms):
        intent = "data_center_query"
    elif has_any(rule_terms):
        intent = "create_new_rule_confirmation"
    elif has_any(memory_terms) or has_any(audit_terms):
        intent = "create_confirmation"
    elif has_any(create_terms) or ("確認單" in normalized and has_any(("生成", "建立", "建", "開"))):
        intent = "create_confirmation"
    elif has_any(suggest_terms):
        intent = "suggest_new_rule_confirmation" if "規則" in normalized else "suggest_create_confirmation"
    else:
        intent = "normal_chat"
    requires_draft = intent in {"create_confirmation", "create_new_rule_confirmation", "create_data_center_update_confirmation", "create_data_center_delete_confirmation"}
    object_type = "rule" if intent == "create_new_rule_confirmation" else "memory" if has_any(memory_terms) else "task"
    return {
        "intent": intent,
        "normalized": normalized,
        "message": raw,
        "inferred_task_type": "general",
        "conversation_state": "DRAFTING" if requires_draft else "SESSION_CONTEXT_ONLY",
        "requires_draft": requires_draft,
        "draft_object_type": object_type,
        "retrieval_source": "storage_confirmed_four_stores_only" if intent == "data_center_query" else None,
        "rule_os_classification": rule_os_classification,
    }

def _extract_json_object(text: str) -> Any:
    value = (text or "").strip()
    if "```" in value:
        parts = value.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{"):
                try: return json.loads(candidate)
                except Exception: pass
    start = value.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(value)):
            ch = value[index]
            if in_string:
                if escape: escape = False
                elif ch == "\\": escape = True
                elif ch == '"': in_string = False
            else:
                if ch == '"': in_string = True
                elif ch == "{": depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(value[start:index + 1])
        start = value.find("{", start + 1)
    return json.loads(value)

def _contains_forbidden_draft_state(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in HIGH_PRIVILEGE_DRAFT_KEYS and item is True:
                return True
            if key == "confirmation_status" and item == "confirmed":
                return True
            if key == "signature_status" and item in ("confirmed", "owner_signed"):
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
    return (
        _MODEL_SESSION_VERIFIED
        and MODEL_SETTINGS.get("enabled") is True
        and MODEL_SETTINGS.get("last_test_status") == "success"
    )


def _mark_model_runtime_unavailable(message: str) -> None:
    global _MODEL_SESSION_VERIFIED
    _MODEL_SESSION_VERIFIED = False
    MODEL_SETTINGS.update(
        {
            "enabled": False,
            "last_test_status": "failed",
            "last_test_message": message,
            "last_test_at": _now(),
        }
    )
    save_runtime_section("model", MODEL_SETTINGS)


def _keyword_tokens(text: str) -> set[str]:
    raw = (text or "").lower()
    tokens = {t for t in raw.replace("/", " ").replace("_", " ").split() if len(t) >= 2}
    for key in ("滷肉飯", "文案", "餐飲", "ui", "介面", "規則", "計畫", "商業"):
        if key in raw:
            tokens.add(key)
    return tokens

def _retrieval_relevance(raw_input: str, source_store: str, text_value: str, task_type: str = "general", score: Any = None) -> tuple[bool, str]:
    relation = classify_evidence_relation(raw_input, text_value, score=score, source_store=source_store)
    return bool(relation["adopted"]), relation["relation_reason"]

def _build_four_store_context(raw_input: str, task_id: str | None = None) -> dict[str, Any]:
    """Read confirmed Data Center/four-store evidence before model drafting, with relevance gate."""
    adopted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    try:
        retrieval = query_retrieval_cases(raw_input, task_id=task_id, top_k=5)
    except Exception as exc:
        retrieval = {"backend": "unavailable", "candidates": [], "error": str(exc)}
    for candidate in retrieval.get("candidates", []) or []:
        case_type = str(candidate.get("case_type") or candidate.get("target") or "vector")
        source_target = str(candidate.get("source_target") or candidate.get("case_json", {}).get("source_target") or "")
        source_store = "memory" if "memory" in case_type else source_target if source_target in ("corpus", "logic") else "vector"
        text_value = str(candidate.get("retrieval_text", ""))
        relation = classify_evidence_relation(raw_input, text_value, score=candidate.get("score"), source_store=source_store)
        ok, reason = bool(relation["adopted"]), relation["relation_reason"]
        hit = {"source_store": source_store, "rule": text_value[:800], "case_id": candidate.get("case_id"), "status": "沿用" if ok else "未採用：相關性不足", "governance_status": candidate.get("governance_status") or candidate.get("status") or "active", "adopted": ok, "reason": reason, "rule_confirmed": ok, "score": candidate.get("score"), "signature_status": candidate.get("signature_status") or "unsigned", "review_passed": candidate.get("review_passed") is True, "content_hash": candidate.get("content_hash") or candidate.get("rule_hash") or candidate.get("retrieval_text_hash"), "author_id": candidate.get("author_id"), "version": candidate.get("version"), **relation}
        if any(token in text_value for token in ("不得", "禁止", "不准", "must not")):
            hit["must_cite"] = True
        (adopted if ok else rejected).append(hit)
    for item in list_persisted_storage_items(limit=50):
        target = item.get("target")
        if target in ("corpus", "logic", "memory", "vector", "vector_db"):
            payload = item.get("payload") or item
            text_value = str(payload.get("summary") or payload.get("content") or payload.get("purpose") or payload.get("raw_input") or item.get("relative_path") or item.get("hash"))
            source_store = "vector" if target == "vector_db" else target
            relation = classify_evidence_relation(raw_input, text_value, source_store=source_store)
            signature_status = payload.get("signature_status") or payload.get("scbkr_snapshot", {}).get("signature_status")
            review_passed = item.get("review_passed") is True or payload.get("review_passed") is True or payload.get("review_result", {}).get("review_passed") is True
            unavailable_status = item.get("status") in ("disabled", "revoked", "archived", "superseded", "deleted") or payload.get("status") in ("disabled", "revoked", "archived", "superseded", "deleted")
            if unavailable_status:
                relation.update({"adopted": False, "adoption_scope": "none", "relation_reason": "狀態不可用：disabled / revoked / archived / superseded / deleted"})
            elif signature_status != "owner_signed":
                relation.update({"adopted": False, "adoption_scope": "none", "relation_reason": "未完成使用者簽名"})
            elif review_passed is not True:
                relation.update({"adopted": False, "adoption_scope": "none", "relation_reason": "未通過使用者驗收"})
            elif relation.get("relation") == "similar_grammar":
                relation.update({"adopted": False, "adoption_scope": "grammar"})
            ok, reason = bool(relation["adopted"]), relation["relation_reason"]
            hit = {"source_store": source_store, "rule": text_value[:800], "status": "沿用" if ok else "未採用：相關性不足", "governance_status": item.get("status") or payload.get("status") or "active", "adopted": ok, "reason": reason, "rule_confirmed": ok, "storage_item_id": item.get("item_id"), "signature_status": signature_status, "review_passed": review_passed, "hash": item.get("hash") or item.get("content_hash"), "author_id": (payload.get("owner_signature") or {}).get("confirmed_by") or payload.get("confirmed_by"), "version": item.get("version") or payload.get("version") or 1, **relation}
            (adopted if ok else rejected).append(hit)
    for rule in list_persisted_memory_rules(limit=20):
        text_value = str(rule.get("rule_text") or rule.get("memory_rule") or rule.get("payload") or rule)
        relation = classify_evidence_relation(raw_input, text_value, source_store="memory")
        ok, reason = bool(relation["adopted"]), relation["relation_reason"]
        signature_status = "owner_signed" if str(rule.get("reviewer_signature") or "").strip() else "unsigned"
        if signature_status != "owner_signed":
            relation.update({"adopted": False, "adoption_scope": "none", "relation_reason": "記憶規則未完成使用者簽名"})
            ok, reason = False, relation["relation_reason"]
        hit = {"source_store": "memory", "rule": text_value[:800], "status": "沿用" if ok else "未採用：相關性不足", "governance_status": rule.get("status") or "active", "adopted": ok, "reason": reason, "rule_confirmed": ok, "must_cite": any(t in text_value for t in ("不得", "禁止", "不准", "must not")), "memory_rule_id": rule.get("rule_id"), "signature_status": signature_status, "review_passed": True, "content_hash": rule.get("rule_hash"), "author_id": "owner", "version": rule.get("version") or 1, **relation}
        (adopted if ok else rejected).append(hit)
    evidence_packet = build_evidence_packet({"adopted_hits": adopted})
    citations = evidence_packet["citations"]
    return {"retrieval_first": True, "query": raw_input, "retrieval_result": retrieval, "hits": citations, "adopted_hits": citations, "candidate_hits": evidence_packet["candidates"], "rejected_hits": rejected, "conflicts": conflicts, "no_confirmed_rules": not citations, "must_cite_confirmed_rules": [h for h in citations if h.get("must_cite")], "evidence_packet": evidence_packet}


def _deferred_four_store_context(raw_input: str) -> dict[str, Any]:
    evidence_packet = build_evidence_packet({"adopted_hits": []})
    return {
        "retrieval_first": True,
        "retrieval_deferred": True,
        "query": raw_input,
        "retrieval_result": {"backend": "deferred_for_fast_workbench_entry", "candidates": []},
        "hits": [],
        "adopted_hits": [],
        "candidate_hits": [],
        "rejected_hits": [],
        "conflicts": [],
        "no_confirmed_rules": True,
        "must_cite_confirmed_rules": [],
        "evidence_packet": evidence_packet,
    }


def _validate_task_understanding(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError("task understanding must be object")
    if _contains_forbidden_draft_state(candidate):
        raise ValueError("task understanding contains forbidden confirmed/high-privilege state")
    if candidate.get("signature_status") in ("confirmed", "owner_signed"):
        raise ValueError("model cannot set signature_status")
    return validate_task_understanding_strict(candidate)


def _model_authored_scbkr_draft(
    raw_input: str,
    task_type: str,
    retrieval_context: dict[str, Any] | None = None,
    rule_assist_assessment: dict[str, Any] | None = None,
    defer_model_call: bool = False,
) -> tuple[dict[str, Any], bool, str | None]:
    understanding = None
    skipped_reason = None
    compiler_errors: list[str] = []
    compiler_attempts = 0
    compiler_repairs = 0
    messages: list[dict[str, Any]] = []
    provider_usages: list[dict[str, Any]] = []
    if defer_model_call:
        skipped_reason = "model_deferred_for_workbench"
    elif MODEL_SETTINGS.get("enabled") is True and MODEL_SETTINGS.get("mode") != "sandbox":
        try:
            if _model_draft_requires_external_api_permission(MODEL_SETTINGS) and PERMISSIONS.get("external_api") is not True:
                skipped_reason = "external_api_permission_disabled"
                raise PermissionError(skipped_reason)
            messages = build_task_understanding_messages(raw_input, task_type, retrieval_context)
            lightweight_local = MODEL_SETTINGS.get("mode") == "local" and any(
                marker in str(MODEL_SETTINGS.get("model_name") or "").lower()
                for marker in ("0.5b", "1b", "1.5b")
            )
            compiler_settings = {
                **MODEL_SETTINGS,
                "max_tokens": min(MODEL_SETTINGS["max_tokens"], 384 if lightweight_local else 1024),
            }
            compiler_attempts = 1
            try:
                response = _post_openai_compatible(compiler_settings, messages, response_format=task_understanding_response_format())
            except TypeError as exc:
                if "response_format" not in str(exc):
                    raise
                response = _post_openai_compatible(compiler_settings, messages)
            model_raw = parse_chat_completion_response(response)
            if isinstance(response.get("usage"), dict):
                provider_usages.append(response["usage"])
            try:
                understanding = _validate_task_understanding(_extract_json_object(model_raw))
            except Exception as first_error:
                compiler_errors.append(str(first_error))
                if lightweight_local:
                    understanding = None
                    skipped_reason = "lightweight_model_invalid_json_used_base_logic"
                else:
                    compiler_repairs = 1
                    compiler_attempts = 2
                    repair_messages = build_repair_messages(messages, model_raw, first_error)
                    try:
                        try:
                            repaired_response = _post_openai_compatible(compiler_settings, repair_messages, response_format=task_understanding_response_format())
                        except TypeError as exc:
                            if "response_format" not in str(exc):
                                raise
                            repaired_response = _post_openai_compatible(compiler_settings, repair_messages)
                        repaired_raw = parse_chat_completion_response(repaired_response)
                        if isinstance(repaired_response.get("usage"), dict):
                            provider_usages.append(repaired_response["usage"])
                        understanding = _validate_task_understanding(_extract_json_object(repaired_raw))
                    except Exception as repair_error:
                        compiler_errors.append(str(repair_error))
                        understanding = None
                        skipped_reason = "model_compiler_repair_failed"
        except PermissionError:
            understanding = None
        except Exception as exc:
            skipped_reason = f"model_unavailable_or_invalid_json: {exc}"
            understanding = None
    else:
        skipped_reason = "model_not_connected"
    draft = build_scbkr_from_understanding(raw_input, task_type, understanding, retrieval_context)
    if rule_assist_assessment is None:
        rule_assist_assessment = _assess_rule_assist(
            raw_input,
            locale=_response_locale(raw_input, None),
            target_mode="task",
            four_store_context=retrieval_context,
        )
    draft = apply_rule_assist_to_scbkr(raw_input, draft, rule_assist_assessment)
    draft = apply_plan_depth_to_draft(
        raw_input,
        draft,
        str((rule_assist_assessment or {}).get("plan_level") or RULE_ASSIST_SETTINGS.get("plan_level") or "FREE"),
    )
    draft["compiler_report"] = build_compiler_report(
        status="model_compiled" if understanding is not None else "base_logic" if compiler_attempts == 0 else "base_logic_after_model",
        attempts=compiler_attempts,
        repairs=compiler_repairs,
        errors=compiler_errors,
        model_used=understanding is not None,
    )
    draft["token_metrics"] = build_token_efficiency_metrics(
        raw_input=raw_input,
        messages=messages,
        retrieval_context=retrieval_context,
        full_rule_registry=_rule_registry().list_rules(),
        provider_usages=provider_usages,
        attempts=compiler_attempts,
        model_settings=MODEL_SETTINGS,
        pricing=PRICING_SETTINGS,
    )
    if skipped_reason:
        draft["draft_model_call_skipped_reason"] = skipped_reason
    return draft, False, skipped_reason

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


def _compiled_scbkr_authoring_view(scbkr: dict[str, Any]) -> dict[str, Any]:
    """Build a semantic-validation view from the editable compiled draft."""
    view: dict[str, Any] = {}
    schema_repaired = bool(scbkr.get("model_schema_repaired"))
    for dimension in SCBKR_CONFIRMATION_REQUIRED_FIELDS:
        payload = scbkr.get(dimension) if isinstance(scbkr.get(dimension), dict) else {}
        owner_edited = bool((payload.get("owner_edit") or {}).get("owner_edited"))
        adapter_generated = payload.get("model_schema_adapter_generated")
        if adapter_generated is None:
            # Older persisted drafts did not retain this flag. Stay conservative:
            # a compact model explanation cannot prove semantic understanding
            # until the owner actually rewrites that dimension.
            adapter_generated = schema_repaired and not owner_edited
        view[dimension] = {
            "content": str(payload.get("owner_draft_content") or payload.get("model_draft_content") or "").strip(),
            "explanation": str(payload.get("model_explanation") or "").strip(),
            "missing_information": payload.get("missing_information") or [],
            "needs_user_confirmation": payload.get("needs_user_confirmation") or [],
            "model_cannot_decide": payload.get("model_cannot_decide") or [],
            "risk_notes": payload.get("risk_notes") or [],
            "schema_adapter_generated": bool(adapter_generated),
            "model_explanation_derived_from_fields": bool(payload.get("model_explanation_derived_from_fields")) or owner_edited,
            "model_explanation_repaired_by_model": bool(payload.get("model_explanation_repaired_by_model")),
        }
    support_fields = (
        "rule_summary",
        "missing_information",
        "user_confirmation_items",
        "model_cannot_decide",
        "risk_reminders",
        "next_actions",
    )
    for key in support_fields:
        view[key] = scbkr.get(key)
    view["model_global_fields_present"] = {key: key in scbkr for key in support_fields}
    view["model_support_fields_derived"] = scbkr.get("model_support_fields_derived") or {}
    return view


def _revalidate_revised_scbkr(task: dict[str, Any], *, revision_source: str) -> dict[str, Any]:
    """Re-run real semantic and kernel gates after a user or model edit.

    A previously limited model draft may become signable only when the actual
    edited five-dimensional content closes every gate. This never invents a
    replacement rule and never changes the original model audit result.
    """
    scbkr = task.get("scbkr")
    if not isinstance(scbkr, dict):
        raise HTTPException(status_code=400, detail="SCBKR draft required before validation")
    validate_scbkr_draft_for_confirmation(scbkr)
    kernel_pack = ensure_local_kernel_cache()
    structural = validate_validity_failure(scbkr, kernel_pack)
    model_authored = bool(scbkr.get("model_authored") or scbkr.get("model_participated") or task.get("model_used"))
    semantic = (
        validate_model_rulebook_semantics(
            _compiled_scbkr_authoring_view(scbkr),
            user_input=str(task.get("raw_input") or ""),
        )
        if model_authored
        else {"passed": True, "note": "Non-model draft; semantic model-authoring gate not applicable."}
    )
    passed = structural.get("passed") is True and semantic.get("passed") is True
    locale = str((scbkr.get("meta") or {}).get("locale") or _response_locale(str(task.get("raw_input") or ""), None))
    previous_source = str(scbkr.get("draft_source") or task.get("draft_source") or "")
    owner_repaired = revision_source in {"owner_dimension_edit", "owner_full_edit"}
    if passed:
        if previous_source == "model_capability_limited":
            resolved_source = "owner_repaired_model_rulebook" if owner_repaired else "model_repaired_rulebook"
        else:
            resolved_source = previous_source or ("owner_repaired_model_rulebook" if owner_repaired else "model_assisted_rulebook")
        capability = dict(scbkr.get("model_capability") or task.get("model_capability") or {})
        if capability:
            capability.update(
                {
                    "state": "owner_repaired" if owner_repaired else "model_repaired",
                    "current_task_closure": True,
                    "unresolved_gaps": [],
                    "gap_codes": [],
                    "owner_decision_required": True,
                    "recommended_action": (
                        "Review the revised rulebook and sign only if it matches your intent."
                        if locale.lower().startswith("en")
                        else "請逐欄確認修正後的規則書；只有符合你的原意時才簽名。"
                    ),
                }
            )
            scbkr["model_capability"] = capability
            task["model_capability"] = capability
        scbkr["draft_source"] = resolved_source
        scbkr["signing_allowed"] = True
        scbkr["next_required_action"] = "owner_review_and_signature"
        task["draft_source"] = resolved_source
        task["status"] = "waiting_user_confirm"
        task["signing_allowed"] = True
        task["next_required_action"] = "owner_review_and_signature"
    else:
        attempts = int((scbkr.get("compiler_report") or {}).get("attempts") or 1)
        capability = build_model_capability_assessment(
            semantic,
            attempts=attempts,
            locale=locale,
            model_name=str(scbkr.get("model_name") or task.get("model_name") or ""),
        )
        scbkr["draft_source"] = "model_capability_limited" if model_authored else previous_source
        scbkr["model_capability"] = capability
        scbkr["signing_allowed"] = False
        scbkr["next_required_action"] = "owner_clarify_or_select_stronger_model"
        task["draft_source"] = scbkr["draft_source"]
        task["model_capability"] = capability
        task["status"] = "model_capability_limited" if model_authored else "model_validation_failed"
        task["signing_allowed"] = False
        task["next_required_action"] = scbkr["next_required_action"]
    scbkr["compiled_semantic_valid"] = semantic.get("passed") is True
    scbkr["compiled_semantic_report"] = semantic
    scbkr["validator_passed"] = passed
    scbkr["last_revision_source"] = revision_source
    scbkr.setdefault("compiler_report", {}).update(
        {
            "validator_passed": passed,
            "validator": structural,
            "compiled_semantic_valid": semantic.get("passed") is True,
            "compiled_semantic_report": semantic,
            "last_revision_source": revision_source,
        }
    )
    task["validator_passed"] = passed
    task["compiled_semantic_valid"] = semantic.get("passed") is True
    task["compiled_semantic_report"] = semantic
    if isinstance(task.get("kernel_runtime"), dict):
        task["kernel_runtime"]["validator"] = structural
    return {"passed": passed, "semantic": semantic, "structural": structural}


def _reset_owner_signature_status(scbkr: dict[str, Any]) -> None:
    if not isinstance(scbkr, dict):
        return
    scbkr["signature_status"] = "waiting_owner_signature"
    scbkr["owner_signature_required"] = True
    scbkr["model_signature_allowed"] = False
    scbkr["model_role"] = "describe_compile_only"
    scbkr.setdefault("R", {})["signature_status"] = "waiting_owner_signature"
    scbkr["R"]["required_signer"] = "user"
    scbkr["R"]["model_signature_allowed"] = False
    scbkr["R"]["closure_condition"] = "owner_signature_required"


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
        draft_source = task.get("scbkr", {}).get("draft_source")
        task["status"] = "draft_failed" if draft_source == "draft_failed" else "model_capability_limited" if draft_source == "model_capability_limited" else "waiting_user_confirm"
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
    public["runtime_verified"] = _MODEL_SESSION_VERIFIED
    if not _MODEL_SESSION_VERIFIED and public.get("last_test_status") == "success":
        public.update(
            {
                "enabled": False,
                "last_test_status": "untested",
                "last_test_message": "本次啟動尚未重新確認模型；請測試連線後再開始生成。",
            }
        )
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
    # These are public response markers for the deterministic test model. Do
    # not let them survive when the user switches to a real local/API model.
    settings.pop("sandbox", None)
    settings.pop("external_call_performed", None)
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


def _friendly_model_error(settings: dict[str, Any], message: str, *, locale: str = "zh-TW") -> str:
    provider = settings.get("provider")
    lowered = message.lower()
    english = str(locale).lower().startswith("en")
    if "api_key" in lowered or "authorization" in lowered:
        return "The API key is missing or invalid." if english else "API key 缺失或無效，請輸入正確 API key。"
    if "timed out" in lowered or "timeout" in lowered:
        return (
            "The model endpoint was reached, but this generation exceeded the current wait time. "
            "No template or fallback was used. Retry or increase the local wait time; a slow response alone does not mean the model is incompatible."
            if english
            else "模型端點可連線，但本次生成超過目前等候時間；系統沒有套用模板或 fallback。請重試或增加本地等候時間，回覆較慢不代表模型不相容。"
        )
    if provider in ("lm_studio", "ollama"):
        name = "LM Studio" if provider == "lm_studio" else "Ollama"
        return (
            f"Could not reach the local model. Check that the {name} server is running and that the Base URL and model name are correct."
            if english
            else f"無法連線到本地模型，請確認 {name} Server 是否已啟動、Base URL 與模型名稱是否正確。"
        )
    return (
        "Could not reach the API model. Check the API Base URL, API key, and model name."
        if english
        else "無法連線到 API 模型，請確認 API base URL、API key 與模型名稱。"
    )


def _model_unavailable_reply(locale: str, reason: str = "") -> str:
    if locale == "en":
        detail = "The model is not connected or did not respond."
        return f"{detail} SCBKR did not replace the model with a template or hidden fallback. Open Model Settings, test the connection, and retry.\n\nStatus: {reason or 'model_unavailable'}"
    detail = "模型目前未連線或沒有回覆。"
    return f"{detail} SCBKR 不會用模板或隱藏 fallback 冒充模型回答。請到「模型設定」測試連線與生成權限後再試。\n\n狀態：{reason or 'model_unavailable'}"

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


def _post_openai_compatible(settings: dict[str, Any], messages: list[dict[str, str]], response_format: dict[str, Any] | None = None) -> dict[str, Any]:
    # Rulebook authoring already receives the local SCBKR Kernel contract. Do
    # not append the larger chat identity/state envelope to that request.
    governed_messages = messages if settings.get("_skip_rule_state_context") else _rule_state_manager().inject_system_context(messages)
    payload = build_chat_completion_payload(governed_messages, settings, response_format=response_format)
    url = settings["base_url"].rstrip("/") + "/chat/completions"
    request = UrlRequest(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=build_headers(settings),
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings["timeout"]) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
        except Exception:
            detail = ""
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"model http error: {exc.code}{suffix}") from exc
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


def _model_rulebook_unavailable_reason() -> str | None:
    if MODEL_SETTINGS.get("mode") == "sandbox" or MODEL_SETTINGS.get("provider") == SANDBOX_PROVIDER:
        return "model_not_connected"
    if not _model_connected():
        return "model_not_connected"
    if not str(MODEL_SETTINGS.get("model_name") or "").strip():
        return "model_not_connected"
    if PERMISSIONS.get("model_generate") is not True:
        return "model_generate_permission_required"
    if _model_call_requires_external_api_permission(MODEL_SETTINGS) and PERMISSIONS.get("external_api") is not True:
        return "external_api_permission_required"
    return None


def _uses_lightweight_local_authoring(settings: dict[str, Any]) -> bool:
    if settings.get("mode") != "local":
        return False
    name = str(settings.get("model_name") or "").lower()
    return any(marker in name for marker in ("0.5b", "1.5b", "2b", "3b", "4b", "mini", "small", "phi-3"))


def _post_same_model_with_schema(
    settings: dict[str, Any],
    messages: list[dict[str, str]],
    response_format: dict[str, Any],
) -> dict[str, Any]:
    """Negotiate structured output without changing provider or model."""
    if _uses_lightweight_local_authoring(settings):
        # CPU-bound 0.5B-4B models can spend the entire request budget inside
        # constrained JSON-schema decoding. The prompt still requires the same
        # object, and the parser plus Kernel Validator enforce the contract.
        return _post_openai_compatible(settings, messages)
    try:
        return _post_openai_compatible(settings, messages, response_format=response_format)
    except Exception as exc:
        message = str(exc).lower()
        if not any(token in message for token in ("response_format", "json_schema", "structured output", "unsupported")):
            raise
        return _post_openai_compatible(settings, messages)


def _repair_model_rulebook_dimensions(
    candidate: dict[str, Any],
    *,
    raw_input: str,
    locale: str,
    settings: dict[str, Any],
    provider_usages: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, str]]]:
    """Ask the same small model to rewrite only unresolved SCBKR dimensions."""
    repaired = json.loads(json.dumps(candidate, ensure_ascii=False))
    repaired, initial_kernel_repairs = compile_kernel_required_clauses(
        repaired,
        user_input=raw_input,
        locale=locale,
    )
    repaired, initial_authority_repairs = enforce_kernel_authority_boundary(
        repaired,
        locale=locale,
    )
    repaired = refresh_model_rulebook_support_fields(repaired, locale=locale)
    report = validate_model_rulebook_semantics(repaired, user_input=raw_input)
    repaired["model_semantic_report"] = report
    repaired["model_semantic_valid"] = report.get("passed") is True
    targets = model_rulebook_repair_targets(report, limit=3)
    repair_audit: list[dict[str, Any]] = [{
        "layer": item["layer"],
        "model_used": False,
        "schema_valid": True,
        "kernel_compile_audit": item,
    } for item in initial_kernel_repairs]
    repair_audit.extend({
        "layer": str(item.get("path") or "authority"),
        "model_used": False,
        "schema_valid": True,
        "kernel_authority_guard": item,
    } for item in initial_authority_repairs)
    if not targets:
        repaired["model_dimension_repairs"] = repair_audit
        return repaired, repair_audit, []

    instructions = {
        layer: model_dimension_repair_instruction(layer, locale=locale)
        for layer in targets
    }
    repair_messages: list[dict[str, str]] = []
    for layer in targets:
        raw_patch = ""
        try:
            current = repaired.get(layer) or {}
            role_alignment = report.get("dimension_role_alignment") or {}
            explanation_alignment = report.get("model_explanation_alignment") or {}
            explanation_only = (
                explanation_alignment.get(layer) is not True
                and layer not in (report.get("placeholder_dimensions") or [])
                and (
                    (layer == "S" and report.get("subject_request_alignment") is True)
                    or (layer != "S" and role_alignment.get(layer) is True)
                )
            )
            use_basis_selection = layer == "K" and (
                not explanation_only
                and role_alignment.get("K") is not True
                or report.get("k_signature_as_basis") is True
                or bool(report.get("k_unrequested_non_citable_sources"))
            )
            if explanation_only:
                messages = build_model_dimension_explanation_messages(
                    raw_input,
                    layer=layer,
                    current_content=str(current.get("content") or ""),
                    locale=locale,
                )
            elif use_basis_selection:
                messages = build_model_basis_selection_messages(
                    raw_input,
                    locale=locale,
                )
            else:
                messages = build_model_dimension_patch_messages(
                    raw_input,
                    layer=layer,
                    instruction=instructions[layer],
                    current_dimension={
                        "model_draft_content": current.get("content"),
                        "model_explanation": current.get("explanation"),
                        "missing_information": current.get("missing_information"),
                        "needs_user_confirmation": current.get("needs_user_confirmation"),
                    },
                    locale=locale,
                    compact=True,
                )
            repair_messages.extend(messages)
            if use_basis_selection:
                basis_settings = {
                    **settings,
                    "max_tokens": min(max(int(settings.get("max_tokens") or 0), 40), 80),
                }
                response = _post_openai_compatible(basis_settings, messages)
            elif explanation_only:
                explanation_settings = {
                    **settings,
                    "max_tokens": min(max(int(settings.get("max_tokens") or 0), 96), 180),
                }
                response = _post_same_model_with_schema(
                    explanation_settings,
                    messages,
                    model_dimension_explanation_response_format(),
                )
            else:
                response = _post_same_model_with_schema(settings, messages, model_dimension_patch_response_format())
            if isinstance(response, dict) and isinstance(response.get("usage"), dict):
                provider_usages.append(response["usage"])
            raw_patch = parse_chat_completion_response(response)
            basis_audit: dict[str, Any] | None = None
            if use_basis_selection:
                selected_terms = parse_model_basis_selection_output(
                    raw_patch,
                    user_input=raw_input,
                    locale=locale,
                )
                repaired, basis_audit = compile_model_basis_selection_candidate(
                    repaired,
                    selected_terms=selected_terms,
                    raw_model_output=raw_patch,
                    locale=locale,
                )
            elif explanation_only:
                explanation = parse_model_dimension_explanation_output(
                    raw_patch,
                    layer=layer,
                    current_content=str(current.get("content") or ""),
                    user_input=raw_input,
                    locale=locale,
                )
                repaired = merge_model_dimension_explanation_candidate(
                    repaired,
                    layer=layer,
                    explanation=explanation,
                )
            else:
                patch = parse_model_dimension_patch_output(
                    raw_patch,
                    layer=layer,
                    instruction=instructions[layer],
                    user_input=raw_input,
                    locale=locale,
                    require_complete_role=layer not in ("B", "R"),
                )
                repaired = merge_model_dimension_patch_candidate(repaired, layer=layer, patch=patch)
            repair_audit.append({
                "layer": layer,
                "model_used": True,
                "schema_valid": True,
                "raw_preview": raw_patch[:900],
                "repair_kind": "explanation_only" if explanation_only else "dimension_content",
                "model_fragment_compiled": basis_audit is not None,
                "kernel_compile_audit": basis_audit,
            })
        except Exception as exc:
            repair_audit.append({
                "layer": layer,
                "model_used": bool(raw_patch),
                "schema_valid": False,
                "error": str(exc),
                "raw_preview": raw_patch[:900],
            })

    repaired, kernel_repairs = compile_kernel_required_clauses(
        repaired,
        user_input=raw_input,
        locale=locale,
    )
    repair_audit.extend({
        "layer": item["layer"],
        "model_used": False,
        "schema_valid": True,
        "kernel_compile_audit": item,
    } for item in kernel_repairs)
    repaired, authority_repairs = enforce_kernel_authority_boundary(
        repaired,
        locale=locale,
    )
    repair_audit.extend({
        "layer": str(item.get("path") or "authority"),
        "model_used": False,
        "schema_valid": True,
        "kernel_authority_guard": item,
    } for item in authority_repairs)
    repaired = refresh_model_rulebook_support_fields(
        repaired,
        locale=locale,
    )
    semantic_report = validate_model_rulebook_semantics(repaired, user_input=raw_input)
    repaired["model_semantic_report"] = semantic_report
    repaired["model_semantic_valid"] = semantic_report.get("passed") is True
    repaired["model_dimension_repairs"] = repair_audit
    return repaired, repair_audit, repair_messages


def _repair_model_rulebook_schema_gap(
    exc: ModelRulebookAuthoringError,
    *,
    raw_input: str,
    locale: str,
    settings: dict[str, Any],
    provider_usages: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    """Repair one incomplete model field without rewriting valid dimensions."""
    code = str(exc.code or "")
    layer = code[:1].upper()
    if layer not in ("S", "C", "B", "K", "R") or not any(
        token in code for token in ("_missing_content", "_missing_explanation", "_must_be_object")
    ):
        raise exc
    raw_candidate = deepcopy(exc.candidate or {})
    if not raw_candidate:
        raise exc

    value = raw_candidate.get(layer)
    current_content = ""
    current_explanation = str(raw_candidate.get(f"{layer}_explanation") or "").strip()
    if isinstance(value, dict):
        current_content = str(
            value.get("content") or value.get("draft") or value.get("summary") or ""
        ).strip()
        current_explanation = str(value.get("explanation") or current_explanation).strip()
    else:
        current_content = str(value or "").strip()

    explanation_only = code.endswith("_missing_explanation") and len(current_content) >= 2
    instruction = model_dimension_repair_instruction(layer, locale=locale)
    if explanation_only:
        messages = build_model_dimension_explanation_messages(
            raw_input,
            layer=layer,
            current_content=current_content,
            locale=locale,
        )
        repair_settings = {
            **settings,
            "max_tokens": min(max(int(settings.get("max_tokens") or 0), 96), 180),
        }
        response = _post_same_model_with_schema(
            repair_settings,
            messages,
            model_dimension_explanation_response_format(),
        )
        raw_patch = parse_chat_completion_response(response)
        explanation = parse_model_dimension_explanation_output(
            raw_patch,
            layer=layer,
            current_content=current_content,
            user_input=raw_input,
            locale=locale,
        )
        patch = {
            "content": current_content,
            "explanation": explanation,
        }
    else:
        messages = build_model_dimension_patch_messages(
            raw_input,
            layer=layer,
            instruction=instruction,
            current_dimension={
                "model_draft_content": current_content,
                "model_explanation": current_explanation,
            },
            locale=locale,
            compact=True,
        )
        response = _post_same_model_with_schema(
            settings,
            messages,
            model_dimension_patch_response_format(),
        )
        raw_patch = parse_chat_completion_response(response)
        patch = parse_model_dimension_patch_output(
            raw_patch,
            layer=layer,
            instruction=instruction,
            user_input=raw_input,
            locale=locale,
            require_complete_role=False,
        )
    if isinstance(response, dict) and isinstance(response.get("usage"), dict):
        provider_usages.append(response["usage"])

    raw_candidate[layer] = {
        "content": patch["content"],
        "explanation": patch["explanation"],
        "missing_information": patch.get("missing_information") or [],
        "needs_user_confirmation": patch.get("needs_user_confirmation") or [],
        "model_cannot_decide": patch.get("model_cannot_decide") or [],
        "risk_notes": patch.get("risk_notes") or [],
        "model_explanation_repaired_by_model": explanation_only,
    }
    raw_candidate.pop(f"{layer}_explanation", None)
    candidate = parse_model_rulebook_candidate(
        json.dumps(raw_candidate, ensure_ascii=False),
        user_input=raw_input,
        locale=locale,
    )
    return candidate, {
        "layer": layer,
        "model_used": True,
        "schema_valid": True,
        "repair_kind": "schema_explanation_only" if explanation_only else "schema_dimension_content",
        "source_error": code,
        "raw_preview": raw_patch[:900],
    }, messages


def _compile_model_assisted_rulebook(raw_input: str, *, plan_level: str, locale: str) -> dict[str, Any]:
    kernel_pack = ensure_local_kernel_cache()
    unavailable = _model_rulebook_unavailable_reason()
    if unavailable:
        return {
            "ok": False,
            "kernel_pack": kernel_pack,
            "failure": build_authoring_failure(
                reason=unavailable,
                model_provider=str(MODEL_SETTINGS.get("provider") or ""),
                model_name=str(MODEL_SETTINGS.get("model_name") or ""),
                message=(
                    "The model is not connected or lacks generation permission. Complete the connection test and enable generation in Model Settings."
                    if str(locale).lower().startswith("en")
                    else "模型未能連上或尚未取得生成權限；請先到模型設定完成連線測試與權限啟用。"
                ),
                context_audit=build_context_audit(messages=[], kernel_pack=kernel_pack),
            ),
        }
    messages = build_model_rulebook_messages(raw_input, kernel_pack=kernel_pack, plan_level=plan_level, locale=locale)
    model_text = ""
    provider_usages: list[dict[str, Any]] = []
    authoring_attempts = 0
    authoring_errors: list[str] = []
    attempt_audit: list[dict[str, Any]] = []
    partial_candidates: list[tuple[int, dict[str, Any], str, list[dict[str, str]]]] = []
    try:
        authoring_settings = {**MODEL_SETTINGS}
        if authoring_settings.get("mode") != "sandbox":
            # Small local models can need several minutes to emit a complete
            # SCBKR confirmation sheet. Keep this separate from the short
            # connection probe: expiry remains explicit and never triggers a
            # template or hidden fallback.
            authoring_settings["timeout"] = max(int(authoring_settings.get("timeout") or 0), 900)
        # Local 3B-4B models sometimes need more room to finish the global
        # review/risk fields after S/C/B/K/R. Truncating those fields is not a
        # capability failure, so local authoring gets a bounded larger budget.
        requested_output_tokens = int(authoring_settings.get("max_tokens") or 0)
        if _uses_lightweight_local_authoring(authoring_settings):
            authoring_settings["max_tokens"] = min(max(requested_output_tokens, 960), 1200)
        else:
            authoring_settings["max_tokens"] = min(max(requested_output_tokens, 640), 800)
        authoring_settings["_skip_rule_state_context"] = True
        # A real endpoint must author the rulebook. Invalid semantic separation
        # is retried with role-specific feedback; it is never replaced by a
        # template. Parseable attempts remain visible as a task-scoped draft.
        active_messages = list(messages)
        authoring: dict[str, Any] | None = None
        for attempt in range(1, 4):
            authoring_attempts = attempt
            response = None
            try:
                response = _post_same_model_with_schema(
                    authoring_settings,
                    active_messages,
                    model_rulebook_response_format(),
                )
            except Exception:
                raise
            if isinstance(response, dict) and isinstance(response.get("usage"), dict):
                provider_usages.append(response["usage"])
            model_text = parse_chat_completion_response(response)
            schema_repair_audit: dict[str, Any] | None = None
            try:
                candidate = parse_model_rulebook_candidate(model_text, user_input=raw_input, locale=locale)
            except ModelRulebookAuthoringError as exc:
                try:
                    candidate, schema_repair_audit, schema_repair_messages = _repair_model_rulebook_schema_gap(
                        exc,
                        raw_input=raw_input,
                        locale=locale,
                        settings=authoring_settings,
                        provider_usages=provider_usages,
                    )
                    active_messages.extend(schema_repair_messages)
                    model_text = json.dumps(candidate, ensure_ascii=False)
                except ModelRulebookAuthoringError:
                    candidate = None
                except Exception as repair_exc:
                    authoring_errors.append(f"schema_dimension_repair_failed:{repair_exc}")
                    candidate = None
                if candidate is not None:
                    semantic_report = candidate.get("model_semantic_report") or {}
                    semantic_valid = semantic_report.get("passed") is True
                    role_count = sum(
                        1 for value in (semantic_report.get("dimension_role_alignment") or {}).values()
                        if value is True
                    )
                    candidate_score = (
                        role_count
                        + int(semantic_report.get("distinct_dimensions") is True)
                        + int(semantic_report.get("request_alignment") is True)
                    )
                else:
                    authoring_errors.append(str(exc))
                    attempt_audit.append({
                        "attempt": attempt,
                        "schema_valid": False,
                        "semantic_valid": False,
                        "error": str(exc),
                        "raw_preview": model_text[:1200],
                    })
                    if attempt >= 3:
                        raise
                    repair_text = (
                        "The previous response could not be parsed as the required SCBKR JSON. Rewrite the complete object: "
                        "S/C/B/K/R must each contain task-specific content and explanation, and include rule_summary, "
                        "missing_information, user_confirmation_items, model_cannot_decide, risk_reminders, and next_actions. "
                        "Do not use markdown."
                        if str(locale).lower().startswith("en")
                        else "上一版無法解析成 SCBKR JSON。請重寫完整物件：S／C／B／K／R 每一維都要有本次任務專用的 content 與 explanation，"
                        "並補齊 rule_summary、missing_information、user_confirmation_items、model_cannot_decide、risk_reminders、next_actions；不要使用 Markdown。"
                    )
                    active_messages = list(build_model_rulebook_messages(raw_input, kernel_pack=kernel_pack, plan_level=plan_level, locale=locale))
                    active_messages.extend([
                        {"role": "assistant", "content": model_text[:1200]},
                        {"role": "user", "content": repair_text},
                    ])
                    continue

            semantic_report = candidate.get("model_semantic_report") or {}
            semantic_valid = semantic_report.get("passed") is True
            role_count = sum(1 for value in (semantic_report.get("dimension_role_alignment") or {}).values() if value is True)
            candidate_score = role_count + int(semantic_report.get("distinct_dimensions") is True) + int(semantic_report.get("request_alignment") is True)
            attempt_audit.append({
                "attempt": attempt,
                "schema_valid": True,
                "semantic_valid": semantic_valid,
                "semantic_report": semantic_report,
                "schema_dimension_repair": schema_repair_audit,
                "raw_preview": model_text[:1200],
            })
            if semantic_valid:
                authoring = candidate
                messages = active_messages
                break

            authoring_errors.append("scbkr_semantic_roles_invalid")
            if _uses_lightweight_local_authoring(authoring_settings):
                combined_messages = list(active_messages)
                all_dimension_repairs: list[dict[str, Any]] = []
                try:
                    for repair_round in range(1, 3):
                        candidate, dimension_repairs, repair_messages = _repair_model_rulebook_dimensions(
                            candidate,
                            raw_input=raw_input,
                            locale=locale,
                            settings=authoring_settings,
                            provider_usages=provider_usages,
                        )
                        for item in dimension_repairs:
                            item["repair_round"] = repair_round
                        all_dimension_repairs.extend(dimension_repairs)
                        combined_messages.extend(repair_messages)
                        semantic_report = candidate.get("model_semantic_report") or {}
                        semantic_valid = semantic_report.get("passed") is True
                        if semantic_valid or not dimension_repairs:
                            break
                    if not semantic_valid:
                        candidate, authority_repairs = enforce_kernel_authority_boundary(
                            candidate,
                            locale=locale,
                        )
                        if authority_repairs:
                            semantic_report = validate_model_rulebook_semantics(candidate, user_input=raw_input)
                            semantic_valid = semantic_report.get("passed") is True
                            candidate["model_semantic_report"] = semantic_report
                            candidate["model_semantic_valid"] = semantic_valid
                            all_dimension_repairs.extend([
                                {
                                    **item,
                                    "model_used": False,
                                    "schema_valid": True,
                                    "repair_round": "kernel_authority_guard",
                                }
                                for item in authority_repairs
                            ])
                    role_count = sum(
                        1 for value in (semantic_report.get("dimension_role_alignment") or {}).values()
                        if value is True
                    )
                    candidate_score = role_count + int(semantic_report.get("distinct_dimensions") is True) + int(semantic_report.get("request_alignment") is True)
                    attempt_audit[-1]["dimension_repairs"] = all_dimension_repairs
                    attempt_audit[-1]["semantic_valid_after_dimension_repairs"] = semantic_valid
                    attempt_audit[-1]["semantic_report_after_dimension_repairs"] = semantic_report
                    model_text = json.dumps(candidate, ensure_ascii=False)
                    if semantic_valid:
                        authoring = candidate
                        messages = combined_messages
                        break
                except Exception as exc:
                    authoring_errors.append(f"dimension_repair_failed:{exc}")
                    attempt_audit[-1]["dimension_repair_error"] = str(exc)
                partial_candidates.append((candidate_score, candidate, model_text, combined_messages))
                break

            partial_candidates.append((candidate_score, candidate, model_text, list(active_messages)))
            if attempt < 3:
                repair_text = build_semantic_repair_instruction(semantic_report, locale=locale)
                active_messages = list(build_model_rulebook_messages(raw_input, kernel_pack=kernel_pack, plan_level=plan_level, locale=locale))
                active_messages.extend([
                    {"role": "assistant", "content": model_text[:1200]},
                    {"role": "user", "content": repair_text},
                ])

        provider = str(MODEL_SETTINGS.get("provider") or "")
        model_name = str(MODEL_SETTINGS.get("model_name") or "")
        if authoring is None and partial_candidates:
            _, best_candidate, best_model_text, best_messages = max(partial_candidates, key=lambda item: item[0])
            best_candidate["model_authoring_attempts"] = authoring_attempts
            best_candidate["model_authoring_errors"] = list(authoring_errors)
            capability = build_model_capability_assessment(
                best_candidate.get("model_semantic_report") or {},
                attempts=authoring_attempts,
                targeted_repair_attempted=any(
                    bool(item.get("dimension_repairs")) for item in attempt_audit
                ),
                locale=locale,
                model_name=model_name,
            )
            context_audit = build_context_audit(
                messages=best_messages,
                model_output=best_model_text,
                kernel_pack=kernel_pack,
            )
            context_audit["authoring_attempts"] = attempt_audit
            context_audit["capability_escalation_based_on_latency"] = False
            draft = authoring_to_scbkr_draft(
                user_input=raw_input,
                authoring=best_candidate,
                kernel_pack=kernel_pack,
                plan_level=plan_level,
                locale=locale,
                model_provider=provider,
                model_name=model_name,
                response_source="model_capability_limited",
                context_audit=context_audit,
            )
            draft["model_capability"] = capability
            draft["signing_allowed"] = False
            draft["next_required_action"] = "owner_clarify_or_select_stronger_model"
            draft["missing_information"] = list(dict.fromkeys([
                *draft.get("missing_information", []),
                *capability.get("unresolved_gaps", []),
            ]))
            draft["compiler_report"].update({
                "status": "model_capability_limited",
                "attempts": authoring_attempts,
                "repairs": max(authoring_attempts - 1, 0),
                "errors": list(authoring_errors),
                "model_semantic_valid": False,
                "capability": capability,
                "next_required_action": "owner_clarify_or_select_stronger_model",
            })
            draft["token_metrics"] = build_token_efficiency_metrics(
                raw_input=raw_input,
                messages=best_messages,
                retrieval_context={"evidence_packet": {}},
                full_rule_registry=_rule_registry().list_rules(),
                provider_usages=provider_usages,
                attempts=authoring_attempts,
                model_settings=MODEL_SETTINGS,
                pricing=PRICING_SETTINGS,
            )
            structural_validation = validate_validity_failure(draft, kernel_pack)
            validation = {
                **structural_validation,
                "passed": False,
                "fail_reasons": sorted(set([
                    *structural_validation.get("fail_reasons", []),
                    "model_semantic_roles_invalid",
                    *capability.get("gap_codes", []),
                ])),
                "semantic_report": best_candidate.get("model_semantic_report") or {},
                "capability_limited": True,
                "repair_instruction": capability.get("recommended_action"),
            }
            draft["validator_passed"] = False
            draft["compiler_report"]["validator_passed"] = False
            draft["compiler_report"]["validator"] = validation
            return {
                "ok": False,
                "capability_limited": True,
                "kernel_pack": kernel_pack,
                "draft": draft,
                "validator": validation,
                "context_audit": context_audit,
                "model_raw_preview": best_model_text[:1200],
                "attempt_audit": attempt_audit,
                "model_capability": capability,
            }

        if authoring is None:
            raise ModelRulebookAuthoringError("empty_model_output")
        authoring["model_authoring_attempts"] = authoring_attempts
        authoring["model_authoring_errors"] = list(authoring_errors)
        context_audit = build_context_audit(messages=messages, model_output=model_text, kernel_pack=kernel_pack)
        context_audit["authoring_attempts"] = attempt_audit
        context_audit["capability_escalation_based_on_latency"] = False
        draft = authoring_to_scbkr_draft(
            user_input=raw_input,
            authoring=authoring,
            kernel_pack=kernel_pack,
            plan_level=plan_level,
            locale=locale,
            model_provider=provider,
            model_name=model_name,
            context_audit=context_audit,
        )
        draft = apply_plan_depth(draft, plan_level)
        draft["compiler_report"]["attempts"] = authoring_attempts
        draft["compiler_report"]["repairs"] = max(authoring_attempts - 1, 0)
        draft["compiler_report"]["errors"] = list(authoring_errors)
        draft["token_metrics"] = build_token_efficiency_metrics(
            raw_input=raw_input,
            messages=messages,
            retrieval_context={"evidence_packet": {}},
            full_rule_registry=_rule_registry().list_rules(),
            provider_usages=provider_usages,
            attempts=authoring_attempts,
            model_settings=MODEL_SETTINGS,
            pricing=PRICING_SETTINGS,
        )
        validation = validate_validity_failure(draft, kernel_pack)
        draft["validator_passed"] = validation.get("passed") is True
        draft.setdefault("compiler_report", {})["validator_passed"] = validation.get("passed") is True
        draft["compiler_report"]["validator"] = validation
        return {
            "ok": validation.get("passed") is True,
            "kernel_pack": kernel_pack,
            "draft": draft,
            "validator": validation,
            "context_audit": context_audit,
            "model_raw_preview": model_text[:1200],
            "attempt_audit": attempt_audit,
        }
    except ModelRulebookAuthoringError as exc:
        return {
            "ok": False,
            "kernel_pack": kernel_pack,
            "model_raw_preview": model_text[:1200],
            "attempt_audit": attempt_audit,
            "failure": build_authoring_failure(
                reason=str(exc),
                model_provider=str(MODEL_SETTINGS.get("provider") or ""),
                model_name=str(MODEL_SETTINGS.get("model_name") or ""),
                message=(
                    f"The model responded but did not produce a valid, semantically separated SCBKR rulebook: {exc}"
                    if str(locale).lower().startswith("en")
                    else f"模型有回覆，但未輸出合格且五維語意分工正確的 SCBKR 規則書：{exc}"
                ),
                context_audit=build_context_audit(messages=messages, model_output=model_text, kernel_pack=kernel_pack),
            ),
        }
    except Exception as exc:
        _mark_model_runtime_unavailable(_friendly_model_error(MODEL_SETTINGS, str(exc), locale=locale))
        lowered = str(exc).lower()
        failure_reason = "model_timeout" if ("timed out" in lowered or "timeout" in lowered) else "model_call_failed"
        return {
            "ok": False,
            "kernel_pack": kernel_pack,
            "model_raw_preview": model_text[:1200],
            "attempt_audit": attempt_audit,
            "failure": build_authoring_failure(
                reason=failure_reason,
                model_provider=str(MODEL_SETTINGS.get("provider") or ""),
                model_name=str(MODEL_SETTINGS.get("model_name") or ""),
                message=_friendly_model_error(MODEL_SETTINGS, str(exc), locale=locale),
                context_audit=build_context_audit(messages=messages, model_output=model_text, kernel_pack=kernel_pack),
            ),
        }


def _apply_model_authoring_failure_to_task(task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    failure = result["failure"]
    task.update(
        {
            "status": failure["draft_source"],
            "draft_source": failure["draft_source"],
            "model_used": bool(failure.get("model_used")),
            "model_provider": failure.get("model_provider"),
            "model_name": failure.get("model_name"),
            "model_schema_valid": False,
            "model_semantic_valid": False,
            "validator_passed": False,
            "fallback_used": False,
            "fallback_reason": "",
            "requires_user_signature": True,
            "model_signature_allowed": False,
            "next_required_action": failure.get("next_required_action"),
            "model_rulebook_authoring": failure,
            "context_audit": failure.get("context_audit"),
            "model_raw_preview": result.get("model_raw_preview", ""),
            "attempt_audit": result.get("attempt_audit") or [],
        }
    )
    task["kernel_runtime"] = {
        "route": "model_assisted_rulebook",
        "l0_gate": {},
        "validator": {"passed": False, "fail_reasons": [failure.get("failure_reason")]},
        "kernel_meta": (result.get("kernel_pack") or {}).get("meta"),
    }
    task["draft_object"] = {
        "draft_id": f"draft:{task['task_id']}",
        "state": "MODEL_UNAVAILABLE" if failure["draft_source"] == "model_unavailable" else "MODEL_SCHEMA_INVALID",
        "intent": "create_new_rule_confirmation",
        "object_type": "rule",
        "user_request_raw": task.get("raw_input"),
        "proposed_title": "SCBKR model-assisted rulebook unavailable",
        "summary": failure.get("failure_message"),
        "model_participated": False,
        "model_provider": failure.get("model_provider"),
        "model_name": failure.get("model_name"),
        "model_schema_valid": False,
        "model_semantic_valid": False,
        "kernel_validator_passed": False,
        "fallback_used": False,
        "fallback_reason": "",
        "requires_user_signature": True,
        "model_signature_allowed": False,
        "next_required_action": failure.get("next_required_action"),
        "risk_flags": [failure.get("failure_reason")],
    }
    return task


def _apply_model_authoring_success_to_task(
    task: dict[str, Any],
    result: dict[str, Any],
    *,
    raw_input: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    capability_limited = result.get("capability_limited") is True
    validator_passed = result["validator"].get("passed") is True and not capability_limited
    next_action = "owner_clarify_or_select_stronger_model" if capability_limited else "owner_review_and_signature"
    task["scbkr"] = result["draft"]
    task["kernel_runtime"] = {
        "route": "model_assisted_rulebook",
        "l0_gate": {},
        "validator": result["validator"],
        "kernel_meta": (result.get("kernel_pack") or {}).get("meta"),
    }
    task["draft_object"] = build_scbkr_draft_object(
        user_request_raw=raw_input,
        scbkr=task["scbkr"],
        intent=str(payload.get("intent") or "create_new_rule_confirmation"),
        object_type=str(payload.get("object_type") or "rule"),
        draft_id=task["task_id"],
        evidence_context=task.get("data_center_context"),
    )
    task["draft_object"].update(
        {
            "draft_source": task["scbkr"].get("draft_source"),
            "model_participated": True,
            "model_provider": task["scbkr"].get("model_provider"),
            "model_name": task["scbkr"].get("model_name"),
            "model_schema_valid": True,
            "model_schema_repaired": bool(task["scbkr"].get("model_schema_repaired")),
            "model_semantic_valid": bool(task["scbkr"].get("model_semantic_valid")),
            "model_semantic_report": task["scbkr"].get("model_semantic_report") or {},
            "kernel_validator_passed": validator_passed,
            "fallback_used": False,
            "fallback_reason": "",
            "requires_user_signature": True,
            "model_signature_allowed": False,
            "signing_allowed": validator_passed,
            "next_required_action": next_action,
            "missing_information": task["scbkr"].get("missing_information", []),
            "risk_flags": task["scbkr"].get("risk_reminders", []),
            "user_confirmation_items": task["scbkr"].get("user_confirmation_items", []),
            "context_audit": result.get("context_audit"),
            "model_capability": task["scbkr"].get("model_capability") or result.get("model_capability") or {},
        }
    )
    task.update(
        {
            "status": "model_capability_limited" if capability_limited else "waiting_user_confirm" if validator_passed else "model_validation_failed",
            "draft_source": task["scbkr"].get("draft_source"),
            "model_used": True,
            "model_provider": task["scbkr"].get("model_provider"),
            "model_name": task["scbkr"].get("model_name"),
            "model_schema_valid": True,
            "model_schema_repaired": bool(task["scbkr"].get("model_schema_repaired")),
            "model_semantic_valid": bool(task["scbkr"].get("model_semantic_valid")),
            "model_semantic_report": task["scbkr"].get("model_semantic_report") or {},
            "validator_passed": validator_passed,
            "fallback_used": False,
            "fallback_reason": "",
            "requires_user_signature": True,
            "model_signature_allowed": False,
            "signing_allowed": validator_passed,
            "next_required_action": next_action,
            "model_raw_preview": result.get("model_raw_preview"),
            "context_audit": result.get("context_audit"),
            "model_capability": task["scbkr"].get("model_capability") or result.get("model_capability") or {},
            "attempt_audit": result.get("attempt_audit") or [],
            "draft_model_call_skipped_reason": "",
        }
    )
    return task


@app.get("/health")
def health() -> dict[str, Any]:
    rule_state = _rule_state_manager().status() if "_rule_state_manager" in globals() else {"awareness_state": "EMPTY"}
    return {
        "ok": True,
        "runtime": os.environ.get("SCBKR_DESKTOP_RUNTIME", "api"),
        "lan_companion_enabled": lan_companion_enabled(),
        "rule_state": rule_state.get("awareness_state"),
        "rule_assist_plan": RULE_ASSIST_SETTINGS.get("plan_level", "FREE"),
    }


def _rule_os_route_reply(mode: str, locale: str, copy: dict[str, Any]) -> str:
    if locale == "en":
        if mode == "generate_rule":
            return (
                f"Classified as \"{copy['modes']['generate_rule']}\".\n\n"
                "Next step is not general chat and not free-form advice. SCBKR must create a five-dimension rule draft, and the model can only act as the SCBKR rule drafter.\n\n"
                "Flow: user input -> S/C/B/K/R draft -> plan-depth reinforcement -> field-by-field review -> user signature -> confirm storage -> compile into a local executable rule."
            )
        if mode == "confirm_storage":
            return (
                f"Classified as \"{copy['modes']['confirm_storage']}\". Storage cannot be completed by the model alone. "
                "User signature, acceptance review, and second confirmation are required before splitting the rule into the rule, data, memory, and retrieval stores."
            )
        if mode in {"tool_execution", "high_risk_action"}:
            return (
                f"Classified as \"{copy['modes'][mode]}\". This cannot be handed to the model for free execution. "
                "SCBKR may draft or simulate first; formal execution requires user confirmation and signature."
            )
        if mode == "query_four_stores":
            return "No signed and accepted four-store material matched this request. Retrieval-store candidates cannot be used as formal authority."
    if mode == "generate_rule":
        return (
            f"已分類為「{copy['modes']['generate_rule']}」。\n\n"
            "下一步不是一般聊天，也不是直接給建議；系統必須建立 SCBKR 五維規則草稿，讓模型只擔任「五維規則草擬員」。"
            "\n\n流程：使用者輸入 → 五維草稿 → 方案深度補強 → 逐欄確認 → 使用者簽名 → 確認入庫 → 編譯成本地可執行規則。"
        )
    if mode == "confirm_storage":
        return "已分類為「確認入庫」。入庫不能由模型自動完成；必須先完成使用者簽名、驗收、二次確認，再拆入規則庫、資料庫、記憶庫與檢索庫。"
    if mode in {"tool_execution", "high_risk_action"}:
        return "已分類為高風險或工具執行。這類動作不能直接丟給模型自由執行；我只能先做草稿或模擬，正式執行前必須由使用者確認與簽名。"
    return "目前四庫沒有與這個問題相符、且已完成簽名與驗收的正式資料。檢索庫候選不能直接當正式依據。"


@app.get("/api/product/manifest")
def product_manifest(locale: str | None = None) -> dict[str, Any]:
    return localized_product_manifest(locale)


@app.get("/api/product/manifest/raw")
def raw_product_manifest() -> dict[str, Any]:
    return deepcopy(load_product_manifest())


@app.get("/api/product/about")
def product_about(topic: str = "identity", locale: str | None = None) -> dict[str, Any]:
    allowed_topics = {"identity", "author", "capabilities", "collaboration", "rule_import", "scbkr", "usage"}
    selected_topic = topic if topic in allowed_topics else "identity"
    return {
        "topic": selected_topic,
        "locale": "en" if (locale or "").lower().startswith("en") else "zh-TW",
        "reply": build_product_reply(selected_topic, locale),
        "source": "product_manifest",
    }


def _rule_assist_locale(locale: str | None = None) -> str:
    requested = str(locale or RULE_ASSIST_SETTINGS.get("locale") or "zh-TW")
    return requested if requested in {"zh-TW", "en", "ja", "ko"} else "zh-TW"


def _current_rule_assist_status(locale: str | None = None) -> dict[str, Any]:
    return public_rule_assist_settings(RULE_ASSIST_SETTINGS, _rule_assist_locale(locale))


def _assess_rule_assist(
    text: str,
    locale: str | None = None,
    target_mode: str = "chat",
    four_store_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return evaluate_rule_assist(
        text=text,
        plan_level=str(RULE_ASSIST_SETTINGS.get("plan_level") or "FREE"),
        locale=_rule_assist_locale(locale),
        target_mode=target_mode,
        four_store_context=four_store_context,
    )


@app.get("/api/rule-assist/status")
def rule_assist_status(locale: str | None = None) -> dict[str, Any]:
    return _current_rule_assist_status(locale)


@app.post("/api/rule-assist/settings")
def update_rule_assist_settings(payload: dict[str, Any]) -> dict[str, Any]:
    RULE_ASSIST_SETTINGS.update(validate_rule_assist_settings_update(RULE_ASSIST_SETTINGS, payload))
    save_runtime_section("rule_assist", RULE_ASSIST_SETTINGS)
    return _current_rule_assist_status(str(payload.get("locale") or RULE_ASSIST_SETTINGS.get("locale") or "zh-TW"))


@app.post("/api/rule-assist/evaluate")
def evaluate_rule_assist_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text") or payload.get("message") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    locale = _response_locale(text, str(payload.get("locale") or ""))
    context = _build_four_store_context(text, None) if payload.get("include_four_store") is not False else None
    return {
        "assessment": _assess_rule_assist(text, locale=locale, target_mode=str(payload.get("target_mode") or "chat"), four_store_context=context),
        "settings": _current_rule_assist_status(locale),
    }


@app.post("/api/rule-assist/check-chat")
def rule_assist_check_chat(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("message") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="message is required")
    locale = _response_locale(text, str(payload.get("locale") or ""))
    context = _build_four_store_context(text, None)
    assessment = _assess_rule_assist(text, locale=locale, target_mode="chat", four_store_context=context)
    return {
        "mode": "rule_assist_check_chat",
        "reply": build_local_rule_assist_reply(text, assessment, locale),
        "reply_source": "deterministic_rule_assist",
        "rule_assist": assessment,
        "model_connected": _model_connected(),
        "settings": _current_rule_assist_status(locale),
    }


def _rule_registry() -> RuleRegistry:
    return RuleRegistry(current_data_dir() / "rule_registry")


def _rule_state_runtime() -> RuleStateRuntime:
    return RuleStateRuntime()


def _rule_state_manager() -> RuleStateManager:
    return RuleStateManager(_rule_registry(), _rule_state_runtime(), lambda: list_active_stored_tasks(limit=20))


@app.get("/api/rule-state/catalog")
def rule_state_catalog() -> dict[str, Any]:
    catalog = _rule_state_runtime().catalog()
    return {"runtimes": catalog, "count": len(catalog)}


@app.get("/api/rule-state/status")
def rule_state_status() -> dict[str, Any]:
    return {**_rule_state_manager().status(), **_rule_state_runtime().status()}


@app.post("/api/rule-state/select")
def select_rule_state(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        manager = _rule_state_manager()
        before = manager.get_current_state().state
        selected = _rule_state_runtime().select(payload)
        manager.validate_state_transition(before, RuleStateEnum.RULEPACK_ACTIVE, {
            "active_rulepack_id": selected.get("runtime_id"),
            "active_rulepack_version": selected.get("runtime_version"),
            "active_rulepack_stage": "POC" if selected.get("entitlement_status") == "developer_preview" else "FORMAL",
            "rule_state_receipt": selected.get("receipt_hash"),
            "entitlement_status": selected.get("entitlement_status"),
        })
        return {**manager.status(), **selected}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rule-state/deactivate")
def deactivate_rule_state(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    state = _rule_state_runtime().deactivate(str((payload or {}).get("reason") or "user_selected_independent"))
    return {**_rule_state_manager().status(), **state}


@app.post("/api/rule-state/validate-overlay")
def validate_rule_overlay(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _rule_state_runtime().validate_overlay(str(payload.get("rule_text") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/rules")
def list_rules() -> dict[str, Any]:
    rules = _rule_registry().list_rules()
    compiled_rules: list[dict[str, Any]] = []
    # Only stored, reviewed tasks can be formal rules. Loading every draft's
    # full JSON made startup scale with test/history volume instead of rules.
    for task in list_active_stored_tasks(limit=1000):
        compiled = task.get("compiled_rule") or {}
        if not compiled:
            continue
        scbkr = task.get("scbkr") or {}
        storage_items = task.get("storage_items") or []
        storage_targets = sorted({str(item.get("target")) for item in storage_items if item.get("target")})
        lifecycle_status = str(compiled.get("lifecycle_status") or task.get("lifecycle_status") or "").strip().lower()
        status = lifecycle_status if lifecycle_status in {"disabled", "revoked", "archived", "superseded", "deleted"} else "active" if compiled.get("active") and task.get("review_passed") is True else "draft"
        compiled_rules.append(
            {
                "rule_id": compiled.get("rule_id") or f"local-rule:{task.get('task_id')}",
                "rule_name": compiled.get("title") or task.get("task_name") or "Stored SCBKR rule",
                "rule_text": (storage_items[0].get("payload", {}).get("content") if storage_items else None)
                or (scbkr.get("S") or {}).get("task_subject")
                or task.get("raw_input"),
                "rule_author": (scbkr.get("confirmed_by") or "user"),
                "rule_source": "compiled_four_store_rule",
                "rule_version": f"v{compiled.get('version') or 1}.0",
                "task_id": task.get("task_id"),
                "supersedes": compiled.get("supersedes") or task.get("supersedes_rule_id"),
                "superseded_by": compiled.get("superseded_by"),
                "rule_scope": compiled.get("match_conditions") or {},
                "allowed_tools": [],
                "denied_tools": ["auto_publish", "auto_email", "auto_store_without_signature"],
                "automation_level": "manual",
                "risk_level": "medium",
                "activation_status": status,
                "signature_status": compiled.get("signature_status"),
                "review_passed": compiled.get("review_passed") is True,
                "storage_confirmed": task.get("storage_confirmed") is True,
                "compiled_rule": compiled,
                "scbkr_summary": {key: scbkr.get(key) for key in ("S", "C", "B", "K", "R")},
                "four_store_locations": storage_targets,
                "version_history": [
                    {"version": f"v{compiled.get('version') or 1}.0", "status": status, "note": "Compiled from owner-signed SCBKR workbench flow."}
                ],
                "citation_policy": compiled.get("citation_policy"),
                "created_at": task.get("created_at"),
                "updated_at": task.get("storage_result", {}).get("written_items", [{}])[0].get("stored_at")
                if task.get("storage_result", {}).get("written_items")
                else task.get("created_at"),
            }
        )
    known = {rule.get("rule_id") for rule in rules}
    rules = rules + [rule for rule in compiled_rules if rule.get("rule_id") not in known]
    return {"rules": rules, "count": len(rules), "registry_version": "scbkr.rule-registry.v2"}


def _combined_rule(rule_id: str) -> dict[str, Any]:
    candidate = next((item for item in list_rules()["rules"] if item.get("rule_id") == rule_id), None)
    if candidate is None:
        raise HTTPException(status_code=404, detail="rule not found")
    return candidate


def _rule_evidence_state(rule: dict[str, Any]) -> dict[str, Any]:
    """Capture authority-bearing rule state, excluding only observation clocks."""

    return {
        "rule_id": rule.get("rule_id"),
        "rule_name": rule.get("rule_name"),
        "rule_text": rule.get("rule_text"),
        "rule_version": rule.get("rule_version"),
        "activation_status": rule.get("activation_status"),
        "signature_status": rule.get("signature_status"),
        "signature": rule.get("signature"),
        "signed_at": rule.get("signed_at"),
        "review_passed": rule.get("review_passed"),
        "storage_confirmed": rule.get("storage_confirmed"),
        "supersedes": rule.get("supersedes"),
        "superseded_by": rule.get("superseded_by"),
        "rule_scope": rule.get("rule_scope"),
        "allowed_tools": rule.get("allowed_tools"),
        "denied_tools": rule.get("denied_tools"),
        "automation_level": rule.get("automation_level"),
        "citation_policy": rule.get("citation_policy"),
        "compiled_rule": rule.get("compiled_rule"),
        "scbkr_summary": rule.get("scbkr_summary"),
        "four_store_locations": rule.get("four_store_locations"),
        "updated_at": rule.get("updated_at"),
    }


def _revalidate_revision_source_at_confirm(task: dict[str, Any]) -> dict[str, Any]:
    source_rule_id = str(task.get("supersedes_rule_id") or "").strip()
    if not source_rule_id:
        return {
            "required": False,
            "allowed": True,
            "conflict": False,
            "reason": "not_a_rule_revision",
        }

    snapshot = task.get("source_rule_snapshot") or {}
    draft_state = snapshot.get("evidence_state")
    if not isinstance(draft_state, dict) or not draft_state or not snapshot.get("evidence_hash"):
        return {
            "required": True,
            "state_scope": "rule_revision_source",
            "confirm_time_rechecked": False,
            "allowed": False,
            "conflict": True,
            "reason": "draft_evidence_snapshot_missing",
            "source_rule_id": source_rule_id,
        }
    computed_draft_hash = evidence_state_hash(draft_state)
    if computed_draft_hash != snapshot.get("evidence_hash"):
        return {
            "required": True,
            "state_scope": "rule_revision_source",
            "confirm_time_rechecked": False,
            "allowed": False,
            "conflict": True,
            "reason": "draft_evidence_snapshot_integrity_failed",
            "source_rule_id": source_rule_id,
            "recorded_evidence_hash": snapshot.get("evidence_hash"),
            "computed_evidence_hash": computed_draft_hash,
        }

    try:
        current_rule = _combined_rule(source_rule_id)
        current_state = _rule_evidence_state(current_rule)
    except HTTPException as exc:
        current_rule = None
        current_state = {
            "rule_id": source_rule_id,
            "source_state": "missing",
            "status_code": exc.status_code,
        }

    gate = compare_evidence_state(draft_state, current_state, state_scope="rule_revision_source")
    gate.update(
        {
            "source_rule_id": source_rule_id,
            "draft_observed_at": snapshot.get("observed_at"),
            "draft_rule_version": snapshot.get("rule_version"),
            "current_rule_version": current_rule.get("rule_version") if current_rule else None,
            "current_activation_status": current_rule.get("activation_status") if current_rule else "missing",
        }
    )
    return gate


def _version_number(value: Any) -> int:
    raw = str(value or "1").lower().lstrip("v")
    try:
        return max(1, int(float(raw.split(".")[0])))
    except (TypeError, ValueError):
        return 1


def _rule_dimension_summary(rule: dict[str, Any], dimension: str) -> str:
    value = (rule.get("scbkr_summary") or {}).get(dimension) or {}
    if not isinstance(value, dict):
        return str(value)[:500]
    preferred = {
        "S": ("model_draft_content", "task_subject", "rule_subject", "task_name"),
        "C": ("model_draft_content", "core_logic", "flow_steps", "causal_chain"),
        "B": ("model_draft_content", "forbidden", "stop_conditions", "failure_conditions"),
        "K": ("model_draft_content", "references", "citable_sources", "source_credibility"),
        "R": ("model_draft_content", "acceptance_criteria", "formation_conditions", "failure_conditions"),
    }[dimension]
    for key in preferred:
        candidate = value.get(key)
        if candidate not in (None, "", [], {}):
            return json.dumps(candidate, ensure_ascii=False)[:500] if not isinstance(candidate, str) else candidate[:500]
    return json.dumps(value, ensure_ascii=False)[:500]


def _update_task_rule_lifecycle(
    task: dict[str, Any],
    *,
    lifecycle_status: str,
    signature: str,
    reason: str,
    superseded_by: str | None = None,
) -> dict[str, Any]:
    now = _now()
    compiled = dict(task.get("compiled_rule") or {})
    if not compiled:
        raise HTTPException(status_code=400, detail="compiled rule not found")
    compiled.update({
        "active": False,
        "lifecycle_status": lifecycle_status,
        "lifecycle_updated_at": now,
        "lifecycle_signature_hash": hashlib.sha256(signature.encode("utf-8")).hexdigest(),
    })
    if superseded_by:
        compiled["superseded_by"] = superseded_by
    task["compiled_rule"] = compiled
    task["lifecycle_status"] = lifecycle_status
    task["lifecycle_reason"] = reason
    task["lifecycle_updated_at"] = now

    stored_by_id = {
        str(item.get("item_id")): item
        for item in list_persisted_storage_items(task_id=str(task.get("task_id")), limit=100)
    }
    updated_items: list[dict[str, Any]] = []
    source_items = task.get("storage_items") or list(stored_by_id.values())
    for source in source_items:
        item = deepcopy(stored_by_id.get(str(source.get("item_id"))) or source)
        item["status"] = lifecycle_status
        item["updated_at"] = now
        item["lifecycle_reason"] = reason
        if superseded_by:
            item["superseded_by"] = superseded_by
        payload = deepcopy(item.get("payload") or {})
        payload["status"] = lifecycle_status
        payload["lifecycle_reason"] = reason
        if superseded_by:
            payload["superseded_by"] = superseded_by
        item["payload"] = payload
        save_storage_item(item)
        updated_items.append(item)
    task["storage_items"] = updated_items

    for source_case in list_persisted_retrieval_cases(task_id=str(task.get("task_id")), limit=None):
        case = deepcopy(source_case)
        case["governance_status"] = lifecycle_status
        case["status"] = lifecycle_status
        case["updated_at"] = now
        if superseded_by:
            case["superseded_by"] = superseded_by
        save_retrieval_case(case)

    save_task(task)
    _append_task_event(
        "rule_lifecycle_changed",
        task,
        status_before=task.get("status"),
        status_after=task.get("status"),
        payload={
            "rule_id": compiled.get("rule_id"),
            "lifecycle_status": lifecycle_status,
            "reason": reason,
            "superseded_by": superseded_by,
            "hard_delete": False,
        },
    )
    return task


def _supersede_prior_rule_after_storage(task: dict[str, Any]) -> dict[str, Any] | None:
    prior_rule_id = str(task.get("supersedes_rule_id") or "").strip()
    if not prior_rule_id:
        return None
    new_rule_id = str((task.get("compiled_rule") or {}).get("rule_id") or f"local-rule:{task.get('task_id')}")
    signature = str((task.get("scbkr") or {}).get("signature") or task.get("confirmed_at") or "owner_revision_storage")
    registry_candidate = next((item for item in _rule_registry().list_rules() if item.get("rule_id") == prior_rule_id), None)
    if registry_candidate is not None:
        updated = _rule_registry().supersede(prior_rule_id, new_rule_id)
        return {"rule_id": prior_rule_id, "status": updated.get("activation_status"), "superseded_by": new_rule_id}
    prior = _combined_rule(prior_rule_id)
    prior_task_id = str(prior.get("task_id") or (prior.get("compiled_rule") or {}).get("task_id") or "")
    if not prior_task_id:
        raise HTTPException(status_code=400, detail="prior compiled task not found")
    prior_task = _get_task(prior_task_id)
    _update_task_rule_lifecycle(
        prior_task,
        lifecycle_status="superseded",
        signature=signature,
        reason=f"Replaced by owner-signed rule {new_rule_id}",
        superseded_by=new_rule_id,
    )
    return {"rule_id": prior_rule_id, "status": "superseded", "superseded_by": new_rule_id}


@app.post("/api/rules/draft")
def create_rule_draft(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        rule = _rule_registry().create_draft(payload)
        assessment = _assess_rule_assist(str(payload.get("rule_text") or payload.get("rule_name") or ""), target_mode="rule")
        draft_object = build_rule_draft_object(rule)
        draft_object["rule_assist_state"] = assessment.get("state")
        draft_object["rule_assist_plan"] = assessment.get("plan_level")
        return {"rule": rule, "draft_object": draft_object, "rule_assist": assessment, "rule_state": _rule_state_manager().status(), "next_required_action": "owner_signature"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rules/draft-from-text")
def create_rule_draft_from_text(payload: dict[str, Any]) -> dict[str, Any]:
    instruction = str(payload.get("instruction") or "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction is required")
    task = _create_task_from_payload({
        "raw_input": instruction,
        "task_name": payload.get("rule_name"),
        "task_type": "general",
        "intent": "create_new_rule_confirmation",
        "object_type": "rule",
        "create_scbkr_draft": True,
        "locale": payload.get("locale"),
        "rule_assist_plan": "FREE",
    })
    return {
        **task,
        "task": task,
        "compiled_from": "model_assisted_rulebook",
        "model_signed": False,
        "next_required_action": task.get("next_required_action"),
    }


@app.post("/api/rules/{rule_id:path}/sign")
@_serialized_rule_state_change
def sign_rule(rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        rule = _rule_registry().sign_user_rule(rule_id, str(payload.get("owner_signature") or ""))
        return {"rule": rule, "rule_state": _rule_state_manager().status(), "next_required_action": "activate_rule"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="rule not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rules/{rule_id:path}/activate")
@_serialized_rule_state_change
def activate_rule(rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        manager = _rule_state_manager()
        before = manager.get_current_state().state
        candidate = next((item for item in _rule_registry().list_rules() if item.get("rule_id") == rule_id), None)
        if not candidate:
            raise KeyError(rule_id)
        if before != RuleStateEnum.RULEPACK_ACTIVE:
            manager.validate_state_transition(before, RuleStateEnum.RULE_ACTIVE, {
                "active_rule_id": candidate.get("rule_id"),
                "active_rule_version": candidate.get("rule_version"),
                "owner_signature": candidate.get("signature"),
                "signed_at": candidate.get("signed_at"),
            })
        rule = _rule_registry().activate(
            rule_id,
            str(payload.get("adopted_by") or ""),
            payload.get("adoption_scope") if isinstance(payload.get("adoption_scope"), dict) else {},
            str(payload.get("adoption_signature") or ""),
        )
        return {"rule": rule, "rule_state": manager.status(), "next_required_action": "rule_match_gate"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="rule not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rules/{rule_id:path}/status")
def change_rule_status(rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status") or "").strip().lower()
    action = {"disabled": "disable", "archived": "archive", "revoked": "delete", "deleted": "delete"}.get(status)
    if not action:
        raise HTTPException(status_code=400, detail="status must be disabled, archived, revoked, or deleted")
    return change_rule_lifecycle(rule_id, {**payload, "action": action})


@app.post("/api/rules/{rule_id:path}/revision")
def create_rule_revision(rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    instruction = str(payload.get("instruction") or "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="revision instruction is required")
    with RULE_STATE_COMMIT_LOCK:
        source = _combined_rule(rule_id)
        if str(source.get("activation_status") or "").lower() == "deleted":
            raise HTTPException(status_code=400, detail="deleted rules cannot be revised")
        source_evidence_state = _rule_evidence_state(source)
        source_rule_snapshot = {
            "rule_id": rule_id,
            "rule_name": source.get("rule_name"),
            "rule_version": source.get("rule_version"),
            "activation_status": source.get("activation_status"),
            "observed_at": _now(),
            "evidence_state": source_evidence_state,
            "evidence_hash": evidence_state_hash(source_evidence_state),
        }
    locale = _response_locale(instruction, str(payload.get("locale") or ""))
    summaries = "\n".join(f"{dimension}: {_rule_dimension_summary(source, dimension)}" for dimension in ("S", "C", "B", "K", "R"))
    if locale == "en":
        raw_input = (
            "Create a new SCBKR rulebook version from this signed rule. Keep unaffected meaning, apply the user's change, "
            "and rewrite all five dimensions so they remain semantically separated. Do not activate or sign it.\n\n"
            f"Previous rule: {source.get('rule_name')} ({source.get('rule_version')})\n{summaries}\n\n"
            f"Requested change: {instruction}"
        )
    else:
        raw_input = (
            "請根據這條已簽名規則建立新版 SCBKR 規則書。保留未受影響的原意，套用使用者修改要求，"
            "並重新寫完整五維，確保主體、因果、邊界、依據、責任不混用。不得自動簽名或啟用。\n\n"
            f"原規則：{source.get('rule_name')}（{source.get('rule_version')}）\n{summaries}\n\n"
            f"修改要求：{instruction}"
        )
    task = _create_task_from_payload({
        "raw_input": raw_input,
        "task_name": f"{source.get('rule_name') or 'SCBKR rule'} - revision",
        "task_type": "rule_revision",
        "intent": "modify_existing_rule",
        "object_type": "rule",
        "create_scbkr_draft": True,
        "locale": locale,
        "rule_assist_plan": "FREE",
    })
    task["supersedes_rule_id"] = rule_id
    task["revision_number"] = _version_number(source.get("rule_version")) + 1
    task["revision_instruction"] = instruction
    task["source_rule_snapshot"] = source_rule_snapshot
    if isinstance(task.get("draft_object"), dict):
        task["draft_object"].update({
            "intent": "modify_existing_rule",
            "supersedes_rule_id": rule_id,
            "revision_number": task["revision_number"],
        })
    save_task(task)
    _append_task_event(
        "rule_revision_draft_created",
        task,
        status_after=task.get("status"),
        payload={"supersedes_rule_id": rule_id, "revision_number": task["revision_number"]},
    )
    return task


@app.post("/api/rules/{rule_id:path}/lifecycle")
@_serialized_rule_state_change
def change_rule_lifecycle(rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "").strip().lower()
    target_status = {"disable": "disabled", "archive": "archived", "delete": "deleted"}.get(action)
    if not target_status:
        raise HTTPException(status_code=400, detail="action must be disable, archive, or delete")
    if payload.get("confirmed_by") != "user" or payload.get("second_confirm") is not True:
        raise HTTPException(status_code=400, detail="rule lifecycle change requires user second confirmation")
    signature = str(payload.get("signature") or "").strip()
    if not signature or signature.lower() in {"model", "assistant", "system"}:
        raise HTTPException(status_code=400, detail="owner signature is required; model cannot change rule lifecycle")
    reason = str(payload.get("reason") or f"User requested {action}").strip()
    source = _combined_rule(rule_id)
    if source.get("rule_source") != "compiled_four_store_rule":
        try:
            updated_rule = _rule_registry().set_status(rule_id, target_status)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="rule not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        append_ledger_event(build_ledger_event(
            "rule_lifecycle_changed",
            trace_id=f"rule-lifecycle-{uuid4().hex[:12]}",
            ledger_id="rule-registry-ledger",
            payload={"rule_id": rule_id, "lifecycle_status": target_status, "reason": reason, "hard_delete": False},
        ))
        return {"rule": updated_rule, "lifecycle_status": target_status, "hard_delete": False, "replay_retained": True, "rule_state": _rule_state_manager().status()}
    task_id = str(source.get("task_id") or (source.get("compiled_rule") or {}).get("task_id") or "")
    if not task_id:
        raise HTTPException(status_code=400, detail="compiled rule task not found")
    updated_task = _update_task_rule_lifecycle(
        _get_task(task_id),
        lifecycle_status=target_status,
        signature=signature,
        reason=reason,
    )
    return {
        "rule": next((item for item in list_rules()["rules"] if item.get("rule_id") == rule_id), source),
        "task_id": task_id,
        "lifecycle_status": target_status,
        "hard_delete": False,
        "replay_retained": True,
        "updated_storage_items": len(updated_task.get("storage_items") or []),
        "rule_state": _rule_state_manager().status(),
    }


@app.get("/api/rulepacks")
def list_rulepacks() -> dict[str, Any]:
    packs = _rule_registry().list_packs()
    return {"rulepacks": packs, "count": len(packs)}


@app.get("/api/rulepacks/subscriptions")
def list_rulepack_subscriptions() -> dict[str, Any]:
    subscriptions = _rule_registry().list_subscriptions()
    return {"subscriptions": subscriptions, "count": len(subscriptions)}


@app.post("/api/rulepacks/import")
def import_rulepack(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        pack = _rule_registry().import_pack(payload)
        next_action = "owner_adoption" if pack["verification"]["signature_verified"] else "author_signature"
        return {"rulepack": pack, "next_required_action": next_action}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rulepacks/{pack_id:path}/subscribe")
def subscribe_rulepack(pack_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        subscription = _rule_registry().subscribe_pack(
            pack_id,
            str(payload.get("version") or ""),
            str(payload.get("adopted_by") or ""),
            payload.get("adoption_scope") if isinstance(payload.get("adoption_scope"), dict) else {},
            str(payload.get("adoption_signature") or ""),
        )
        return {"subscription": subscription, "next_required_action": "rule_match_gate"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="rulepack not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rulepacks/subscriptions/{subscription_id:path}/disable")
def disable_rulepack_subscription(subscription_id: str) -> dict[str, Any]:
    try:
        return {"subscription": _rule_registry().unsubscribe_pack(subscription_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="subscription not found") from exc


@app.post("/api/rules/match")
def match_rules(payload: dict[str, Any]) -> dict[str, Any]:
    return _rule_registry().match(payload)


def _tool_gate_engine() -> ToolGateEngine:
    return ToolGateEngine(
        _rule_registry(),
        PERMISSIONS,
        current_data_dir() / "execution_traces" / "tool-gates.jsonl",
    )


@app.get("/api/tools")
def list_tools() -> dict[str, Any]:
    tools = list_tool_definitions()
    return {"tools": tools, "count": len(tools), "registry_version": "scbkr.tool-registry.v2"}


@app.post("/api/tools/evaluate")
def evaluate_tool_call(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return _tool_gate_engine().evaluate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/tools/traces")
def list_tool_traces(limit: int = 100) -> dict[str, Any]:
    traces = _tool_gate_engine().list_traces(limit)
    return {"traces": traces, "count": len(traces)}


@app.post("/api/tools/web-search")
def execute_web_search(payload: dict[str, Any]) -> dict[str, Any]:
    engine = _tool_gate_engine()
    gate = engine.evaluate({
        "tool_id": "web_search",
        "action": "search",
        "workflow": "natural_language_web_search",
        "text": str(payload.get("query") or ""),
        "user_confirmation": payload.get("user_confirmation") is True,
        "task_id": payload.get("task_id"),
    })
    if gate["allowed"] is not True:
        raise HTTPException(status_code=403, detail={"message": "web search blocked by SCBKR gates", "gate": gate})
    try:
        result = WebRuntime(load_launch_settings()).search(str(payload.get("query") or ""), int(payload.get("limit") or 5))
        execution = engine.record_execution(gate, "execution_succeeded", {"provider": result["provider"], "result_count": result["count"], "rule_state": _rule_state_runtime().status().get("state")})
        return {**result, "response_declaration": _rule_state_manager().status(), "authorization": gate, "execution_trace": execution}
    except Exception as exc:
        execution = engine.record_execution(gate, "execution_failed", {"error": str(exc)[:300]})
        raise HTTPException(status_code=502, detail={"message": str(exc), "authorization": gate, "execution_trace": execution}) from exc


@app.post("/api/tools/read-page")
def execute_page_reader(payload: dict[str, Any]) -> dict[str, Any]:
    engine = _tool_gate_engine()
    gate = engine.evaluate({
        "tool_id": "web_search",
        "action": "observe",
        "workflow": "page_reader",
        "text": str(payload.get("url") or ""),
        "user_confirmation": payload.get("user_confirmation") is True,
        "task_id": payload.get("task_id"),
    })
    if gate["allowed"] is not True:
        raise HTTPException(status_code=403, detail={"message": "page reader blocked by SCBKR gates", "gate": gate})
    try:
        result = WebRuntime(load_launch_settings()).read_page(str(payload.get("url") or ""), int(payload.get("max_chars") or 12000))
        execution = engine.record_execution(gate, "execution_succeeded", {"url": result["url"], "characters": len(result["text"]), "rule_state": _rule_state_runtime().status().get("state")})
        return {**result, "authorization": gate, "execution_trace": execution}
    except Exception as exc:
        execution = engine.record_execution(gate, "execution_failed", {"error": str(exc)[:300]})
        raise HTTPException(status_code=502, detail={"message": str(exc), "authorization": gate, "execution_trace": execution}) from exc


@app.get("/api/launch/settings")
def get_launch_settings() -> dict[str, Any]:
    return public_launch_settings()


@app.post("/api/launch/settings")
def update_launch_settings(payload: dict[str, Any]) -> dict[str, Any]:
    return public_launch_settings(save_launch_settings(payload))


@app.get("/api/launch/readiness")
def get_launch_readiness() -> dict[str, Any]:
    return launch_readiness()


@app.get("/api/metrics/token-efficiency")
def token_efficiency_metrics() -> dict[str, Any]:
    metrics = summarize_metrics(list_persisted_tasks(limit=20))
    metrics["aggregation_scope"] = "latest_20_tasks"
    return metrics


@app.get("/api/metrics/pricing")
def get_metrics_pricing() -> dict[str, Any]:
    """Return the local price snapshot used for transparent cost math."""
    return normalize_pricing(PRICING_SETTINGS, model_name=str(MODEL_SETTINGS.get("model_name") or ""))


@app.post("/api/metrics/pricing")
def set_metrics_pricing(payload: dict[str, Any]) -> dict[str, Any]:
    """Save user-supplied pricing; no provider price is guessed by SCBKR."""
    next_pricing = normalize_pricing(payload, model_name=str(payload.get("model_name") or MODEL_SETTINGS.get("model_name") or ""))
    next_pricing["source"] = str(payload.get("source") or "user_configured")
    next_pricing["updated_at"] = _now()
    PRICING_SETTINGS.clear()
    PRICING_SETTINGS.update(next_pricing)
    save_runtime_section("pricing", PRICING_SETTINGS)
    return next_pricing


def _token_ab_report_paths() -> tuple[Path, Path]:
    report_dir = current_data_dir() / "metrics"
    return report_dir / "token-ab-latest.json", report_dir / "token-ab-latest.md"


@app.get("/api/metrics/token-ab/latest")
def get_latest_token_ab_benchmark() -> dict[str, Any]:
    json_path, _ = _token_ab_report_paths()
    if not json_path.exists():
        return {
            "status": "not_run",
            "savings_verified": False,
            "message": "尚未執行同一模型 A/B 實測。",
        }
    try:
        report = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="token A/B report could not be read") from exc
    return {"status": "completed", **report}


@app.post("/api/metrics/token-ab/run")
def run_same_model_token_ab(payload: dict[str, Any]) -> dict[str, Any]:
    """Run two explicit calls against one provider/model and persist local evidence."""

    question = str(payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    if not _model_connected() or MODEL_SETTINGS.get("mode") == "sandbox":
        raise HTTPException(status_code=409, detail="a connected real model is required for token A/B verification")
    try:
        _assert_model_gateway_call_allowed(MODEL_SETTINGS)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    locale = _response_locale(question, str(payload.get("locale") or ""))
    classification = classify_user_input(question)
    four_store_context = _build_four_store_context(question, str(payload.get("task_id") or "") or None)
    current_rule_package = payload.get("current_rule_package")
    if not isinstance(current_rule_package, dict):
        current_rule_package = build_current_rule_package(
            question,
            four_store_context,
            plan_level=str(RULE_ASSIST_SETTINGS.get("plan_level") or "FREE"),
            locale=locale,
            classification=classification,
        )

    full_history = payload.get("full_history") or payload.get("chat_history") or []
    if not isinstance(full_history, list):
        raise HTTPException(status_code=400, detail="full_history must be a list")
    full_history = [item for item in full_history[-100:] if isinstance(item, dict)]
    full_rule_context = payload.get("full_rule_context")
    if full_rule_context is None:
        full_rule_context = {
            "four_store_context": four_store_context,
            "registered_rules": _rule_registry().list_rules(),
            "storage_items": list_persisted_storage_items(limit=1000),
        }

    requested_provider = str(MODEL_SETTINGS.get("provider") or "")
    requested_model = str(MODEL_SETTINGS.get("model_name") or "")
    context_length = max(2048, int(MODEL_SETTINGS.get("context_length") or 8192))
    reserved_output_tokens = max(64, int(MODEL_SETTINGS.get("max_tokens") or 640))
    safe_prompt_ceiling = max(512, context_length - reserved_output_tokens - 512)
    default_prompt_budget = max(1024, min(4096, context_length // 2))
    requested_prompt_budget = int(payload.get("max_prompt_tokens") or default_prompt_budget)
    max_prompt_tokens = max(512, min(requested_prompt_budget, safe_prompt_ceiling))

    def model_call(*, provider: str, model: str, messages: list[dict[str, str]], variant: str) -> dict[str, Any]:
        if provider != requested_provider or model != requested_model:
            raise ValueError("token A/B provider/model identity changed during the benchmark")
        settings = {**MODEL_SETTINGS, "_skip_rule_state_context": True}
        return _post_openai_compatible(settings, messages)

    try:
        report = run_token_ab_benchmark(
            question=question,
            full_history=full_history,
            full_rule_context=full_rule_context,
            current_rule_package=current_rule_package,
            provider=requested_provider,
            model_name=requested_model,
            model_call=model_call,
            system_prompt=(
                "Answer only from the supplied confirmed context. Do not invent facts. Reply in English."
                if locale == "en"
                else "只能依提供的已確認內容回答，不得編造資料。請使用繁體中文。"
            ),
            max_prompt_tokens=max_prompt_tokens,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"token A/B benchmark failed: {exc}") from exc

    json_path, markdown_path = _token_ab_report_paths()
    write_token_ab_report(report, json_path=json_path, markdown_path=markdown_path)
    return {
        "status": "completed",
        **report,
        "local_report": {
            "json": str(json_path),
            "markdown": str(markdown_path),
        },
    }


@app.get("/api/system/status")
def system_status() -> dict[str, Any]:
    persisted_tasks_count = len(list_persisted_task_summaries(limit=10_000))
    return {
        "api_url": LOCAL_DESKTOP_API_BASE_URL,
        "web_url": "http://localhost:5500",
        "runtime": "P13-A/B/C SQLite + JSONL retrieval runtime",
        "physical_write_performed": False,
        "tasks_count": persisted_tasks_count,
        "model": _public_model_settings(),
        "permissions": PERMISSIONS,
    }




@app.get("/api/desktop/status")
def desktop_status() -> dict[str, Any]:
    sidecar_host = os.environ.get("SCBKR_API_HOST", "127.0.0.1")
    sidecar_port = int(os.environ.get("SCBKR_API_PORT", "8787"))
    desktop_runtime = os.environ.get("SCBKR_DESKTOP_RUNTIME") in {"release-candidate", "store-candidate"}
    release_package_built = desktop_runtime
    desktop_stage = "SCBKR-2.3-free-store-candidate" if desktop_runtime else "development"
    return {
        "desktop_stage": desktop_stage,
        "desktop_shell": True,
        "installer_built": desktop_runtime,
        "preview_package_built": False,
        "release_candidate_package_built": release_package_built,
        "tauri_skeleton": False,
        "desktop_release_candidate": desktop_runtime,
        "release_candidate_stage": "SCBKR-2.3-free-rc",
        "sidecar_supported": True,
        "sidecar_running": True,
        "sandbox_available": False,
        "api_status": "running",
        "api_server_reachable": True,
        "api_url": f"http://{sidecar_host}:{sidecar_port}",
        "model_mode": MODEL_SETTINGS.get("mode"),
        "local_model_base_url": MODEL_SETTINGS.get("base_url"),
        "sidecar_host": sidecar_host,
        "sidecar_port": sidecar_port,
        "data_dir": os.environ.get("SCBKR_DATA_DIR"),
        "external_call_required": MODEL_SETTINGS.get("mode") in ("external", "hybrid"),
        "preview": False,
        "preview_package": "not included",
        "release_candidate_package": "built" if release_package_built else "runtime",
        "production_packaging": False,
        "production_packaging_status": (
            "Windows release candidate complete; Microsoft Store signing and submission are pending"
            if desktop_runtime
            else "release candidate not built"
        ),
        "installer": "NSIS release-candidate installer" if desktop_runtime else "not built",
        "release_candidate_installer": "NSIS release-candidate installer",
        "store_submission_ready": False,
        "store_submission_target": "Microsoft Store",
        "store_submission_blockers": [
            "partner_center_publisher_identity",
            "code_signing_identity",
            "store_listing_and_legal_urls",
            "store_submission_package",
            "microsoft_certification",
        ],
        "public_edition": "FREE",
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
    global _MODEL_SESSION_VERIFIED
    _MODEL_SESSION_VERIFIED = False
    payload = _model_payload_preserving_blank_api_key(payload)
    next_settings = {**MODEL_SETTINGS, **payload, "enabled": False, "last_test_status": "untested", "last_test_message": "", "updated_at": _now()}
    if "api_key" not in payload:
        next_settings["api_key"] = MODEL_SETTINGS.get("api_key", "")
    _apply_provider_defaults(next_settings, payload)
    validate_model_settings(next_settings)
    MODEL_SETTINGS.clear()
    MODEL_SETTINGS.update(next_settings)
    save_runtime_section("model", MODEL_SETTINGS)
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
    save_runtime_section("permissions", PERMISSIONS)
    return PERMISSIONS


@app.post("/api/model/test")
def test_model(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    global _MODEL_SESSION_VERIFIED
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
            test_settings = {
                **MODEL_SETTINGS,
                # A connection check proves that the model can generate, not
                # how much it can write. Eight tokens keep old local hardware
                # from being marked offline merely because a verbose reply
                # reaches the ordinary authoring timeout.
                "temperature": 0,
                "max_tokens": min(MODEL_SETTINGS["max_tokens"], 8),
                "timeout": (
                    max(int(MODEL_SETTINGS.get("timeout") or 0), 300)
                    if MODEL_SETTINGS.get("mode") == "local"
                    else MODEL_SETTINGS["timeout"]
                ),
            }
            response = _post_openai_compatible(
                test_settings,
                [{"role": "user", "content": "Reply with exactly: SCBKR READY"}],
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
    if status["last_test_status"] == "success":
        MODEL_SETTINGS.pop("raw_error", None)
    MODEL_SETTINGS["enabled"] = status["last_test_status"] == "success"
    _MODEL_SESSION_VERIFIED = status["last_test_status"] == "success"
    save_runtime_section("model", MODEL_SETTINGS)
    result = _public_model_settings()
    if MODEL_SETTINGS.get("mode") == "sandbox":
        result.update({"ok": True, "provider": SANDBOX_PROVIDER, "sandbox": True, "external_call_performed": False})
    return result


@app.post("/api/chat/intent")
def chat_intent(payload: dict[str, Any]) -> dict[str, Any]:
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    result = route_chat_intent(message)
    locale = _response_locale(message, str(payload.get("locale") or ""))
    result["rule_assist"] = _assess_rule_assist(message, locale=locale, target_mode="intent")
    if result["intent"].startswith("suggest"):
        result["suggestion"] = _build_chat_suggestion(message)
        result["suggestion"].update({"title": "可生成 SCBKR 確認單", "actions": ["生成確認單", "繼續聊天", "取消"]})
    return result


@app.post("/api/chat/general")
def general_chat(payload: dict[str, Any]) -> dict[str, Any]:
    user_text = str(payload.get("message", "")).strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="message is required")
    recent_chat_history: list[dict[str, str]] = []
    raw_history = payload.get("chat_history") or payload.get("messages") or []
    if isinstance(raw_history, list):
        for item in raw_history[-12:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").lower()
            content = str(item.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                recent_chat_history.append({"role": role, "content": content[:4000]})
    input_classification = classify_user_input(user_text)
    product_topic = detect_product_topic(user_text)
    locale = _response_locale(user_text, str(payload.get("locale") or ""))
    product_info_request = bool(
        product_topic
        or _is_scbkr_product_question(user_text)
        or _is_workbench_capability_question(user_text)
    )
    # Product identity and usage are shipped local authority. They do not need
    # semantic retrieval, and an unrelated signed rule must never be presented
    # as the basis for a product-help answer.
    four_store_context = (
        _deferred_four_store_context(user_text)
        if product_info_request
        else _build_four_store_context(user_text, None)
    )
    rule_assist = _assess_rule_assist(user_text, locale=locale, target_mode="chat", four_store_context=four_store_context)
    current_rule_package = build_current_rule_package(
        user_text,
        four_store_context,
        plan_level=str(rule_assist.get("plan_level") or RULE_ASSIST_SETTINGS.get("plan_level") or "FREE"),
        locale=locale,
        classification=input_classification,
    )
    post_check: dict[str, Any] = {"checked": False, "allowed": True, "violations": [], "action": "not_applicable"}
    model_fallback_error: str | None = None
    provider_usages: list[dict[str, Any]] = []
    model_request_messages: list[dict[str, Any]] = []
    chat_model_settings = {**MODEL_SETTINGS, "_skip_rule_state_context": True}
    mode = str(input_classification.get("mode") or "general_chat")
    if mode == "general_chat" and current_rule_package.get("matched_rules"):
        mode = "answer_with_rules"
        input_classification = {
            **input_classification,
            "mode": mode,
            "reason": "已命中已簽名本地規則，自動改走 current_rule_package 引用規則回答。",
            "requires_four_store": True,
        }
    if _is_workbench_capability_question(user_text):
        reply = SCBKR_WORKBENCH_CAPABILITY_ZH
        source = "scbkr_workbench_capability_lock"
    elif mode == "generate_rule":
        copy = rule_os_text(locale)
        reply = _rule_os_route_reply(mode, locale, copy)
        source = "rule_os_hard_router"
    elif mode == "confirm_storage":
        reply = _rule_os_route_reply(mode, locale, rule_os_text(locale))
        source = "rule_os_storage_gate"
    elif mode == "modify_existing_rule":
        reply = (
            "Open Rule Center, select the signed rule, and choose Manage rule. Describe the change there; the connected model will draft a new unsigned version while the current version stays active. Only you can review and sign the replacement."
            if locale == "en"
            else "請到規則中心選取要修改的已簽名規則，再按「管理規則」。在那裡用人話描述修改內容；連接的模型會草擬一份未簽名新版，舊版在新版完成驗收前仍維持原狀。只有你能確認與簽名新版。"
        )
        source = "rule_os_modify_gate"
    elif mode in {"tool_execution", "high_risk_action"}:
        reply = _rule_os_route_reply(mode, locale, rule_os_text(locale))
        source = "rule_os_permission_gate"
    elif mode == "query_four_stores":
        if current_rule_package.get("matched_rules") or current_rule_package.get("citable_data") or current_rule_package.get("user_preferences"):
            reply = build_rule_package_local_reply(user_text, current_rule_package, locale)
        else:
            reply = _rule_os_route_reply(mode, locale, rule_os_text(locale))
        source = "rule_os_four_store_reader"
    elif product_topic:
        reply = build_product_reply(product_topic, locale, depth=detect_explanation_depth(user_text))
        source = f"product_manifest:{product_topic}"
    elif _is_scbkr_product_question(user_text):
        reply = build_product_reply("identity", locale, depth=detect_explanation_depth(user_text))
        source = "product_manifest:identity"
    elif mode == "answer_with_rules":
        if current_rule_package.get("draft_only") and not current_rule_package.get("matched_rules"):
            if not _model_connected():
                model_fallback_error = "model_not_connected"
                reply = _model_unavailable_reply(locale, model_fallback_error)
                source = "model_unavailable"
            elif MODEL_SETTINGS.get("mode") == "sandbox":
                reply = build_local_rule_assist_reply(user_text, rule_assist, locale)
                source = "sandbox"
            else:
                try:
                    _assert_model_gateway_call_allowed(MODEL_SETTINGS)
                    if locale == "en":
                        no_rule_system = (
                            "You are the normal chat entry for SCBKR. The hard router already searched the local four stores, "
                            "and no signed active rule matched this request. Answer as a helpful general model in the user's language. "
                            "You may use recent chat only for conversational continuity. Do not treat chat as a rule, formal evidence, "
                            "or stored memory; do not create a task or write to the four stores. Do not claim that a rule was applied, "
                            "signed, stored, or activated, and do not claim that an external action was executed."
                        )
                    else:
                        no_rule_system = (
                            "你是 SCBKR 的一般聊天入口。硬路由已先查本地四庫，但本次沒有命中已簽名且啟用的規則。"
                            "請像一般模型一樣，以使用者語言正常、具體地回答。最近短期對話只能維持聊天連貫，"
                            "不得當成規則、正式依據或長期記憶，也不得建立 task 或寫入四庫。"
                            "不得宣稱已套用、簽名、入庫或啟用規則，也不得宣稱已執行外部動作。"
                        )
                    model_request_messages = [
                        {"role": "system", "content": no_rule_system},
                        *recent_chat_history,
                        {"role": "user", "content": user_text},
                    ]
                    response = _post_openai_compatible(chat_model_settings, model_request_messages)
                    if isinstance(response.get("usage"), dict):
                        provider_usages.append(response["usage"])
                    reply = parse_chat_completion_response(response)
                    source = "model_gateway_general_no_rule"
                except PermissionError as exc:
                    if _model_call_requires_external_api_permission(MODEL_SETTINGS):
                        raise HTTPException(status_code=403, detail=EXTERNAL_API_LOOPBACK_ERROR) from exc
                    model_fallback_error = str(exc)
                    reply = _model_unavailable_reply(locale, "model_permission_required")
                    source = "model_unavailable"
                except Exception as exc:
                    model_fallback_error = _friendly_model_error(MODEL_SETTINGS, str(exc))
                    _mark_model_runtime_unavailable(model_fallback_error)
                    reply = _model_unavailable_reply(locale, model_fallback_error)
                    source = "model_unavailable"
        elif not _model_connected():
            model_fallback_error = "model_not_connected"
            reply = _model_unavailable_reply(locale, model_fallback_error)
            source = "model_unavailable"
        elif MODEL_SETTINGS.get("mode") == "sandbox":
            reply = build_rule_package_local_reply(user_text, current_rule_package, locale)
            source = "rule_os_local_rule_package"
        else:
            try:
                _assert_model_gateway_call_allowed(MODEL_SETTINGS)
                messages = build_rule_package_messages(user_text, current_rule_package, locale)
                response = _post_openai_compatible(chat_model_settings, messages)
                model_request_messages = messages
                if isinstance(response.get("usage"), dict):
                    provider_usages.append(response["usage"])
                reply = parse_chat_completion_response(response)
                source = "model_gateway_rule_package"
            except PermissionError as exc:
                if _model_call_requires_external_api_permission(MODEL_SETTINGS):
                    raise HTTPException(status_code=403, detail=EXTERNAL_API_LOOPBACK_ERROR) from exc
                model_fallback_error = str(exc)
                reply = _model_unavailable_reply(locale, "model_permission_required")
                source = "model_unavailable"
            except Exception as exc:
                model_fallback_error = _friendly_model_error(MODEL_SETTINGS, str(exc))
                _mark_model_runtime_unavailable(model_fallback_error)
                reply = _model_unavailable_reply(locale, model_fallback_error)
                source = "model_unavailable"
        post_check = check_model_answer_against_rule_package(reply, current_rule_package)
        if not post_check.get("allowed"):
            if source.startswith("model_gateway"):
                violation_codes = ", ".join(str(item.get("code") or "rule_violation") for item in post_check.get("violations", []))
                if locale == "en":
                    reply = "The model output was blocked by the local rule check. SCBKR did not replace it with a template or fallback answer. Review the rule package or retry the connected model."
                else:
                    reply = "模型輸出未通過本地規則檢查，已被擋下。SCBKR 沒有用模板或 fallback 冒充答案；請檢查本次規則包或重試已連線模型。"
                if violation_codes:
                    reply = f"{reply}\n\nRule check: {violation_codes}"
                source = f"{source}_post_check_blocked"
            else:
                reply = downgrade_answer_to_draft(reply, post_check, locale)
    elif not _model_connected():
        model_fallback_error = "model_not_connected"
        reply = _model_unavailable_reply(locale, model_fallback_error)
        source = "model_unavailable"
    elif MODEL_SETTINGS.get("mode") == "sandbox":
        reply = build_local_rule_assist_reply(user_text, rule_assist, locale)
        source = "sandbox"
    else:
        try:
            _assert_model_gateway_call_allowed(MODEL_SETTINGS)
            model_request_messages = [
                {"role": "system", "content": "你是 SCBKR 一般聊天入口。必須使用使用者最新訊息所使用的語言回答；若使用者明確指定另一語言，則依指定語言回答。此規則在 EMPTY、DRAFTING、User Rule 與沈耀規則狀態都成立。繁體中文使用者不得自行切成簡體中文，也不得自行編造價格、優惠、工法、傳承。不要建立 task，不要寫入 Data Center。若使用者問 SCBKR / Workbench / Data Center / 四庫 / S/C/B/K/R，必須依本產品定義回答；不得把 SCBKR 解釋成外部組織、SAP、學校、科研平台或未知縮寫。一般聊天可使用最近短期對話維持連貫，但不得把它寫入規則庫；若要正式回答任務，必須改用 current_rule_package。\n\n" + build_rule_assist_prompt(rule_assist, locale)},
                *recent_chat_history,
                {"role": "user", "content": user_text},
            ]
            response = _post_openai_compatible(chat_model_settings, model_request_messages)
            if isinstance(response.get("usage"), dict):
                provider_usages.append(response["usage"])
            reply = parse_chat_completion_response(response)
            source = "model_gateway"
        except PermissionError as exc:
            if _model_call_requires_external_api_permission(MODEL_SETTINGS):
                raise HTTPException(status_code=403, detail=EXTERNAL_API_LOOPBACK_ERROR) from exc
            model_fallback_error = str(exc)
            reply = _model_unavailable_reply(locale, "model_permission_required")
            source = "model_unavailable"
        except Exception as exc:
            model_fallback_error = _friendly_model_error(MODEL_SETTINGS, str(exc))
            _mark_model_runtime_unavailable(model_fallback_error)
            reply = _model_unavailable_reply(locale, model_fallback_error)
            source = "model_unavailable"
    if locale == "zh-TW":
        reply = _zh_tw_output_guard(reply)
    if not product_info_request and rule_assist.get("four_store", {}).get("answer_priority") == "basic_chat_or_draft_only":
        if locale == "en":
            marker = "Four-store state: no signed citation was found, so this is basic chat or a draft only."
            if marker.lower() not in reply.lower():
                reply = f"{reply}\n\n{marker}"
        else:
            marker = "四庫狀態：目前沒有已簽名引用，所以此回覆只能當一般聊天或草案，不作為正式規則依據。"
            if marker not in reply:
                reply = f"{reply}\n\n{marker}"
    if rule_assist.get("state") == "OWNER_SIGNATURE_REQUIRED" and "簽名" not in reply and locale != "en":
        reply = f"{reply}\n\nGate：這涉及高風險工具、發布、入庫或外部連線；我只能先做草案，正式執行前必須由使用者簽名確認。"
    elif rule_assist.get("state") == "OWNER_SIGNATURE_REQUIRED" and locale == "en" and "signature" not in reply.lower():
        reply = f"{reply}\n\nGate: this touches high-risk tools, publishing, storage, or external connection. I can draft only; owner signature is required before execution."
    rule_state_manager = _rule_state_manager()
    reply = rule_state_manager.guard_reply(reply)
    rule_applied = bool(current_rule_package.get("matched_rules"))
    current_state = rule_state_manager.status(locale)
    if (rule_applied and source != "model_unavailable") or current_state.get("state") == "RULEPACK_ACTIVE":
        reply = rule_state_manager.decorate_reply(reply, locale)
    suggestion = _build_chat_suggestion(user_text) if mode == "general_chat" and any(trigger in user_text for trigger in SUGGESTION_TRIGGERS) else None
    # The per-request estimate compares the retrieved evidence used for this
    # task with the compiled minimal package. Full-store, same-model A/B remains
    # available as an explicit benchmark and must never block ordinary chat.
    token_cost_audit = measure_context_compression(
        {
            "latest_user_message": user_text,
            "recent_chat_history": recent_chat_history,
            "retrieved_four_store_context": four_store_context,
            "rule_assist": rule_assist,
        },
        current_rule_package,
        messages=model_request_messages,
        provider_usages=provider_usages,
        model_settings=MODEL_SETTINGS,
        pricing=PRICING_SETTINGS,
        measurement_scope="rule_answer" if mode == "answer_with_rules" else "general_chat",
    )
    return {
        "mode": "general_chat",
        "route_mode": mode,
        "input_classification": input_classification,
        "current_rule_package": current_rule_package,
        "token_cost_audit": token_cost_audit,
        "post_check": post_check,
        "reply": reply,
        "reply_source": source,
        "model_used": source.startswith("model_gateway") or source == "sandbox",
        "model_fallback_error": model_fallback_error,
        "chat_context_used": current_rule_package.get("chat_context_used", False),
        "rule_state": current_state,
        "rule_applied": rule_applied,
        "rule_assist": rule_assist,
        "model_connected": _model_connected(),
        "suggestion": suggestion,
        "task_created": False,
        "data_center_written": False,
        "auto_workbench": mode == "generate_rule",
    }


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


def _create_task_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw_input = str(payload.get("raw_input", "")).strip()
    if not raw_input:
        raise HTTPException(status_code=400, detail="raw_input is required")
    input_classification = classify_user_input(raw_input)
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
        "rule_assist_plan": RULE_ASSIST_SETTINGS.get("plan_level", "FREE"),
        "input_classification": input_classification,
        "rule_os_mode": input_classification.get("mode"),
    }
    if payload.get("create_scbkr_draft") is True:
        defer_model_draft = payload.get("defer_model_draft") is True
        task["data_center_context"] = _deferred_four_store_context(raw_input) if defer_model_draft else _build_four_store_context(raw_input, task_id)
        task["data_center_context"].update({"advisory": True, "retrieval_required": True, "auto_confirmed": False, "auto_storage": False, "candidate_count": len(task["data_center_context"].get("hits", []))})
        plan_level = str(payload.get("rule_assist_plan") or RULE_ASSIST_SETTINGS.get("plan_level", "FREE"))
        task["rule_assist_plan"] = plan_level
        task["rule_assist"] = _assess_rule_assist(raw_input, locale=_response_locale(raw_input, None), target_mode=str(payload.get("object_type") or "task"), four_store_context=task["data_center_context"])
        authoring_result = _compile_model_assisted_rulebook(
            raw_input,
            plan_level=plan_level,
            locale=_response_locale(raw_input, str(payload.get("locale") or "")),
        )
        if authoring_result.get("draft"):
            _apply_model_authoring_success_to_task(task, authoring_result, raw_input=raw_input, payload=payload)
            task["draft_object"]["rule_assist_state"] = task["rule_assist"].get("state")
            task["draft_object"]["rule_assist_plan"] = task["rule_assist"].get("plan_level")
            task["draft_object"]["generated_under_kernel"] = task["scbkr"].get("meta", {}).get("generated_under_kernel")
            task["confirmed"] = False
            TASKS[task_id] = task
            save_task(task)
            save_scbkr_confirmation(task_id, task["scbkr"])
            _append_task_event("task_created", task, status_after="waiting_scbkr", payload={"task_type": task["task_type"]})
            _append_task_event("scbkr_model_assisted_rulebook_created", task, status_before="waiting_scbkr", status_after=task["status"], payload={"draft_source": task.get("draft_source"), "model_provider": task.get("model_provider"), "model_name": task.get("model_name"), "validator": task["kernel_runtime"].get("validator"), "context_audit": task.get("context_audit")})
            return task
        _apply_model_authoring_failure_to_task(task, authoring_result)
        TASKS[task_id] = task
        save_task(task)
        _append_task_event("task_created", task, status_after="waiting_scbkr", payload={"task_type": task["task_type"]})
        _append_task_event("scbkr_model_assisted_rulebook_failed", task, status_before="waiting_scbkr", status_after=task["status"], payload=task.get("model_rulebook_authoring"))
        return task
    TASKS[task_id] = task
    save_task(task)
    _append_task_event("task_created", task, status_after=task["status"], payload={"task_type": task["task_type"]})
    return task


@app.post("/api/tasks/create")
def create_task(payload: dict[str, Any]) -> dict[str, Any]:
    return _create_task_from_payload(payload)


@app.post("/api/tasks/create-fast")
async def create_task_fast(request: Request) -> dict[str, Any]:
    body = (await request.body()).decode("utf-8").strip()
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid task payload") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="task payload must be an object")
    return _create_task_from_payload(payload)


@app.post("/api/tasks/{task_id}/scbkr")
def create_scbkr(task_id: str) -> dict[str, Any]:
    task = _get_task(task_id)
    _ensure_scbkr_edit_allowed(task)
    status_before = task.get("status")
    task["data_center_context"] = _build_four_store_context(task["raw_input"], task_id)
    task["data_center_context"].update({"advisory": True, "retrieval_required": True, "auto_confirmed": False, "auto_storage": False, "candidate_count": len(task["data_center_context"].get("hits", []))})
    task["rule_assist_plan"] = RULE_ASSIST_SETTINGS.get("plan_level", "FREE")
    task["rule_assist"] = _assess_rule_assist(task["raw_input"], locale=_response_locale(task["raw_input"], None), target_mode="task", four_store_context=task["data_center_context"])
    authoring_result = _compile_model_assisted_rulebook(
        task["raw_input"],
        plan_level=str(task["rule_assist_plan"] or "FREE"),
        locale=_response_locale(task["raw_input"], None),
    )
    if authoring_result.get("draft"):
        _apply_model_authoring_success_to_task(task, authoring_result, raw_input=task["raw_input"], payload={"intent": "create_new_rule_confirmation", "object_type": "rule"})
        task["draft_object"]["rule_assist_state"] = task["rule_assist"].get("state")
        task["draft_object"]["rule_assist_plan"] = task["rule_assist"].get("plan_level")
        task["draft_object"]["generated_under_kernel"] = task["scbkr"].get("meta", {}).get("generated_under_kernel")
        save_task(task)
        save_scbkr_confirmation(task_id, task["scbkr"])
        _append_task_event("scbkr_model_assisted_rulebook_created", task, status_before=status_before, status_after=task["status"], payload={"draft_source": task.get("draft_source"), "validator": task["kernel_runtime"].get("validator"), "context_audit": task.get("context_audit")})
        return task
    _apply_model_authoring_failure_to_task(task, authoring_result)
    save_task(task)
    _append_task_event("scbkr_model_assisted_rulebook_failed", task, status_before=status_before, status_after=task["status"], payload=task.get("model_rulebook_authoring"))
    return task


@app.post("/api/tasks/{task_id}/scbkr/regenerate-draft")
def regenerate_scbkr_draft(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    _ensure_scbkr_edit_allowed(task)
    status_before = task.get("status")
    raw_input = str(payload.get("raw_input") or task.get("raw_input") or "").strip()
    task["data_center_context"] = _build_four_store_context(raw_input, task_id)
    task["rule_assist_plan"] = RULE_ASSIST_SETTINGS.get("plan_level", "FREE")
    task["rule_assist"] = _assess_rule_assist(raw_input, locale=_response_locale(raw_input, None), target_mode="task", four_store_context=task["data_center_context"])
    authoring_result = _compile_model_assisted_rulebook(
        raw_input,
        plan_level=str(task["rule_assist_plan"] or "FREE"),
        locale=_response_locale(raw_input, None),
    )
    if authoring_result.get("draft"):
        _apply_model_authoring_success_to_task(task, authoring_result, raw_input=raw_input, payload={"intent": "create_new_rule_confirmation", "object_type": "rule"})
        task["confirmed"] = False
        task["draft_object"]["rule_assist_state"] = task["rule_assist"].get("state")
        task["draft_object"]["rule_assist_plan"] = task["rule_assist"].get("plan_level")
        task["draft_object"]["generated_under_kernel"] = task["scbkr"].get("meta", {}).get("generated_under_kernel")
        save_task(task)
        save_scbkr_confirmation(task_id, task["scbkr"])
        _append_task_event("scbkr_model_assisted_rulebook_regenerated", task, status_before=status_before, status_after=task["status"], payload={"draft_source": task.get("draft_source"), "validator": task["kernel_runtime"].get("validator"), "context_audit": task.get("context_audit")})
        return {"task_id": task_id, "scbkr": task["scbkr"], "draft_source": task["scbkr"].get("draft_source"), "fallback_used": False, "fallback_reason": "", "model_raw_preview": task.get("model_raw_preview", ""), "schema_valid": True, **_task_response(task)}
    _apply_model_authoring_failure_to_task(task, authoring_result)
    task["confirmed"] = False
    save_task(task)
    _append_task_event("scbkr_model_assisted_rulebook_failed", task, status_before=status_before, status_after=task["status"], payload=task.get("model_rulebook_authoring"))
    return {"task_id": task_id, "scbkr": None, "draft_source": task.get("draft_source"), "fallback_used": False, "fallback_reason": "", "model_raw_preview": "", "schema_valid": False, **_task_response(task)}


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
        task["scbkr"] = deepcopy(candidate)
        task["scbkr"]["owner_revision"] = {"kind": "full_edit", "requires_new_signature": True}
    _reset_owner_signature_status(task["scbkr"])
    task["confirmed"] = False
    task["scbkr"]["confirmation_status"] = "draft"
    _revalidate_revised_scbkr(task, revision_source="owner_full_edit")
    task["draft_object"] = build_scbkr_draft_object(user_request_raw=task.get("raw_input", ""), scbkr=task["scbkr"], draft_id=task_id, evidence_context=task.get("data_center_context"))
    _invalidate_downstream_after_scbkr_revision(task, status_before)
    save_task(task)
    save_scbkr_confirmation(task_id, task["scbkr"])
    _append_task_event("scbkr_user_edited", task, status_before=status_before, status_after=task["status"], payload={"layer": payload.get("layer", "manual")})
    return _task_response(task)


@app.post("/api/tasks/{task_id}/scbkr/apply-rule-assist")
def apply_scbkr_rule_assist(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    task = _get_task(task_id)
    _ensure_scbkr_edit_allowed(task)
    if "scbkr" not in task:
        raise HTTPException(status_code=400, detail="SCBKR draft required before rule assist")
    payload = payload or {}
    status_before = task.get("status")
    raw_input = str(payload.get("raw_input") or task.get("raw_input") or "").strip()
    task["data_center_context"] = task.get("data_center_context") or _build_four_store_context(raw_input, task_id)
    task["rule_assist_plan"] = RULE_ASSIST_SETTINGS.get("plan_level", "FREE")
    task["rule_assist"] = _assess_rule_assist(
        raw_input,
        locale=_response_locale(raw_input, None),
        target_mode="task",
        four_store_context=task["data_center_context"],
    )
    task["scbkr"] = apply_rule_assist_to_scbkr(raw_input, task["scbkr"], task["rule_assist"])
    _reset_owner_signature_status(task["scbkr"])
    task["confirmed"] = False
    task["scbkr"]["confirmation_status"] = "draft"
    _revalidate_revised_scbkr(task, revision_source="rule_assist")
    task["draft_object"] = build_scbkr_draft_object(
        user_request_raw=raw_input,
        scbkr=task["scbkr"],
        draft_id=task_id,
        evidence_context=task.get("data_center_context"),
    )
    task["draft_object"]["rule_assist_state"] = task["rule_assist"].get("state")
    task["draft_object"]["rule_assist_plan"] = task["rule_assist"].get("plan_level")
    _invalidate_downstream_after_scbkr_revision(task, status_before)
    save_task(task)
    save_scbkr_confirmation(task_id, task["scbkr"])
    _append_task_event(
        "scbkr_rule_assist_applied",
        task,
        status_before=status_before,
        status_after=task["status"],
        payload={
            "plan_level": task["rule_assist"].get("plan_level"),
            "rule_assist_state": task["rule_assist"].get("state"),
        },
    )
    return _task_response(task)


@app.post("/api/tasks/{task_id}/scbkr/patch-draft")
def scbkr_patch_draft(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    _ensure_scbkr_edit_allowed(task)
    if "scbkr" not in task:
        raise HTTPException(status_code=409, detail="A model-authored SCBKR draft is required before editing a dimension")
    layer = str(payload.get("layer") or "B").upper()
    instruction = str(payload.get("instruction", "")).strip()
    if layer not in SCBKR_CONFIRMATION_REQUIRED_FIELDS:
        raise HTTPException(status_code=400, detail="layer must be S/C/B/K/R")
    if not instruction:
        raise HTTPException(status_code=400, detail="edit instruction is required")
    before = task.get("scbkr", {}).get(layer, {})
    raw_input = str(task.get("raw_input") or "").strip()
    assessment = _assess_rule_assist(
        raw_input,
        locale=_response_locale(raw_input, None),
        target_mode="task",
        four_store_context=task.get("data_center_context"),
    )
    locale = _response_locale(raw_input or instruction, payload.get("locale"))
    sandbox_mode = MODEL_SETTINGS.get("mode") == "sandbox" or MODEL_SETTINGS.get("provider") == SANDBOX_PROVIDER
    provider_usage: dict[str, Any] = {}
    if sandbox_mode:
        # This deterministic adapter exists only for automated tests. It is
        # never reported as a connected production model.
        sandbox_patch = strip_confirmation_metadata(build_scbkr_layer_patch(
            raw_input=raw_input,
            scbkr=task.get("scbkr", {}),
            layer=layer,
            instruction=instruction,
            assessment=assessment,
        ))
        after = {
            **strip_confirmation_metadata(before if isinstance(before, dict) else {}),
            **sandbox_patch,
        }
        model_metadata = {
            "model_used": False,
            "sandbox_used": True,
            "model_source": "sandbox_test_adapter",
            "model_provider": SANDBOX_PROVIDER,
            "model_name": str(MODEL_SETTINGS.get("model_name") or SANDBOX_PROVIDER),
            "model_schema_valid": True,
            "model_semantic_valid": True,
        }
    else:
        unavailable = _model_rulebook_unavailable_reason()
        if unavailable:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": unavailable,
                    "message": _model_unavailable_reply(locale, unavailable),
                    "next_required_action": "open_model_settings_and_test_connection",
                },
            )
        messages = build_model_dimension_patch_messages(
            raw_input,
            layer=layer,
            instruction=instruction,
            current_dimension=before if isinstance(before, dict) else {},
            locale=locale,
            compact=_uses_lightweight_local_authoring(MODEL_SETTINGS),
        )
        patch_settings = {**MODEL_SETTINGS, "_skip_rule_state_context": True}
        patch_settings["timeout"] = max(int(patch_settings.get("timeout") or 0), 90)
        patch_settings["max_tokens"] = min(max(int(patch_settings.get("max_tokens") or 0), 256), 700)
        try:
            if str(patch_settings.get("provider") or "").lower() == "lm_studio":
                response = _post_openai_compatible(patch_settings, messages)
            else:
                try:
                    response = _post_openai_compatible(
                        patch_settings,
                        messages,
                        response_format=model_dimension_patch_response_format(),
                    )
                except Exception as exc:
                    if "response_format" not in str(exc):
                        raise
                    response = _post_openai_compatible(patch_settings, messages)
            provider_usage = dict(response.get("usage") or {}) if isinstance(response, dict) else {}
            model_text = parse_chat_completion_response(response)
            model_patch = parse_model_dimension_patch_output(
                model_text,
                layer=layer,
                instruction=instruction,
                user_input=raw_input,
                locale=locale,
            )
            after = strip_confirmation_metadata(apply_model_dimension_patch(
                before if isinstance(before, dict) else {},
                layer=layer,
                patch=model_patch,
                model_provider=str(MODEL_SETTINGS.get("provider") or ""),
                model_name=str(MODEL_SETTINGS.get("model_name") or ""),
            ))
        except ModelRulebookAuthoringError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": exc.code,
                    "message": (
                        "The model response did not form a valid SCBKR field. No edit was applied."
                        if locale == "en"
                        else "模型回覆尚未形成合格的 SCBKR 欄位，這次沒有套用修改。"
                    ),
                    "next_required_action": "revise_instruction_or_switch_model",
                },
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "model_patch_call_failed",
                    "message": _model_unavailable_reply(locale, "model_patch_call_failed"),
                    "next_required_action": "retry_or_switch_model",
                },
            ) from exc
        model_metadata = {
            "model_used": True,
            "sandbox_used": False,
            "model_source": "connected_model",
            "model_provider": str(MODEL_SETTINGS.get("provider") or ""),
            "model_name": str(MODEL_SETTINGS.get("model_name") or ""),
            "model_schema_valid": True,
            "model_semantic_valid": True,
        }
    _validate_scbkr_patch_after_draft(layer, after)
    patch = {
        "layer": layer,
        "before_summary": str(before)[:240],
        "after_draft": after,
        "reason": instruction or "使用者要求模型提出此層修改草案。",
        "plan_level": assessment.get("plan_level"),
        "rule_assist_state": assessment.get("state"),
        "auto_confirmed": False,
        "provider_usage": provider_usage,
        **model_metadata,
    }
    return {"task_id": task_id, "patch": patch, "confirmed": False, "status": task.get("status")}


@app.post("/api/tasks/{task_id}/scbkr/owner-edit")
def owner_edit_scbkr_dimension(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply an owner's visible field edit to the actual compiled dimension."""
    task = _get_task(task_id)
    _ensure_scbkr_edit_allowed(task)
    if "scbkr" not in task:
        raise HTTPException(status_code=400, detail="SCBKR draft required before edit")
    layer = str(payload.get("layer") or "").upper()
    content = str(payload.get("content") or "").strip()
    if layer not in SCBKR_CONFIRMATION_REQUIRED_FIELDS:
        raise HTTPException(status_code=400, detail="layer must be S/C/B/K/R")
    if len(content) < 2:
        raise HTTPException(status_code=400, detail="dimension content is required")

    current_scbkr = deepcopy(task["scbkr"])
    current_dimension = current_scbkr.get(layer) if isinstance(current_scbkr.get(layer), dict) else {}
    owner_patch = {
        "content": content,
        "explanation": "使用者直接修改此欄位；重新簽名前仍為草稿。",
        "missing_information": [],
        "needs_user_confirmation": ["請確認此修改後再簽名。"],
        "model_cannot_decide": ["模型不得覆蓋使用者的直接修改。"],
        "risk_notes": ["修改後必須重新通過驗證與簽名。"],
    }
    edited_dimension = apply_model_dimension_patch(
        current_dimension,
        layer=layer,
        patch=owner_patch,
    )
    edited_dimension.pop("model_patch", None)
    edited_dimension["owner_edit"] = {
        "owner_edited": True,
        "content": content,
        "requires_new_signature": True,
    }
    edited_dimension["owner_draft_content"] = content
    edited_dimension["model_schema_adapter_generated"] = False
    edited_dimension["model_explanation_derived_from_fields"] = True
    edited_dimension = strip_confirmation_metadata(edited_dimension)
    if layer == "R":
        edited_dimension["signature_status"] = "waiting_owner_signature"
    _validate_scbkr_patch_after_draft(layer, edited_dimension)

    for key in ("confirmed", "confirmed_at", "confirmed_by", "confirmation_statement", "signature", "confirmed_snapshot", "confirmed_snapshot_hash"):
        current_scbkr.pop(key, None)
    for dim in SCBKR_CONFIRMATION_REQUIRED_FIELDS:
        if isinstance(current_scbkr.get(dim), dict):
            current_scbkr[dim] = strip_confirmation_metadata(current_scbkr[dim])
    current_scbkr[layer] = edited_dimension
    current_scbkr["confirmation_status"] = "draft"
    _reset_owner_signature_status(current_scbkr)
    validate_scbkr_draft_for_confirmation(current_scbkr)

    status_before = task.get("status")
    task["scbkr"] = current_scbkr
    task["confirmed"] = False
    validation = _revalidate_revised_scbkr(task, revision_source="owner_dimension_edit")
    task["draft_object"] = build_scbkr_draft_object(
        user_request_raw=task.get("raw_input", ""),
        scbkr=task["scbkr"],
        draft_id=task_id,
        evidence_context=task.get("data_center_context"),
    )
    _invalidate_downstream_after_scbkr_revision(task, status_before)
    save_task(task)
    save_scbkr_confirmation(task_id, task["scbkr"])
    _append_task_event(
        "scbkr_owner_dimension_edited",
        task,
        status_before=status_before,
        status_after=task["status"],
        payload={"layer": layer, "requires_new_signature": True, "validator_passed": validation["passed"]},
    )
    return _task_response(task, auto_confirmed=False)


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
    for key in ("confirmed", "confirmed_at", "confirmed_by", "confirmation_statement", "signature", "confirmed_snapshot", "confirmed_snapshot_hash"):
        candidate_scbkr.pop(key, None)
    for dim in SCBKR_CONFIRMATION_REQUIRED_FIELDS:
        if isinstance(candidate_scbkr.get(dim), dict):
            candidate_scbkr[dim] = strip_confirmation_metadata(candidate_scbkr[dim])
    candidate_scbkr[layer] = deepcopy(after_draft)
    candidate_scbkr["confirmation_status"] = "draft"
    _reset_owner_signature_status(candidate_scbkr)
    try:
        validate_scbkr_draft_for_confirmation(candidate_scbkr)
    except HTTPException:
        raise HTTPException(status_code=400, detail=SCBKR_INVALID_PATCH_MESSAGE)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=SCBKR_INVALID_PATCH_MESSAGE) from exc

    status_before = task.get("status")
    task["scbkr"] = candidate_scbkr
    _reset_owner_signature_status(task["scbkr"])
    task["confirmed"] = False
    _revalidate_revised_scbkr(task, revision_source="model_dimension_patch")
    task["draft_object"] = build_scbkr_draft_object(user_request_raw=task.get("raw_input", ""), scbkr=task["scbkr"], draft_id=task_id, evidence_context=task.get("data_center_context"))
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
    confirmed_by = str(payload.get("confirmed_by") or "user").strip().lower()
    signature = str(payload.get("signature") or "").strip()
    if confirmed_by != "user" or signature.lower() in {"model", "assistant", "system"}:
        raise HTTPException(status_code=400, detail="model cannot sign or confirm SCBKR")
    if not signature:
        raise HTTPException(status_code=400, detail="owner signature is required before SCBKR confirmation")
    downstream_invalidated = False
    if "scbkr" in payload:
        _ensure_scbkr_edit_allowed(task)
        candidate = deepcopy(payload["scbkr"])
        validate_scbkr_draft_for_confirmation(candidate)
        status_before_revision = task.get("status")
        downstream_invalidated = _invalidate_downstream_after_scbkr_revision(task, status_before_revision)
        for key in ("confirmed", "confirmed_at", "confirmed_by", "confirmation_statement", "signature", "confirmed_snapshot", "confirmed_snapshot_hash"):
            candidate.pop(key, None)
        for dim in SCBKR_CONFIRMATION_REQUIRED_FIELDS:
            if isinstance(candidate.get(dim), dict):
                candidate[dim] = strip_confirmation_metadata(candidate[dim])
        candidate["confirmation_status"] = "draft"
        candidate["owner_revision"] = {"kind": "full_edit", "requires_new_signature": True}
        _reset_owner_signature_status(candidate)
        task["scbkr"] = candidate
        task["confirmed"] = False
        _revalidate_revised_scbkr(task, revision_source="owner_full_edit")
    elif task.get("confirmed") is not True:
        _revalidate_revised_scbkr(task, revision_source=str(task.get("scbkr", {}).get("last_revision_source") or "pre_signature_check"))
    validate_scbkr_draft_for_confirmation(task["scbkr"])
    if task.get("scbkr", {}).get("signing_allowed") is not True:
        raise HTTPException(
            status_code=409,
            detail="Current rulebook still has unresolved SCBKR gaps. Complete the highlighted fields or use a stronger model for one compilation pass before signing.",
        )
    if task.get("validator_passed") is not True:
        raise HTTPException(status_code=409, detail="Kernel Validator must pass before owner signature")
    if task.get("scbkr", {}).get("draft_source") == "draft_failed":
        raise HTTPException(status_code=400, detail="SCBKR draft failed; task subject is required before confirmation")
    confirm_all_dimensions(
        task["scbkr"],
        confirmed_by="user",
        confirmation_statement=payload.get("confirmation_statement"),
        signature=signature,
    )
    status_before = task.get("status")
    if all_dimensions_confirmed(task["scbkr"]):
        task["confirmed"] = True
        task["status"] = "confirmed"
        task["scbkr"]["signature_status"] = "owner_signed"
        task["scbkr"].setdefault("R", {})["signature_status"] = "owner_signed"
        if isinstance(task.get("draft_object"), dict):
            task["draft_object"].update({"state": "OWNER_SIGNED", "confirmed_by": "user", "signed_at": _now()})
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
        generation_four_store_context = _build_four_store_context(str(task.get("raw_input") or ""), task_id)
        generation_rule_package = build_current_rule_package(
            str(task.get("raw_input") or ""),
            generation_four_store_context,
            plan_level=str(task.get("rule_assist_plan") or RULE_ASSIST_SETTINGS.get("plan_level") or "FREE"),
            locale=_response_locale(str(task.get("raw_input") or ""), None),
            classification=task.get("input_classification") or classify_user_input(str(task.get("raw_input") or "")),
        )
        task["current_rule_package"] = generation_rule_package

        def violates_contract(text: str) -> bool:
            forbidden = ("SCBKR 草案", "五維確認單", "confirmation_status", "等待使用者確認", "重新確認 S/C/B/K/R", "S/C/B/K/R JSON")
            stripped = text.strip()
            return any(token in stripped for token in forbidden) or (stripped.startswith("{") and all(k in stripped for k in ('"S"', '"C"', '"B"', '"K"', '"R"')))

        def call_generation_model() -> dict[str, Any]:
            if MODEL_SETTINGS.get("mode") == "sandbox":
                sandbox_output = generate_with_sandbox_model(task, task["scbkr"])
                result = build_generation_result(task, task["scbkr"], sandbox_output.get("generated_text") or sandbox_output.get("content") or "")
                result.update(sandbox_output)
                decorated = _rule_state_manager().decorate_reply(str(result.get("content") or result.get("generated_text") or ""))
                result["content"] = decorated
                result["generated_text"] = decorated
                result.update({"source": "sandbox_mock_model", "next_required_action": "user_review_required"})
                return result
            generation_messages = build_generation_messages(task, task["scbkr"])
            compact_package = {
                "task_type": generation_rule_package.get("task_type"),
                "matched_rules": generation_rule_package.get("matched_rules", [])[:2],
                "citable_data": generation_rule_package.get("citable_data", [])[:2],
                "user_preferences": generation_rule_package.get("user_preferences", [])[:2],
                "forbidden_actions": generation_rule_package.get("forbidden_actions", [])[:5],
                "stop_conditions": generation_rule_package.get("stop_conditions", [])[:4],
                "missing_information": generation_rule_package.get("missing_information", [])[:4],
                "output_limits": generation_rule_package.get("output_limits", [])[:3],
                "draft_only": generation_rule_package.get("draft_only"),
                "citation_policy": generation_rule_package.get("citation_policy"),
                "chat_context_used": False,
            }
            generation_messages.append({"role": "system", "content": "本次模型生成只能依已確認的 SCBKR 與下列最小規則包，不得靠聊天上下文補規則。請用使用者語言輸出簡短、可讀、等待驗收的結果；不要重新輸出五維表單，控制在 220 字內。current_rule_package=" + json.dumps(compact_package, ensure_ascii=False, sort_keys=True)})
            generation_settings = {
                **MODEL_SETTINGS,
                "max_tokens": min(int(MODEL_SETTINGS.get("max_tokens") or 256), 256),
                "timeout": max(int(MODEL_SETTINGS.get("timeout") or 0), 90),
            }
            response = _post_openai_compatible(generation_settings, generation_messages)
            result = build_generation_result(task, task["scbkr"], parse_chat_completion_response(response))
            result["content"] = _rule_state_manager().decorate_reply(str(result.get("content") or ""))
            result["token_metrics"] = build_token_efficiency_metrics(
                raw_input=str(task.get("raw_input") or ""),
                messages=generation_messages,
                retrieval_context=task.get("data_center_context"),
                full_rule_registry=_rule_registry().list_rules(),
                provider_usages=[response.get("usage")] if isinstance(response.get("usage"), dict) else [],
                attempts=1,
                model_settings=MODEL_SETTINGS,
                pricing=PRICING_SETTINGS,
            )
            return result

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
        check = check_model_answer_against_rule_package(
            str(task["generation_result"].get("content") or task["generation_result"].get("generated_text") or ""),
            generation_rule_package,
        )
        task["generation_result"]["post_check"] = check
        if not check.get("allowed"):
            downgraded = downgrade_answer_to_draft(str(task["generation_result"].get("content") or ""), check, _response_locale(str(task.get("raw_input") or ""), None))
            task["generation_result"]["content"] = downgraded
            task["generation_result"]["generated_text"] = downgraded
            task["generation_result"]["status"] = "waiting_review"
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
        task["storage_request"] = build_storage_request(task, task.get("review_result", {}), candidate_targets=["vector", "corpus", "logic", "memory"])
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
            "risk_notice": "二次確認後才會寫入本機資料；檢索庫目前保留索引中繼資料，實體 JSON 僅寫入支援的本機庫。",
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
@_serialized_rule_state_change
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
        if task.get("confirmed") is not True or task.get("scbkr", {}).get("signature_status") != "owner_signed":
            raise ValueError("owner-signed SCBKR confirmation is required before storage commit")
        if not all_dimensions_confirmed(task["scbkr"]):
            raise ValueError("SCBKR must be fully confirmed before storage commit")
        if "storage_request" not in task:
            raise ValueError("尚未產生入庫計畫，不能二次確認寫入。請先按「產生入庫請求」。")
        if "storage_plan" not in task:
            raise ValueError("尚未建立入庫計畫。請先產生入庫請求。")
        user_decision = task.get("user_decision") or task.get("storage_request", {}).get("user_decision")
        selected_targets = validate_ui_targets(payload.get("selected_targets") or task.get("selected_targets") or task.get("storage_plan", {}).get("selected_targets") or [])
        if not selected_targets and user_decision in ("temporary_only", "do_not_store"):
            task["storage_confirmed"] = False
            task["physical_write_performed"] = False
            task["status"] = user_decision
            task["storage_result"] = {"status": user_decision, "selected_targets": [], "written_targets": [], "skipped_targets": ["vector", "corpus", "logic", "memory"], "physical_write_performed": False, "user_decision": user_decision}
            save_task(task)
            _append_task_event("storage_confirmed", task, status_before=status_before, status_after=task["status"], payload=task["storage_result"])
            return task
        if not selected_targets:
            raise ValueError("尚未選擇寫入目標。請先選擇檢索庫、資料庫、規則庫或記憶庫。")
        if payload.get("storage_confirmed") is not True or payload.get("second_confirm") is not True:
            raise ValueError("請勾選或按下「使用者二次確認寫入」後才能入庫。")
        if payload.get("confirmed_by") != "user":
            raise ValueError("confirmed_by=user is required")
        signature = str(payload.get("signature") or payload.get("storage_signature") or "").strip()
        if not signature:
            raise ValueError("signature is required")

        confirm_time_state_gate = _revalidate_revision_source_at_confirm(task)
        task["confirm_time_state_gate"] = confirm_time_state_gate
        if confirm_time_state_gate.get("allowed") is not True:
            conflict_message = rule_os_text(str(task.get("locale") or "zh-TW")).get("state_conflict_prompt")
            task["storage_confirmed"] = False
            task["physical_write_performed"] = False
            task["status"] = "storage_conflict"
            task["next_required_action"] = "refresh_revision_from_current_rule_and_reconfirm"
            task["storage_conflict"] = {
                "code": confirm_time_state_gate.get("reason"),
                "message": conflict_message,
                "gate": confirm_time_state_gate,
            }
            save_task(task)
            _append_task_event(
                "storage_state_conflict",
                task,
                status_before=status_before,
                status_after=task["status"],
                payload=task["storage_conflict"],
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "code": confirm_time_state_gate.get("reason"),
                    "message": conflict_message,
                    "conflict": confirm_time_state_gate,
                },
            )

        plan_targets = [to_plan_target(target) for target in selected_targets]
        physical_targets = [target for target in plan_targets if target in ("vector", "corpus", "logic", "memory")]
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
        physical_plan["allow_vector_metadata"] = "vector" in physical_targets
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
        task["storage_result"]["confirm_time_state_gate"] = confirm_time_state_gate
        task["compiled_rule"] = compile_executable_rule(task, items)
        task["storage_result"]["compiled_rule"] = task["compiled_rule"]
        save_task(task)
        try:
            task["retrieval_index_result"] = index_task_storage_cases(task)
            save_task(task)
        except Exception as index_error:
            task["retrieval_index_result"] = {"status": "index_failed", "error": str(index_error)}
            task["storage_result"]["retrieval_index_error"] = str(index_error)
            save_task(task)
        supersession = _supersede_prior_rule_after_storage(task)
        if supersession:
            task["supersession_result"] = supersession
            task["storage_result"]["supersession_result"] = supersession
            save_task(task)
            _append_task_event("rule_revision_activated", task, status_before=status_before, status_after=task["status"], payload=supersession)
        _append_task_event("database_written", task, status_before=status_before, status_after=task["status"], payload=task["storage_result"])
        _append_task_event("storage_physical_write_completed", task, status_before=status_before, status_after=task["status"], payload={"item_count": len(items), "physical_write_performed": True})
        _append_task_event("storage_confirmed", task, status_before=status_before, status_after=task["status"], payload=task["storage_result"])
        return task
    except HTTPException:
        raise
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
    return {"tasks": list_persisted_task_summaries(limit=50)}


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
    target = item.get("target")
    store_labels = {
        "vector": "檢索庫",
        "vector_db": "檢索庫",
        "corpus": "資料庫",
        "logic": "規則庫",
        "memory": "記憶庫",
    }
    store_roles = {
        "vector": "相似候選召回庫",
        "vector_db": "相似候選召回庫",
        "corpus": "正式資料庫",
        "logic": "可執行規則判準庫",
        "memory": "長期偏好與使用者規則記憶",
    }
    citation_roles = {
        "vector": "候選召回，不能單獨當正式判準",
        "vector_db": "候選召回，不能單獨當正式判準",
        "corpus": "可引用原文素材",
        "logic": "可引用規則/流程/邊界判準",
        "memory": "可引用使用者長期偏好與固定提醒",
    }
    status = item.get("status", "active")
    status_labels = {
        "active": "可引用",
        "superseded": "已被新版取代",
        "archived": "已封存",
        "revoked": "已撤銷",
    }
    content = payload.get("content") or payload.get("rule_statement") or payload.get("summary") or payload.get("purpose") or payload
    content_text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, sort_keys=True, indent=2)
    title = payload.get("title") or payload.get("name") or payload.get("purpose") or payload.get("summary") or item.get("item_id")
    summary = payload.get("summary") or payload.get("purpose") or content_text[:220]
    return {
        "id": item.get("item_id"),
        "item_id": item.get("item_id"),
        "title": title,
        "summary": summary,
        "task_id": item.get("task_id"),
        "created_at": item.get("created_at"),
        "stored_at": item.get("stored_at") or item.get("created_at"),
        "hash": item.get("content_hash") or payload.get("hash"),
        "content_hash": item.get("content_hash"),
        "target": target,
        "store_label": store_labels.get(str(target), str(target or "")),
        "store_role": payload.get("store_role") or store_roles.get(str(target), str(target or "")),
        "store_purpose": payload.get("store_purpose") or "",
        "citation_policy": payload.get("citation_policy") or citation_roles.get(str(target), ""),
        "model_reading_hint": f"{store_labels.get(str(target), str(target or ''))}：{payload.get('store_role') or store_roles.get(str(target), str(target or ''))}；{payload.get('citation_policy') or citation_roles.get(str(target), '')}",
        "path": relative_path,
        "storage_location": storage_location,
        "relative_path": relative_path,
        "preview": _preview(content_text),
        "content_text": content_text,
        "plain_summary": summary,
        "payload": payload,
        "status": status,
        "status_label": status_labels.get(str(status), str(status)),
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
    # The task JSON contains full SCBKR drafts and can be large. The overview
    # is a dashboard, so keep it responsive by counting the recent task window.
    tasks_all = list_persisted_tasks(limit=100)
    storage_all = list_persisted_storage_items(limit=1000)
    ledger_all = read_ledger_events()
    tasks = [t for t in tasks_all if not task_id or t.get("task_id") == task_id]
    storage = [i for i in storage_all if not task_id or i.get("task_id") == task_id]
    ledger = [e for e in ledger_all if not task_id or e.get("task_id") == task_id]
    def counts(prefix: str, items: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, int]:
        return {
            f"{prefix}storage_records_count": len(items),
            f"{prefix}vector_count": sum(1 for i in items if i.get("target") in ("vector", "vector_db")),
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
        "task_sample_limit": 100,
        "counts_scope": "recent_tasks",
    }

@app.get("/api/data-center/{section}")
def data_center_section(section: str, task_id: str | None = None) -> dict[str, Any]:
    # Four-store views are backed by storage_items and do not need to load
    # every historical task snapshot just to show their contents.
    store_sections = {"vector", "corpus", "logic", "memory"}
    tasks_all = [] if section in store_sections else list_persisted_tasks(limit=100)
    storage_all = list_persisted_storage_items(limit=1000)
    tasks = [t for t in tasks_all if not task_id or t.get("task_id") == task_id]
    storage = [i for i in storage_all if not task_id or i.get("task_id") == task_id]
    ledger = read_ledger_events(task_id=task_id) if task_id else read_ledger_events()
    if section == "tasks": items = [_dc_item_from_task(t, "task") for t in tasks]
    elif section == "confirmations": items = [_dc_item_from_task(t, "scbkr") for t in tasks if t.get("confirmed")]
    elif section == "generations": items = [_dc_item_from_task(t, "generation_result") for t in tasks if t.get("generation_result")]
    elif section == "reviews": items = [_dc_item_from_task(t, "review_result") for t in tasks if t.get("review_result")]
    elif section == "storage": items = [{**_dc_item_from_task(t, "storage_result"), "storage_confirmed": t.get("storage_confirmed"), "physical_write_performed": t.get("physical_write_performed"), **(t.get("storage_result") or {})} for t in tasks if t.get("storage_result")]
    elif section == "vector": items = [_dc_item_from_storage(i) for i in storage if i.get("target") in ("vector", "vector_db")]
    elif section == "corpus": items = [_dc_item_from_storage(i) for i in storage if i.get("target") == "corpus"]
    elif section == "logic": items = [_dc_item_from_storage(i) for i in storage if i.get("target") == "logic"]
    elif section == "memory": items = [_dc_item_from_storage(i) for i in storage if i.get("target") == "memory"]
    elif section == "ledger": items = ledger[-200:]
    else: raise HTTPException(status_code=404, detail="data center section not found")
    return {"section": section, "mode": "task" if task_id else "all", "task_id": task_id, "count": len(items), "items": items, "empty_message": "目前尚無資料。" if not items else ""}



def _find_storage_item(item_id: str) -> dict[str, Any]:
    for item in list_persisted_storage_items(limit=100):
        if item.get("item_id") == item_id:
            return item
    raise HTTPException(status_code=404, detail="data center item not found")

@app.post("/api/data-center/query")
def data_center_query(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query", "")).strip()
    items = []
    for section in ("vector", "corpus", "logic", "memory"):
        section_items = data_center_section(section).get("items", [])
        for item in section_items:
            haystack = json.dumps(item, ensure_ascii=False)
            if not query or any(token and token in haystack for token in _keyword_tokens(query)):
                items.append(item)
    return {"query": query, "candidates": items[:20], "count": len(items[:20])}


@app.post("/api/data-center/ask")
def data_center_ask(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    context = _build_four_store_context(query)
    locale = "en" if _looks_english(query) else "zh-TW"
    classification = classify_user_input(query)
    current_rule_package = build_current_rule_package(
        query,
        context,
        plan_level=str(RULE_ASSIST_SETTINGS.get("plan_level") or "FREE"),
        locale=locale,
        classification=classification,
    )
    citations = context.get("evidence_packet", {}).get("citations", [])
    excluded = len(context.get("candidate_hits", [])) + len(context.get("rejected_hits", []))
    if not citations:
        answer = _rule_state_manager().decorate_reply("目前四庫沒有與這個問題相符、且已完成簽名與驗收的正式資料。模型沒有可引用依據，因此不生成答案。", locale)
        return {
            "query": query,
            "answer": answer,
            "rule_state": _rule_state_manager().status(locale),
            "input_classification": classification,
            "current_rule_package": current_rule_package,
            "post_check": {"checked": False, "allowed": True, "violations": [], "action": "no_model_no_citation"},
            "citations": [],
            "citation_count": 0,
            "candidates_excluded": excluded,
            "model_called": False,
            "status": "no_authoritative_evidence",
        }
    citation_payload = []
    for item in citations:
        section_item = None
        if item.get("storage_item_id"):
            try:
                section_item = _dc_item_from_storage(_find_storage_item(str(item.get("storage_item_id"))))
            except HTTPException:
                section_item = None
        citation_payload.append({
            "source_store": item.get("source_store"),
            "store_role": (section_item or {}).get("store_role"),
            "store_purpose": (section_item or {}).get("store_purpose"),
            "citation_policy": (section_item or {}).get("citation_policy"),
            "model_reading_hint": (section_item or {}).get("model_reading_hint"),
            "rule": item.get("rule"),
            "content_hash": item.get("content_hash") or item.get("hash"),
            "author_id": item.get("author_id"),
            "version": item.get("version"),
        })
    answer = "\n".join(f"[{item.get('source_store')}｜{item.get('store_role') or '四庫資料'}] {item.get('rule')}" for item in citation_payload)
    model_called = False
    model_error = None
    if _model_connected():
        try:
            _assert_model_gateway_call_allowed(MODEL_SETTINGS)
            response = _post_openai_compatible(MODEL_SETTINGS, build_rule_package_messages(query, current_rule_package, locale) + [
                {"role": "system", "content": "你是 SCBKR 四庫閱讀器。只能整理提供的正式引用，不得加入引用中不存在的事實。必須遵守 store_role / citation_policy：檢索庫只能當候選召回，不得單獨當正式判準；資料庫是正式資料；規則庫是規則/流程/邊界判準；記憶庫是使用者長期偏好與固定提醒。輸出必須保留來源庫標記。"},
                {"role": "user", "content": json.dumps({"question": query, "authoritative_citations": citation_payload}, ensure_ascii=False)},
            ])
            answer = parse_chat_completion_response(response)
            model_called = True
        except Exception as exc:
            model_error = _friendly_model_error(MODEL_SETTINGS, str(exc))
    post_check = check_model_answer_against_rule_package(answer, current_rule_package)
    if not post_check.get("allowed"):
        answer = downgrade_answer_to_draft(answer, post_check, locale)
    answer = _rule_state_manager().decorate_reply(answer, locale)
    return {
        "query": query,
        "answer": answer,
        "rule_state": _rule_state_manager().status(locale),
        "input_classification": classification,
        "current_rule_package": current_rule_package,
        "post_check": post_check,
        "citations": citations,
        "citation_count": len(citations),
        "candidates_excluded": excluded,
        "model_called": model_called,
        "model_error": model_error,
        "status": "model_reading_draft" if model_called else "deterministic_citation_readout",
    }

@app.post("/api/data-center/items/{item_id}/update-confirm")
def update_data_center_item_confirm(item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("update_confirmed") is not True or payload.get("confirmed_by") != "user" or not str(payload.get("signature", "")).strip():
        raise HTTPException(status_code=400, detail="update confirmation requires user confirmation and signature")
    old = _find_storage_item(item_id)
    now = _now()
    old_updated = deepcopy(old)
    new_payload = payload.get("new_payload") or deepcopy(old.get("payload") or {})
    new_item_id = f"{item_id}-v{uuid4().hex[:8]}"
    old_updated["status"] = "superseded"
    old_updated["superseded_by"] = new_item_id
    old_updated["updated_at"] = now
    new_item = deepcopy(old)
    new_item.update({"item_id": new_item_id, "parent_item_id": item_id, "version": int(old.get("version") or 1) + 1, "status": "active", "payload": new_payload, "created_at": now, "updated_at": now, "change_reason": payload.get("change_reason")})
    new_item["content_hash"] = hash_payload(new_payload)
    save_storage_item(old_updated)
    save_storage_item(new_item)
    append_ledger_event(build_ledger_event("data_center_item_updated", task_id=old.get("task_id"), trace_id=f"dc-{item_id}", ledger_id="data-center-ledger", payload={"item_id": item_id, "new_item_id": new_item_id, "change_reason": payload.get("change_reason"), "versioned": True}))
    return {"old_item": _dc_item_from_storage(old_updated), "new_item": _dc_item_from_storage(new_item), "versioned": True}

@app.post("/api/data-center/items/{item_id}/delete-confirm")
def delete_data_center_item_confirm(item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("delete_confirmed") is not True or payload.get("confirmed_by") != "user" or not str(payload.get("signature", "")).strip():
        raise HTTPException(status_code=400, detail="delete confirmation requires user confirmation and signature")
    item = _find_storage_item(item_id)
    mode = payload.get("mode") if payload.get("mode") in ("archive", "revoke") else "archive"
    updated = deepcopy(item)
    updated["status"] = "archived" if mode == "archive" else "revoked"
    updated[f"{updated['status']}_at"] = _now()
    updated["delete_reason"] = payload.get("delete_reason")
    save_storage_item(updated)
    append_ledger_event(build_ledger_event("data_center_item_deleted", task_id=item.get("task_id"), trace_id=f"dc-{item_id}", ledger_id="data-center-ledger", payload={"item_id": item_id, "mode": mode, "hard_delete": False, "delete_reason": payload.get("delete_reason")}))
    return {"item": _dc_item_from_storage(updated), "mode": mode, "hard_delete": False}


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


def _candidate_web_dist_dirs() -> list[Path]:
    candidates: list[Path] = []
    if os.environ.get("SCBKR_WEB_DIST_DIR"):
        candidates.append(Path(os.environ["SCBKR_WEB_DIST_DIR"]))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "web-dist")
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    candidates.append(exe_dir / "web-dist")
    candidates.append(Path(__file__).resolve().parents[2] / "apps" / "web" / "dist")
    return candidates


def _find_web_dist_dir() -> Path | None:
    for candidate in _candidate_web_dist_dirs():
        if (candidate / "index.html").is_file():
            return candidate
    return None


def mount_web_dist_if_available() -> Path | None:
    web_dist = _find_web_dist_dir()
    if web_dist is None:
        return None
    assets = web_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="web-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_web_ui(full_path: str) -> FileResponse:
        requested = (web_dist / full_path).resolve() if full_path else web_dist / "index.html"
        try:
            requested.relative_to(web_dist.resolve())
        except ValueError:
            requested = web_dist / "index.html"
        if requested.is_file() and requested.name != "index.html":
            return FileResponse(requested)
        return FileResponse(web_dist / "index.html")

    return web_dist


mount_web_dist_if_available()
