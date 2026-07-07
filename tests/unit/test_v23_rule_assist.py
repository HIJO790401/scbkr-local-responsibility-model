import importlib

from fastapi.testclient import TestClient

from apps.api import main
from core.rule_assist import evaluate_rule_assist


def fresh_main(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    return importlib.reload(main)


def test_free_plan_stays_draft_only():
    assessment = evaluate_rule_assist("記住我發布前都要確認", "FREE", target_mode="rule")
    assert assessment["plan_level"] == "FREE"
    assert assessment["state"] == "DRAFT"
    assert assessment["capability_state"] == "basic_chat_and_user_signed_draft"
    assert assessment["gates"][0]["status"] == "draft_only"


def test_nt690_blocks_empty_acknowledgement_and_fills_structure():
    assessment = evaluate_rule_assist("好的", "NT690", target_mode="chat")
    assert assessment["plan_level"] == "NT690"
    assert assessment["state"] == "OWNER_REVIEW"
    assert assessment["gates"][0]["gate_id"].startswith("L0")
    assert "EMPTY_ACKNOWLEDGEMENT" in assessment["gates"][0]["findings"]
    assert "S" in assessment["gates"][1]["fills"]
    assert "auto_close" in assessment["gates"][1]["model_forbidden"]


def test_nt3300_requires_owner_signature_for_high_risk_tool_action():
    assessment = evaluate_rule_assist("幫我上網搜尋後寄信發布給客戶", "NT3300", target_mode="tool")
    assert assessment["plan_level"] == "NT3300"
    assert assessment["state"] == "OWNER_SIGNATURE_REQUIRED"
    refusal = assessment["gates"][-1]
    assert refusal["gate_id"].endswith("SERVICE-REFUSAL-GATE")
    assert refusal["status"] == "owner_signature_required"
    assert "external_send" in refusal["blocked_without_signature"]


def test_rule_assist_api_persists_plan_and_chat_falls_back_without_model(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(local_main.app)
    updated = client.post("/api/rule-assist/settings", json={"plan_level": "NT3300"}).json()
    assert updated["plan_level"] == "NT3300"

    reply = client.post("/api/chat/general", json={"message": "你好，這裡可以怎麼建立規則？"}).json()
    assert reply["reply_source"] == "rule_assist_local_fallback"
    assert reply["rule_assist"]["plan_level"] == "NT3300"
    assert "四庫" in reply["reply"]


def test_general_chat_guards_traditional_chinese_and_marks_no_four_store(monkeypatch):
    monkeypatch.setattr(main, "_model_connected", lambda: True)
    monkeypatch.setitem(main.MODEL_SETTINGS, "mode", "local")
    monkeypatch.setattr(main, "_assert_model_gateway_call_allowed", lambda settings: None)
    monkeypatch.setattr(
        main,
        "_post_openai_compatible",
        lambda settings, messages: {"choices": [{"message": {"content": "这里有什么可以帮您？"}}]},
    )

    reply = TestClient(main.app).post("/api/chat/general", json={"message": "你好，請繁體中文回答。", "locale": "zh-TW"}).json()
    assert "這裡有什麼可以幫您" in reply["reply"]
    assert "目前沒有已簽名引用" in reply["reply"]
