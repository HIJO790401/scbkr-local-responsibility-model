import importlib
import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import core.storage.runtime_paths as runtime_paths
import core.storage.sqlite_runtime as sqlite_runtime
import core.ledger.jsonl_ledger as jsonl_ledger

runtime_paths = importlib.reload(runtime_paths)
sqlite_runtime = importlib.reload(sqlite_runtime)
jsonl_ledger = importlib.reload(jsonl_ledger)

from apps.api import main
from apps.api.main import TASKS, app
from core.ledger.jsonl_ledger import read_ledger_events
from core.storage.runtime_paths import REPO_ROOT
from core.storage.sqlite_runtime import list_memory_rules, list_storage_items

client = TestClient(app)
REPO_SQLITE_PATH = REPO_ROOT / "data" / "scbkr.sqlite3"
REPO_LEDGER_JSONL_PATH = REPO_ROOT / "data" / "ledger" / "audit-log.jsonl"


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    TASKS.clear()
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

    yield tmp_path
    TASKS.clear()


def _mock_model_response(*args, **kwargs):
    return {"choices": [{"message": {"content": "mock local generation"}}]}


def create_review_passed_task(monkeypatch):
    monkeypatch.setattr(main, "_post_openai_compatible", _mock_model_response)
    task = client.post("/api/tasks/create", json={"raw_input": "draft a plan", "task_type": "general"}).json()
    assert client.post(f"/api/tasks/{task['task_id']}/scbkr").status_code == 200
    assert client.post(f"/api/tasks/{task['task_id']}/confirm", json={"signature": "confirm-sig"}).status_code == 200
    assert client.post(f"/api/tasks/{task['task_id']}/generate").status_code == 200
    review = client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "pass", "review_message": "accepted", "reviewer_signature": "review-sig"},
    )
    assert review.status_code == 200
    request = client.post(f"/api/tasks/{task['task_id']}/storage-request")
    assert request.status_code == 200
    return request.json()


def create_review_failed_task(monkeypatch):
    monkeypatch.setattr(main, "_post_openai_compatible", _mock_model_response)
    task = client.post("/api/tasks/create", json={"raw_input": "draft a bad plan", "task_type": "general"}).json()
    client.post(f"/api/tasks/{task['task_id']}/scbkr")
    client.post(f"/api/tasks/{task['task_id']}/confirm", json={"signature": "confirm-sig"})
    client.post(f"/api/tasks/{task['task_id']}/generate")
    failed = client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "fail", "review_message": "bad output", "reviewer_signature": "review-sig"},
    )
    assert failed.status_code == 200
    return failed.json()


def test_storage_confirm_with_signature_writes_corpus_logic_exports_and_indexes(monkeypatch, isolated_runtime):
    repo_sqlite_existed = REPO_SQLITE_PATH.exists()
    repo_ledger_existed = REPO_LEDGER_JSONL_PATH.exists()
    task = create_review_passed_task(monkeypatch)

    response = client.post(
        f"/api/tasks/{task['task_id']}/storage-confirm",
        json={"storage_confirmed": True, "confirmed_by": "user", "signature": "storage-sig", "selected_targets": ["corpus", "logic", "exports", "vector_db"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["physical_write_performed"] is True
    assert body["status"] == "storage_committed"
    assert (isolated_runtime / "corpus").is_dir()
    assert (isolated_runtime / "logic").is_dir()
    assert (isolated_runtime / "exports").is_dir()
    assert not (isolated_runtime / "vector_db").exists()
    assert {item["target"] for item in list_storage_items(task_id=task["task_id"])} == {"corpus", "logic", "exports"}
    event_types = [event["event_type"] for event in read_ledger_events(task_id=task["task_id"])]
    assert "storage_physical_write_completed" in event_types
    assert REPO_SQLITE_PATH.exists() is repo_sqlite_existed
    assert REPO_LEDGER_JSONL_PATH.exists() is repo_ledger_existed


def test_storage_confirm_missing_signature_is_rejected(monkeypatch, isolated_runtime):
    task = create_review_passed_task(monkeypatch)

    response = client.post(f"/api/tasks/{task['task_id']}/storage-confirm", json={"storage_confirmed": True, "confirmed_by": "user"})

    assert response.status_code == 400
    assert not (isolated_runtime / "corpus").exists()


def test_review_failed_task_cannot_storage_commit(monkeypatch, isolated_runtime):
    task = create_review_failed_task(monkeypatch)

    response = client.post(
        f"/api/tasks/{task['task_id']}/storage-confirm",
        json={"storage_confirmed": True, "confirmed_by": "user", "signature": "storage-sig"},
    )

    assert response.status_code == 400
    assert not (isolated_runtime / "corpus").exists()


def test_memory_rule_confirm_writes_memory_only_after_signature(monkeypatch, isolated_runtime):
    task = create_review_failed_task(monkeypatch)
    draft_payload = {
        "user_failure_judgement": "user judged bad output",
        "rule_statement": "ask before producing this kind of plan",
        "applies_to_task_types": ["general"],
        "trigger_conditions": ["same issue"],
        "forbidden_patterns": ["bad pattern"],
        "required_behavior": ["ask first"],
    }
    draft = client.post(f"/api/tasks/{task['task_id']}/memory-rule-draft", json=draft_payload)
    assert draft.status_code == 200
    assert not (isolated_runtime / "memory").exists()

    missing = client.post(f"/api/tasks/{task['task_id']}/memory-rule-confirm", json={"reviewer_signature": ""})
    assert missing.status_code == 400
    assert not (isolated_runtime / "memory").exists()

    response = client.post(f"/api/tasks/{task['task_id']}/memory-rule-confirm", json={"reviewer_signature": "memory-sig"})

    assert response.status_code == 200
    body = response.json()
    assert body["memory_rule_stored"] is True
    assert body["memory_rule_physical_write_performed"] is True
    assert (isolated_runtime / "memory").is_dir()
    assert list((isolated_runtime / "memory").glob("*.json"))
    assert list_memory_rules(task_id=task["task_id"])
    event_types = [event["event_type"] for event in read_ledger_events(task_id=task["task_id"])]
    assert "memory_rule_physical_write_completed" in event_types
