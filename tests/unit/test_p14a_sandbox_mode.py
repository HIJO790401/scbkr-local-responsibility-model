import importlib

import pytest
from fastapi import HTTPException


def _reload_main(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    main = importlib.reload(main)
    main.TASKS.clear()
    main.PERMISSIONS.update({"model_generate": False, "external_api": False, "dangerous_operation_confirmed": False})
    main.set_model_settings({"mode": "sandbox"})
    return main


def _confirmed_task(main):
    task = main.create_task({"raw_input": "sandbox unit task", "task_type": "workflow"})
    task = main.create_scbkr(task["task_id"])
    return main.confirm_task(task["task_id"], {"signature": "sig"})


def test_sandbox_model_test_needs_no_api_key_and_no_external_call(tmp_path, monkeypatch):
    main = _reload_main(tmp_path, monkeypatch)
    called = {"external": False}
    def fail_if_called(*args, **kwargs):
        called["external"] = True
        raise AssertionError("external model call must not run in sandbox")
    monkeypatch.setattr(main, "_post_openai_compatible", fail_if_called)

    result = main.test_model()

    assert result["ok"] is True
    assert result["provider"] == "sandbox_mock_model"
    assert result["sandbox"] is True
    assert result["external_call_performed"] is False
    assert called["external"] is False


def test_sandbox_generate_rejects_unconfirmed_task(tmp_path, monkeypatch):
    main = _reload_main(tmp_path, monkeypatch)
    main.PERMISSIONS.update({"model_generate": True})
    main.test_model()
    task = main.create_task({"raw_input": "unconfirmed sandbox", "task_type": "workflow"})

    with pytest.raises(HTTPException):
        main.generate(task["task_id"])


def test_sandbox_generate_rejects_invalid_sealed_snapshot(tmp_path, monkeypatch):
    main = _reload_main(tmp_path, monkeypatch)
    main.PERMISSIONS.update({"model_generate": True})
    main.test_model()
    task = _confirmed_task(main)
    task["scbkr"]["S"]["task_name"] = "tampered after seal"
    main.save_task(task)

    with pytest.raises(HTTPException):
        main.generate(task["task_id"])


def test_sandbox_generate_rejects_missing_model_generate_permission(tmp_path, monkeypatch):
    main = _reload_main(tmp_path, monkeypatch)
    main.test_model()
    task = _confirmed_task(main)

    with pytest.raises(HTTPException) as exc:
        main.generate(task["task_id"])

    assert exc.value.status_code == 403
    assert exc.value.detail == "model_generate permission is required before sandbox generation"


def test_sandbox_generate_metadata_and_locks(tmp_path, monkeypatch):
    main = _reload_main(tmp_path, monkeypatch)
    main.PERMISSIONS.update({"model_generate": True})
    main.test_model()
    task = _confirmed_task(main)
    generated = main.generate(task["task_id"])

    assert generated["generation_result"]["sandbox"] is True
    assert generated["generation_result"]["provider"] == "sandbox_mock_model"
    assert generated["generation_result"]["external_call_performed"] is False
    assert generated["review_passed"] is False
    assert generated["storage_confirmed"] is False
    assert generated["physical_write_performed"] is False
    with pytest.raises(HTTPException):
        main.storage_request(task["task_id"])


def test_sandbox_review_failed_does_not_auto_write_memory(tmp_path, monkeypatch):
    main = _reload_main(tmp_path, monkeypatch)
    main.PERMISSIONS.update({"model_generate": True})
    main.test_model()
    task = main.generate(_confirmed_task(main)["task_id"])
    failed = main.review(task["task_id"], {"review_decision": "fail", "review_message": "fail"})

    assert failed["status"] == "review_failed"
    assert failed.get("memory_rule_stored") is not True
    assert failed.get("memory_rule_physical_write_performed") is not True


def test_sandbox_storage_confirm_still_requires_signature(tmp_path, monkeypatch):
    main = _reload_main(tmp_path, monkeypatch)
    main.PERMISSIONS.update({"model_generate": True})
    main.test_model()
    task = main.generate(_confirmed_task(main)["task_id"])
    task = main.review(task["task_id"], {"review_decision": "pass", "reviewer_signature": "sig"})
    task = main.storage_request(task["task_id"])

    with pytest.raises(HTTPException):
        main.storage_confirm(task["task_id"], {"storage_confirmed": True, "confirmed_by": "user"})


def test_sandbox_generate_bypasses_real_gateway_enabled_and_api_key(tmp_path, monkeypatch):
    main = _reload_main(tmp_path, monkeypatch)
    calls = {"external": 0}
    def fail_external(*args, **kwargs):
        calls["external"] += 1
        raise AssertionError("sandbox generation must not call LM Studio, Ollama, or external API")
    monkeypatch.setattr(main, "_post_openai_compatible", fail_external)
    main.MODEL_SETTINGS.update({
        "mode": "sandbox",
        "provider": "sandbox_mock_model",
        "base_url": "",
        "api_key": "",
        "model_name": "sandbox_mock_model",
        "enabled": False,
        "last_test_status": "untested",
    })
    main.PERMISSIONS.update({
        "model_generate": True,
        "external_api": False,
        "web_search": False,
        "local_file_access": False,
        "storage_write": False,
        "memory_write": False,
    })
    task = _confirmed_task(main)

    generated = main.generate(task["task_id"])

    assert generated["generation_result"]["sandbox"] is True
    assert generated["generation_result"]["model_provider"] == "sandbox_mock_model"
    assert generated["generation_result"]["external_call_performed"] is False
    assert calls["external"] == 0


def test_sandbox_generate_does_not_auto_review_storage_or_memory(tmp_path, monkeypatch):
    main = _reload_main(tmp_path, monkeypatch)
    main.PERMISSIONS.update({"model_generate": True})
    task = main.generate(_confirmed_task(main)["task_id"])

    assert task["status"] == "waiting_review"
    assert task["review_passed"] is False
    assert task["storage_confirmed"] is False
    assert task.get("storage_request") is None
    assert task.get("memory_rule_draft") is None
    assert task.get("memory_rule_stored") is not True
