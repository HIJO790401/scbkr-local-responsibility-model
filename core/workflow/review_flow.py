"""Pure P7 review decision flow helpers.

P7 only converts a waiting-review generation result into a user review result.
It never writes ledger events, data, databases, storage, memory rules, calls
APIs/models, modifies SCBKR, or regenerates content.
"""

from core.workflow.review_result import (
    build_review_failed_result,
    build_review_passed_result,
    build_rollback_requested_result,
)

REVIEW_DECISIONS = ("pass", "fail", "rollback")
ROLLBACK_LAYERS = ("S", "C", "B", "K", "R")


def validate_review_decision(review_decision):
    """Validate a P7 review decision."""
    if review_decision not in REVIEW_DECISIONS:
        raise ValueError("review_decision must be one of: pass, fail, rollback")
    return True


def validate_rollback_layer(rollback_layer):
    """Validate a P7 rollback target layer."""
    if rollback_layer not in ROLLBACK_LAYERS:
        raise ValueError("rollback_layer must be one of: S, C, B, K, R")
    return True


def assert_generation_result_waiting_review(generation_result):
    """Raise ValueError unless generation_result is still waiting for user review."""
    if generation_result.get("status") != "waiting_review":
        raise ValueError("generation_result.status must be waiting_review")
    if generation_result.get("review_passed") is not False:
        raise ValueError("generation_result.review_passed must be false")
    if generation_result.get("storage_confirmed") is not False:
        raise ValueError("generation_result.storage_confirmed must be false")
    return True


def apply_review_decision(
    task,
    generation_result,
    review_decision,
    review_message,
    rollback_layer=None,
    reviewer_signature=None,
):
    """Apply a user review decision without side effects."""
    assert_generation_result_waiting_review(generation_result)
    validate_review_decision(review_decision)

    if review_decision == "pass":
        return build_review_passed_result(
            task,
            generation_result,
            review_message,
            reviewer_signature=reviewer_signature,
        )
    if review_decision == "fail":
        return build_review_failed_result(
            task,
            generation_result,
            review_message,
            reviewer_signature=reviewer_signature,
        )

    validate_rollback_layer(rollback_layer)
    return build_rollback_requested_result(
        task,
        generation_result,
        rollback_layer,
        review_message,
        reviewer_signature=reviewer_signature,
    )
