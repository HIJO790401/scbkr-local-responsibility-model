import importlib

from fastapi.testclient import TestClient

from apps.api import main
from core.rule_assist import evaluate_rule_assist


def fresh_main(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    return importlib.reload(main)


def test_free_plan_builds_structured_draft_without_model_authority():
    assessment = evaluate_rule_assist("記住我發布前都要確認", "FREE", target_mode="rule")
    assert assessment["plan_level"] == "FREE"
    assert assessment["state"] == "DRAFT_STRUCTURED"
    assert assessment["capability_state"] == "free_model_assisted_structure"
    assert assessment["owner_signature_required"] is True
    assert assessment["model_claim_limit"] == "model_may_draft_never_sign_or_close"


def test_unknown_plan_normalizes_to_free_and_blocks_empty_acknowledgement():
    assessment = evaluate_rule_assist("好的", "PRIVATE", target_mode="chat")
    assert assessment["plan_level"] == "FREE"
    assert assessment["state"] == "OWNER_REVIEW"
    assert assessment["gates"][0]["gate_id"].startswith("L0")
    assert "EMPTY_ACKNOWLEDGEMENT" in assessment["gates"][0]["findings"]
    assert "S" in assessment["gates"][1]["fills"]
    assert "auto_close" in assessment["gates"][1]["model_forbidden"]


def test_sandbox_cannot_masquerade_as_connected_rulebook_author(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    local_main.MODEL_SETTINGS.update({"provider": "sandbox_mock_model", "mode": "sandbox", "model_name": "sandbox_mock_model"})
    client = TestClient(local_main.app)
    client.post("/api/rule-assist/settings", json={"plan_level": "FREE"})
    task = client.post(
        "/api/tasks/create",
        json={
            "raw_input": "幫我生成商業文案規則表單",
            "task_type": "general",
            "create_scbkr_draft": True,
        },
    ).json()

    assert task["status"] == "model_unavailable"
    assert task["model_used"] is False
    assert "scbkr" not in task

    response = client.post(
        f"/api/tasks/{task['task_id']}/scbkr/patch-draft",
        json={"layer": "B", "instruction": "B層不對，補上不能發布與不能編造價格"},
    )
    assert response.status_code == 409
    assert "model-authored SCBKR draft" in response.json()["detail"]


def test_rule_assist_api_forces_free_and_reports_model_unavailable_without_fallback(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(local_main.app)
    updated = client.post("/api/rule-assist/settings", json={"plan_level": "PRIVATE"}).json()
    assert updated["plan_level"] == "FREE"

    reply = client.post("/api/chat/general", json={"message": "你好，這裡可以怎麼建立規則？"}).json()
    assert reply["reply_source"] == "model_unavailable"
    assert reply["rule_assist"]["plan_level"] == "FREE"
    assert reply["model_used"] is False


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
