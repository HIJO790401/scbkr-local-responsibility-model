import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from apps.api.main import MODEL_SETTINGS, PERMISSIONS, TASKS, app


client = TestClient(app)


def setup_function():
    TASKS.clear()
    MODEL_SETTINGS.update(
        {
            "mode": "external",
            "model_name": "test-model",
            "base_url": "https://example.test/v1",
            "api_key": "secret-key",
            "timeout": 1,
            "enabled": False,
        }
    )
    PERMISSIONS.update({"external_api": False, "dangerous_operation_confirmed": False})


def _failed_task():
    response = client.post("/api/tasks/create", json={"raw_input": "draft a plan", "task_type": "general"})
    task = response.json()
    task["generation_result"] = {"result_status": "generated", "final_output": "bad output"}
    response = client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "fail", "review_message": "missing required details"},
    )
    assert response.status_code == 200
    return response.json()


def test_review_fail_does_not_auto_create_memory_rule_draft():
    task = _failed_task()

    assert task["status"] == "review_failed"
    assert task["review_passed"] is False
    assert "failure_report_draft" in task["review_result"]
    assert "memory_rule_draft" not in task
    assert "memory_rule_confirmed_plan" not in task
    assert "memory_rule_stored" not in task


def test_memory_rule_draft_requires_explicit_user_fields():
    task = _failed_task()

    missing = client.post(f"/api/tasks/{task['task_id']}/memory-rule-draft", json={"rule_statement": "x"})
    assert missing.status_code == 400

    response = client.post(
        f"/api/tasks/{task['task_id']}/memory-rule-draft",
        json={
            "user_failure_judgement": "User judged this failure as a reusable boundary issue.",
            "rule_statement": "For this task type, explicitly check required details before final output.",
            "applies_to_task_types": ["general"],
            "trigger_conditions": ["required details are listed by user"],
            "forbidden_patterns": ["omit required details"],
            "required_behavior": ["verify every required detail is present"],
        },
    )

    assert response.status_code == 200
    draft = response.json()["memory_rule_draft"]
    assert draft["memory_rule_status"] == "draft"
    assert draft["physical_write_performed"] is False
    assert "memory_rule_stored" not in response.json()


def test_memory_rule_confirm_requires_existing_draft_and_signature():
    task = _failed_task()

    no_draft = client.post(f"/api/tasks/{task['task_id']}/memory-rule-confirm", json={"reviewer_signature": "me"})
    assert no_draft.status_code == 400

    drafted = client.post(
        f"/api/tasks/{task['task_id']}/memory-rule-draft",
        json={
            "user_failure_judgement": "User judged this failure as a reusable boundary issue.",
            "rule_statement": "For this task type, explicitly check required details before final output.",
            "applies_to_task_types": ["general"],
            "trigger_conditions": ["required details are listed by user"],
            "forbidden_patterns": ["omit required details"],
            "required_behavior": ["verify every required detail is present"],
        },
    ).json()

    blank = client.post(f"/api/tasks/{drafted['task_id']}/memory-rule-confirm", json={"reviewer_signature": "   "})
    assert blank.status_code == 400

    confirmed = client.post(
        f"/api/tasks/{drafted['task_id']}/memory-rule-confirm", json={"reviewer_signature": "reviewer-1"}
    )
    assert confirmed.status_code == 200
    plan = confirmed.json()["memory_rule_confirmed_plan"]
    assert plan["memory_rule_status"] == "confirmed_plan"
    assert plan["physical_write_performed"] is False
    assert confirmed.json()["memory_rule_stored"] is True
    assert confirmed.json()["memory_rule_physical_write_performed"] is True


def test_external_model_test_requires_high_risk_confirmation_before_call():
    PERMISSIONS["external_api"] = True
    PERMISSIONS["dangerous_operation_confirmed"] = False

    response = client.post("/api/model/test")

    assert response.status_code == 200
    body = response.json()
    assert body["last_test_status"] == "failed"
    assert "高風險確認未通過" in body["last_test_message"] or "high_risk" in body["last_test_message"]
    assert body["api_key"] != "secret-key"
