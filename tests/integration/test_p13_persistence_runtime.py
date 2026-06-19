import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from apps.api import main
from apps.api.main import TASKS, app
from core.ledger.jsonl_ledger import read_ledger_events
from core.storage.runtime_paths import DATA_DIR, LEDGER_JSONL_PATH, SQLITE_PATH
from core.storage.sqlite_runtime import load_task

client = TestClient(app)


def forbidden_runtime_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return [item for item in path.rglob("*") if item.is_file() and item.name != ".gitkeep"]


def setup_function():
    TASKS.clear()
    if SQLITE_PATH.exists():
        SQLITE_PATH.unlink()
    if LEDGER_JSONL_PATH.exists():
        LEDGER_JSONL_PATH.unlink()
    main.MODEL_SETTINGS.update(
        {
            "mode": "local",
            "model_name": "test-model",
            "base_url": "http://127.0.0.1:9/v1",
            "api_key": "secret-key",
            "timeout": 1,
            "enabled": True,
            "last_test_status": "success",
        }
    )
    main.PERMISSIONS.update({"model_generate": True, "external_api": False, "dangerous_operation_confirmed": False})


def create_task():
    response = client.post("/api/tasks/create", json={"raw_input": "draft a plan", "task_type": "general"})
    assert response.status_code == 200
    return response.json()


def test_create_task_persists_to_sqlite_and_appends_jsonl():
    task = create_task()

    assert SQLITE_PATH.exists()
    assert LEDGER_JSONL_PATH.exists()
    assert load_task(task["task_id"])["task_id"] == task["task_id"]
    assert read_ledger_events(task_id=task["task_id"])[0]["event_type"] == "task_created"


def test_scbkr_and_confirm_persist_confirmation_and_ledger_event():
    task = create_task()
    scbkr_response = client.post(f"/api/tasks/{task['task_id']}/scbkr")
    assert scbkr_response.status_code == 200

    with sqlite3.connect(SQLITE_PATH) as conn:
        row = conn.execute(
            "SELECT confirmation_status FROM scbkr_confirmations WHERE task_id = ?",
            (task["task_id"],),
        ).fetchone()
    assert row[0] == "draft"

    confirm_response = client.post(f"/api/tasks/{task['task_id']}/confirm")
    assert confirm_response.status_code == 200
    confirmed = load_task(task["task_id"])
    assert confirmed["confirmed"] is True

    event_types = [event["event_type"] for event in read_ledger_events(task_id=task["task_id"])]
    assert "scbkr_confirmed" in event_types


def test_get_task_recovers_from_sqlite_after_cache_clear():
    task = create_task()
    TASKS.clear()

    recovered = main.get_task(task["task_id"])

    assert recovered["task_id"] == task["task_id"]
    assert task["task_id"] in TASKS


def test_get_task_ledger_reads_task_events_from_jsonl():
    task = create_task()
    client.post(f"/api/tasks/{task['task_id']}/scbkr")

    response = main.get_task_ledger_events(task["task_id"])

    event_types = [event["event_type"] for event in response["events"]]
    assert "task_created" in event_types
    assert "scbkr_draft_created" in event_types


def test_storage_confirm_only_writes_plan_not_physical_storage():
    task = create_task()
    task = TASKS[task["task_id"]]
    task["review_result"] = {"status": "review_passed", "review_passed": True, "storage_confirmed": False}
    task["review_passed"] = True
    task["status"] = "review_passed"

    request_response = client.post(f"/api/tasks/{task['task_id']}/storage-request")
    assert request_response.status_code == 200
    confirm_response = client.post(f"/api/tasks/{task['task_id']}/storage-confirm", json={"selected_targets": ["vector_db"]})

    assert confirm_response.status_code == 200
    body = confirm_response.json()
    assert body["physical_write_performed"] is False
    assert body["storage_plan"]["physical_write_performed"] is False
    assert forbidden_runtime_files(DATA_DIR / "vector_db") == []


def test_memory_rule_confirm_writes_plan_not_data_memory():
    task = create_task()
    task = TASKS[task["task_id"]]
    task["review_result"] = {"status": "review_failed", "review_passed": False, "storage_confirmed": False, "failure_report_draft": {"failure_summary": "bad output"}}
    task["status"] = "review_failed"
    draft_payload = {
        "user_failure_judgement": "bad output",
        "rule_statement": "never do that",
        "applies_to_task_types": ["general"],
        "trigger_conditions": ["same issue"],
        "forbidden_patterns": ["bad pattern"],
        "required_behavior": ["ask first"],
    }
    draft_response = client.post(f"/api/tasks/{task['task_id']}/memory-rule-draft", json=draft_payload)
    assert draft_response.status_code == 200

    confirm_response = client.post(
        f"/api/tasks/{task['task_id']}/memory-rule-confirm",
        json={"reviewer_signature": "user-signature"},
    )

    assert confirm_response.status_code == 200
    assert confirm_response.json()["physical_write_performed"] is False
    assert forbidden_runtime_files(DATA_DIR / "memory") == []


def test_rebuild_ledger_index_route_rebuilds_from_jsonl():
    task = create_task()
    with sqlite3.connect(SQLITE_PATH) as conn:
        conn.execute("DELETE FROM ledger_index")

    response = main.rebuild_ledger_index()

    assert response["indexed_count"] >= 1
    with sqlite3.connect(SQLITE_PATH) as conn:
        row = conn.execute("SELECT event_type FROM ledger_index WHERE task_id = ?", (task["task_id"],)).fetchone()
    assert row[0] == "task_created"
