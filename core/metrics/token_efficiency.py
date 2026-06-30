"""Deterministic token estimates and provider usage aggregation."""
from __future__ import annotations

import json
import math
from typing import Any


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
    baseline_tokens = estimate_tokens(full_context)
    compiled_tokens = estimate_tokens(actual_context)
    saved = max(0, baseline_tokens - compiled_tokens)
    usages = [usage for usage in (provider_usages or []) if isinstance(usage, dict)]
    provider_prompt = sum(int(item.get("prompt_tokens") or 0) for item in usages)
    provider_completion = sum(int(item.get("completion_tokens") or 0) for item in usages)
    return {
        "metrics_version": "scbkr.token-efficiency.v2",
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
        "metrics_version": "scbkr.token-efficiency.v2",
        "task_count": len(metrics),
        "estimated_tokens_avoided": sum(int(item.get("estimated_tokens_avoided") or 0) for item in metrics),
        "provider_total_tokens": sum(int(item.get("provider_total_tokens") or 0) for item in metrics),
        "model_attempts": sum(int(item.get("model_attempts") or 0) for item in metrics),
        "candidate_evidence_excluded": sum(int(item.get("candidate_evidence_excluded") or 0) for item in metrics),
    }
