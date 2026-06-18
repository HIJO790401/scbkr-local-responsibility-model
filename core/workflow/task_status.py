"""SCBKR P1 task status constants and pure validation helpers.

This module has no IO side effects. It does not read files, write files,
connect to databases, call models, or call external APIs.
"""

TASK_STATUSES = [
    "draft",
    "waiting_scbkr",
    "waiting_user_confirm",
    "confirmed",
    "generating",
    "waiting_review",
    "review_passed",
    "review_failed",
    "rollback_requested",
    "waiting_storage_request",
    "waiting_storage_confirm",
    "memory_rule_waiting_confirm",
    "memory_rule_stored",
    "completed",
    "paused",
    "error",
]

ALLOWED_TRANSITIONS = {
    "draft": ["waiting_scbkr", "paused", "error"],
    "waiting_scbkr": ["waiting_user_confirm", "paused", "error"],
    "waiting_user_confirm": ["confirmed", "paused", "error"],
    "confirmed": ["generating", "waiting_user_confirm", "paused", "error"],
    "generating": ["waiting_review", "error"],
    "waiting_review": ["review_passed", "review_failed", "rollback_requested", "paused", "error"],
    "review_passed": ["waiting_storage_request", "completed", "paused", "error"],
    "review_failed": ["rollback_requested", "memory_rule_waiting_confirm", "completed", "paused", "error"],
    "rollback_requested": ["waiting_user_confirm", "paused", "error"],
    "waiting_storage_request": ["waiting_storage_confirm", "completed", "paused", "error"],
    "waiting_storage_confirm": ["completed", "paused", "error"],
    "memory_rule_waiting_confirm": ["memory_rule_stored", "completed", "paused", "error"],
    "memory_rule_stored": ["completed", "paused", "error"],
    "completed": [],
    "paused": ["waiting_scbkr", "waiting_user_confirm", "confirmed", "waiting_review", "waiting_storage_request", "waiting_storage_confirm", "error"],
    "error": ["rollback_requested", "paused"],
}


def is_valid_status(status: str) -> bool:
    """Return whether status is one of the SCBKR task status values."""
    return status in TASK_STATUSES


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """Return whether a transition is allowed by the P1 state map."""
    return to_status in ALLOWED_TRANSITIONS.get(from_status, [])
