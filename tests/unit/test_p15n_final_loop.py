from apps.api.main import _build_four_store_context, chat_intent


def test_chat_intent_routes_confirmation_and_typo_without_general_markdown():
    for text in ["你能生成責任鏈任務確認單嗎", "幫我做責任鏈", "幫我建確認單", "責任練任務確認單"]:
        data = chat_intent({"message": text})
        assert data["intent"] == "create_confirmation"


def test_chat_intent_suggests_confirmation_card_for_planning_request():
    data = chat_intent({"message": "我想做一個商業文案計畫"})
    assert data["intent"] == "suggest_create_confirmation"
    assert data["suggestion"]["title"] == "可生成 SCBKR 確認單"
    assert "生成確認單" in data["suggestion"]["actions"]


def test_retrieval_gate_rejects_unrelated_ui_rule_for_braised_pork_copy(monkeypatch):
    def fake_query(*args, **kwargs):
        return {"candidates": [{"case_id": "ui-1", "case_type": "logic", "retrieval_text": "UI 介面佈局原則：按鈕必須靠右", "score": None}]}

    monkeypatch.setattr("apps.api.main.query_retrieval_cases", fake_query)
    monkeypatch.setattr("apps.api.main.list_persisted_storage_items", lambda limit=50: [])
    monkeypatch.setattr("apps.api.main.list_persisted_memory_rules", lambda limit=20: [])
    context = _build_four_store_context("滷肉飯 文案")
    assert context["hits"] == []
    assert context["rejected_hits"][0]["status"] == "未採用：相關性不足"
