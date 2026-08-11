import importlib
import json

from fastapi.testclient import TestClient

from apps.api import main
from core.rule_state.schemas import RuleStateEnum, SystemContextBlock
from core.rule_state.prompt_builder import build_system_prompt, declaration_parts


def fresh_main(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    return importlib.reload(main)


def valid_model_rulebook(subject: str):
    return {
        "S": {
            "content": f"本規則處理「{subject}」，由使用者擔任規則擁有者與最終確認者。",
            "explanation": "鎖定本次需求與使用者主體。",
            "missing_information": ["適用範圍"],
            "needs_user_confirmation": ["確認適用範圍"],
            "model_cannot_decide": ["使用者最終目的"],
            "risk_notes": ["主體不清可能套錯規則"],
        },
        "C": {
            "content": "先核對需求與資料，再建立可編輯草稿；若資料不足，則停止並要求使用者補充。",
            "explanation": "依序核對、草擬，缺資料時停止。",
            "missing_information": ["驗收順序"],
            "needs_user_confirmation": ["確認判斷順序"],
            "model_cannot_decide": ["是否接受草稿"],
            "risk_notes": ["跳過核對會造成錯誤"],
        },
        "B": {
            "content": "使用者未確認前不得發布、入庫或執行；資料不足、範圍不明或越權時必須停止。",
            "explanation": "定義禁止事項與停止條件。",
            "missing_information": ["例外條件"],
            "needs_user_confirmation": ["確認禁止事項"],
            "model_cannot_decide": ["是否解除停止"],
            "risk_notes": ["越權會造成外部影響"],
        },
        "K": {
            "content": "只可引用使用者已確認的本次需求與正式資料；未確認內容、聊天猜測與 VECTOR 候選不可引用。",
            "explanation": "區分正式依據與不可引用候選。",
            "missing_information": ["正式資料清單"],
            "needs_user_confirmation": ["確認可引用資料"],
            "model_cannot_decide": ["資料是否真實"],
            "risk_notes": ["錯誤引用會污染結果"],
        },
        "R": {
            "content": "使用者逐欄驗收並簽名後規則才成立；模型不能簽名、入庫或啟用，錯誤時由使用者回放並修復。",
            "explanation": "責任、驗收、簽名與修復留給使用者。",
            "missing_information": ["簽名聲明"],
            "needs_user_confirmation": ["使用者簽名"],
            "model_cannot_decide": ["現實行動責任"],
            "risk_notes": ["未簽名規則不得引用"],
        },
        "rule_summary": f"{subject}的可編輯 SCBKR 規則草稿。",
        "missing_information": ["適用範圍"],
        "user_confirmation_items": ["逐欄確認 S/C/B/K/R"],
        "model_cannot_decide": ["是否正式啟用"],
        "risk_reminders": ["模型不得代替使用者簽名"],
        "next_actions": ["使用者修改並簽名"],
    }


def configure_connected_model(local_main, monkeypatch, subject: str):
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
    payload = valid_model_rulebook(subject)
    monkeypatch.setattr(
        local_main,
        "_post_openai_compatible",
        lambda settings, messages, response_format=None: {
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 180},
        },
    )


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
    configure_connected_model(local_main, monkeypatch, "記住我之後發布前都要確認")
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
    configure_connected_model(local_main, monkeypatch, "Before publishing, require my approval.")
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
    reply = TestClient(main.app).post("/api/chat/general", json={
        "message": "Hola, responde en español.",
        "chat_history": [
            {"role": "user", "content": "Mi nombre es Ana."},
            {"role": "assistant", "content": "Entendido."},
        ],
    }).json()
    assert "使用者最新訊息所使用的語言" in captured["messages"][0]["content"]
    assert captured["messages"][-3:] == [
        {"role": "user", "content": "Mi nombre es Ana."},
        {"role": "assistant", "content": "Entendido."},
        {"role": "user", "content": "Hola, responde en español."},
    ]
    assert "Hola" in reply["reply"]


def test_signed_rule_answer_does_not_send_chat_history_as_formal_context(monkeypatch):
    monkeypatch.setattr(main, "_model_connected", lambda: True)
    monkeypatch.setitem(main.MODEL_SETTINGS, "mode", "local")
    monkeypatch.setattr(main, "_assert_model_gateway_call_allowed", lambda settings: None)
    monkeypatch.setattr(main, "_build_four_store_context", lambda *args, **kwargs: {"evidence_packet": {"citations": []}})
    monkeypatch.setattr(main, "build_current_rule_package", lambda *args, **kwargs: {
        "matched_rules": [{"rule_id": "signed-rule", "signature_status": "owner_signed", "active": True}],
        "citable_data": [],
        "user_preferences": [],
        "retrieval_candidates": [],
        "chat_context_used": False,
        "prohibitions": ["不得編造"],
    })
    captured = {}

    def fake_call(settings, messages):
        captured["messages"] = messages
        return {"choices": [{"message": {"content": "依已簽名規則回答。"}}]}

    monkeypatch.setattr(main, "_post_openai_compatible", fake_call)
    response = TestClient(main.app).post("/api/chat/general", json={
        "message": "請依規則判斷",
        "chat_history": [{"role": "user", "content": "這是不能當正式依據的舊聊天"}],
    })
    assert response.status_code == 200
    assert response.json()["route_mode"] == "answer_with_rules"
    assert response.json()["chat_context_used"] is False
    assert "不能當正式依據的舊聊天" not in str(captured["messages"])


def test_lightweight_local_model_bad_output_stops_without_base_draft(tmp_path, monkeypatch):
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
    local_main.PERMISSIONS["model_generate"] = True
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

    assert calls == [1200, 1200, 1200]
    assert task["status"] == "model_rulebook_schema_invalid"
    assert task["fallback_used"] is False
    assert "scbkr" not in task
    assert task["draft_object"]["state"] == "MODEL_SCHEMA_INVALID"
