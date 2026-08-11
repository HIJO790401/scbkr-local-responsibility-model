import importlib
import json

from fastapi.testclient import TestClient

from apps.api import main


def test_natural_language_rule_is_saved_as_unsigned_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    local_main = importlib.reload(main)
    local_main.MODEL_SETTINGS.update({
        "enabled": True,
        "last_test_status": "success",
        "mode": "local",
        "provider": "lm_studio",
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key": "local",
        "model_name": "fake-local-scbkr",
    })
    local_main.PERMISSIONS["model_generate"] = True
    model_draft = {
        "S": {"content": "本規則適用於使用者準備發布文章的情境。", "explanation": "鎖定文章發布任務與使用者主體。", "missing_information": ["文章類型"], "needs_user_confirmation": ["確認適用文章"], "model_cannot_decide": ["是否發布"], "risk_notes": ["可能套錯文章"]},
        "C": {"content": "先完成文章草稿，再交使用者核對；若未確認，則停止發布。", "explanation": "先草擬、再確認，未確認就停止。", "missing_information": ["核對流程"], "needs_user_confirmation": ["確認流程"], "model_cannot_decide": ["是否通過"], "risk_notes": ["跳過核對可能誤發"]},
        "B": {"content": "未取得使用者確認與簽名前不得發布；內容或責任不清時必須停止。", "explanation": "限制發布並定義停止條件。", "missing_information": ["例外條件"], "needs_user_confirmation": ["確認禁止事項"], "model_cannot_decide": ["是否解除停止"], "risk_notes": ["未授權發布風險"]},
        "K": {"content": "只可引用使用者已確認的文章與正式資料；未確認內容、聊天猜測與 VECTOR 候選不可引用。", "explanation": "區分正式依據與候選。", "missing_information": ["正式資料"], "needs_user_confirmation": ["確認資料"], "model_cannot_decide": ["資料真實性"], "risk_notes": ["錯誤引用風險"]},
        "R": {"content": "使用者驗收並簽名後規則才成立；模型不能簽名、入庫或啟用，錯誤時由使用者回放並修復。", "explanation": "簽名與責任留給使用者。", "missing_information": ["簽名聲明"], "needs_user_confirmation": ["使用者簽名"], "model_cannot_decide": ["現實責任"], "risk_notes": ["未簽名不得引用"]},
        "rule_summary": "文章發布前必須由使用者簽名確認。",
        "missing_information": ["文章類型"],
        "user_confirmation_items": ["逐欄確認 S/C/B/K/R"],
        "model_cannot_decide": ["是否正式發布"],
        "risk_reminders": ["模型不得代簽"],
        "next_actions": ["使用者修改並簽名"],
    }
    monkeypatch.setattr(
        local_main,
        "_post_openai_compatible",
        lambda settings, messages, response_format=None: {
            "choices": [{"message": {"content": json.dumps(model_draft, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 180},
        },
    )
    client = TestClient(local_main.app)

    response = client.post("/api/rules/draft-from-text", json={"instruction": "凡是要發布文章，都必須先由我簽名確認。"})

    assert response.status_code == 200
    body = response.json()
    assert body["compiled_from"] == "model_assisted_rulebook"
    assert body["model_signed"] is False
    assert body["status"] == "waiting_user_confirm"
    assert body["model_used"] is True
    assert body["fallback_used"] is False
    assert body["scbkr"]["confirmation_status"] == "draft"
    assert body["scbkr"]["R"]["signature_status"] == "waiting_owner_signature"


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
