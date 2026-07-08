"""Plan depth compiler for SCBKR drafts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PLAN_LEVELS = {"FREE", "NT690", "NT3300"}


def _plan(plan_level: str | None) -> str:
    value = str(plan_level or "FREE").upper()
    return value if value in PLAN_LEVELS else "FREE"


def apply_plan_depth(draft: dict[str, Any], plan_level: str = "FREE") -> dict[str, Any]:
    plan = _plan(plan_level)
    result = deepcopy(draft)
    result.setdefault("meta", {})["plan_level"] = plan
    result.setdefault("plan_depth", {"plan_level": plan, "adds": []})
    if plan == "FREE":
        result["plan_depth"]["adds"] = ["basic_five_dimensions", "user_self_signature", "local_storage", "local_citation", "not_full_closure"]
        return result
    result["plan_depth"]["adds"] = [
        "responsibility_boundary",
        "missing_data_questions",
        "stop_conditions",
        "insufficient_basis",
        "model_overreach_limits",
        "draft_only_conditions",
        "user_real_world_responsibility",
    ]
    result.setdefault("B", {}).setdefault("stop_conditions", []).extend(
        ["資料不足時不得正式引用。", "模型不可越權執行現實動作。", "只能草稿時必須清楚標示。"]
    )
    result.setdefault("K", {})["insufficient_basis_policy"] = "缺正式依據時標示 OWNER_REVIEW / NEED_DEFINITION。"
    result.setdefault("R", {})["adoption_responsibility_notice"] = "使用者採用後現實行動由使用者自行承擔。"
    result["R"]["clarifying_questions"] = [
        "這條規則何時必須停止？",
        "哪些資料不足時不能引用？",
        "哪些現實行動需要使用者再次確認？",
    ]
    if plan == "NT690":
        return result
    result["plan_depth"]["adds"].extend(
        [
            "validity_conditions",
            "failure_conditions",
            "risk_levels",
            "repair_path",
            "replay_requirements",
            "version_conditions",
            "dual_signature_conditions",
            "rulepack",
            "long_term_workflow_conditions",
            "kernel_author_structure_signature",
            "rulebook_audit_record",
        ]
    )
    result["R"]["risk_levels"] = {
        "low": "只產生草稿。",
        "medium": "引用正式本地規則但仍需驗收。",
        "high": "涉及現實發布、寄送、付款、刪除或外部工具。",
    }
    result["R"]["version_conditions"] = ["新版不得覆寫舊版，必須保留 parent/superseded 關係。"]
    result["R"]["dual_signature_conditions"] = ["kernel_author = 許文耀 / 沈耀", "structure_source = SCBKR Kernel", "local_user_signature required"]
    result["R"]["long_term_workflow_conditions"] = ["只有 signed / reviewed / active 規則可被長期 workflow 正式引用。"]
    result["rulepack"] = {
        "enabled": True,
        "citation_policy": "signed_reviewed_active_only",
        "vector_policy": "recall_only",
    }
    result["rulebook_audit_record"] = {
        "kernel_author_structure_signature_status": "optional_pending",
        "local_user_signature_status": "required_pending",
    }
    return result

