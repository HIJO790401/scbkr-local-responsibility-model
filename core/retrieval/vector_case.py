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
        "task_type": task.get("task_type", ""),
        "task_summary": task.get("task_name") or task.get("raw_input", ""),
        "scbkr_summary": {
            "S": _dimension_summary(scbkr, "S"),
            "C": _dimension_summary(scbkr, "C"),
            "B": _dimension_summary(scbkr, "B"),
            "K": _dimension_summary(scbkr, "K"),
            "R": _dimension_summary(scbkr, "R"),
        },
        "review_passed": True,
        "storage_confirmed": True,
        "storage_plan_status": "storage_confirmed_plan",
        "source": "storage_commit_plan",
        "similarity_metadata": {
            "created_from": "storage_commit_plan",
            "route_hint": "none",
            "tags": [],
        },
        "embedding_status": "not_created",
        "physical_write_performed": False,
    }


def validate_vector_case(case):
    """Validate the basic vector case shape used by P9 pure retrieval routes."""
    required_fields = (
        "case_id",
        "task_id",
        "task_type",
        "task_summary",
        "scbkr_summary",
        "review_passed",
        "storage_confirmed",
        "storage_plan_status",
        "source",
        "similarity_metadata",
        "embedding_status",
        "physical_write_performed",
    )
    missing_fields = [field for field in required_fields if field not in case]
    if missing_fields:
        raise ValueError(f"vector case missing required fields: {', '.join(missing_fields)}")
    for dimension in ("S", "C", "B", "K", "R"):
        if dimension not in case["scbkr_summary"]:
            raise ValueError(f"vector case missing scbkr_summary.{dimension}")
    if case["embedding_status"] not in VALID_EMBEDDING_STATUSES:
        raise ValueError("embedding_status is invalid")
    return True


def assert_case_eligible_for_retrieval(case):
    """Reject cases that were not user-confirmed storage-plan cases."""
    validate_vector_case(case)
    if case.get("review_passed") is not True:
        raise ValueError("case.review_passed must be true")
    if case.get("storage_confirmed") is not True:
        raise ValueError("case.storage_confirmed must be true")
    if case.get("storage_plan_status") != "storage_confirmed_plan":
        raise ValueError("case.storage_plan_status must be storage_confirmed_plan")
    if case.get("source") != "storage_commit_plan":
        raise ValueError("case.source must be storage_commit_plan")
    if case.get("physical_write_performed") is not False:
        raise ValueError("case.physical_write_performed must be false in P9")
    for field in BLOCKED_CASE_FIELDS:
        if field in case:
            raise ValueError(f"{field} cannot be used for retrieval")
    return True
