import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from apps.api.main import MODEL_SETTINGS, PERMISSIONS, TASKS, app
from core.scbkr.confirmation import VALID_DIMENSIONS
from core.workflow.generation_flow import assert_task_can_generate

client = TestClient(app)


def setup_function():
    TASKS.clear()
    MODEL_SETTINGS.update(
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
    PERMISSIONS.update({"model_generate": True, "external_api": False, "dangerous_operation_confirmed": False})


def create_task_with_scbkr():
    created = client.post("/api/tasks/create", json={"raw_input": "draft a plan", "task_type": "general"})
    assert created.status_code == 200
    task_id = created.json()["task_id"]
    scbkr = client.post(f"/api/tasks/{task_id}/scbkr")
    assert scbkr.status_code == 200
    return scbkr.json()


def test_confirm_route_confirms_all_dimensions_and_task():
    task = create_task_with_scbkr()
    response = client.post(f"/api/tasks/{task['task_id']}/confirm", json={"signature": "user"})

    assert response.status_code == 200
    body = response.json()
    assert body["confirmed"] is True
    assert body["scbkr"]["confirmation_status"] == "confirmed"
    for dimension_key in VALID_DIMENSIONS:
        dimension = body["scbkr"][dimension_key]
        assert dimension["confirmed"] is True
        assert dimension["snapshot_hash"]
        assert dimension["confirmed_snapshot"]


def test_generate_is_rejected_before_confirm():
    task = create_task_with_scbkr()

    with pytest.raises(ValueError, match="task.confirmed"):
        assert_task_can_generate(task, task["scbkr"], MODEL_SETTINGS, PERMISSIONS)


def test_generate_is_rejected_when_one_dimension_confirmation_is_broken():
    task = create_task_with_scbkr()
    confirmed = client.post(f"/api/tasks/{task['task_id']}/confirm").json()
    confirmed["scbkr"]["K"]["confirmed"] = False

    with pytest.raises(ValueError, match="S/C/B/K/R dimensions"):
        assert_task_can_generate(confirmed, confirmed["scbkr"], MODEL_SETTINGS, PERMISSIONS)


def test_confirm_route_accepts_no_body():
    task = create_task_with_scbkr()
    response = client.post(f"/api/tasks/{task['task_id']}/confirm")

    assert response.status_code == 200
    assert response.json()["confirmed"] is True


def test_confirm_route_writes_signature_and_statement_to_scbkr_metadata():
    task = create_task_with_scbkr()
    statement = "我確認本任務 S/C/B/K/R 五維責任鏈。"
    response = client.post(
        f"/api/tasks/{task['task_id']}/confirm",
        json={"confirmed_by": "user", "confirmation_statement": statement, "signature": "user-signature"},
    )

    assert response.status_code == 200
    scbkr = response.json()["scbkr"]
    assert scbkr["confirmed_by"] == "user"
    assert scbkr["confirmation_statement"] == statement
    assert scbkr["signature"] == "user-signature"
    assert scbkr["confirmed_snapshot_hash"]


def test_confirmed_task_passes_snapshot_gate_without_calling_model():
    task = create_task_with_scbkr()
    confirmed = client.post(f"/api/tasks/{task['task_id']}/confirm").json()

    assert assert_task_can_generate(confirmed, confirmed["scbkr"], MODEL_SETTINGS, PERMISSIONS) is True


def test_generate_route_rejects_tampered_s_live_payload_before_model_call():
    task = create_task_with_scbkr()
    confirmed = client.post(f"/api/tasks/{task['task_id']}/confirm").json()
    TASKS[confirmed["task_id"]]["scbkr"]["S"]["task_name"] = "竄改後任務名稱"

    response = client.post(f"/api/tasks/{confirmed['task_id']}/generate")

    assert response.status_code == 400
    assert "sealed snapshots" in str(response.json())


def test_generate_route_rejects_tampered_b_boundary_before_model_call():
    task = create_task_with_scbkr()
    confirmed = client.post(f"/api/tasks/{task['task_id']}/confirm").json()
    TASKS[confirmed["task_id"]]["scbkr"]["B"]["data_write_scope"].append("竄改：允許寫入 data")

    response = client.post(f"/api/tasks/{confirmed['task_id']}/generate")

    assert response.status_code == 400
    assert "sealed snapshots" in str(response.json())


def test_generate_route_rejects_deleted_confirmed_snapshot_before_model_call():
    task = create_task_with_scbkr()
    confirmed = client.post(f"/api/tasks/{task['task_id']}/confirm").json()
    del TASKS[confirmed["task_id"]]["scbkr"]["C"]["confirmed_snapshot"]

    response = client.post(f"/api/tasks/{confirmed['task_id']}/generate")

    assert response.status_code == 400
    assert "sealed snapshots" in str(response.json())


def test_generate_route_rejects_modified_snapshot_hash_before_model_call():
    task = create_task_with_scbkr()
    confirmed = client.post(f"/api/tasks/{task['task_id']}/confirm").json()
    TASKS[confirmed["task_id"]]["scbkr"]["R"]["snapshot_hash"] = "0" * 64

    response = client.post(f"/api/tasks/{confirmed['task_id']}/generate")

    assert response.status_code == 400
    assert "sealed snapshots" in str(response.json())
