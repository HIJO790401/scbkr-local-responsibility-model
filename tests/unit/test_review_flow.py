import pytest

from core.workflow.review_flow import (
    apply_review_decision,
    assert_generation_result_waiting_review,
    validate_review_decision,
)
from core.workflow.review_result import build_failure_report_draft


def make_task(**overrides):
    task = {
        "task_id": "task-1",
        "trace_id": "trace-1",
        "ledger_id": "ledger-1",
    }
    task.update(overrides)
    return task


def make_generation_result(**overrides):
    generation_result = {
        "task_id": "task-1",
        "trace_id": "trace-1",
        "ledger_id": "ledger-1",
        "status": "waiting_review",
        "content": "待驗收內容",
        "review_passed": False,
        "storage_confirmed": False,
        "source": "caller_supplied_model_response",
        "next_required_action": "user_review_required",
    }
    generation_result.update(overrides)
    return generation_result


def test_generation_result_status_must_be_waiting_review():
    with pytest.raises(ValueError):
        assert_generation_result_waiting_review(make_generation_result(status="review_passed"))


def test_generation_result_review_passed_must_be_false():
    with pytest.raises(ValueError):
        assert_generation_result_waiting_review(make_generation_result(review_passed=True))


def test_generation_result_storage_confirmed_must_be_false():
    with pytest.raises(ValueError):
        assert_generation_result_waiting_review(make_generation_result(storage_confirmed=True))


def test_invalid_review_decision_raises_value_error():
    with pytest.raises(ValueError):
        validate_review_decision("approve")

    with pytest.raises(ValueError):
        apply_review_decision(make_task(), make_generation_result(), "approve", "訊息")


def test_rollback_decision_requires_valid_rollback_layer():
    with pytest.raises(ValueError):
        apply_review_decision(make_task(), make_generation_result(), "rollback", "需要回退")

    with pytest.raises(ValueError):
        apply_review_decision(
            make_task(),
            make_generation_result(),
            "rollback",
            "需要回退",
            rollback_layer="SYSTEM",
        )


def test_pass_result_only_marks_review_passed_and_keeps_storage_locked():
    result = apply_review_decision(
        make_task(),
        make_generation_result(),
        "pass",
        "使用者通過驗收",
        reviewer_signature="user-signature",
    )

    assert result["status"] == "review_passed"
    assert result["review_decision"] == "pass"
    assert result["review_passed"] is True
    assert result["storage_confirmed"] is False
    assert result["next_required_action"] == "ask_user_storage_request"
    assert "memory_rule_stored" not in result
    assert "completed" not in result


def test_fail_result_only_creates_failure_report_draft():
    result = apply_review_decision(
        make_task(),
        make_generation_result(content="失敗內容"),
        "fail",
        "結果不符合需求",
    )

    assert result["status"] == "review_failed"
    assert result["review_decision"] == "fail"
    assert result["review_passed"] is False
    assert result["storage_confirmed"] is False
    assert result["memory_rule_status"] == "not_created"
    assert "failure_report_draft" in result
    assert result["failure_report_draft"]["rule_candidate_status"] == "draft_only"
    assert result["failure_report_draft"]["requires_user_signature"] is True
    assert "memory_rule_confirmed" not in result
    assert "memory_rule_stored" not in result


def test_failure_report_draft_is_not_a_memory_rule():
    draft = build_failure_report_draft(make_task(), make_generation_result(), "失敗原因")

    assert draft["rule_candidate_status"] == "draft_only"
    assert draft["requires_user_signature"] is True
    assert "memory_rule_confirmed" not in draft
    assert "memory_rule_stored" not in draft


def test_rollback_result_only_marks_requested_layer_without_regenerate():
    for layer in ("S", "C", "B", "K", "R"):
        result = apply_review_decision(
            make_task(),
            make_generation_result(),
            "rollback",
            "需要回退修改",
            rollback_layer=layer,
        )

        assert result["status"] == "rollback_requested"
        assert result["review_decision"] == "rollback"
        assert result["rollback_layer"] == layer
        assert result["review_passed"] is False
        assert result["storage_confirmed"] is False
        assert result["next_required_action"] == "revise_scbkr_layer_and_reconfirm"
        assert "regenerate" not in result
        assert "confirmed" not in result
