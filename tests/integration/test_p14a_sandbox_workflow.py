import importlib
import sqlite3


def test_p14a_sandbox_full_workflow_no_external_model(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    import core.ledger.jsonl_ledger as ledger
    main = importlib.reload(main); ledger = importlib.reload(ledger)
    main.TASKS.clear()
    main.PERMISSIONS.update({"model_generate": True, "external_api": False, "dangerous_operation_confirmed": False})
    main.set_model_settings({"mode": "sandbox"})

    external_called = {"value": False}
    def fail_if_external_called(*args, **kwargs):
        external_called["value"] = True
        raise AssertionError("sandbox must not call external model")
    monkeypatch.setattr(main, "_post_openai_compatible", fail_if_external_called)

    task = main.create_task({"raw_input": "run sandbox workflow integration", "task_type": "workflow"})
    task = main.create_scbkr(task["task_id"])
    task = main.confirm_task(task["task_id"], {"signature": "confirm-sig"})
    model_test = main.test_model()
    assert model_test["ok"] is True
    assert model_test["provider"] == "sandbox_mock_model"
    assert model_test["sandbox"] is True
    assert model_test["external_call_performed"] is False

    generated = main.generate(task["task_id"])
    assert generated["generation_result"]["sandbox"] is True
    assert generated["generation_result"]["provider"] == "sandbox_mock_model"
    assert generated["generation_result"]["external_call_performed"] is False
    assert external_called["value"] is False
    assert generated["physical_write_performed"] is False

    reviewed = main.review(task["task_id"], {"review_decision": "pass", "reviewer_signature": "review-sig"})
    requested = main.storage_request(task["task_id"])
    assert requested["physical_write_performed"] is False
    committed = main.storage_confirm(
        task["task_id"],
        {"storage_confirmed": True, "confirmed_by": "user", "signature": "storage-sig", "selected_targets": ["corpus", "logic", "exports"]},
    )
    assert committed["physical_write_performed"] is True
    assert committed["status"] == "storage_committed"

    indexed = main.index_task_retrieval(task["task_id"])
    assert indexed["indexed_cases"]
    query = main.retrieval_query({"query_text": "sandbox workflow integration", "top_k": 3, "case_type": "any"})
    assert query["requires_user_confirmation"] is True
    assert query["auto_confirmed"] is False
    assert query["generation_allowed"] is False

    events = [event["event_type"] for event in ledger.read_ledger_events(task_id=task["task_id"])]
    for expected in ("task_created", "scbkr_draft_created", "scbkr_confirmed", "generation_completed", "review_passed", "storage_physical_write_completed"):
        assert expected in events

    with sqlite3.connect(tmp_path / "scbkr.sqlite3") as conn:
        assert conn.execute("select count(*) from tasks where task_id = ?", (task["task_id"],)).fetchone()[0] == 1
