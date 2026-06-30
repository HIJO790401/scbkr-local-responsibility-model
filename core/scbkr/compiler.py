"""Strict compiler contract for model-authored task understanding drafts."""
from __future__ import annotations

import json
from typing import Any

from core.scbkr.draft_grammar import normalize_task_understanding

TASK_UNDERSTANDING_CONTRACT_VERSION = "scbkr.task-understanding.v2"
STRING_FIELDS = {
    "task_domain",
    "task_subject",
    "user_original_judgement",
    "user_goal",
    "core_claim",
}
LIST_FIELDS = {
    "output_format",
    "causal_chain",
    "boundary_rules",
    "forbidden_dilutions",
    "basis_sources",
    "evidence_relation_notes",
    "acceptance_criteria",
    "storage_candidates",
}
FIXED_FIELDS = {"owner_signature_required", "model_role"}
REQUIRED_FIELDS = STRING_FIELDS | LIST_FIELDS | FIXED_FIELDS


def task_understanding_json_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {
        key: {"type": "string"} for key in sorted(STRING_FIELDS)
    }
    properties.update({key: {"type": "array", "items": {"type": "string"}} for key in sorted(LIST_FIELDS)})
    properties.update(
        {
            "owner_signature_required": {"const": True},
            "model_role": {"const": "describe_compile_only"},
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "SCBKR Task Understanding Draft",
        "type": "object",
        "additionalProperties": False,
        "required": sorted(REQUIRED_FIELDS),
        "properties": properties,
    }


def task_understanding_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "scbkr_task_understanding_v2",
            "strict": True,
            "schema": task_understanding_json_schema(),
        },
    }


def validate_task_understanding_strict(candidate: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(candidate, dict):
        raise ValueError("task understanding must be an object")
    unknown = sorted(set(candidate) - REQUIRED_FIELDS)
    missing = sorted(REQUIRED_FIELDS - set(candidate))
    if unknown:
        errors.append("unknown fields: " + ", ".join(unknown))
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
    for key in STRING_FIELDS:
        if key in candidate and not isinstance(candidate[key], str):
            errors.append(f"{key} must be a string")
    for key in LIST_FIELDS:
        if key in candidate and (
            not isinstance(candidate[key], list)
            or any(not isinstance(item, str) for item in candidate[key])
        ):
            errors.append(f"{key} must be an array of strings")
    if candidate.get("owner_signature_required") is not True:
        errors.append("owner_signature_required must be true")
    if candidate.get("model_role") != "describe_compile_only":
        errors.append("model_role must be describe_compile_only")
    if not str(candidate.get("task_subject") or candidate.get("core_claim") or candidate.get("user_goal") or "").strip():
        errors.append("task_subject, core_claim, or user_goal must contain the task meaning")
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_task_understanding(candidate)


def build_repair_messages(
    original_messages: list[dict[str, str]],
    invalid_output: str,
    error: Exception,
) -> list[dict[str, str]]:
    return [
        *original_messages,
        {"role": "assistant", "content": invalid_output[:12000]},
        {
            "role": "user",
            "content": (
                "Your JSON failed the SCBKR compiler. Repair it once. "
                f"Compiler errors: {error}. Return exactly one JSON object matching this schema: "
                + json.dumps(task_understanding_json_schema(), ensure_ascii=False, separators=(",", ":"))
            ),
        },
    ]


def build_compiler_report(
    *,
    status: str,
    attempts: int,
    repairs: int,
    errors: list[str] | None = None,
    model_used: bool = False,
) -> dict[str, Any]:
    return {
        "contract_version": TASK_UNDERSTANDING_CONTRACT_VERSION,
        "status": status,
        "attempts": attempts,
        "repairs": repairs,
        "errors": list(errors or []),
        "model_used": model_used,
        "field_provenance": {
            "raw_input": "owner_input",
            "task_understanding": "model_inference" if model_used else "base_logic",
            "citations": "signed_evidence_only",
            "final_confirmation": "owner_signature_required",
        },
    }
