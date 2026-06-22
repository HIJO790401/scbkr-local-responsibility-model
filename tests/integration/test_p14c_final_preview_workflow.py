import importlib
import sqlite3
from pathlib import Path

import pytest


def load_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    import core.ledger.jsonl_ledger as ledger
    main = importlib.reload(main)
    ledger = importlib.reload(ledger)
    main.TASKS.clear()
    main.PERMISSIONS.update({"model_generate": False, "external_api": False, "dangerous_operation_confirmed": False})
    main.set_model_settings({"mode": "sandbox"})
    return main, ledger


def make_confirmed_task(main):
    task = main.create_task({"raw_input": "P14-C final sandbox workflow", "task_type": "workflow"})
    main.create_scbkr(task["task_id"])
    return main.confirm_task(task["task_id"], {"confirmed_by": "user", "signature": "confirm-sig"})


def test_p14c_final_desktop_status_contract(tmp_path, monkeypatch):
    main, _ = load_runtime(tmp_path, monkeypatch)
    status = main.desktop_status()
    assert status["desktop_stage"] == "P14-C-preview"
    assert status["api_server_reachable"] is True
    assert status["sidecar_running"] is True
    assert status["sandbox_available"] is True
    assert status["preview_package"] in ("built", "preview runtime")
    assert status["production_packaging"] is False
    assert status["production_packaging_status"] == "future stage pending"
    assert status["installer"] == "not a production installer"
    assert status["sidecar_host"] == "127.0.0.1"
    assert status["sidecar_port"] == 8787


def test_p14c_final_sandbox_full_workflow_complete_and_persistence(tmp_path, monkeypatch):
    main, ledger = load_runtime(tmp_path, monkeypatch)
    external_called = {"value": False}

    def fail_external(*args, **kwargs):
        external_called["value"] = True
        raise AssertionError("sandbox must not call LM Studio, Ollama, or external API")

    monkeypatch.setattr(main, "_post_openai_compatible", fail_external)
    task = make_confirmed_task(main)
    main.set_permissions({"model_generate": True})
    generated = main.generate(task["task_id"])
    result = generated["generation_result"]
    assert result["sandbox"] is True
    assert result["model_provider"] == "sandbox_mock_model"
    assert result["external_call_performed"] is False
    assert result["next_required_action"] == "user_review_required"
    assert generated["status"] == "waiting_review"
    assert generated["physical_write_performed"] is False
    assert external_called["value"] is False

    reviewed = main.review(task["task_id"], {"review_decision": "pass", "reviewer_signature": "review-sig"})
    assert reviewed["review_passed"] is True
    requested = main.storage_request(task["task_id"])
    assert requested["status"] == "waiting_storage_confirm"
    assert requested["physical_write_performed"] is False
    committed = main.storage_confirm(task["task_id"], {"storage_confirmed": True, "confirmed_by": "user", "signature": "storage-sig", "selected_targets": ["corpus", "logic", "exports"]})
    assert committed["storage_confirmed"] is True
    assert committed["physical_write_performed"] is True
    completed = main.complete_task(task["task_id"], {"confirmed_by": "user"})
    assert completed["status"] == "completed"
    assert completed["final_result"]["task_id"] == task["task_id"]

    assert (tmp_path / "scbkr.sqlite3").exists()
    assert (tmp_path / "ledger" / "audit-log.jsonl").exists()
    assert any(tmp_path.rglob("*.json"))
    with sqlite3.connect(tmp_path / "scbkr.sqlite3") as conn:
        assert conn.execute("select count(*) from tasks where task_id = ?", (task["task_id"],)).fetchone()[0] == 1
    assert "task_completed" in [event["event_type"] for event in ledger.read_ledger_events(task_id=task["task_id"])]


def test_p14c_final_review_failed_and_unsigned_storage_gates(tmp_path, monkeypatch):
    main, _ = load_runtime(tmp_path, monkeypatch)
    task = make_confirmed_task(main)
    main.set_permissions({"model_generate": True})
    main.generate(task["task_id"])
    failed = main.review(task["task_id"], {"review_decision": "fail", "review_message": "not acceptable"})
    assert failed["status"] == "review_failed"
    with pytest.raises(Exception):
        main.storage_request(task["task_id"])
    with pytest.raises(Exception):
        main.storage_confirm(task["task_id"], {"storage_confirmed": True, "confirmed_by": "user", "signature": "storage-sig"})
    assert main._get_task(task["task_id"])["physical_write_performed"] is False

    task2 = make_confirmed_task(main)
    main.generate(task2["task_id"])
    main.review(task2["task_id"], {"review_decision": "pass"})
    main.storage_request(task2["task_id"])
    with pytest.raises(Exception):
        main.storage_confirm(task2["task_id"], {"storage_confirmed": False, "confirmed_by": "user", "signature": "storage-sig"})
    with pytest.raises(Exception):
        main.storage_confirm(task2["task_id"], {"storage_confirmed": True, "confirmed_by": "user"})
    assert main._get_task(task2["task_id"])["physical_write_performed"] is False
