from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import apps.api.main as main
from core.rule_state.manager import RuleStateManager
from core.rule_state.prompt_builder import CONTEXT_POLLUTION_GUARD, build_system_prompt, decorate_response
from core.rule_state.schemas import RuleStateEnum, SystemContextBlock
from core.rule_state.transitions import validate_state_transition


class Registry:
    def __init__(self, rules=None):
        self.rules = rules or []

    def list_rules(self):
        return self.rules


class Runtime:
    def __init__(self, state=None):
        self.state = state or {"state": "independent"}

    def status(self):
        return self.state


def test_empty_cannot_skip_signature_to_rule_active():
    with pytest.raises(ValueError, match="illegal"):
        validate_state_transition(RuleStateEnum.EMPTY, RuleStateEnum.RULE_ACTIVE, {})


def test_rule_active_requires_signed_versioned_evidence():
    with pytest.raises(ValueError, match="signed and versioned"):
        validate_state_transition(RuleStateEnum.DRAFTING, RuleStateEnum.RULE_ACTIVE, {"active_rule_id": "rule:1"})
    assert validate_state_transition(RuleStateEnum.DRAFTING, RuleStateEnum.RULE_ACTIVE, {
        "active_rule_id": "rule:1",
        "active_rule_version": "v1.0.0",
        "owner_signature": "owner_ack:hash",
        "signed_at": "2026-07-01T00:00:00Z",
    }) is True


def test_rulepack_active_requires_verified_receipt_and_entitlement():
    evidence = {
        "active_rulepack_id": "shenyao-rule-state",
        "active_rulepack_version": "1.2.0",
        "active_rulepack_stage": "POC",
        "rule_state_receipt": "receipt",
        "entitlement_status": "developer_preview",
    }
    assert validate_state_transition(RuleStateEnum.EMPTY, RuleStateEnum.RULEPACK_ACTIVE, evidence) is True
    with pytest.raises(ValueError, match="verified entitlement"):
        validate_state_transition(RuleStateEnum.EMPTY, RuleStateEnum.RULEPACK_ACTIVE, {**evidence, "entitlement_status": "not_configured"})


def test_manager_derives_all_primary_states():
    assert RuleStateManager(Registry(), Runtime()).get_current_state().state == RuleStateEnum.EMPTY
    assert RuleStateManager(Registry([{"activation_status": "waiting_owner_signature"}]), Runtime()).get_current_state().state == RuleStateEnum.DRAFTING

    active_rule = {
        "rule_id": "rule:user-1",
        "rule_version": "v1.0.0",
        "rule_author": "User",
        "signature": "owner_ack:hash",
        "signed_at": "2026-07-01T00:00:00Z",
        "updated_at": "2026-07-01T00:01:00Z",
        "activation_status": "active",
    }
    user_context = RuleStateManager(Registry([active_rule]), Runtime()).get_current_state()
    assert user_context.state == RuleStateEnum.RULE_ACTIVE
    assert user_context.responsibility_holder == "User"

    protected = Runtime({
        "state": "shenyao_active",
        "runtime_id": "shenyao-rule-state",
        "runtime_version": "1.2.0",
        "entitlement_status": "developer_preview",
    })
    shenyao_context = RuleStateManager(Registry([active_rule]), protected).get_current_state()
    assert shenyao_context.state == RuleStateEnum.RULEPACK_ACTIVE
    assert shenyao_context.responsibility_holder == "沈耀888π／許文耀"


