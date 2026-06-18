"""Pure P8 storage result helpers."""


def build_storage_rejected_result(task, reason):
    """Build a storage rejected result without physical writes."""
    return {
        "task_id": task.get("task_id"),
        "trace_id": task.get("trace_id"),
        "ledger_id": task.get("ledger_id"),
        "status": "storage_rejected",
        "reason": reason,
        "storage_confirmed": False,
        "physical_write_performed": False,
    }


def build_storage_runtime_pending_result(storage_commit_plan):
    """Build a storage runtime pending result without physical writes."""
    return {
        "task_id": storage_commit_plan.get("task_id"),
        "trace_id": storage_commit_plan.get("trace_id"),
        "ledger_id": storage_commit_plan.get("ledger_id"),
        "status": "storage_runtime_pending",
        "storage_confirmed": storage_commit_plan["storage_confirmed"],
        "physical_write_performed": False,
        "next_required_action": "implement_storage_runtime_later",
    }
