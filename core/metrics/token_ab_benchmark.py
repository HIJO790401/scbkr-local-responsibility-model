"""Same-model A/B measurement for SCBKR rule-package token savings."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import time
from typing import Any

from core.metrics.token_meter import measure_tokens, stable_text


TOKEN_AB_VERSION = "scbkr.same-model-token-ab.v1"
ModelCall = Callable[..., Any]


def _json_block(label: str, value: Any) -> str:
    return f"{label}:\n{json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)}"


def _build_messages(
    *,
    variant: str,
    question: str,
    full_history: list[dict[str, Any]],
    full_rule_context: Any,
    current_rule_package: Any,
    system_prompt: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if variant == "A":
        for item in full_history:
            role = str(item.get("role") or "user")
            content = str(item.get("content") or "")
            messages.append({"role": role, "content": content})
        messages.append({"role": "system", "content": _json_block("FULL_RULE_CONTEXT", full_rule_context)})
    else:
        messages.append({"role": "system", "content": _json_block("CURRENT_RULE_PACKAGE", current_rule_package)})
    messages.append({"role": "user", "content": question})
    return messages


def _measure_prompt(
    messages: list[dict[str, str]],
    *,
    provider: str,
    model_name: str,
) -> dict[str, Any]:
    return measure_tokens(
        messages,
        provider=provider,
        model_name=model_name,
        as_messages=True,
    )


def _fit_full_context_to_prompt_budget(
    *,
    question: str,
    full_history: list[dict[str, Any]],
    full_rule_context: Any,
    current_rule_package: Any,
    system_prompt: str,
    provider: str,
    model_name: str,
    max_prompt_tokens: int | None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    original = _build_messages(
        variant="A",
        question=question,
        full_history=full_history,
        full_rule_context=full_rule_context,
        current_rule_package=current_rule_package,
        system_prompt=system_prompt,
    )
    original_measure = _measure_prompt(
        original,
        provider=provider,
        model_name=model_name,
    )
    audit = {
        "bounded": False,
        "max_prompt_tokens": max_prompt_tokens,
        "original_prompt_tokens_estimate": original_measure["tokens"],
        "bounded_prompt_tokens_estimate": original_measure["tokens"],
        "token_count_method": original_measure["method"],
        "tokenizer_name": original_measure["tokenizer_name"],
        "original_snapshot_characters": 0,
        "retained_snapshot_characters": 0,
        "original_message_count": len(original),
        "bounded_message_count": len(original),
    }
    if max_prompt_tokens is None or original_measure["tokens"] <= max_prompt_tokens:
        return original, audit

    snapshot = stable_text({
        "full_history": full_history,
        "full_rule_context": full_rule_context,
    })
    audit["original_snapshot_characters"] = len(snapshot)
    snapshot_sha256 = _fingerprint(snapshot)

    def candidate(prefix_length: int) -> list[dict[str, str]]:
        envelope = {
            "bounded_to_model_context": True,
            "original_snapshot_sha256": snapshot_sha256,
            "original_snapshot_characters": len(snapshot),
            "retained_snapshot_characters": prefix_length,
            "snapshot_prefix": snapshot[:prefix_length],
        }
        return [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": _json_block("BOUNDED_FULL_CONTEXT_SNAPSHOT", envelope)},
            {"role": "user", "content": question},
        ]

    empty = candidate(0)
    empty_measure = _measure_prompt(empty, provider=provider, model_name=model_name)
    if empty_measure["tokens"] > max_prompt_tokens:
        raise ValueError("model context is too small for the benchmark system prompt and question")

    low = 0
    high = len(snapshot)
    best_messages = empty
    best_measure = empty_measure
    while low <= high:
        middle = (low + high) // 2
        trial = candidate(middle)
        trial_measure = _measure_prompt(trial, provider=provider, model_name=model_name)
        if trial_measure["tokens"] <= max_prompt_tokens:
            best_messages = trial
            best_measure = trial_measure
            low = middle + 1
        else:
            high = middle - 1

    retained = max(0, high)
    audit.update({
        "bounded": True,
        "bounded_prompt_tokens_estimate": best_measure["tokens"],
        "retained_snapshot_characters": retained,
        "bounded_message_count": len(best_messages),
        "retained_snapshot_percent": round(retained / len(snapshot) * 100, 2) if snapshot else 100.0,
    })
    return best_messages, audit


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "to_dict"):
        dumped = value.to_dict()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _normalize_usage(response: dict[str, Any]) -> dict[str, Any]:
    usage = _mapping(response.get("usage"))

    def number(*keys: str) -> int | None:
        for key in keys:
            value = usage.get(key)
            if value is None:
                continue
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                continue
        return None

    prompt = number("prompt_tokens", "input_tokens")
    completion = number("completion_tokens", "output_tokens")
    total = number("total_tokens")
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    available = prompt is not None and completion is not None and total is not None
    return {
        "available": available,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "raw": usage,
    }


def _extract_output(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str):
        return output_text
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        choice = _mapping(choices[0])
        message = _mapping(choice.get("message"))
        content = message.get("content", choice.get("text"))
        if isinstance(content, str):
            return content
    content = response.get("content")
    if isinstance(content, str):
        return content
    return stable_text(content) if content is not None else ""


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_text(value).encode("utf-8")).hexdigest()


def _run_variant(
    *,
    variant: str,
    provider: str,
    model_name: str,
    messages: list[dict[str, str]],
    model_call: ModelCall,
) -> dict[str, Any]:
    started = time.perf_counter()
    response_value = model_call(
        provider=provider,
        model=model_name,
        messages=messages,
        variant=variant,
    )
    if inspect.isawaitable(response_value):
        raise TypeError("model_call must be synchronous; await it in the caller before benchmarking")
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    response = _mapping(response_value)
    if not response:
        raise TypeError("model_call must return a mapping or an object with model_dump()/to_dict()")

    provider_usage = _normalize_usage(response)
    output = _extract_output(response)
    prompt_estimate = measure_tokens(messages, provider=provider, model_name=model_name, as_messages=True)
    completion_estimate = measure_tokens(output, provider=provider, model_name=model_name)
    estimated_prompt = prompt_estimate["tokens"]
    estimated_completion = completion_estimate["tokens"]
    estimated_total = estimated_prompt + estimated_completion
    reported_model = str(response.get("model") or "")

    if provider_usage["available"]:
        measurement_basis = "provider_usage"
        prompt_tokens = provider_usage["prompt_tokens"]
        completion_tokens = provider_usage["completion_tokens"]
        total_tokens = provider_usage["total_tokens"]
    else:
        methods = {prompt_estimate["method"], completion_estimate["method"]}
        measurement_basis = "tokenizer" if "heuristic_chars_2" not in methods else "heuristic_estimate"
        prompt_tokens = estimated_prompt
        completion_tokens = estimated_completion
        total_tokens = estimated_total

    return {
        "variant": variant,
        "context_mode": "full_history_and_full_rule_context" if variant == "A" else "minimal_current_rule_package",
        "provider": provider,
        "requested_model": model_name,
        "reported_model": reported_model or None,
        "model_identity_basis": "provider_response" if reported_model else "requested_model",
        "measurement_basis": measurement_basis,
        "provider_usage_available": provider_usage["available"],
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
        "model_calls": 1,
        "output": output,
        "message_count": len(messages),
        "prompt_sha256": _fingerprint(messages),
        "local_estimate": {
            "prompt_tokens": estimated_prompt,
            "completion_tokens": estimated_completion,
            "total_tokens": estimated_total,
            "prompt_method": prompt_estimate["method"],
            "completion_method": completion_estimate["method"],
            "tokenizer_name": prompt_estimate["tokenizer_name"],
        },
        "provider_usage": provider_usage["raw"] or None,
    }


def _delta(a: int, b: int) -> dict[str, Any]:
    saved = a - b
    return {
        "a": a,
        "b": b,
        "saved": saved,
        "reduction_percent": round(saved / a * 100, 2) if a else None,
    }


def run_token_ab_benchmark(
    *,
    question: str,
    full_history: list[dict[str, Any]],
    full_rule_context: Any,
    current_rule_package: Any,
    provider: str,
    model_name: str,
    model_call: ModelCall,
    system_prompt: str = "Answer the user using only applicable confirmed information. Do not invent facts.",
    max_prompt_tokens: int | None = None,
) -> dict[str, Any]:
    """Run A and B against exactly the same requested provider and model.

    ``model_call`` receives keyword arguments ``provider``, ``model``,
    ``messages`` and ``variant`` and must return a provider-like response.
    Savings are verified only when both responses include provider usage.
    """

    if not question.strip():
        raise ValueError("question is required")
    if not provider.strip() or not model_name.strip():
        raise ValueError("provider and model_name are required")
    if not callable(model_call):
        raise TypeError("model_call must be callable")

    if max_prompt_tokens is not None and max_prompt_tokens < 128:
        raise ValueError("max_prompt_tokens must be at least 128")

    messages_a, context_budget = _fit_full_context_to_prompt_budget(
        question=question,
        full_history=full_history,
        full_rule_context=full_rule_context,
        current_rule_package=current_rule_package,
        system_prompt=system_prompt,
        provider=provider,
        model_name=model_name,
        max_prompt_tokens=max_prompt_tokens,
    )
    messages_b = _build_messages(
        variant="B",
        question=question,
        full_history=full_history,
        full_rule_context=full_rule_context,
        current_rule_package=current_rule_package,
        system_prompt=system_prompt,
    )
    minimal_measure = _measure_prompt(
        messages_b,
        provider=provider,
        model_name=model_name,
    )
    context_budget["minimal_prompt_tokens_estimate"] = minimal_measure["tokens"]
    if max_prompt_tokens is not None and minimal_measure["tokens"] > max_prompt_tokens:
        raise ValueError(
            "current_rule_package exceeds the connected model context; use a larger context window or reduce the signed package"
        )
    result_a = _run_variant(
        variant="A", provider=provider, model_name=model_name, messages=messages_a, model_call=model_call
    )
    result_b = _run_variant(
        variant="B", provider=provider, model_name=model_name, messages=messages_b, model_call=model_call
    )
    if context_budget["bounded"]:
        result_a["context_mode"] = "bounded_full_history_and_full_rule_context"

    reported_models = {item for item in (result_a["reported_model"], result_b["reported_model"]) if item}
    if len(reported_models) > 1:
        raise ValueError(f"provider returned different models for A and B: {sorted(reported_models)}")
    if reported_models and model_name not in reported_models:
        raise ValueError(f"provider model does not match requested model: {sorted(reported_models)} != {model_name}")

    savings_verified = bool(result_a["provider_usage_available"] and result_b["provider_usage_available"])
    if savings_verified:
        measurement_basis = "provider_usage"
    elif "heuristic_estimate" in {result_a["measurement_basis"], result_b["measurement_basis"]}:
        measurement_basis = "heuristic_estimate"
    else:
        measurement_basis = "tokenizer"

    return {
        "benchmark_version": TOKEN_AB_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model_name": model_name,
        "same_provider": True,
        "same_model": True,
        "question": question,
        "input_evidence": {
            "full_history_message_count": len(full_history),
            "full_history_sha256": _fingerprint(full_history),
            "full_rule_context_sha256": _fingerprint(full_rule_context),
            "current_rule_package_sha256": _fingerprint(current_rule_package),
            "context_budget": context_budget,
        },
        "comparison_basis": "same_provider_same_model_two_real_calls" if savings_verified else "same_provider_same_model_local_count",
        "measurement_basis": measurement_basis,
        "savings_verified": savings_verified,
        "verification_note": (
            "Both A and B use provider-reported usage from the same requested provider/model."
            if savings_verified
            else "Provider usage was missing from at least one call; savings are an unverified local token estimate."
        ),
        "variants": {"A": result_a, "B": result_b},
        "savings": {
            "prompt": _delta(int(result_a["prompt_tokens"]), int(result_b["prompt_tokens"])),
            "completion": _delta(int(result_a["completion_tokens"]), int(result_b["completion_tokens"])),
            "total": _delta(int(result_a["total_tokens"]), int(result_b["total_tokens"])),
            "latency_ms": {
                "a": result_a["latency_ms"],
                "b": result_b["latency_ms"],
                "difference": round(result_a["latency_ms"] - result_b["latency_ms"], 3),
            },
            "model_calls": {"a": 1, "b": 1, "total": 2},
        },
    }


def render_token_ab_markdown(report: dict[str, Any]) -> str:
    """Render a human-readable audit without inventing a savings claim."""

    variants = report["variants"]
    savings = report["savings"]
    status = "Verified by provider usage" if report["savings_verified"] else "Estimate only (not verified)"
    lines = [
        "# Same-model A/B Token Benchmark",
        "",
        f"- Provider: `{report['provider']}`",
        f"- Model: `{report['model_name']}`",
        f"- Status: **{status}**",
        f"- Basis: `{report['measurement_basis']}`",
        f"- Question: {report['question']}",
        "",
        "## Measurements",
        "",
        "| Variant | Context | Prompt | Completion | Total | Latency (ms) | Calls |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for key in ("A", "B"):
        item = variants[key]
        lines.append(
            f"| {key} | `{item['context_mode']}` | {item['prompt_tokens']} | "
            f"{item['completion_tokens']} | {item['total_tokens']} | {item['latency_ms']} | {item['model_calls']} |"
        )
    lines.extend(
        [
            "",
            "## Savings",
            "",
            f"- Prompt tokens: {savings['prompt']['saved']} ({savings['prompt']['reduction_percent']}%)",
            f"- Completion tokens: {savings['completion']['saved']} ({savings['completion']['reduction_percent']}%)",
            f"- Total tokens: {savings['total']['saved']} ({savings['total']['reduction_percent']}%)",
            f"- Verification: {report['verification_note']}",
            "",
            "## Outputs",
            "",
            "### A: Full context",
            "",
            variants["A"]["output"] or "(empty output)",
            "",
            "### B: Minimal current_rule_package",
            "",
            variants["B"]["output"] or "(empty output)",
            "",
        ]
    )
    return "\n".join(lines)


def write_token_ab_report(
    report: dict[str, Any],
    *,
    json_path: str | Path,
    markdown_path: str | Path,
) -> tuple[Path, Path]:
    json_target = Path(json_path)
    markdown_target = Path(markdown_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_target.write_text(render_token_ab_markdown(report), encoding="utf-8")
    return json_target, markdown_target
