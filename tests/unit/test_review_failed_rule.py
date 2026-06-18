import json
from pathlib import Path

import pytest

from core.review_rules.rule_confirmation import confirm_memory_rule_plan
from core.review_rules.rule_draft import build_memory_rule_draft
from core.review_rules.rule_validation import (
    assert_review_failed_for_memory_rule,
    validate_reviewer_signature,
    validate_rule_scope,
    validate_rule_statement,
    validate_user_failure_judgement,
)

SCHEMA_PATH = Path("schemas/review_failed_rule.schema.json")


def task():
    return {
        "task_id": "task-1",
        "trace_id": "trace-1",
        "ledger_id": "ledger-1",
        "task_type": "writing",
    }


def review_failed_result(**overrides):
    result = {
        "task_id": "task-1",
        "trace_id": "trace-1",
        "ledger_id": "ledger-1",
        "status": "review_failed",
        "review_passed": False,
        "storage_confirmed": False,
        "failure_report_draft": {
            "failure_summary": "模型輸出未符合使用者驗收標準。",
            "review_message": "缺少明確邊界。",
            "rule_candidate_status": "draft_only",
        },
    }
    result.update(overrides)
    return result


def draft(**overrides):
    value = build_memory_rule_draft(
        task=task(),
        review_result=review_failed_result(),
        user_failure_judgement="使用者確認失敗原因是邊界描述不足。",
        rule_statement="未來同類任務必須明確列出不可執行的外部操作。",
        applies_to_task_types=["writing"],
        trigger_conditions=["任務涉及外部操作邊界"],
        forbidden_patterns=["宣稱已執行未授權工具"],
        required_behavior=["先列出權限與確認狀態"],
        rule_id="rule-1",
    )
    value.update(overrides)
    return value


def test_review_failed_rule_schema_is_valid_json_schema_shape():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["type"] == "object"
    assert schema["properties"]["memory_rule_status"]["enum"] == ["draft", "confirmed_plan"]
    assert "memory_rule_stored" not in json.dumps(schema)
    assert "physical_memory_written" not in json.dumps(schema)
    assert "completed" not in json.dumps(schema)


def test_review_passed_status_is_rejected():
    with pytest.raises(ValueError, match="status must be review_failed"):
        assert_review_failed_for_memory_rule(review_failed_result(status="review_passed"))


def test_rollback_requested_status_is_rejected():
    with pytest.raises(ValueError, match="status must be review_failed"):
        assert_review_failed_for_memory_rule(review_failed_result(status="rollback_requested"))


def test_review_passed_true_is_rejected():
    with pytest.raises(ValueError, match="review_passed must be false"):
        assert_review_failed_for_memory_rule(review_failed_result(review_passed=True))


def test_storage_confirmed_true_is_rejected():
    with pytest.raises(ValueError, match="storage_confirmed must be false"):
        assert_review_failed_for_memory_rule(review_failed_result(storage_confirmed=True))


def test_missing_failure_report_draft_is_rejected():
    result = review_failed_result()
    result.pop("failure_report_draft")

    with pytest.raises(ValueError, match="failure_report_draft is required"):
        assert_review_failed_for_memory_rule(result)


def test_existing_memory_rule_confirmed_is_rejected():
    with pytest.raises(ValueError, match="memory_rule_confirmed"):
        assert_review_failed_for_memory_rule(review_failed_result(memory_rule_confirmed=True))


def test_existing_memory_rule_stored_is_rejected():
    with pytest.raises(ValueError, match="memory_rule_stored"):
        assert_review_failed_for_memory_rule(review_failed_result(memory_rule_stored=True))


def test_user_failure_judgement_blank_is_rejected():
    with pytest.raises(ValueError, match="must not be blank"):
        validate_user_failure_judgement("   ")


def test_rule_statement_blank_is_rejected():
    with pytest.raises(ValueError, match="must not be blank"):
        validate_rule_statement("   ")


def test_scope_all_empty_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        validate_rule_scope([], [], [], [])


def test_reviewer_signature_blank_is_rejected():
    with pytest.raises(ValueError, match="must not be blank"):
        validate_reviewer_signature("   ")


def test_memory_rule_draft_has_draft_only_fields_and_no_write_claims():
    memory_rule_draft = draft()

    assert memory_rule_draft["memory_rule_status"] == "draft"
    assert memory_rule_draft["requires_user_signature"] is True
    assert memory_rule_draft["reviewer_signature"] is None
    assert memory_rule_draft["physical_write_performed"] is False
    assert memory_rule_draft["next_required_action"] == "user_sign_memory_rule"
    assert "memory_rule_stored" not in memory_rule_draft
    assert "physical_memory_written" not in memory_rule_draft
    assert "completed" not in memory_rule_draft


def test_failure_report_draft_cannot_be_rule_statement():
    result = review_failed_result()

    with pytest.raises(ValueError, match="failure_report_draft must not be used"):
        build_memory_rule_draft(
            task=task(),
            review_result=result,
            user_failure_judgement="使用者確認失敗原因成立。",
            rule_statement=result["failure_report_draft"]["failure_summary"],
            applies_to_task_types=[],
            trigger_conditions=["驗收失敗"],
            forbidden_patterns=[],
            required_behavior=[],
        )


def test_memory_rule_confirmed_plan_has_pending_runtime_fields_and_no_write_claims():
    confirmed_plan = confirm_memory_rule_plan(draft(), "reviewer:alice")

    assert confirmed_plan["memory_rule_status"] == "confirmed_plan"
    assert confirmed_plan["requires_user_signature"] is False
    assert confirmed_plan["reviewer_signature"] == "reviewer:alice"
    assert confirmed_plan["physical_write_performed"] is False
    assert confirmed_plan["next_required_action"] == "memory_runtime_pending"
    assert "memory_rule_stored" not in confirmed_plan
    assert "physical_memory_written" not in confirmed_plan
    assert "completed" not in confirmed_plan


def test_confirm_memory_rule_plan_requires_draft_waiting_for_signature_without_write():
    with pytest.raises(ValueError, match="memory_rule_status must be draft"):
        confirm_memory_rule_plan(draft(memory_rule_status="confirmed_plan"), "reviewer:alice")

    with pytest.raises(ValueError, match="requires_user_signature must be true"):
        confirm_memory_rule_plan(draft(requires_user_signature=False), "reviewer:alice")

    with pytest.raises(ValueError, match="physical_write_performed must be false"):
        confirm_memory_rule_plan(draft(physical_write_performed=True), "reviewer:alice")
