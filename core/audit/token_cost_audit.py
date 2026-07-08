"""Token and cost audit for the local-first SCBKR runtime.

The audit compares a full-context prompt shape with the minimal
``current_rule_package`` used by the formal answer path. It deliberately uses
estimated tokens unless a project tokenizer is introduced later.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PASS_THRESHOLD_PERCENT = 98.06
FORMAL_BASIS = "signed_active_four_store_rules_only"


def _stable_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def estimate_tokens(text: str) -> int:
    """Estimate mixed Chinese/English tokens with a conservative chars/2 rule."""

    if not text:
        return 0
    return max(1, round(len(text) / 2))


def _formal_source_summary(current_rule_package: dict[str, Any]) -> dict[str, Any]:
    matched_rules = list(current_rule_package.get("matched_rules") or [])
    citable_data = list(current_rule_package.get("citable_data") or [])
    user_preferences = list(current_rule_package.get("user_preferences") or [])
    vector_candidates = list(current_rule_package.get("retrieval_candidates") or [])
    non_citable = list(current_rule_package.get("non_citable_data") or [])
    return {
        "matched_rules": len(matched_rules),
        "citable_data": len(citable_data),
        "user_preferences": len(user_preferences),
        "vector_candidates": len(vector_candidates),
        "non_citable_data": len(non_citable),
        "vector_recall_only": True,
    }


def measure_context_compression(full_context: Any, current_rule_package: dict[str, Any]) -> dict[str, Any]:
    full_context_text = _stable_text(full_context)
    package_text = _stable_text(current_rule_package)
    full_tokens = estimate_tokens(full_context_text)
    package_tokens = estimate_tokens(package_text)
    if full_tokens <= 0:
        ratio = 0.0
        percent = 0.0
    else:
        ratio = package_tokens / full_tokens
        percent = max(0.0, (1.0 - ratio) * 100)
    status = "PASS_98_06" if percent >= PASS_THRESHOLD_PERCENT else "NEEDS_OPTIMIZATION"
    return {
        "full_context_chars": len(full_context_text),
        "full_context_tokens_est": full_tokens,
        "current_rule_package_chars": len(package_text),
        "current_rule_package_tokens_est": package_tokens,
        "compression_ratio": round(ratio, 6),
        "compression_percent": round(percent, 2),
        "chat_context_used": bool(current_rule_package.get("chat_context_used", False)),
        "formal_basis": FORMAL_BASIS,
        "threshold_percent": PASS_THRESHOLD_PERCENT,
        "status": status,
        "formal_source_summary": _formal_source_summary(current_rule_package),
        "excluded_context": [
            "raw_chat_history",
            "unreviewed_drafts",
            "unsigned_rules",
            "archived_or_superseded_rules",
            "vector_records_as_formal_basis",
            "full_memory_dump",
        ],
        "retained_context": [
            "signed_active_logic_rules",
            "reviewed_active_corpus_items",
            "owner_signed_memory_preferences",
            "vector_retrieval_candidates_recall_only",
            "rule_boundaries_and_post_check_policy",
        ],
    }


def render_token_cost_audit_report(
    *,
    audit: dict[str, Any],
    test_input: str,
    followup_input: str,
    used_rules: list[dict[str, Any]] | None = None,
) -> str:
    used_rules = used_rules or []
    rule_lines = "\n".join(
        f"- {rule.get('rule_name') or rule.get('rule_id') or 'local rule'}: {rule.get('activation_status') or rule.get('status') or 'active'}"
        for rule in used_rules
    ) or "- No rule metadata provided."
    excluded = "\n".join(f"- {item}" for item in audit.get("excluded_context", []))
    retained = "\n".join(f"- {item}" for item in audit.get("retained_context", []))
    source_summary = audit.get("formal_source_summary") or {}
    return f"""# Token / Cost Audit Report

## Test Input
- Rule creation: {test_input}
- Follow-up: {followup_input}

## Used Rules
{rule_lines}

## Token Estimate
- Full Context: {audit.get("full_context_tokens_est")} tokens ({audit.get("full_context_chars")} chars)
- Rule Package: {audit.get("current_rule_package_tokens_est")} tokens ({audit.get("current_rule_package_chars")} chars)
- Compression Ratio: {audit.get("compression_ratio")}
- Compression: {audit.get("compression_percent")}%
- Threshold: {audit.get("threshold_percent")}%
- Status: {audit.get("status")}

## Formal Basis
- Formal basis: {audit.get("formal_basis")}
- Chat context used as formal basis: {"Yes" if audit.get("chat_context_used") else "No"}
- Matched LOGIC rules: {source_summary.get("matched_rules", 0)}
- Citable CORPUS data: {source_summary.get("citable_data", 0)}
- MEMORY preferences: {source_summary.get("user_preferences", 0)}
- VECTOR candidates: {source_summary.get("vector_candidates", 0)}
- VECTOR recall only: {"Yes" if source_summary.get("vector_recall_only") else "No"}

## Excluded
{excluded}

## Retained
{retained}

## Why Four Stores Replace Long Context
Signed Active LOGIC, reviewed CORPUS, and owner-signed MEMORY records carry formal authority. VECTOR is retained only as recall metadata, so the model receives a minimal rule package instead of a full chat transcript or full memory dump.

## Context Pollution
{"No unnecessary chat context was used as formal basis." if not audit.get("chat_context_used") else "Chat context pollution detected; optimize routing before production."}
"""


def write_token_cost_audit_report(
    path: str | Path,
    *,
    audit: dict[str, Any],
    test_input: str,
    followup_input: str,
    used_rules: list[dict[str, Any]] | None = None,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_token_cost_audit_report(
            audit=audit,
            test_input=test_input,
            followup_input=followup_input,
            used_rules=used_rules,
        ),
        encoding="utf-8",
    )
    return output_path
