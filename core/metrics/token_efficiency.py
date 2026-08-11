"""Deterministic token estimates and provider usage aggregation."""
from __future__ import annotations

import json
import math
from typing import Any

from core.metrics.token_meter import build_token_meter_report


def estimate_tokens(value: Any) -> int:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    cjk = sum(1 for char in text if "\u3400" <= char <= "\u9fff")
    other = max(0, len(text) - cjk)
    return max(1, math.ceil(cjk / 1.7 + other / 4.0))


def build_token_efficiency_metrics(
    *,
    raw_input: str,
    messages: list[dict[str, Any]],
    retrieval_context: dict[str, Any] | None,
    full_rule_registry: list[dict[str, Any]] | None,
    provider_usages: list[dict[str, Any]] | None = None,
    attempts: int = 0,
    model_settings: dict[str, Any] | None = None,
    pricing: dict[str, Any] | None = None,
    measurement_scope: str = "rule_authoring",
) -> dict[str, Any]:
    context = retrieval_context or {}
    full_context = {
        "raw_input": raw_input,
        "retrieval_context": context,
        "rule_registry": full_rule_registry or [],
    }
    actual_context = {
        "messages": messages,
        "evidence_packet": context.get("evidence_packet") or {},
    }
    meter = build_token_meter_report(
        full_context=full_context,
        current_rule_package=actual_context,
        messages=messages,
        provider_usages=provider_usages,
        model_settings=model_settings,
        pricing=pricing,
        measurement_scope=measurement_scope,
    )
    baseline_tokens = meter["baseline_prompt_tokens"]
    compiled_tokens = meter["compiled_prompt_tokens"]
    saved = meter["tokens_saved"]
    usages = [usage for usage in (provider_usages or []) if isinstance(usage, dict)]
    provider_prompt = sum(int(item.get("prompt_tokens") or 0) for item in usages)
    provider_completion = sum(int(item.get("completion_tokens") or 0) for item in usages)
    return {
        **meter,
        "metrics_version": "scbkr.token-efficiency.v3",
        "estimation_method": "cjk_1.7_ascii_4",
        "baseline_context_tokens_estimate": baseline_tokens,
        "compiled_context_tokens_estimate": compiled_tokens,
        "estimated_tokens_avoided": saved,
        "estimated_reduction_percent": round(saved / baseline_tokens * 100, 1) if baseline_tokens else 0.0,
        "provider_prompt_tokens": provider_prompt or None,
        "provider_completion_tokens": provider_completion or None,
        "provider_total_tokens": (provider_prompt + provider_completion) or None,
        "model_attempts": attempts,
        "authoritative_citations_loaded": int((context.get("evidence_packet") or {}).get("authority_count") or 0),
        "candidate_evidence_excluded": int((context.get("evidence_packet") or {}).get("candidate_count") or 0),
    }


def summarize_metrics(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [task.get("scbkr", {}).get("token_metrics") for task in tasks]
    metrics = [item for item in metrics if isinstance(item, dict)]
    return {
        "metrics_version": "scbkr.token-efficiency.v3",
        "measurement_scope": "aggregate_history",
        "measurement_basis": "aggregate",
        "comparison_basis": "none",
        "savings_verified": False,
        "status": "HISTORY_ONLY",
        "task_count": len(metrics),
        "estimated_tokens_avoided": sum(int(item.get("estimated_tokens_avoided") or 0) for item in metrics),
        "provider_total_tokens": sum(int(item.get("provider_total_tokens") or 0) for item in metrics),
        "actual_total_tokens": sum(int(item.get("actual_total_tokens") or 0) for item in metrics),
        "estimated_cost_saved": round(sum(float(item.get("estimated_cost_saved") or 0) for item in metrics), 8),
        "model_attempts": sum(int(item.get("model_attempts") or 0) for item in metrics),
        "candidate_evidence_excluded": sum(int(item.get("candidate_evidence_excluded") or 0) for item in metrics),
    }
