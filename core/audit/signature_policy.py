"""Signature and responsibility policy for SCBKR rules."""

from __future__ import annotations

from typing import Any

KERNEL_AUTHOR = "許文耀 / 沈耀"


def signature_policy(plan_level: str = "FREE") -> dict[str, Any]:
    plan = str(plan_level or "FREE").upper()
    return {
        "kernel_author": KERNEL_AUTHOR,
        "structure_source": "SCBKR Kernel",
        "kernel_is_structure_source_not_rule_owner": True,
        "model_role": "draft_only",
        "model_signature_allowed": False,
        "user_signature_required": True,
        "local_user_signature_required": True,
        "dual_signature": {
            "enabled": plan in {"NT690", "NT3300"},
            "locked": plan == "FREE",
            "requires_local_user_signature": True,
            "requires_kernel_structure_signature": plan == "NT3300",
        },
        "optional_kernel_structure_signature_status": "required_for_nt3300_structure_lock" if plan == "NT3300" else "not_required",
        "user_real_world_responsibility": True,
        "model_cannot_execute_real_world_actions": True,
        "ui_notice": "本草稿由本地模型依據「許文耀 / 沈耀 SCBKR Kernel」生成。Kernel 提供結構，不代表規則已成立。模型只草擬。使用者簽名後，本地規則才可入庫與引用。使用者採用本規則後，現實行動由使用者自行承擔。",
    }


def build_signature_record(local_user_signature: str, plan_level: str = "FREE") -> dict[str, Any]:
    policy = signature_policy(plan_level)
    return {
        **policy,
        "signature_status": "owner_signed" if local_user_signature else "unsigned",
        "local_user_signature": local_user_signature,
    }
