"""Local-first SCBKR product runtime orchestration."""

from __future__ import annotations

from typing import Any

from core.kernel.local_kernel_cache import ensure_local_kernel_cache
from core.kernel.modules.l0_zeroth_theorem import evaluate_l0_gate
from core.scbkr.direct_scbkr_compiler import compile_direct_scbkr_draft
from core.scbkr.plan_depth_compiler import apply_plan_depth
from core.scbkr.validity_failure_validator import validate_validity_failure
from core.rule_os.classifier import classify_user_input
from core.rule_os.rule_package import build_current_rule_package


def compile_rule_from_input(user_input: str, *, plan_level: str = "FREE", locale: str = "zh-TW") -> dict[str, Any]:
    kernel_pack = ensure_local_kernel_cache()
    l0 = evaluate_l0_gate(user_input, kernel_pack)
    draft = compile_direct_scbkr_draft(user_input, kernel_pack, plan_level=plan_level, locale=locale)
    draft = apply_plan_depth(draft, plan_level)
    validation = validate_validity_failure(draft, kernel_pack)
    return {
        "route": "generate_rule",
        "kernel_pack": kernel_pack,
        "l0_gate": l0,
        "draft": draft,
        "validator": validation,
        "status": "waiting_user_confirm" if validation["passed"] else "model_validation_failed",
    }


def route_runtime_input(user_input: str) -> dict[str, Any]:
    route = classify_user_input(user_input)
    mode = route.get("mode")
    if mode == "general_chat" and any(token in user_input for token in ("寫程式", "script", "code", "腳本")):
        mode = "generate_code"
    elif mode == "general_chat" and any(token in user_input for token in ("文案", "公告", "copy", "announcement")):
        mode = "generate_copy"
    elif mode == "general_chat" and any(token in user_input for token in ("可以嗎", "判斷", "該不該", "should i")):
        mode = "judgement"
    return {**route, "route": mode}


def build_formal_answer_package(
    user_input: str,
    four_store_context: dict[str, Any] | None,
    *,
    plan_level: str = "FREE",
    locale: str = "zh-TW",
) -> dict[str, Any]:
    package = build_current_rule_package(user_input, four_store_context, plan_level=plan_level, locale=locale)
    package["formal_judgement"] = {
        "chat_context_used": False,
        "basic_context_allowed": "conversation_only_non_authoritative",
        "formal_basis": "signed_reviewed_active_logic_corpus_memory",
        "vector_policy": "recall_only_not_formal_basis",
    }
    return package

