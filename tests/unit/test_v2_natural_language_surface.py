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
