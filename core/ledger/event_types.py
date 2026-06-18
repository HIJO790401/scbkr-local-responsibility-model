"""Pure constants and validation helpers for SCBKR ledger events."""

LEDGER_EVENT_TYPES = (
    "task_created",
    "scbkr_generated",
    "scbkr_modified",
    "user_confirmed",
    "generation_started",
    "generation_finished",
    "review_passed",
    "review_failed",
    "rollback_requested",
    "storage_requested",
    "storage_confirmed",
    "memory_rule_drafted",
    "memory_rule_confirmed",
    "task_completed",
    "task_paused",
    "task_error",
    "system_note",
)

LEDGER_ACTORS = ("user", "system", "model", "tool")

LEDGER_LAYERS = ("S", "C", "B", "K", "R", "SYSTEM")


def is_valid_event_type(value):
    """Return whether value is a supported ledger event type."""
    return value in LEDGER_EVENT_TYPES


def is_valid_actor(value):
    """Return whether value is a supported ledger actor."""
    return value in LEDGER_ACTORS


def is_valid_layer(value):
    """Return whether value is a supported SCBKR ledger layer."""
    return value in LEDGER_LAYERS
