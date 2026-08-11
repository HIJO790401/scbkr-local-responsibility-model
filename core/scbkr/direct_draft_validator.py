"""Hard validator for direct SCBKR drafts."""

from __future__ import annotations

from typing import Any

from core.kernel.scbkr_kernel_compiler import KERNEL_NAME

GENERIC_EMPTY_VALUES = {
    "處理使用者需求",
    "依規則判斷",
    "不得違規",
    "依據資料",
    "使用者負責",
}


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_text(v) for v in value)
    return str(value or "")


def _live_dimension_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        return _text(payload).strip()
    for key in ("owner_draft_content", "model_draft_content", "core_logic", "task_subject", "source_credibility", "real_world_responsibility"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return _text(payload).strip()


def validate_direct_draft(draft: dict[str, Any], kernel_pack: dict[str, Any] | None = None) -> dict[str, Any]:
    reasons: list[str] = []
    live_dimension_text = {
        dim: _live_dimension_content(draft.get(dim))
        for dim in ("S", "C", "B", "K", "R")
    }
    for dim in ("S", "C", "B", "K", "R"):
        if not isinstance(draft.get(dim), dict) or not _text(draft.get(dim)).strip():
            reasons.append("template_empty")
            break
    # Historical model attempts remain in the audit payload on purpose. Only
    # the current editable five-dimensional content may determine whether the
    # live draft is still a placeholder.
    if any(text in GENERIC_EMPTY_VALUES for text in live_dimension_text.values()):
        reasons.append("template_empty")
    if len(_text(draft.get("S", {}))) < 24:
        reasons.append("missing_specific_subject")
    if len(_text(draft.get("C", {}))) < 40:
        reasons.append("missing_causality")
    if "VECTOR" not in _text(draft.get("K", {})).upper() or "recall only" not in _text(draft.get("K", {})).lower():
        reasons.append("missing_k_policy")
    r_text = _text(draft.get("R", {}))
    if "formation" not in r_text.lower() and "成立" not in r_text:
        reasons.append("missing_validity_condition")
    if "failure" not in r_text.lower() and "失效" not in r_text:
        reasons.append("missing_failure_condition")
    if "replay" not in r_text.lower() and "回放" not in r_text:
        reasons.append("missing_replay")
    if "repair" not in r_text.lower() and "修復" not in r_text:
        reasons.append("missing_repair_path")
    meta_text = _text(draft.get("meta", {})) + " " + r_text
    if KERNEL_NAME not in meta_text:
        reasons.append("missing_kernel_attribution")
    if "使用者簽名後才成立" not in r_text and draft.get("meta", {}).get("requires_user_signature") is not True and "requires_user_signature" not in meta_text:
        reasons.append("missing_user_signature_condition")
    responsibility_signals = ("自行承擔", "使用者負責", "使用者承擔", "owner is responsible", "user is responsible", "user accepts responsibility", "accountable")
    if not any(signal in r_text.lower() for signal in responsibility_signals) and "real_world_outcome_owner" not in meta_text:
        reasons.append("missing_user_responsibility")
    if draft.get("signature_status") in {"confirmed", "owner_signed"}:
        reasons.append("model_overreach")
    if draft.get("confirmed") is True or draft.get("storage_confirmed") is True:
        reasons.append("model_overreach")
    if str(draft.get("meta", {}).get("model_role") or "").lower() not in {"draft_only", "assistant_draft_only"}:
        reasons.append("model_overreach")
    return {
        "passed": not reasons,
        "fail_reasons": sorted(set(reasons)),
        "repair_instruction": "模型未通過 SCBKR 驗證；請補具體 S/C/B/K/R、成立/失效/回放/修復、Kernel 來源與使用者責任。" if reasons else "",
    }
