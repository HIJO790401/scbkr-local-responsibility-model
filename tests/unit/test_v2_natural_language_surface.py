import importlib

from fastapi.testclient import TestClient

from apps.api import main


def test_natural_language_rule_is_saved_as_unsigned_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    client = TestClient(main.app)

    response = client.post("/api/rules/draft-from-text", json={"instruction": "凡是要發布文章，都必須先由我簽名確認。"})

    assert response.status_code == 200
    body = response.json()
    assert body["compiled_from"] == "natural_language"
    assert body["model_signed"] is False
    assert body["rule"]["rule_text"] == "凡是要發布文章，都必須先由我簽名確認。"
    assert body["rule"]["activation_status"] == "waiting_owner_signature"
    assert body["rule"]["rule_scope"]["actions"] == ["publish"]


def test_four_store_reader_refuses_to_answer_without_authoritative_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    monkeypatch.setitem(main.MODEL_SETTINGS, "enabled", False)
    client = TestClient(main.app)

    response = client.post("/api/data-center/ask", json={"query": "沈族規則是什麼？"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_authoritative_evidence"
    assert body["model_called"] is False
    assert body["citations"] == []


def test_data_center_section_exposes_human_readable_storage_item(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    local_main = importlib.reload(main)
    local_main.save_storage_item({
        "item_id": "logic-readable-1",
        "task_id": "task-readable",
        "target": "logic",
        "status": "active",
        "content_hash": "abc123",
        "relative_path": "logic/logic-readable-1.json",
        "version": 1,
        "payload": {
            "summary": "商業文案規則表單",
            "content": "B層：不得編造價格；K層：沒有四庫資料不得宣稱正式引用。",
        },
    })

    response = TestClient(local_main.app).get("/api/data-center/logic")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["store_label"] == "規則庫"
    assert item["store_role"] == "可執行規則判準庫"
    assert item["status_label"] == "可引用"
    assert "規則庫" in item["model_reading_hint"]
    assert "不得編造價格" in item["content_text"]
    assert item["plain_summary"] == "商業文案規則表單"
