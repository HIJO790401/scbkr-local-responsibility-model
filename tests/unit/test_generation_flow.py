import json

import pytest

from core.model_gateway.settings import DEFAULT_MODEL_SETTINGS
from core.workflow.generation_flow import (
    assert_task_can_generate,
    build_generation_messages,
    build_model_request_package,
    run_generation_gate,
)
from core.workflow.generation_result import build_generation_error, build_generation_result


def make_task(**overrides):
    task = {
        "task_id": "task-1",
        "trace_id": "trace-1",
        "ledger_id": "ledger-1",
        "task_name": "測試任務",
        "raw_input": "請依照 SCBKR 執行測試任務",
        "task_type": "workflow",
        "status": "confirmed",
        "confirmed": True,
        "review_passed": False,
        "storage_confirmed": False,
    }
    task.update(overrides)
    return task


def make_scbkr(**overrides):
    scbkr = {
        "S": {"task_name": "測試任務", "pending_questions": []},
        "C": {"flow_steps": ["建立 request"], "pending_questions": []},
        "B": {"data_write_scope": ["不寫 data"], "pending_questions": []},
        "K": {"references": ["P6 測試"], "pending_questions": []},
        "R": {
            "acceptance_criteria": ["結果只能進入 waiting_review"],
            "review_status": "not_started",
            "pending_questions": [],
        },
        "confirmation_status": "confirmed",
    }
    scbkr.update(overrides)
    return scbkr


def make_model_settings(**overrides):
    settings = dict(DEFAULT_MODEL_SETTINGS)
    settings.update(
        {
            "enabled": True,
            "model_name": "local-model",
            "last_test_status": "success",
        }
    )
    settings.update(overrides)
    return settings


def test_unconfirmed_task_is_rejected():
    with pytest.raises(ValueError):
        assert_task_can_generate(
            make_task(confirmed=False),
            make_scbkr(),
            make_model_settings(),
            {"external_api": False},
        )


def test_task_status_other_than_confirmed_is_rejected():
    with pytest.raises(ValueError):
        assert_task_can_generate(
            make_task(status="waiting_user_confirm"),
            make_scbkr(),
            make_model_settings(),
            {"external_api": False},
        )


def test_scbkr_confirmation_status_other_than_confirmed_is_rejected():
    with pytest.raises(ValueError):
        assert_task_can_generate(
            make_task(),
            make_scbkr(confirmation_status="draft"),
            make_model_settings(),
            {"external_api": False},
        )


def test_model_gateway_disabled_or_incomplete_settings_are_rejected():
    for settings in (
        make_model_settings(enabled=False),
        make_model_settings(model_name=""),
        make_model_settings(last_test_status="failed"),
        make_model_settings(last_test_status="untested"),
    ):
        with pytest.raises(ValueError):
            assert_task_can_generate(make_task(), make_scbkr(), settings, {"external_api": True})


def test_external_mode_without_external_api_permission_is_rejected():
    with pytest.raises(ValueError):
        assert_task_can_generate(
            make_task(),
            make_scbkr(),
            make_model_settings(mode="external"),
            {"external_api": False},
        )


def test_build_generation_messages_contains_scbkr_dimensions():
    messages = build_generation_messages(make_task(), make_scbkr())
    user_payload = json.loads(messages[1]["content"])

    assert messages[0]["role"] == "system"
    assert "不得宣稱驗收通過" in messages[0]["content"]
    for dimension in ("S", "C", "B", "K", "R"):
        assert dimension in user_payload
    assert user_payload["acceptance_criteria"] == ["結果只能進入 waiting_review"]


def test_build_model_request_package_only_builds_payload():
    package = build_model_request_package(
        make_task(),
        make_scbkr(),
        make_model_settings(),
        {"external_api": False},
    )

    assert package["status"] == "generation_request_ready"
    assert package["next_required_action"] == "caller_must_send_to_model_explicitly"
    assert package["model_payload"]["model"] == "local-model"
    assert package["model_payload"]["messages"][0]["role"] == "system"


def test_run_generation_gate_without_model_response_returns_request_package():
    result = run_generation_gate(
        make_task(),
        make_scbkr(),
        make_model_settings(),
        {"external_api": False},
    )

    assert result["status"] == "generation_request_ready"
    assert result["next_required_action"] == "caller_must_send_to_model_explicitly"
    assert "model_payload" in result


def test_run_generation_gate_with_caller_supplied_response_returns_generation_result():
    model_response = {"choices": [{"message": {"content": "待驗收模型輸出"}}]}
    result = run_generation_gate(
        make_task(),
        make_scbkr(),
        make_model_settings(),
        {"external_api": False},
        model_response=model_response,
    )

    assert result["status"] == "waiting_review"
    assert result["content"] == "待驗收模型輸出"
    assert result["review_passed"] is False
    assert result["storage_confirmed"] is False
    assert result["next_required_action"] == "user_review_required"
    assert result["source"] == "caller_supplied_model_response"


def test_generation_result_helpers_keep_review_and_storage_locked():
    result = build_generation_result(make_task(), make_scbkr(), "content")
    error = build_generation_error("錯誤", layer="C")

    assert result["status"] == "waiting_review"
    assert result["review_passed"] is False
    assert result["storage_confirmed"] is False
    assert error["review_passed"] is False
    assert error["storage_confirmed"] is False
