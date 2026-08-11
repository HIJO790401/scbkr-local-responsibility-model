"""Probe real model-authored SCBKR drafts without starting the product API.

This is a source-level diagnostic for constrained local machines. It sends the
same compact authoring messages used by the product, parses the model's output,
and runs the SCBKR semantic and Kernel validators. It never signs or stores a
rule and never substitutes a template.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.kernel.local_kernel_cache import ensure_local_kernel_cache
from core.scbkr.model_rulebook_author import (
    authoring_to_scbkr_draft,
    build_context_audit,
    build_model_basis_selection_messages,
    build_model_dimension_explanation_messages,
    build_model_dimension_patch_messages,
    build_model_rulebook_messages,
    compile_kernel_required_clauses,
    compile_model_basis_selection_candidate,
    merge_model_dimension_explanation_candidate,
    merge_model_dimension_patch_candidate,
    model_dimension_repair_instruction,
    model_rulebook_repair_targets,
    parse_model_basis_selection_output,
    parse_model_dimension_explanation_output,
    parse_model_dimension_patch_output,
    parse_model_rulebook_candidate,
    refresh_model_rulebook_support_fields,
    validate_model_rulebook_semantics,
)
from core.scbkr.plan_depth_compiler import apply_plan_depth
from core.scbkr.validity_failure_validator import validate_validity_failure


DEFAULT_REQUESTS = {
    "zh-code-deployment": (
        "幫我建立程式部署規則：先跑測試再檢查版本與環境；測試失敗、依賴不明或沒有回滾方案時不得部署；"
        "只能引用已確認的測試報告與版本紀錄；由專案負責人驗收簽名。"
    ),
    "zh-debt-civil-case": (
        "幫我生成債務民事案件資料整理規則書：先核對當事人、借款證據、金額、日期與時效；"
        "資料不足時只能列待確認，不得替我判決勝敗。"
    ),
    "en-refund-approval": (
        "Create a reusable customer refund approval rule. Verify the order and evidence first, "
        "stop when records are missing, and require my signature before the rule becomes active."
    ),
}


def _post_model(
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("model response must be a JSON object")
    return value


def _response_text(response: dict[str, Any]) -> str:
    try:
        return str(response["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("model response does not contain assistant content") from exc


def _staged_dimension_authoring(
    *,
    args: argparse.Namespace,
    request_text: str,
    locale: str,
    initial_raw: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]], float]:
    """Ask the same model for one SCBKR role at a time after a full-form failure."""
    try:
        initial_support = json.loads(initial_raw)
    except (TypeError, ValueError):
        initial_support = {}
    if not isinstance(initial_support, dict):
        initial_support = {}
    candidate: dict[str, Any] = {
        key: initial_support.get(key)
        for key in (
            "rule_summary",
            "missing_information",
            "user_confirmation_items",
            "model_cannot_decide",
            "risk_reminders",
            "next_actions",
        )
        if initial_support.get(key) not in (None, "", [], {})
    }
    audit: list[dict[str, Any]] = []
    usages: list[dict[str, Any]] = []
    total_elapsed = 0.0
    for layer in ("S", "C", "B", "K", "R"):
        instruction = model_dimension_repair_instruction(layer, locale=locale)
        patch_messages = build_model_dimension_patch_messages(
            request_text,
            layer=layer,
            instruction=instruction,
            current_dimension=None,
            locale=locale,
            compact=False,
        )
        started = time.perf_counter()
        patch_response = _post_model(
            base_url=args.base_url,
            model=args.model,
            messages=patch_messages,
            temperature=args.temperature,
            max_tokens=min(args.max_tokens, 420),
            timeout=args.timeout,
        )
        elapsed = time.perf_counter() - started
        total_elapsed += elapsed
        patch_raw = _response_text(patch_response)
        usage = patch_response.get("usage") or {}
        usages.append(usage)
        try:
            patch = parse_model_dimension_patch_output(
                patch_raw,
                layer=layer,
                instruction=instruction,
                user_input=request_text,
                locale=locale,
                require_complete_role=True,
            )
            candidate = merge_model_dimension_patch_candidate(
                candidate,
                layer=layer,
                patch=patch,
            )
            audit.append({
                "layer": layer,
                "model_schema_valid": True,
                "model_semantic_valid": True,
                "elapsed_seconds": round(elapsed, 3),
                "provider_usage": usage,
                "raw_model_output": patch_raw,
                "fallback_used": False,
            })
        except Exception as exc:
            audit.append({
                "layer": layer,
                "model_schema_valid": False,
                "model_semantic_valid": False,
                "elapsed_seconds": round(elapsed, 3),
                "provider_usage": usage,
                "raw_model_output": patch_raw,
                "error": f"{type(exc).__name__}: {exc}",
                "fallback_used": False,
            })
            continue
    if any(layer not in candidate for layer in ("S", "C", "B", "K", "R")):
        return None, audit, usages, total_elapsed
    candidate = refresh_model_rulebook_support_fields(candidate, locale=locale)
    semantic_report = validate_model_rulebook_semantics(candidate, user_input=request_text)
    candidate["model_semantic_report"] = semantic_report
    candidate["model_semantic_valid"] = semantic_report.get("passed") is True
    return candidate, audit, usages, total_elapsed


def run(args: argparse.Namespace) -> dict[str, Any]:
    request_text = args.request or DEFAULT_REQUESTS[args.case_id]
    locale = args.locale or ("en" if args.case_id.startswith("en-") else "zh-TW")
    kernel_pack = ensure_local_kernel_cache()
    messages = build_model_rulebook_messages(
        request_text,
        kernel_pack=kernel_pack,
        plan_level="FREE",
        locale=locale,
    )
    if args.replay_output:
        prior = json.loads(Path(args.replay_output).expanduser().resolve().read_text(encoding="utf-8"))
        raw = str(prior.get("raw_model_output") or "")
        if not raw:
            raise RuntimeError("replay artifact does not contain raw_model_output")
        response = {"usage": prior.get("provider_usage") or {}}
        elapsed = float(prior.get("elapsed_seconds") or 0)
    else:
        started = time.perf_counter()
        response = _post_model(
            base_url=args.base_url,
            model=args.model,
            messages=messages,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
        )
        elapsed = time.perf_counter() - started
        raw = _response_text(response)
    initial_parse_error = ""
    staged_repair_audit: list[dict[str, Any]] = []
    staged_provider_usages: list[dict[str, Any]] = []
    staged_elapsed = 0.0
    try:
        candidate = parse_model_rulebook_candidate(raw, user_input=request_text, locale=locale)
    except Exception as exc:
        initial_parse_error = f"{type(exc).__name__}: {exc}"
        if args.repair:
            try:
                candidate, staged_repair_audit, staged_provider_usages, staged_elapsed = _staged_dimension_authoring(
                    args=args,
                    request_text=request_text,
                    locale=locale,
                    initial_raw=raw,
                )
            except Exception as staged_exc:
                staged_repair_audit.append({
                    "stage": "staged_dimension_authoring",
                    "model_schema_valid": False,
                    "model_semantic_valid": False,
                    "error": f"{type(staged_exc).__name__}: {staged_exc}",
                    "fallback_used": False,
                })
                candidate = None
        else:
            candidate = None
    if candidate is None:
        result = {
            "case_id": args.case_id,
            "locale": locale,
            "request": request_text,
            "model": args.model,
            "elapsed_seconds": round(elapsed, 3),
            "provider_usage": response.get("usage") or {},
            "provider_usages": [response.get("usage") or {}],
            "repair_audit": [],
            "repair_elapsed_seconds": 0.0,
            "model_schema_valid": False,
            "model_semantic_valid": False,
            "parse_error": initial_parse_error,
            "staged_repair_audit": staged_repair_audit,
            "staged_repair_elapsed_seconds": round(staged_elapsed, 3),
            "validator": {
                "passed": False,
                "fail_reasons": ["model_schema_invalid"],
            },
            "fallback_used": False,
            "replayed_from_raw_output": bool(args.replay_output),
            "requires_user_signature": True,
            "model_signature_allowed": False,
            "authoring_candidate": None,
            "draft": None,
            "raw_model_output": raw,
            "response_finish_reason": (
                response.get("choices", [{}])[0].get("finish_reason")
                if isinstance(response.get("choices"), list) and response.get("choices")
                else None
            ),
        }
        if args.output:
            output = Path(args.output).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result
    repair_audit: list[dict[str, Any]] = list(staged_repair_audit)
    provider_usages = [response.get("usage") or {}, *staged_provider_usages]
    repair_elapsed = staged_elapsed
    if args.repair:
        for repair_round in range(1, 3):
            candidate, pre_kernel_repairs = compile_kernel_required_clauses(
                candidate,
                user_input=request_text,
                locale=locale,
            )
            repair_audit.extend({
                "round": repair_round,
                "layer": item["layer"],
                "provider_usage": {},
                "raw_model_output": "",
                "model_schema_valid": True,
                "model_used": False,
                "kernel_compile_audit": item,
                "fallback_used": False,
                "elapsed_seconds": 0.0,
            } for item in pre_kernel_repairs)
            candidate = refresh_model_rulebook_support_fields(candidate, locale=locale)
            semantic_report = validate_model_rulebook_semantics(candidate, user_input=request_text)
            candidate["model_semantic_report"] = semantic_report
            candidate["model_semantic_valid"] = semantic_report.get("passed") is True
            targets = model_rulebook_repair_targets(
                semantic_report,
                limit=3,
            )
            if not targets:
                break
            for layer in targets:
                instruction = model_dimension_repair_instruction(layer, locale=locale)
                current = candidate.get(layer) or {}
                role_alignment = semantic_report.get("dimension_role_alignment") or {}
                explanation_alignment = semantic_report.get("model_explanation_alignment") or {}
                explanation_only = (
                    explanation_alignment.get(layer) is not True
                    and layer not in (semantic_report.get("placeholder_dimensions") or [])
                    and (
                        (layer == "S" and semantic_report.get("subject_request_alignment") is True)
                        or (layer != "S" and role_alignment.get(layer) is True)
                    )
                )
                use_basis_selection = layer == "K" and (
                    not explanation_only
                    and role_alignment.get("K") is not True
                    or semantic_report.get("k_signature_as_basis") is True
                    or bool(semantic_report.get("k_unrequested_non_citable_sources"))
                )
                if explanation_only:
                    patch_messages = build_model_dimension_explanation_messages(
                        request_text,
                        layer=layer,
                        current_content=str(current.get("content") or ""),
                        locale=locale,
                    )
                elif use_basis_selection:
                    patch_messages = build_model_basis_selection_messages(
                        request_text,
                        locale=locale,
                    )
                else:
                    patch_messages = build_model_dimension_patch_messages(
                        request_text,
                        layer=layer,
                        instruction=instruction,
                        current_dimension={
                            "model_draft_content": current.get("content"),
                            "model_explanation": current.get("explanation"),
                            "missing_information": current.get("missing_information"),
                            "needs_user_confirmation": current.get("needs_user_confirmation"),
                        },
                        locale=locale,
                        compact=True,
                    )
                patch_started = time.perf_counter()
                patch_response: dict[str, Any] = {}
                patch_raw = ""
                try:
                    patch_response = _post_model(
                        base_url=args.base_url,
                        model=args.model,
                        messages=patch_messages,
                        temperature=args.temperature,
                        max_tokens=min(
                            args.max_tokens,
                            80 if use_basis_selection else (180 if explanation_only else 420),
                        ),
                        timeout=args.timeout,
                    )
                    patch_raw = _response_text(patch_response)
                    basis_audit: dict[str, Any] | None = None
                    if use_basis_selection:
                        selected_terms = parse_model_basis_selection_output(
                            patch_raw,
                            user_input=request_text,
                            locale=locale,
                        )
                        candidate, basis_audit = compile_model_basis_selection_candidate(
                            candidate,
                            selected_terms=selected_terms,
                            raw_model_output=patch_raw,
                            locale=locale,
                        )
                    elif explanation_only:
                        explanation = parse_model_dimension_explanation_output(
                            patch_raw,
                            layer=layer,
                            current_content=str(current.get("content") or ""),
                            user_input=request_text,
                            locale=locale,
                        )
                        candidate = merge_model_dimension_explanation_candidate(
                            candidate,
                            layer=layer,
                            explanation=explanation,
                        )
                    else:
                        patch = parse_model_dimension_patch_output(
                            patch_raw,
                            layer=layer,
                            instruction=instruction,
                            user_input=request_text,
                            locale=locale,
                            require_complete_role=layer not in ("B", "R"),
                        )
                        candidate = merge_model_dimension_patch_candidate(
                            candidate,
                            layer=layer,
                            patch=patch,
                        )
                    repair_audit.append({
                        "round": repair_round,
                        "layer": layer,
                        "provider_usage": patch_response.get("usage") or {},
                        "raw_model_output": patch_raw,
                        "model_schema_valid": True,
                        "repair_kind": "explanation_only" if explanation_only else "dimension_content",
                        "model_fragment_compiled": basis_audit is not None,
                        "kernel_compile_audit": basis_audit,
                        "fallback_used": False,
                    })
                except Exception as exc:
                    repair_audit.append({
                        "round": repair_round,
                        "layer": layer,
                        "provider_usage": patch_response.get("usage") or {},
                        "raw_model_output": patch_raw,
                        "model_schema_valid": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "fallback_used": False,
                    })
                finally:
                    patch_elapsed = time.perf_counter() - patch_started
                    repair_elapsed += patch_elapsed
                    repair_audit[-1]["elapsed_seconds"] = round(patch_elapsed, 3)
                    provider_usages.append(patch_response.get("usage") or {})
            candidate, kernel_repairs = compile_kernel_required_clauses(
                candidate,
                user_input=request_text,
                locale=locale,
            )
            repair_audit.extend({
                "round": repair_round,
                "layer": item["layer"],
                "provider_usage": {},
                "raw_model_output": "",
                "model_schema_valid": True,
                "model_used": False,
                "kernel_compile_audit": item,
                "fallback_used": False,
                "elapsed_seconds": 0.0,
            } for item in kernel_repairs)
            candidate = refresh_model_rulebook_support_fields(
                candidate,
                locale=locale,
            )
            report = validate_model_rulebook_semantics(candidate, user_input=request_text)
            candidate["model_semantic_report"] = report
            candidate["model_semantic_valid"] = report.get("passed") is True
            if report.get("passed") is True:
                break
    context_audit = build_context_audit(
        messages=messages,
        model_output=raw,
        kernel_pack=kernel_pack,
    )
    context_audit.update(
        {
            "provider_usage": response.get("usage") or {},
            "provider_usages": provider_usages,
            "elapsed_seconds": round(elapsed, 3),
            "repair_elapsed_seconds": round(repair_elapsed, 3),
            "structured_transport": "prompt_only_kernel_validated",
            "fallback_used": False,
        }
    )
    draft = authoring_to_scbkr_draft(
        user_input=request_text,
        authoring=candidate,
        kernel_pack=kernel_pack,
        plan_level="FREE",
        locale=locale,
        model_provider="lm_studio",
        model_name=args.model,
        context_audit=context_audit,
    )
    draft = apply_plan_depth(draft, "FREE")
    validation = validate_validity_failure(draft, kernel_pack)
    draft["validator_passed"] = validation.get("passed") is True
    result = {
        "case_id": args.case_id,
        "locale": locale,
        "request": request_text,
        "model": args.model,
        "elapsed_seconds": round(elapsed, 3),
        "provider_usage": response.get("usage") or {},
        "provider_usages": provider_usages,
        "repair_audit": repair_audit,
        "repair_elapsed_seconds": round(repair_elapsed, 3),
        "model_schema_valid": True,
        "model_semantic_valid": candidate.get("model_semantic_valid") is True,
        "initial_parse_error": initial_parse_error,
        "staged_dimension_authoring_used": bool(staged_repair_audit),
        "model_semantic_report": candidate.get("model_semantic_report") or {},
        "validator": validation,
        "fallback_used": False,
        "replayed_from_raw_output": bool(args.replay_output),
        "requires_user_signature": True,
        "model_signature_allowed": False,
        "authoring_candidate": candidate,
        "draft": draft,
        "raw_model_output": raw,
    }
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", choices=sorted(DEFAULT_REQUESTS), default="zh-code-deployment")
    parser.add_argument("--request", default="")
    parser.add_argument("--locale", default="")
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="qwen2.5-1.5b-instruct")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=800)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", default="")
    parser.add_argument("--replay-output", default="")
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
