"""Pure P9 vector case helpers for responsibility-chain retrieval routes.

P13-C retrieval cases live in ``case_builder.py``. This module intentionally
keeps the legacy P9 vector-case shape aligned with schemas/vector_case.schema.json.
"""

VALID_EMBEDDING_STATUSES = ("not_created", "created_later")
BLOCKED_CASE_FIELDS = (
    "failure_report_draft",
    "memory_rule_status",
    "memory_rule_confirmed",
    "memory_rule_stored",
    "rule_candidate_status",
)


def _dimension_summary(scbkr, dimension):
    value = scbkr.get(dimension, "")
    if isinstance(value, dict):
        return " ".join(str(item) for item in value.values())
    return str(value)


def build_vector_case_from_storage_plan(task, scbkr, storage_commit_plan, case_id=None):
    """Build a schema-valid P9 vector case without P13-C retrieval fields."""
    return {
        "case_id": case_id,
        "task_id": task.get("task_id"),
        "task_type": task.get("task_type"),
        "task_summary": task.get("task_name") or task.get("raw_input"),
        "raw_input": task.get("raw_input"),
        "scbkr_summary": {k: scbkr.get(k, "") for k in ("S","C","B","K","R")},
        "review_passed": storage_plan.get("review_passed", True),
        "storage_confirmed": storage_plan.get("storage_confirmed", True),
        "storage_plan_status": storage_plan.get("storage_plan_status", "storage_confirmed_plan"),
        "source": storage_plan.get("source", "storage_commit_plan"),
        "embedding_status": storage_plan.get("embedding_status", "not_created"),
        "physical_write_performed": storage_plan.get("physical_write_performed", False),
        "created_at": datetime.now(UTC).isoformat(),
    }

def assert_case_eligible_for_retrieval(case: dict[str, Any]) -> bool:
    if case.get("review_passed") is not True: raise ValueError("review_passed case required")
    if case.get("storage_confirmed") is not True: raise ValueError("storage_confirmed case required")
    if case.get("storage_plan_status") != "storage_confirmed_plan": raise ValueError("confirmed storage plan required")
    if case.get("source") != "storage_commit_plan": raise ValueError("trusted storage source required")
    for key in ("failure_report_draft", "memory_rule_status", "memory_rule_confirmed", "memory_rule_stored", "rule_candidate_status"):
        if key in case: raise ValueError("memory/review-failed cases are not success vector cases")
    return True
