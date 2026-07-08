"""Validity/failure gate wrapper for direct drafts."""

from __future__ import annotations

from typing import Any

from .direct_draft_validator import validate_direct_draft


def validate_validity_failure(draft: dict[str, Any], kernel_pack: dict[str, Any] | None = None) -> dict[str, Any]:
    result = validate_direct_draft(draft, kernel_pack)
    hard_reasons = {
        "template_empty",
        "missing_specific_subject",
        "missing_causality",
        "missing_validity_condition",
        "missing_failure_condition",
        "missing_replay",
        "missing_repair_path",
        "missing_kernel_attribution",
        "model_overreach",
    }
    return {
        **result,
        "validator": "validity_failure_validator",
        "hard_fail_reasons": [reason for reason in result["fail_reasons"] if reason in hard_reasons],
    }

