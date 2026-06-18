"""Pure P8 storage commit plan helpers.

These helpers build storage plan dictionaries only. They never write SQLite,
ChromaDB, data files, ledger JSONL, four-database storage, or memory rules.
"""

from core.storage.storage_request import assert_review_passed_for_storage
from core.storage.targets import validate_storage_targets

FAILURE_BLOCK_FIELDS = (
    "failure_report_draft",
    "memory_rule_status",
    "memory_rule_confirmed",
    "memory_rule_stored",
    "rule_candidate_status",
)


def assert_no_failed_content_for_storage(review_result):
    """Reject failed content or memory-rule drafts from storage planning."""
    if review_result.get("status") == "review_failed":
        raise ValueError("review_failed content cannot be stored in P8")
    for field in FAILURE_BLOCK_FIELDS:
        if field in review_result:
            raise ValueError(f"{field} cannot be stored in P8")
    return True


def validate_memory_signature(selected_targets, storage_signature):
    """Require a user signature when memory target is selected."""
    if "memory" in selected_targets and not storage_signature:
        raise ValueError("memory storage target requires storage_signature")
    return True


def build_storage_items(task, review_result, selected_targets, storage_signature=None):
    """Build target-specific storage item drafts without physical writes."""
    validate_storage_targets(selected_targets)
    validate_memory_signature(selected_targets, storage_signature)
    items = []
    for target in selected_targets:
        if target == "vector_db":
            items.append(
                {
                    "target": "vector_db",
                    "item_type": "confirmed_case_summary",
                    "task_id": task.get("task_id"),
                    "task_type": task.get("task_type"),
                    "review_passed": True,
                    "scbkr_summary_placeholder": "待 P9 或後續 storage runtime 建立摘要與 embedding。",
                    "embedding_status": "not_created",
                    "physical_write_performed": False,
                }
            )
        elif target == "corpus":
            items.append(
                {
                    "target": "corpus",
                    "item_type": "source_material_placeholder",
                    "physical_write_performed": False,
                }
            )
        elif target == "logic":
            items.append(
                {
                    "target": "logic",
                    "item_type": "reusable_logic_placeholder",
                    "physical_write_performed": False,
                }
            )
        elif target == "memory":
            items.append(
                {
                    "target": "memory",
                    "item_type": "user_confirmed_memory_candidate",
                    "requires_user_signature": True,
                    "storage_signature": storage_signature,
                    "physical_write_performed": False,
                }
            )
    return items


def build_storage_commit_plan(
    task,
    review_result,
    selected_targets,
    storage_signature=None,
    storage_notes="",
):
    """Build a user-confirmed storage plan without physical storage writes."""
    assert_review_passed_for_storage(review_result)
    assert_no_failed_content_for_storage(review_result)
    validate_storage_targets(selected_targets)
    validate_memory_signature(selected_targets, storage_signature)
    storage_items = build_storage_items(
        task,
        review_result,
        selected_targets,
        storage_signature=storage_signature,
    )
    return {
        "task_id": task.get("task_id"),
        "trace_id": task.get("trace_id"),
        "ledger_id": task.get("ledger_id"),
        "storage_plan_status": "storage_confirmed_plan",
        "storage_confirmed": True,
        "selected_targets": list(selected_targets),
        "storage_items": storage_items,
        "storage_signature": storage_signature,
        "storage_notes": storage_notes,
        "physical_write_performed": False,
        "next_required_action": "storage_runtime_pending",
    }
