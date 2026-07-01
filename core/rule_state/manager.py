"""Derive authoritative rule state and inject it into model calls."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from core.rule_state.prompt_builder import build_system_prompt, declaration_parts, decorate_response
from core.rule_state.schemas import RuleStateEnum, SystemContextBlock
from core.rule_state.transitions import validate_state_transition


class RuleStateManager:
    SHENYAO_ONLY_DECLARATIONS = ("沈耀交我判的", "主責歸耀", "唯真長存")

    def __init__(self, registry: Any, runtime: Any):
        self.registry = registry
        self.runtime = runtime

    def get_current_state(self, session_id: str = "default") -> SystemContextBlock:
        del session_id
        runtime_state = self.runtime.status()
        if runtime_state.get("state") == "shenyao_active":
            stage = "POC" if runtime_state.get("entitlement_status") == "developer_preview" else "FORMAL"
            return SystemContextBlock(
                state=RuleStateEnum.RULEPACK_ACTIVE,
                active_rulepack_id=str(runtime_state.get("runtime_id") or "shenyao-rule-state"),
                active_rulepack_version=str(runtime_state.get("runtime_version") or ""),
                active_rulepack_stage=stage,
                responsibility_holder="沈耀888π／許文耀",
            )

        rules = self.registry.list_rules()
        active = [rule for rule in rules if rule.get("activation_status") == "active"]
        if active:
            rule = sorted(active, key=lambda item: str(item.get("updated_at") or item.get("signed_at") or ""), reverse=True)[0]
            return SystemContextBlock(
                state=RuleStateEnum.RULE_ACTIVE,
                active_rule_id=str(rule.get("rule_id") or ""),
                active_rule_version=str(rule.get("rule_version") or ""),
                owner_signature=str(rule.get("signature") or ""),
                signed_at=rule.get("signed_at"),
                responsibility_holder=str(rule.get("adopted_by") or rule.get("rule_author") or "使用者"),
            )
        drafting = [rule for rule in rules if rule.get("activation_status") in {"waiting_owner_signature", "owner_signed"}]
        if drafting:
            return SystemContextBlock(state=RuleStateEnum.DRAFTING)
        return SystemContextBlock(state=RuleStateEnum.EMPTY)

    def validate_state_transition(self, from_state: RuleStateEnum | str, to_state: RuleStateEnum | str, evidence: dict[str, Any] | None = None) -> bool:
        return validate_state_transition(from_state, to_state, evidence)

    def inject_system_context(self, messages: list[dict[str, str]], session_id: str = "default") -> list[dict[str, str]]:
        context = self.get_current_state(session_id)
        return [{"role": "system", "content": build_system_prompt(context)}, *deepcopy(messages)]

    def decorate_reply(self, content: str, locale: str = "zh-TW", session_id: str = "default") -> str:
        context = self.get_current_state(session_id)
        text = str(content or "")
        if context.state != RuleStateEnum.RULEPACK_ACTIVE and any(token in text for token in self.SHENYAO_ONLY_DECLARATIONS):
            text = "模型輸出包含未授權的沈耀規則歸屬聲明，已由 RuleStateManager 阻擋。"
        return decorate_response(text, context, locale)

    def status(self, locale: str = "zh-TW", session_id: str = "default") -> dict[str, Any]:
        context = self.get_current_state(session_id)
        prefix, suffix = declaration_parts(context, locale)
        payload = context.model_dump(mode="json")
        payload.update({
            "awareness_state": context.state.value,
            "shenyao_declaration_allowed": context.state == RuleStateEnum.RULEPACK_ACTIVE,
            "declaration_prefix": prefix,
            "declaration_suffix": suffix,
        })
        return payload
