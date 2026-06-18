"""Pure builders for P11 review-failed memory rule confirmed plans."""

from core.review_rules.rule_validation import validate_reviewer_signature


def confirm_memory_rule_plan(memory_rule_draft, reviewer_signature):
    """Confirm a memory rule plan without writing memory, data, ledger, or DBs."""
    if memory_rule_draft.get("memory_rule_status") != "draft":
        raise ValueError("memory_rule_draft.memory_rule_status must be draft")
    if memory_rule_draft.get("requires_user_signature") is not True:
        raise ValueError("memory_rule_draft.requires_user_signature must be true")
    if memory_rule_draft.get("physical_write_performed") is not False:
        raise ValueError("memory_rule_draft.physical_write_performed must be false")
    validate_reviewer_signature(reviewer_signature)

    return {
        **memory_rule_draft,
        "reviewer_signature": reviewer_signature,
        "memory_rule_status": "confirmed_plan",
        "requires_user_signature": False,
        "physical_write_performed": False,
        "next_required_action": "memory_runtime_pending",
    }
