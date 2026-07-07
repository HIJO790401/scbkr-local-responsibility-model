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
from core.permissions.permission_checker import assert_permission_allowed, validate_permission_settings
from core.permissions.permission_flags import DEFAULT_PERMISSION_SETTINGS
from core.product_manifest import (
    build_product_reply,
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
from core.rules.registry import RuleRegistry
from core.rule_state.manager import RuleStateManager
from core.rule_state.runtime import RuleStateRuntime
from core.rule_state.schemas import RuleStateEnum
from core.tools.registry import ToolGateEngine, list_tool_definitions
from core.tools.web_runtime import WebRuntime
from core.launch.readiness import launch_readiness, load_launch_settings, public_launch_settings, save_launch_settings
from core.storage.runtime_paths import current_data_dir
from core.runtime_settings import load_runtime_section, save_runtime_section
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
MODEL_SETTINGS: dict[str, Any] = load_runtime_section("model", DEFAULT_MODEL_SETTINGS)
PERMISSIONS: dict[str, Any] = load_runtime_section("permissions", DEFAULT_PERMISSION_SETTINGS)
RULE_ASSIST_SETTINGS: dict[str, Any] = load_runtime_section("rule_assist", DEFAULT_RULE_ASSIST_SETTINGS)
COMPANION_PAIRINGS: dict[str, dict[str, Any]] = {}
COMPANION_TOKENS: dict[str, dict[str, Any]] = {}


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

驗收通過後，我可以產生入庫建議，建議是否寫入向量庫、語料庫、程式邏輯庫、記憶庫。模型只能建議，不能自動入庫；必須由使用者二次確認後才會 physical write。寫入後，後續任務可以從 Data Center 與四庫引用已確認資料，Workbench 也會顯示引用證據。"""

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
    guarded = text
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
    suggest_terms = ("我想做", "我要處理", "以後要重用", "變成規則", "規劃一個流程", "商業文案計畫", "滷肉飯文案")
    if has_any(delete_terms):
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
    return MODEL_SETTINGS.get("enabled") is True and MODEL_SETTINGS.get("last_test_status") == "success"


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
            unavailable_status = item.get("status") in ("revoked", "archived", "superseded") or payload.get("status") in ("revoked", "archived", "superseded")
            if unavailable_status:
                relation.update({"adopted": False, "adoption_scope": "none", "relation_reason": "狀態不可用：revoked / archived / superseded"})
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
) -> tuple[dict[str, Any], bool, str | None]:
    understanding = None
    skipped_reason = None
    compiler_errors: list[str] = []
    compiler_attempts = 0
    compiler_repairs = 0
    messages: list[dict[str, Any]] = []
    provider_usages: list[dict[str, Any]] = []
    if MODEL_SETTINGS.get("enabled") is True and MODEL_SETTINGS.get("mode") != "sandbox":
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
        task["status"] = "draft_failed" if task.get("scbkr", {}).get("draft_source") == "draft_failed" else "waiting_user_confirm"
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


def _post_openai_compatible(settings: dict[str, Any], messages: list[dict[str, str]], response_format: dict[str, Any] | None = None) -> dict[str, Any]:
    governed_messages = _rule_state_manager().inject_system_context(messages)
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
    rule_state = _rule_state_manager().status() if "_rule_state_manager" in globals() else {"awareness_state": "EMPTY"}
    return {
        "ok": True,
        "runtime": os.environ.get("SCBKR_DESKTOP_RUNTIME", "api"),
        "lan_companion_enabled": lan_companion_enabled(),
        "rule_state": rule_state.get("awareness_state"),
        "rule_assist_plan": RULE_ASSIST_SETTINGS.get("plan_level", "FREE"),
    }


@app.get("/api/product/manifest")
def product_manifest(locale: str | None = None) -> dict[str, Any]:
    return localized_product_manifest(locale)


@app.get("/api/product/manifest/raw")
def raw_product_manifest() -> dict[str, Any]:
    return deepcopy(load_product_manifest())


@app.get("/api/product/about")
def product_about(topic: str = "identity", locale: str | None = None) -> dict[str, Any]:
    allowed_topics = {"identity", "author", "capabilities", "collaboration", "rule_import"}
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


@app.post("/api/rule-assist/mock-chat")
def rule_assist_mock_chat(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("message") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="message is required")
    locale = _response_locale(text, str(payload.get("locale") or ""))
    context = _build_four_store_context(text, None)
    assessment = _assess_rule_assist(text, locale=locale, target_mode="chat", four_store_context=context)
    return {
        "mode": "rule_assist_mock_chat",
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
    return RuleStateManager(_rule_registry(), _rule_state_runtime())


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
    return {"rules": rules, "count": len(rules), "registry_version": "scbkr.rule-registry.v2"}


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
    lowered = instruction.lower()
    known_tools = [tool["tool_id"] for tool in list_tool_definitions()]
    allowed_tools = [tool_id for tool_id in known_tools if tool_id.lower() in lowered]
    action = "publish" if any(token in lowered for token in ("發布", "publish")) else "execute" if any(token in lowered for token in ("執行", "execute")) else "store" if any(token in lowered for token in ("入庫", "store")) else "draft"
    creator = load_product_manifest()["creator"]
    name = instruction.splitlines()[0].strip("。.!！?？ ")[:48]
    keywords = sorted(_keyword_tokens(instruction))[:12]
    validation = _rule_state_runtime().validate_overlay(instruction)
    draft_payload = {
        "rule_name": name or "自然語言規則草案",
        "rule_text": instruction,
        "rule_author": str(payload.get("rule_author") or creator["name"]["zh-TW"]),
        "rule_source": "user_defined",
        "rule_version": "v1.0.0",
        "rule_scope": {"task_types": ["*"], "tools": allowed_tools, "workflows": ["*"], "keywords": keywords, "actions": [action]},
        "allowed_tools": allowed_tools,
        "denied_tools": [],
        "automation_level": "manual",
        "risk_level": "medium",
        "changelog": ["由自然語言建立，等待使用者檢查與簽名。"],
        "rule_state_receipt": validation["rule_state"].get("receipt_hash"),
        "validation_status": validation["status"],
    }
    try:
        rule = _rule_registry().create_draft(draft_payload)
        assessment = _assess_rule_assist(instruction, locale=_response_locale(instruction, None), target_mode="rule")
        draft_object = build_rule_draft_object(rule)
        draft_object["rule_assist_state"] = assessment.get("state")
        draft_object["rule_assist_plan"] = assessment.get("plan_level")
        return {"rule": rule, "draft_object": draft_object, "rule_assist": assessment, "validation": validation, "rule_state": _rule_state_manager().status(), "compiled_from": "natural_language", "model_signed": False, "next_required_action": "owner_review_and_signature"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rules/{rule_id:path}/sign")
def sign_rule(rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        rule = _rule_registry().sign_user_rule(rule_id, str(payload.get("owner_signature") or ""))
        return {"rule": rule, "rule_state": _rule_state_manager().status(), "next_required_action": "activate_rule"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="rule not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rules/{rule_id:path}/activate")
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
    try:
        rule = _rule_registry().set_status(rule_id, str(payload.get("status") or ""))
        return {"rule": rule, "rule_state": _rule_state_manager().status()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="rule not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    return summarize_metrics(list_persisted_tasks(limit=1000))


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
    release_runtime = os.environ.get("SCBKR_DESKTOP_RUNTIME") == "release-candidate"
    release_package_built = release_runtime or os.environ.get("SCBKR_DESKTOP_PREVIEW") == "1"
    desktop_stage = "P14-C-preview"
    return {
        "desktop_stage": desktop_stage,
        "desktop_shell": True,
        "installer_built": False,
        "preview_package_built": release_package_built,
        "release_candidate_package_built": release_package_built,
        "tauri_skeleton": True,
        "desktop_release_candidate": True,
        "release_candidate_stage": "P15-S-1.0-final-rc",
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
        "preview_package": "built" if release_package_built else "preview runtime",
        "release_candidate_package": "built" if release_package_built else "runtime",
        "production_packaging": False,
        "production_packaging_status": "future stage pending",
        "installer": "not a production installer",
        "release_candidate_installer": "release candidate installer",
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
                # A connection check only needs a short reply. Keeping this
                # small prevents lightweight local models from rejecting the
                # request when their loaded context window is limited.
                "max_tokens": min(MODEL_SETTINGS["max_tokens"], 64),
            }
            response = _post_openai_compatible(
                test_settings,
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
    if status["last_test_status"] == "success":
        MODEL_SETTINGS.pop("raw_error", None)
    MODEL_SETTINGS["enabled"] = status["last_test_status"] == "success"
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
    product_topic = detect_product_topic(user_text)
    locale = _response_locale(user_text, str(payload.get("locale") or ""))
    four_store_context = _build_four_store_context(user_text, None)
    rule_assist = _assess_rule_assist(user_text, locale=locale, target_mode="chat", four_store_context=four_store_context)
    if _is_workbench_capability_question(user_text):
        reply = SCBKR_WORKBENCH_CAPABILITY_ZH
        source = "scbkr_workbench_capability_lock"
    elif product_topic:
        reply = build_product_reply(product_topic, locale)
        source = f"product_manifest:{product_topic}"
    elif _is_scbkr_product_question(user_text):
        reply = build_product_reply("identity", locale)
        source = "product_manifest:identity"
    elif not _model_connected():
        reply = build_local_rule_assist_reply(user_text, rule_assist, locale)
        source = "rule_assist_local_fallback"
    elif MODEL_SETTINGS.get("mode") == "sandbox":
        reply = build_local_rule_assist_reply(user_text, rule_assist, locale)
        source = "sandbox"
    else:
        try:
            _assert_model_gateway_call_allowed(MODEL_SETTINGS)
            response = _post_openai_compatible(MODEL_SETTINGS, [{"role": "system", "content": "你是 SCBKR 一般聊天入口。必須使用使用者最新訊息所使用的語言回答；若使用者明確指定另一語言，則依指定語言回答。此規則在 EMPTY、DRAFTING、User Rule 與沈耀規則狀態都成立。繁體中文使用者不得自行切成簡體中文，也不得自行編造價格、優惠、工法、傳承。不要建立 task，不要寫入 Data Center。若使用者問 SCBKR / Workbench / Data Center / 四庫 / S/C/B/K/R，必須依本產品定義回答；不得把 SCBKR 解釋成外部組織、SAP、學校、科研平台或未知縮寫。\n\n" + build_rule_assist_prompt(rule_assist, locale)}, {"role": "user", "content": user_text}])
            reply = parse_chat_completion_response(response)
            source = "model_gateway"
        except PermissionError as exc:
            if _model_call_requires_external_api_permission(MODEL_SETTINGS):
                raise HTTPException(status_code=403, detail=EXTERNAL_API_LOOPBACK_ERROR) from exc
            raise HTTPException(status_code=403, detail="目前未允許模型生成，聊天內容不會送出。請開啟 model_generate 權限或改用 Sandbox。") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"模型呼叫失敗：{_friendly_model_error(MODEL_SETTINGS, str(exc))}") from exc
    if locale == "zh-TW":
        reply = _zh_tw_output_guard(reply)
    if rule_assist.get("four_store", {}).get("answer_priority") == "basic_chat_or_draft_only":
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
    reply = _rule_state_manager().decorate_reply(reply, locale)
    suggestion = _build_chat_suggestion(user_text) if any(trigger in user_text for trigger in SUGGESTION_TRIGGERS) else None
    return {"mode": "general_chat", "reply": reply, "reply_source": source, "rule_state": _rule_state_manager().status(locale), "rule_assist": rule_assist, "model_connected": _model_connected(), "suggestion": suggestion, "task_created": False, "data_center_written": False, "auto_workbench": False}


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
        "rule_assist_plan": RULE_ASSIST_SETTINGS.get("plan_level", "FREE"),
    }
    if payload.get("create_scbkr_draft") is True:
        task["data_center_context"] = _build_four_store_context(raw_input, task_id)
        task["data_center_context"].update({"advisory": True, "retrieval_required": True, "auto_confirmed": False, "auto_storage": False, "candidate_count": len(task["data_center_context"].get("hits", []))})
        task["rule_assist"] = _assess_rule_assist(raw_input, locale=_response_locale(raw_input, None), target_mode=str(payload.get("object_type") or "task"), four_store_context=task["data_center_context"])
        task["scbkr"], fallback_used, skipped_reason = _model_authored_scbkr_draft(raw_input, task["task_type"], task["data_center_context"], task["rule_assist"])
        task["draft_object"] = build_scbkr_draft_object(
            user_request_raw=raw_input,
            scbkr=task["scbkr"],
            intent=str(payload.get("intent") or "create_confirmation"),
            object_type=str(payload.get("object_type") or "task"),
            draft_id=task_id,
            evidence_context=task["data_center_context"],
        )
        if skipped_reason:
            task["draft_model_call_skipped_reason"] = skipped_reason
        task["status"] = "draft_failed" if task.get("scbkr", {}).get("draft_source") == "draft_failed" else "waiting_user_confirm"
        task["draft_object"]["rule_assist_state"] = task["rule_assist"].get("state")
        task["draft_object"]["rule_assist_plan"] = task["rule_assist"].get("plan_level")
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
    task["rule_assist_plan"] = RULE_ASSIST_SETTINGS.get("plan_level", "FREE")
    task["rule_assist"] = _assess_rule_assist(task["raw_input"], locale=_response_locale(task["raw_input"], None), target_mode="task", four_store_context=task["data_center_context"])
    task["scbkr"], fallback_used, skipped_reason = _model_authored_scbkr_draft(task["raw_input"], task["task_type"], task["data_center_context"], task["rule_assist"])
    task["draft_object"] = build_scbkr_draft_object(user_request_raw=task["raw_input"], scbkr=task["scbkr"], draft_id=task_id, evidence_context=task["data_center_context"])
    task["draft_object"]["rule_assist_state"] = task["rule_assist"].get("state")
    task["draft_object"]["rule_assist_plan"] = task["rule_assist"].get("plan_level")
    if skipped_reason:
        task["draft_model_call_skipped_reason"] = skipped_reason
    task["status"] = "draft_failed" if task.get("scbkr", {}).get("draft_source") == "draft_failed" else "waiting_user_confirm"
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


@app.post("/api/tasks/{task_id}/scbkr/regenerate-draft")
def regenerate_scbkr_draft(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = _get_task(task_id)
    _ensure_scbkr_edit_allowed(task)
    status_before = task.get("status")
    raw_input = str(payload.get("raw_input") or task.get("raw_input") or "").strip()
    task["data_center_context"] = _build_four_store_context(raw_input, task_id)
    task["rule_assist_plan"] = RULE_ASSIST_SETTINGS.get("plan_level", "FREE")
    task["rule_assist"] = _assess_rule_assist(raw_input, locale=_response_locale(raw_input, None), target_mode="task", four_store_context=task["data_center_context"])
    task["scbkr"], fallback_used, skipped_reason = _model_authored_scbkr_draft(raw_input, task.get("task_type", "general"), task["data_center_context"], task["rule_assist"])
    task["draft_object"] = build_scbkr_draft_object(user_request_raw=raw_input, scbkr=task["scbkr"], draft_id=task_id, evidence_context=task["data_center_context"])
    task["draft_object"]["rule_assist_state"] = task["rule_assist"].get("state")
    task["draft_object"]["rule_assist_plan"] = task["rule_assist"].get("plan_level")
    task["status"] = "draft_failed" if task.get("scbkr", {}).get("draft_source") == "draft_failed" else "waiting_user_confirm"
    task["confirmed"] = False
    if skipped_reason:
        task["draft_model_call_skipped_reason"] = skipped_reason
    save_task(task)
    save_scbkr_confirmation(task_id, task["scbkr"])
    _append_task_event("scbkr_draft_regenerated", task, status_before=status_before, status_after=task["status"], payload={"fallback_used": fallback_used, "fallback_reason": skipped_reason})
    return {"task_id": task_id, "scbkr": task["scbkr"], "draft_source": task["scbkr"].get("draft_source"), "fallback_used": fallback_used, "fallback_reason": skipped_reason, "model_raw_preview": "", "schema_valid": not fallback_used, **_task_response(task)}


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
    _reset_owner_signature_status(task["scbkr"])
    task["confirmed"] = False
    task["status"] = "draft_failed" if task.get("scbkr", {}).get("draft_source") == "draft_failed" else "waiting_user_confirm"
    task["scbkr"]["confirmation_status"] = "draft"
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
    task["status"] = "draft_failed" if task.get("scbkr", {}).get("draft_source") == "draft_failed" else "waiting_user_confirm"
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
    layer = str(payload.get("layer") or "B").upper()
    instruction = str(payload.get("instruction", "")).strip()
    if layer not in SCBKR_CONFIRMATION_REQUIRED_FIELDS:
        raise HTTPException(status_code=400, detail="layer must be S/C/B/K/R")
    before = task.get("scbkr", {}).get(layer, {})
    raw_input = str(task.get("raw_input") or "").strip()
    assessment = _assess_rule_assist(
        raw_input,
        locale=_response_locale(raw_input, None),
        target_mode="task",
        four_store_context=task.get("data_center_context"),
    )
    after = strip_confirmation_metadata(build_scbkr_layer_patch(
        raw_input=raw_input,
        scbkr=task.get("scbkr", {}),
        layer=layer,
        instruction=instruction,
        assessment=assessment,
    ))
    if layer == "B" and ("日期" in instruction or "date" in instruction.lower()):
        after["stop_conditions"] = list(after.get("stop_conditions") or []) + ["模型不得自行確認事件日期；日期必須由使用者填寫或確認。"]
        after["sensitive_operation_confirm"] = True
    patch = {
        "layer": layer,
        "before_summary": str(before)[:240],
        "after_draft": after,
        "reason": instruction or "使用者要求模型提出此層修改草案。",
        "plan_level": assessment.get("plan_level"),
        "rule_assist_state": assessment.get("state"),
        "auto_confirmed": False,
    }
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
    task["status"] = "draft_failed" if task.get("scbkr", {}).get("draft_source") == "draft_failed" else "waiting_user_confirm"
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
    confirmed_by = str(payload.get("confirmed_by") or "user").strip().lower()
    signature = str(payload.get("signature") or "").strip()
    if task.get("scbkr", {}).get("draft_source") == "draft_failed":
        raise HTTPException(status_code=400, detail="SCBKR draft failed; task subject is required before confirmation")
    if confirmed_by != "user" or signature.lower() in {"model", "assistant", "system"}:
        raise HTTPException(status_code=400, detail="model cannot sign or confirm SCBKR")
    if not signature:
        raise HTTPException(status_code=400, detail="owner signature is required before SCBKR confirmation")
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
            response = _post_openai_compatible(MODEL_SETTINGS, generation_messages)
            result = build_generation_result(task, task["scbkr"], parse_chat_completion_response(response))
            result["content"] = _rule_state_manager().decorate_reply(str(result.get("content") or ""))
            result["token_metrics"] = build_token_efficiency_metrics(
                raw_input=str(task.get("raw_input") or ""),
                messages=generation_messages,
                retrieval_context=task.get("data_center_context"),
                full_rule_registry=_rule_registry().list_rules(),
                provider_usages=[response.get("usage")] if isinstance(response.get("usage"), dict) else [],
                attempts=1,
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
            raise ValueError("尚未選擇寫入目標。請先選擇向量庫、語料庫、程式邏輯庫或記憶庫。")
        if payload.get("storage_confirmed") is not True or payload.get("second_confirm") is not True:
            raise ValueError("請勾選或按下「使用者二次確認寫入」後才能入庫。")
        if payload.get("confirmed_by") != "user":
            raise ValueError("confirmed_by=user is required")
        signature = str(payload.get("signature") or payload.get("storage_signature") or "").strip()
        if not signature:
            raise ValueError("signature is required")

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
    target = item.get("target")
    store_labels = {
        "vector": "向量庫",
        "vector_db": "向量庫",
        "corpus": "語料庫",
        "logic": "邏輯庫",
        "memory": "記憶庫",
    }
    store_roles = {
        "vector": "相似案例索引",
        "vector_db": "相似案例索引",
        "corpus": "原文素材庫",
        "logic": "規則與流程判準庫",
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
    tasks_all = list_persisted_tasks(limit=1000)
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
    elif section == "vector": items = [_dc_item_from_storage(i) for i in storage if i.get("target") in ("vector", "vector_db")]
    elif section == "corpus": items = [_dc_item_from_storage(i) for i in storage if i.get("target") == "corpus"]
    elif section == "logic": items = [_dc_item_from_storage(i) for i in storage if i.get("target") == "logic"]
    elif section == "memory": items = [_dc_item_from_storage(i) for i in storage if i.get("target") == "memory"]
    elif section == "ledger": items = ledger[-200:]
    else: raise HTTPException(status_code=404, detail="data center section not found")
    return {"section": section, "mode": "task" if task_id else "all", "task_id": task_id, "count": len(items), "items": items, "empty_message": "目前尚無資料。" if not items else ""}



def _find_storage_item(item_id: str) -> dict[str, Any]:
    for item in list_persisted_storage_items(limit=1000):
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
    citations = context.get("evidence_packet", {}).get("citations", [])
    excluded = len(context.get("candidate_hits", [])) + len(context.get("rejected_hits", []))
    if not citations:
        answer = _rule_state_manager().decorate_reply("目前四庫沒有與這個問題相符、且已完成簽名與驗收的正式資料。模型沒有可引用依據，因此不生成答案。", "en" if _looks_english(query) else "zh-TW")
        return {
            "query": query,
            "answer": answer,
            "rule_state": _rule_state_manager().status("en" if _looks_english(query) else "zh-TW"),
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
            response = _post_openai_compatible(MODEL_SETTINGS, [
                {"role": "system", "content": "你是 SCBKR 四庫閱讀器。只能整理提供的正式引用，不得加入引用中不存在的事實。必須遵守 store_role / citation_policy：vector 只能當候選召回，不得單獨當正式判準；corpus 是原文素材；logic 是規則/流程/邊界判準；memory 是使用者長期偏好與固定提醒。輸出繁體中文，並保留來源庫標記。"},
                {"role": "user", "content": json.dumps({"question": query, "authoritative_citations": citation_payload}, ensure_ascii=False)},
            ])
            answer = parse_chat_completion_response(response)
            model_called = True
        except Exception as exc:
            model_error = _friendly_model_error(MODEL_SETTINGS, str(exc))
    answer = _rule_state_manager().decorate_reply(answer, "en" if _looks_english(query) else "zh-TW")
    return {
        "query": query,
        "answer": answer,
        "rule_state": _rule_state_manager().status("en" if _looks_english(query) else "zh-TW"),
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
