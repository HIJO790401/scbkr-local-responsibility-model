import importlib

from fastapi.testclient import TestClient

from apps.api import main
from core.rule_state.schemas import RuleStateEnum, SystemContextBlock
from core.rule_state.prompt_builder import build_system_prompt, declaration_parts


def fresh_main(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    return importlib.reload(main)


def test_v22_intent_router_separates_chat_rule_memory_and_confirmed_retrieval():
    cases = {
        "你好，今天聊聊介面": ("normal_chat", "SESSION_CONTEXT_ONLY"),
        "以後凡是發布內容都要先讓我確認，幫我建立規則": ("create_new_rule_confirmation", "DRAFTING"),
        "記住我之後發布前都要確認": ("create_confirmation", "DRAFTING"),
        "引用我們之前聊過的規則": ("data_center_query", "SESSION_CONTEXT_ONLY"),
    }
    for text, expected in cases.items():
        routed = main.route_chat_intent(text)
        assert (routed["intent"], routed["conversation_state"]) == expected
    assert main.route_chat_intent("引用我們之前聊過的規則")["retrieval_source"] == "storage_confirmed_four_stores_only"


def test_task_creation_exposes_uniform_v22_draft_object(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(local_main.app)
    task = client.post(
        "/api/tasks/create",
        json={
            "raw_input": "記住我之後發布前都要確認",
            "task_type": "general",
            "intent": "create_confirmation",
            "object_type": "memory",
            "create_scbkr_draft": True,
        },
    ).json()
    draft = task["draft_object"]
    assert draft["state"] == "DRAFTING"
    assert draft["object_type"] == "memory"
    assert draft["suggested_store"] == ["memory"]
    assert draft["owner_review_required"] is True
    assert draft["signature_required"] is True
    assert draft["storage_confirmed"] is False
    assert draft["final_store"] is None
    assert "store" in draft["blocked_actions_before_signature"]


def test_rule_draft_exposes_same_workflow_card_contract(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(local_main.app)
    payload = client.post("/api/rules/draft-from-text", json={"instruction": "Before publishing, require my approval."}).json()
    draft = payload["draft_object"]
    assert draft["object_type"] == "rule"
    assert draft["suggested_store"] == ["logic"]
    assert draft["signature_required"] is True
    assert draft["storage_confirmed"] is False


def test_rule_state_prompt_and_declarations_are_multilingual():
    prompt = build_system_prompt(SystemContextBlock(state=RuleStateEnum.RULEPACK_ACTIVE, active_rulepack_id="shenyao", active_rulepack_version="1", active_rulepack_stage="FORMAL", responsibility_holder="沈耀"))
    assert "使用者最新訊息所使用的語言" in prompt
    ja = declaration_parts(SystemContextBlock(state=RuleStateEnum.DRAFTING), "ja")
    ko = declaration_parts(SystemContextBlock(state=RuleStateEnum.EMPTY), "ko")
    assert "DRAFTING" in ja[0] and "署名" in ja[1]
    assert "EMPTY" in ko[0] and "활성 규칙" in ko[1]


def test_general_chat_requests_same_language_from_model(monkeypatch):
    monkeypatch.setattr(main, "_model_connected", lambda: True)
    monkeypatch.setitem(main.MODEL_SETTINGS, "mode", "local")
    monkeypatch.setattr(main, "_assert_model_gateway_call_allowed", lambda settings: None)
    captured = {}

    def fake_call(settings, messages):
        captured["messages"] = messages
        return {"choices": [{"message": {"content": "Hola, puedo ayudarte."}}]}

    monkeypatch.setattr(main, "_post_openai_compatible", fake_call)
    reply = TestClient(main.app).post("/api/chat/general", json={"message": "Hola, responde en español."}).json()
    assert "使用者最新訊息所使用的語言" in captured["messages"][0]["content"]
    assert "Hola" in reply["reply"]


def test_lightweight_local_model_uses_one_short_attempt_then_valid_base_draft(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    local_main.MODEL_SETTINGS.update({
        "enabled": True,
        "last_test_status": "success",
        "mode": "local",
        "provider": "lm_studio",
        "base_url": "http://127.0.0.1:1234/v1",
        "model_name": "qwen2.5-0.5b-instruct",
        "max_tokens": 4096,
    })
    calls = []

    def invalid_small_model(settings, messages, response_format=None):
        calls.append(settings["max_tokens"])
        return {"choices": [{"message": {"content": "not valid JSON"}}]}

    monkeypatch.setattr(local_main, "_post_openai_compatible", invalid_small_model)
    task = local_main.create_task({
        "raw_input": "記住：我的公開內容都要先由我確認。",
        "task_type": "general",
        "object_type": "memory",
        "create_scbkr_draft": True,
    })

    assert calls == []
    assert task["status"] == "waiting_user_confirm"
    assert task["scbkr"]["draft_source"] == "direct_scbkr_kernel_compiler"
    assert task["scbkr"]["compiler_report"]["status"] == "direct_kernel_compiled"
    assert task["draft_object"]["state"] == "DRAFTING"
