"""Pure validation helpers for P11 review-failed memory rule planning."""


def assert_review_failed_for_memory_rule(review_result):
    """Validate that a review result is eligible to source a memory rule draft."""
    if review_result.get("status") != "review_failed":
        raise ValueError("review_result.status must be review_failed")
    if review_result.get("review_passed") is not False:
        raise ValueError("review_result.review_passed must be false")
    if review_result.get("storage_confirmed") is not False:
        raise ValueError("review_result.storage_confirmed must be false")
    if "failure_report_draft" not in review_result:
        raise ValueError("review_result.failure_report_draft is required")
    if "memory_rule_confirmed" in review_result:
        raise ValueError("review_result must not already contain memory_rule_confirmed")
    if "memory_rule_stored" in review_result:
        raise ValueError("review_result must not already contain memory_rule_stored")
    if "completed" in review_result:
        raise ValueError("review_result must not already contain completed")
    return True


def validate_user_failure_judgement(user_failure_judgement):
    """Validate the user-provided judgement that makes the failure reason usable."""
    if not isinstance(user_failure_judgement, str):
        raise ValueError("user_failure_judgement must be a string")
    if not user_failure_judgement.strip():
        raise ValueError("user_failure_judgement must not be blank")
    return True


def validate_rule_statement(rule_statement):
    """Validate the user-provided rule statement."""
    if not isinstance(rule_statement, str):
        raise ValueError("rule_statement must be a string")
    if not rule_statement.strip():
        raise ValueError("rule_statement must not be blank")
    return True


def validate_rule_scope(
    applies_to_task_types,
    trigger_conditions,
    forbidden_patterns,
    required_behavior,
):
    """Validate list-based rule scope fields without interpreting the rule."""
    if not isinstance(applies_to_task_types, list):
        raise ValueError("applies_to_task_types must be a list")
    if not isinstance(trigger_conditions, list):
        raise ValueError("trigger_conditions must be a list")
    if not isinstance(forbidden_patterns, list):
        raise ValueError("forbidden_patterns must be a list")
    if not isinstance(required_behavior, list):
        raise ValueError("required_behavior must be a list")
    if not (trigger_conditions or forbidden_patterns or required_behavior):
        raise ValueError(
            "at least one of trigger_conditions, forbidden_patterns, or required_behavior is required"
        )
    return True


def validate_reviewer_signature(reviewer_signature):
    """Validate the explicit reviewer signature required for a confirmed plan."""
    if not isinstance(reviewer_signature, str):
        raise ValueError("reviewer_signature must be a string")
    if not reviewer_signature.strip():
        raise ValueError("reviewer_signature must not be blank")
    return True
