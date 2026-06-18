"""Pure builders for P11 review-failed memory rule drafts."""

from core.review_rules.rule_validation import (
    assert_review_failed_for_memory_rule,
    validate_rule_scope,
    validate_rule_statement,
    validate_user_failure_judgement,
)


def _default_rule_id(task, review_result):
    task_id = task.get("task_id") or review_result.get("task_id") or "unknown_task"
    trace_id = task.get("trace_id") or review_result.get("trace_id") or "unknown_trace"
    return f"memory_rule_draft:{task_id}:{trace_id}"


def _reject_failure_report_as_rule(review_result, rule_statement):
    failure_report_draft = review_result.get("failure_report_draft")
    if rule_statement == failure_report_draft:
        raise ValueError("failure_report_draft must not be used as rule_statement")
    if isinstance(failure_report_draft, dict) and rule_statement.strip() in {
        str(failure_report_draft).strip(),
        failure_report_draft.get("failure_summary", "").strip(),
    }:
        raise ValueError("failure_report_draft must not be used as rule_statement")


def build_memory_rule_draft(
    task,
    review_result,
    user_failure_judgement,
    rule_statement,
    applies_to_task_types,
    trigger_conditions,
    forbidden_patterns,
    required_behavior,
    rule_id=None,
):
    """Build a draft-only memory rule plan without writing memory or data."""
    assert_review_failed_for_memory_rule(review_result)
    validate_user_failure_judgement(user_failure_judgement)
    validate_rule_statement(rule_statement)
    validate_rule_scope(
        applies_to_task_types,
        trigger_conditions,
        forbidden_patterns,
        required_behavior,
    )
    _reject_failure_report_as_rule(review_result, rule_statement)

    failure_report_draft = review_result["failure_report_draft"]
    return {
        "rule_id": rule_id or _default_rule_id(task, review_result),
        "source_task_id": task.get("task_id") or review_result.get("task_id"),
        "source_trace_id": task.get("trace_id") or review_result.get("trace_id"),
        "source_ledger_id": task.get("ledger_id") or review_result.get("ledger_id"),
        "source_review_status": "review_failed",
        "failure_summary": failure_report_draft.get("failure_summary", ""),
        "failure_report_draft": dict(failure_report_draft),
        "user_failure_judgement": user_failure_judgement,
        "rule_statement": rule_statement,
        "applies_to_task_types": list(applies_to_task_types),
        "trigger_conditions": list(trigger_conditions),
        "forbidden_patterns": list(forbidden_patterns),
        "required_behavior": list(required_behavior),
        "reviewer_signature": None,
        "memory_rule_status": "draft",
        "requires_user_signature": True,
        "physical_write_performed": False,
        "next_required_action": "user_sign_memory_rule",
    }
