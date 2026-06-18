import json
from pathlib import Path

import pytest

from core.storage.storage_plan import build_storage_commit_plan
from core.storage.storage_request import assert_review_passed_for_storage, build_storage_request
from core.storage.storage_result import (
    build_storage_rejected_result,
    build_storage_runtime_pending_result,
)
from core.storage.targets import STORAGE_TARGETS, validate_storage_target


def make_task(**overrides):
    task = {
        "task_id": "task-1",
        "trace_id": "trace-1",
        "ledger_id": "ledger-1",
        "task_type": "workflow",
    }
    task.update(overrides)
    return task


def make_review_result(**overrides):
    review_result = {
        "task_id": "task-1",
        "trace_id": "trace-1",
        "ledger_id": "ledger-1",
        "status": "review_passed",
        "review_decision": "pass",
        "review_passed": True,
        "storage_confirmed": False,
        "next_required_action": "ask_user_storage_request",
    }
    review_result.update(overrides)
    return review_result


def test_storage_request_schema_is_valid_json_schema_shape():
    schema = json.loads(Path("schemas/storage_request.schema.json").read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert tuple(schema["properties"]["candidate_targets"]["items"]["enum"]) == STORAGE_TARGETS
    assert tuple(schema["properties"]["selected_targets"]["items"]["enum"]) == STORAGE_TARGETS


def test_review_result_must_be_passed_for_storage():
    with pytest.raises(ValueError):
        assert_review_passed_for_storage(make_review_result(status="review_failed"))

    with pytest.raises(ValueError):
        assert_review_passed_for_storage(make_review_result(review_passed=False))

    with pytest.raises(ValueError):
        assert_review_passed_for_storage(make_review_result(storage_confirmed=True))


def test_build_storage_request_defaults_do_not_include_memory():
    request = build_storage_request(make_task(), make_review_result())

    assert request["candidate_targets"] == ["vector_db", "corpus", "logic"]
    assert "memory" not in request["candidate_targets"]
    assert request["selected_targets"] == []
    assert request["storage_confirmed"] is False
    assert request["next_required_action"] == "user_confirm_storage_targets"


def test_invalid_storage_target_is_rejected():
    with pytest.raises(ValueError):
        validate_storage_target("archive")

    with pytest.raises(ValueError):
        build_storage_request(make_task(), make_review_result(), candidate_targets=["vector_db", "archive"])

    with pytest.raises(ValueError):
        build_storage_commit_plan(make_task(), make_review_result(), ["archive"])


def test_memory_target_requires_storage_signature():
    with pytest.raises(ValueError):
        build_storage_commit_plan(make_task(), make_review_result(), ["memory"])

    plan = build_storage_commit_plan(
        make_task(),
        make_review_result(),
        ["memory"],
        storage_signature="user-signature",
    )

    assert plan["storage_confirmed"] is True
    assert plan["storage_items"][0]["requires_user_signature"] is True
    assert plan["storage_items"][0]["storage_signature"] == "user-signature"


def test_failed_or_memory_rule_content_cannot_build_storage_plan():
    with pytest.raises(ValueError):
        build_storage_commit_plan(make_task(), make_review_result(status="review_failed"), ["vector_db"])

    with pytest.raises(ValueError):
        build_storage_commit_plan(
            make_task(),
            make_review_result(failure_report_draft={"rule_candidate_status": "draft_only"}),
            ["vector_db"],
        )

    with pytest.raises(ValueError):
        build_storage_commit_plan(
            make_task(),
            make_review_result(memory_rule_status="not_created"),
            ["vector_db"],
        )


def test_storage_commit_plan_is_confirmed_plan_without_physical_writes():
    plan = build_storage_commit_plan(
        make_task(),
        make_review_result(),
        ["vector_db", "corpus", "logic", "memory"],
        storage_signature="user-signature",
        storage_notes="二次確認",
    )

    assert plan["storage_plan_status"] == "storage_confirmed_plan"
    assert plan["storage_confirmed"] is True
    assert plan["physical_write_performed"] is False
    assert plan["next_required_action"] == "storage_runtime_pending"
    assert all(item["physical_write_performed"] is False for item in plan["storage_items"])

    vector_item = next(item for item in plan["storage_items"] if item["target"] == "vector_db")
    assert vector_item["embedding_status"] == "not_created"

    memory_item = next(item for item in plan["storage_items"] if item["target"] == "memory")
    assert memory_item["requires_user_signature"] is True
    assert "failure_report_draft" not in memory_item
    assert "memory_rule_status" not in memory_item
    assert "memory_rule_confirmed" not in memory_item
    assert "memory_rule_stored" not in memory_item


def test_storage_result_helpers_do_not_mark_physical_writes():
    rejected = build_storage_rejected_result(make_task(), "使用者拒絕入庫")
    pending = build_storage_runtime_pending_result(
        build_storage_commit_plan(make_task(), make_review_result(), ["logic"])
    )

    assert rejected["status"] == "storage_rejected"
    assert rejected["storage_confirmed"] is False
    assert rejected["physical_write_performed"] is False
    assert pending["status"] == "storage_runtime_pending"
    assert pending["physical_write_performed"] is False
    assert pending["next_required_action"] == "implement_storage_runtime_later"