def test_shenyao_declaration_only_appears_in_verified_rulepack_state():
    empty = decorate_response("可以正常聊天。", SystemContextBlock(state=RuleStateEnum.EMPTY))
    drafting = decorate_response("草擬內容。", SystemContextBlock(state=RuleStateEnum.DRAFTING))
    user_rule = decorate_response("使用者規則結果。", SystemContextBlock(
        state=RuleStateEnum.RULE_ACTIVE,
        active_rule_id="rule:user-1",
        active_rule_version="v1.0.0",
        signed_at=datetime.now(UTC),
        responsibility_holder="User",
    ))
    shenyao = decorate_response("框架判斷結果。", SystemContextBlock(
        state=RuleStateEnum.RULEPACK_ACTIVE,
        active_rulepack_id="shenyao-rule-state",
        active_rulepack_version="1.2.0",
        active_rulepack_stage="POC",
        responsibility_holder="沈耀888π／許文耀",
    ))

    for output in (empty, drafting, user_rule):
        assert "沈耀交我判的" not in output
        assert "主責歸耀" not in output
        assert "唯真長存" not in output
    assert "沈耀交我判的" in shenyao
    assert "主責歸耀" in shenyao
    assert "唯真長存" in shenyao
    assert "OwnerReview" in shenyao

    blocked = RuleStateManager(Registry(), Runtime()).decorate_reply("主責歸耀。唯真長存。")
    assert "未授權" in blocked
    assert "主責歸耀" not in blocked
    assert "唯真長存" not in blocked


def test_system_context_is_injected_before_existing_messages():
    manager = RuleStateManager(Registry(), Runtime())
    messages = manager.inject_system_context([{"role": "user", "content": "hello"}])
    assert messages[0]["role"] == "system"
    assert "規則或主責的擁有者" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "hello"}

    active_prompt = build_system_prompt(SystemContextBlock(
        state=RuleStateEnum.RULEPACK_ACTIVE,
        active_rulepack_id="shenyao-rule-state",
        active_rulepack_version="1.2.0",
        active_rulepack_stage="FORMAL",
        responsibility_holder="沈耀888π／許文耀",
    ))
    assert CONTEXT_POLLUTION_GUARD in active_prompt
    assert "若要求 JSON，不得把自我陳述混入 JSON" in active_prompt


def test_general_chat_exposes_shenyao_declaration_only_when_verified_runtime_is_active(monkeypatch):
    protected = Runtime({
        "state": "shenyao_active",
        "runtime_id": "shenyao-rule-state",
        "runtime_version": "1.2.0",
        "entitlement_status": "developer_preview",
    })
    protected_manager = RuleStateManager(Registry(), protected)
    monkeypatch.setattr(main, "_rule_state_manager", lambda: protected_manager)
    monkeypatch.setattr(main, "_model_connected", lambda: True)
    monkeypatch.setitem(main.MODEL_SETTINGS, "mode", "external")
    monkeypatch.setattr(main, "_assert_model_gateway_call_allowed", lambda settings: None)
    monkeypatch.setattr(main, "_post_openai_compatible", lambda settings, messages: {"choices": [{"message": {"content": "判斷內容"}}]})

    response = TestClient(main.app).post("/api/chat/general", json={"message": "請判斷這件事"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["rule_state"]["awareness_state"] == "RULEPACK_ACTIVE"
    assert payload["rule_state"]["shenyao_declaration_allowed"] is True
    assert "沈耀交我判的" in payload["reply"]
    assert "主責歸耀" in payload["reply"]
    assert "唯真長存" in payload["reply"]


def test_general_chat_blocks_unverified_shenyao_ownership_claim(monkeypatch):
    empty_manager = RuleStateManager(Registry(), Runtime())
    monkeypatch.setattr(main, "_rule_state_manager", lambda: empty_manager)
    monkeypatch.setattr(main, "_model_connected", lambda: True)
    monkeypatch.setitem(main.MODEL_SETTINGS, "mode", "external")
    monkeypatch.setattr(main, "_assert_model_gateway_call_allowed", lambda settings: None)
    monkeypatch.setattr(main, "_post_openai_compatible", lambda settings, messages: {"choices": [{"message": {"content": "主責歸耀。唯真長存。"}}]})

    payload = TestClient(main.app).post("/api/chat/general", json={"message": "hello"}).json()
    assert payload["rule_state"]["awareness_state"] == "EMPTY"
    assert payload["rule_state"]["shenyao_declaration_allowed"] is False
    assert "未授權" in payload["reply"]
    assert "主責歸耀" not in payload["reply"]
