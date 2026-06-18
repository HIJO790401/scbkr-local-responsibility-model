"""Pure P6 generation result helpers.

These helpers only build dictionaries. They do not write files, ledger events,
databases, storage, or call APIs/models.
"""


def build_generation_result(task, scbkr, parsed_content):
    """Build a waiting-review generation result from caller-supplied model content."""
    return {
        "task_id": task.get("task_id"),
        "trace_id": task.get("trace_id"),
        "ledger_id": task.get("ledger_id"),
        "status": "waiting_review",
        "content": parsed_content,
        "review_passed": False,
        "storage_confirmed": False,
        "source": "caller_supplied_model_response",
        "scbkr_confirmation_status": scbkr.get("confirmation_status"),
        "next_required_action": "user_review_required",
    }


def build_generation_error(message, layer="SYSTEM"):
    """Build a generation gate error dictionary without side effects."""
    return {
        "status": "error",
        "message": message,
        "layer": layer,
        "review_passed": False,
        "storage_confirmed": False,
        "next_required_action": "fix_generation_gate_error",
    }
