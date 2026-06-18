"""Pure P7 review result helpers.

These helpers only build dictionaries. They do not write files, ledger events,
databases, storage, memory rules, or call APIs/models.
"""


def _task_refs(task):
    return {
        "task_id": task.get("task_id"),
        "trace_id": task.get("trace_id"),
        "ledger_id": task.get("ledger_id"),
    }


def build_review_passed_result(task, generation_result, review_message, reviewer_signature=None):
    """Build a user review pass result without storage confirmation."""
    return {
        **_task_refs(task),
        "status": "review_passed",
        "review_decision": "pass",
        "review_passed": True,
        "storage_confirmed": False,
        "review_message": review_message,
        "reviewer_signature": reviewer_signature,
        "next_required_action": "ask_user_storage_request",
    }


def build_failure_report_draft(task, generation_result, review_message):
    """Build a draft-only failure report for later user decision."""
    content = generation_result.get("content", "")
    if not isinstance(content, str):
        content = str(content)
    return {
        "failure_summary": "使用者未通過本次模型輸出，需後續判定是否重試、回退或另行處理。",
        "generation_result_status": generation_result.get("status"),
        "failed_content_excerpt": content[:500],
        "review_message": review_message,
        "rule_candidate_status": "draft_only",
        "requires_user_signature": True,
    }


def build_review_failed_result(task, generation_result, review_message, reviewer_signature=None):
    """Build a user review fail result without creating any memory rule."""
    return {
        **_task_refs(task),
        "status": "review_failed",
        "review_decision": "fail",
        "review_passed": False,
        "storage_confirmed": False,
        "review_message": review_message,
        "reviewer_signature": reviewer_signature,
        "failure_report_draft": build_failure_report_draft(task, generation_result, review_message),
        "memory_rule_status": "not_created",
        "next_required_action": "user_decide_retry_rollback_or_later_memory_rule",
    }


def build_rollback_requested_result(
    task,
    generation_result,
    rollback_layer,
    review_message,
    reviewer_signature=None,
):
    """Build a rollback request result without modifying SCBKR or regenerating."""
    if rollback_layer not in ("S", "C", "B", "K", "R"):
        raise ValueError("rollback_layer must be one of: S, C, B, K, R")
    return {
        **_task_refs(task),
        "status": "rollback_requested",
        "review_decision": "rollback",
        "rollback_layer": rollback_layer,
        "review_passed": False,
        "storage_confirmed": False,
        "review_message": review_message,
        "reviewer_signature": reviewer_signature,
        "next_required_action": "revise_scbkr_layer_and_reconfirm",
    }
