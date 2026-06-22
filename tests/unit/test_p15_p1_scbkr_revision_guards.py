from copy import deepcopy

import pytest
from fastapi import HTTPException

from apps.api import main
from core.scbkr.generator import create_scbkr_draft


def make_task(**overrides):
    task = {
        "task_id": overrides.pop("task_id", "task-p15-p1"),
        "trace_id": "trace-p15-p1",
        "ledger_id": "ledger-p15-p1",
        "task_name": "P15 P1",
        "task_type": "workflow",
        "raw_input": "建立一個安全確認單",
        "status": "waiting_user_confirm",
        "confirmed": False,
        "review_passed": False,
        "storage_confirmed": False,
        "physical_write_performed": False,
        "scbkr": create_scbkr_draft("建立一個安全確認單", "workflow"),
    }
    task.update(overrides)
    main.TASKS[task["task_id"]] = task
    return task


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    main.TASKS.clear()
    yield
    main.TASKS.clear()


def confirm_payload(task):
    scbkr = deepcopy(task["scbkr"])
    scbkr["S"]["task_name"] = "更新後任務"
    return {"scbkr": scbkr, "confirmed_by": "user", "signature": "user"}


def test_edited_scbkr_invalidates_generation_review_and_storage_artifacts():
    task = make_task(
        status="waiting_storage_confirm",
        generation_result={"content": "old"},
        review_result={"review_passed": True},
        review_passed=True,
        storage_request={"old": True},
        storage_plan={"old": True},
        storage_result={"old": True},
        storage_confirmed=True,
        completed_at="2026-01-01T00:00:00+00:00",
        final_result={"old": True},
    )

    result = main.confirm_task(task["task_id"], confirm_payload(task))

    assert result["downstream_invalidated"] is True
    for key in ("generation_result", "review_result", "storage_request", "storage_plan", "storage_result", "completed_at", "final_result"):
        assert key not in result
    assert result["review_passed"] is False
    assert result["storage_confirmed"] is False
    assert result["physical_write_performed"] is False
    assert result["confirmed"] is True
    assert result["status"] == "confirmed"
    events = main.get_task_ledger(task["task_id"])
    assert any(event["event_type"] == "scbkr_revised_downstream_invalidated" for event in events)


def test_edited_scbkr_after_invalidation_cannot_review_or_storage_confirm_old_outputs():
    task = make_task(
        status="waiting_storage_confirm",
        generation_result={"content": "old"},
        review_result={"review_passed": True},
        review_passed=True,
        storage_request={"old": True},
        storage_plan={"old": True},
        storage_confirmed=True,
    )
    main.confirm_task(task["task_id"], confirm_payload(task))

    with pytest.raises(HTTPException) as review_error:
        main.review(task["task_id"], {"review_decision": "pass", "review_message": "old pass"})
    assert review_error.value.status_code == 400

    with pytest.raises(HTTPException) as storage_error:
        main.storage_confirm(task["task_id"], {"storage_confirmed": True, "confirmed_by": "user", "signature": "user"})
    assert storage_error.value.status_code == 400


@pytest.mark.parametrize("overrides", [{"physical_write_performed": True}, {"status": "completed"}, {"status": "storage_committed"}])
def test_committed_or_completed_task_cannot_directly_edit_scbkr(overrides):
    task = make_task(**overrides)
    with pytest.raises(HTTPException) as exc:
        main.confirm_task(task["task_id"], confirm_payload(task))
    assert exc.value.status_code == 400
    assert "已入庫或已完成" in str(exc.value.detail)


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda s: {"S": {}, "C": {}, "B": {}, "K": {}, "R": {}}, "empty dimension"),
        (lambda s: {k: v for k, v in s.items() if k != "R"}, "R: missing dimension"),
        (lambda s: (s["S"].pop("task_name"), s)[1], "S.task_name: missing field"),
        (lambda s: (s["C"].pop("flow_steps"), s)[1], "C.flow_steps: missing field"),
        (lambda s: (s["B"].pop("data_read_scope"), s)[1], "B.data_read_scope: missing field"),
        (lambda s: (s["K"].pop("references"), s)[1], "K.references: missing field"),
        (lambda s: (s["R"].pop("expected_outputs"), s)[1], "R.expected_outputs: missing field"),
        (lambda s: (s["S"].update({"task_name": ""}), s)[1], "S.task_name: empty field"),
        (lambda s: (s["C"].update({"flow_steps": []}), s)[1], "C.flow_steps: empty field"),
        (lambda s: (s["R"].update({"expected_outputs": None}), s)[1], "R.expected_outputs: empty field"),
    ],
)
def test_incomplete_scbkr_payloads_are_rejected(mutate, expected):
    task = make_task()
    bad_scbkr = mutate(deepcopy(task["scbkr"]))
    with pytest.raises(HTTPException) as exc:
        main.confirm_task(task["task_id"], {"scbkr": bad_scbkr})
    assert exc.value.status_code == 400
    assert expected in str(exc.value.detail)


def test_complete_edited_scbkr_confirms_and_preserves_sealed_gate():
    task = make_task(generation_result={"content": "old"})
    result = main.confirm_task(task["task_id"], confirm_payload(task))

    assert result["confirmed"] is True
    assert result["scbkr"]["confirmed"] is True
    assert result["scbkr"].get("confirmed_snapshot_hash")
    assert main.all_dimensions_confirmed(result["scbkr"]) is True
    assert "generation_result" not in result
