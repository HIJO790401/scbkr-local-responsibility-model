"""Exact token and cost measurement for local and OpenAI-compatible models.

The provider's ``usage`` object is authoritative when it is returned.  When a
provider does not return usage, this module uses a locally available tokenizer
and clearly labels the result as a tokenizer count or a heuristic estimate.
Prices are intentionally user-configured; the product must never invent a
current cloud price.
"""

from __future__ import annotations

from functools import lru_cache
import json
import math
from typing import Any


TOKEN_METER_VERSION = "scbkr.token-meter.v1"
DEFAULT_PRICING: dict[str, Any] = {
    "currency": "USD",
    "input_per_million": None,
    "output_per_million": None,
    "cached_input_per_million": None,
    "source": "not_configured",
    "snapshot_id": "",
    "model_name": "",
    "updated_at": None,
}


def stable_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def heuristic_token_count(value: Any) -> int:
    """Conservative fallback used only when no tokenizer or provider usage exists."""

    text = stable_text(value)
    return max(1, math.ceil(len(text) / 2)) if text else 0


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _usage_number(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def summarize_provider_usage(usages: list[dict[str, Any]] | None) -> dict[str, Any]:
    valid = [item for item in (usages or []) if isinstance(item, dict)]
    prompt = sum(_usage_number(item.get("prompt_tokens")) for item in valid)
    completion = sum(_usage_number(item.get("completion_tokens")) for item in valid)
    reported_total = sum(_usage_number(item.get("total_tokens")) for item in valid)
    total = reported_total or prompt + completion
    cached = sum(_usage_number((item.get("prompt_tokens_details") or {}).get("cached_tokens")) for item in valid)
    reasoning = sum(_usage_number((item.get("completion_tokens_details") or {}).get("reasoning_tokens")) for item in valid)
    return {
        "available": bool(valid and (prompt or completion or reported_total)),
        "request_count": len(valid),
        "prompt_tokens": prompt or None,
        "completion_tokens": completion or None,
        "total_tokens": total or None,
        "cached_input_tokens": cached or None,
        "reasoning_tokens": reasoning or None,
    }


@lru_cache(maxsize=8)
def _openai_encoding(model_name: str):
    try:
        import tiktoken

        try:
            return tiktoken.encoding_for_model(model_name)
        except KeyError:
            # This is exact for the selected cl100k encoding, but not claimed
            # as an exact model tokenizer when the model is unknown.
            return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


@lru_cache(maxsize=8)
def _huggingface_tokenizer(model_name: str):
    try:
        from transformers import AutoTokenizer

        candidates = [model_name]
        lowered = model_name.lower()
        aliases = {
            "qwen2.5-0.5b-instruct": "Qwen/Qwen2.5-0.5B-Instruct",
            "qwen2.5-1.5b-instruct": "Qwen/Qwen2.5-1.5B-Instruct",
            "qwen2.5-3b-instruct": "Qwen/Qwen2.5-3B-Instruct",
            "qwen2.5-7b-instruct": "Qwen/Qwen2.5-7B-Instruct",
            "qwen3.5-4b": "Qwen/Qwen3.5-4B",
            "qwen3.5-4b-instruct": "Qwen/Qwen3.5-4B",
        }
        if lowered in aliases:
            candidates.append(aliases[lowered])
        for candidate in candidates:
            if not candidate:
                continue
            try:
                # Never make a chat request wait for a tokenizer download.
                return AutoTokenizer.from_pretrained(candidate, local_files_only=True)
            except Exception:
                continue
    except Exception:
        return None
    return None


def _tokenizer_count(value: Any, *, provider: str, model_name: str, as_messages: bool = False) -> tuple[int, str, str]:
    # Empty audit inputs are common for product help and permission-gated
    # requests. Loading a multi-gigabyte model tokenizer to count zero tokens
    # makes the first desktop interaction needlessly slow.
    if _is_empty_value(value):
        return 0, "empty", ""

    if as_messages and isinstance(value, list) and provider in {"lm_studio", "ollama"}:
        tokenizer = _huggingface_tokenizer(model_name)
        if tokenizer is not None:
            try:
                tokens = tokenizer.apply_chat_template(value, tokenize=True, add_generation_prompt=True)
                return len(tokens), "huggingface_chat_template", getattr(tokenizer, "name_or_path", model_name)
            except Exception:
                pass

    if provider in {"lm_studio", "ollama"}:
        tokenizer = _huggingface_tokenizer(model_name)
        if tokenizer is not None:
            try:
                return len(tokenizer.encode(stable_text(value), add_special_tokens=True)), "huggingface_tokenizer", getattr(tokenizer, "name_or_path", model_name)
            except Exception:
                pass

    if provider in {"openai_compatible", "custom"}:
        encoding = _openai_encoding(model_name)
        if encoding is not None:
            return len(encoding.encode(stable_text(value))), "tiktoken", getattr(encoding, "name", model_name)

    return heuristic_token_count(value), "heuristic_chars_2", "heuristic"


def measure_tokens(
    value: Any,
    *,
    provider: str = "",
    model_name: str = "",
    as_messages: bool = False,
) -> dict[str, Any]:
    """Count tokens locally and disclose whether the count is tokenizer-based.

    This is evidence for an estimate only. Provider-reported usage remains the
    authoritative source for a verified A/B comparison.
    """

    count, method, tokenizer_name = _tokenizer_count(
        value,
        provider=provider,
        model_name=model_name,
        as_messages=as_messages,
    )
    return {
        "tokens": count,
        "method": method,
        "tokenizer_name": tokenizer_name,
        "is_tokenizer_count": method not in {"heuristic_chars_2", "empty"},
    }


def _number_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def normalize_pricing(pricing: dict[str, Any] | None, *, model_name: str = "") -> dict[str, Any]:
    merged = {**DEFAULT_PRICING, **(pricing or {})}
    return {
        "currency": str(merged.get("currency") or "USD").upper(),
        "input_per_million": _number_or_none(merged.get("input_per_million")),
        "output_per_million": _number_or_none(merged.get("output_per_million")),
        "cached_input_per_million": _number_or_none(merged.get("cached_input_per_million")),
        "source": str(merged.get("source") or "not_configured"),
        "snapshot_id": str(merged.get("snapshot_id") or ""),
        "model_name": str(merged.get("model_name") or model_name),
        "updated_at": merged.get("updated_at"),
    }


def _cost(tokens: int | None, rate: float | None) -> float | None:
    if tokens is None or rate is None:
        return None
    return round(tokens * rate / 1_000_000, 8)


def build_token_meter_report(
    *,
    full_context: Any,
    current_rule_package: Any,
    messages: list[dict[str, Any]] | None = None,
    provider_usages: list[dict[str, Any]] | None = None,
    model_settings: dict[str, Any] | None = None,
    pricing: dict[str, Any] | None = None,
    measurement_scope: str = "rule_answer",
) -> dict[str, Any]:
    settings = model_settings or {}
    provider = str(settings.get("provider") or "")
    model_name = str(settings.get("model_name") or "")
    usage = summarize_provider_usage(provider_usages)
    baseline, baseline_method, tokenizer_name = _tokenizer_count(full_context, provider=provider, model_name=model_name)
    package, package_method, package_tokenizer_name = _tokenizer_count(current_rule_package, provider=provider, model_name=model_name)
    actual_prompt = usage.get("prompt_tokens")
    actual_completion = usage.get("completion_tokens")
    actual_total = usage.get("total_tokens")
    if usage["available"]:
        request_count = actual_prompt or 0
        request_method = "provider_usage"
        request_tokenizer_name = ""
    else:
        request_count, request_method, request_tokenizer_name = _tokenizer_count(
            messages or [],
            provider=provider,
            model_name=model_name,
            as_messages=True,
        )
    compiled_prompt = actual_prompt if actual_prompt is not None else request_count
    saved = max(0, baseline - compiled_prompt)
    reduction = round(saved / baseline * 100, 2) if baseline else 0.0
    meter_source = "provider_usage" if usage["available"] else ("tokenizer" if request_method != "heuristic_chars_2" else "heuristic_estimate")
    pricing_record = normalize_pricing(pricing, model_name=model_name)
    configured_input = pricing_record["input_per_million"] is not None
    configured_output = pricing_record["output_per_million"] is not None
    input_cost = _cost(actual_prompt, pricing_record["input_per_million"])
    output_cost = _cost(actual_completion, pricing_record["output_per_million"])
    cost_configured = configured_input and configured_output
    billed_cost = round((input_cost or 0) + (output_cost or 0), 8) if cost_configured and usage["available"] else None
    saved_cost = _cost(saved, pricing_record["input_per_million"]) if configured_input else None
    local_execution = provider in {"lm_studio", "ollama"} or settings.get("mode") == "local"
    return {
        "metrics_version": TOKEN_METER_VERSION,
        "measurement_scope": measurement_scope,
        "measurement_basis": meter_source,
        "provider": provider or None,
        "model_name": model_name or None,
        "provider_usage_available": usage["available"],
        "provider_request_count": usage["request_count"],
        "actual_prompt_tokens": actual_prompt,
        "actual_completion_tokens": actual_completion,
        "actual_total_tokens": actual_total,
        "cached_input_tokens": usage["cached_input_tokens"],
        "reasoning_tokens": usage["reasoning_tokens"],
        "baseline_prompt_tokens": baseline,
        "compiled_prompt_tokens": compiled_prompt,
        "tokens_saved": saved,
        "reduction_percent": reduction,
        "comparison_basis": "counterfactual_local_count",
        "savings_verified": False,
        "actual_usage_verified": usage["available"],
        "tokenizer_name": (request_tokenizer_name or package_tokenizer_name or tokenizer_name),
        "baseline_token_count_method": baseline_method,
        "compiled_token_count_method": package_method,
        "request_token_count_method": request_method,
        "local_execution": local_execution,
        "pricing": pricing_record,
        "price_status": "configured" if cost_configured else ("local_no_api_charge" if local_execution else "not_configured"),
        "price_source": pricing_record["source"],
        "currency": pricing_record["currency"],
        "api_cost": 0.0 if local_execution and usage["available"] else billed_cost,
        "estimated_cost": 0.0 if local_execution and usage["available"] else billed_cost,
        "estimated_cost_saved": saved_cost,
        "cost_is_billed": bool(usage["available"] and cost_configured and not local_execution),
        # Compatibility fields used by existing UI and reports.
        "full_context_tokens_est": baseline,
        "current_rule_package_tokens_est": package,
        "compression_ratio": round(package / baseline, 6) if baseline else 0.0,
        "compression_percent": round(max(0.0, (1 - package / baseline) * 100), 2) if baseline else 0.0,
        "status": "MEASURED_INPUT" if usage["available"] else "ESTIMATED",
    }
