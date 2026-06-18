"""Pure P8 storage request helpers."""

from core.storage.targets import validate_storage_targets

DEFAULT_CANDIDATE_TARGETS = ["vector_db", "corpus", "logic"]


def assert_review_passed_for_storage(review_result):
    """Raise ValueError unless review_result is eligible for storage planning."""
    if review_result.get("status") != "review_passed":
        raise ValueError("review_result.status must be review_passed")
    if review_result.get("review_passed") is not True:
        raise ValueError("review_result.review_passed must be true")
    if review_result.get("storage_confirmed") is not False:
        raise ValueError("review_result.storage_confirmed must be false")
    return True


def build_storage_request(task, review_result, candidate_targets=None):
    """Build a storage request asking the user to choose storage targets."""
    assert_review_passed_for_storage(review_result)
    targets = list(DEFAULT_CANDIDATE_TARGETS if candidate_targets is None else candidate_targets)
    validate_storage_targets(targets)
    return {
        "task_id": task.get("task_id"),
        "trace_id": task.get("trace_id"),
        "ledger_id": task.get("ledger_id"),
        "review_status": "review_passed",
        "review_passed": True,
        "storage_confirmed": False,
        "candidate_targets": targets,
        "selected_targets": [],
        "blocked_targets": [],
        "storage_signature": None,
        "storage_notes": "",
        "next_required_action": "user_confirm_storage_targets",
    }
