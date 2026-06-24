from fastapi.testclient import TestClient

from apps.api.main import app


def test_general_chat_suggestion_does_not_create_task_or_write_data_center():
    client = TestClient(app)
    response = client.post("/api/chat/general", json={"message": "我覺得情報類輸出如果只有描述，沒有責任主體、沒有邊界判定、沒有框架判詞，就不該入庫。"})
    assert response.status_code == 200
    data = response.json()
    assert data["task_created"] is False
    assert data["data_center_written"] is False
    assert data["auto_workbench"] is False
    assert data["suggestion"]["suggested_write_direction"] == "記憶庫"


def test_accept_suggestion_prefills_task_entry_without_creating_task():
    client = TestClient(app)
    suggestion = client.post("/api/chat/general", json={"message": "不得把模型猜測日期直接 confirmed。"}).json()["suggestion"]
    response = client.post("/api/chat/suggestions/accept", json={"suggestion": suggestion})
    assert response.status_code == 200
    data = response.json()
    assert data["task_created"] is False
    assert data["data_center_written"] is False
    assert data["prefill"]["user_original"] == "不得把模型猜測日期直接 confirmed。"
    assert data["prefill"]["draft_only_notice"]


def test_task_entry_button_creates_model_authored_draft_waiting_confirm():
    client = TestClient(app)
    response = client.post("/api/tasks/create", json={"raw_input": "我要寫一個心靈雞湯文案", "task_type": "general", "create_scbkr_draft": True})
    assert response.status_code == 200
    task = response.json()
    assert task["confirmed"] is False
    assert task["status"] == "waiting_user_confirm"
    assert task["scbkr"]["model_authored"] is False
    assert set("SCBKR") == set(task["scbkr"][key] and key for key in "SCBKR")
    assert task["data_center_context"]["advisory"] is True
    assert task["data_center_context"]["auto_confirmed"] is False


def test_confirmed_sandbox_execution_returns_formal_copy_not_draft(monkeypatch):
    client = TestClient(app)
    client.post("/api/settings/model", json={"provider": "sandbox_mock_model", "mode": "sandbox"})
    client.post("/api/settings/permissions", json={"model_generate": True})
    task = client.post("/api/tasks/create", json={"raw_input": "我要寫一個心靈雞湯文案", "task_type": "general", "create_scbkr_draft": True}).json()
    confirmed = client.post(f"/api/tasks/{task['task_id']}/confirm", json={"scbkr": task["scbkr"], "confirmed_by": "user", "confirmation_statement": "ok", "signature": "user"})
    assert confirmed.status_code == 200
    generated = client.post(f"/api/tasks/{task['task_id']}/generate")
    assert generated.status_code == 200
    content = generated.json()["generation_result"]["content"]
    assert "心靈雞湯文案初稿" in content
    assert "SCBKR 草案" not in content
    assert "等待使用者確認" not in content


def test_patch_and_dates_are_user_confirm_gated():
    client = TestClient(app)
    task = client.post("/api/tasks/create", json={"raw_input": "整理日期規則", "task_type": "general", "create_scbkr_draft": True}).json()
    patch = client.post(f"/api/tasks/{task['task_id']}/scbkr/patch-draft", json={"layer": "B", "instruction": "不要讓模型自己確認日期"}).json()["patch"]
    assert patch["auto_confirmed"] is False
    applied = client.post(f"/api/tasks/{task['task_id']}/scbkr/apply-patch", json={"patch": patch}).json()
    assert applied["confirmed"] is False
    assert applied["status"] == "waiting_user_confirm"
    dated = client.post(f"/api/tasks/{task['task_id']}/dates", json={"event_date": "2026-06-23", "model_inferred_date": "2026-06-22", "user_confirmed": True}).json()
    assert dated["date_governance"]["confirmation_status"] == "confirmed_by_user"
