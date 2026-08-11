"""Derive authoritative rule state and inject it into model calls."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from core.rule_state.prompt_builder import build_system_prompt, declaration_parts, decorate_response
from core.rule_state.schemas import RuleStateEnum, SystemContextBlock
from core.rule_state.transitions import validate_state_transition


class RuleStateManager:
    SHENYAO_ONLY_DECLARATIONS = ("沈耀交我判的", "主責歸耀", "唯真長存")

    def __init__(self, registry: Any, runtime: Any, stored_rule_provider: Any | None = None):
        self.registry = registry
        self.runtime = runtime
        self.stored_rule_provider = stored_rule_provider

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
        if self.stored_rule_provider is not None:
            stored_tasks = self.stored_rule_provider() or []
            active_tasks = [
                task
                for task in stored_tasks
                if task.get("storage_confirmed") is True
                and task.get("physical_write_performed") is True
                and task.get("review_passed") is True
                and (task.get("scbkr") or {}).get("signature_status") == "owner_signed"
                and (task.get("compiled_rule") or {}).get("active") is True
            ]
            if active_tasks:
                task = sorted(
                    active_tasks,
                    key=lambda item: str((item.get("storage_result") or {}).get("written_items", [{}])[0].get("stored_at") or item.get("confirmed_at") or ""),
                    reverse=True,
                )[0]
                compiled = task.get("compiled_rule") or {}
                scbkr = task.get("scbkr") or {}
                return SystemContextBlock(
                    state=RuleStateEnum.RULE_ACTIVE,
                    active_rule_id=str(compiled.get("rule_id") or f"local-rule:{task.get('task_id')}"),
                    active_rule_version=f"v{compiled.get('version') or 1}.0",
                    owner_signature=str(scbkr.get("signature") or "owner_signed"),
                    signed_at=scbkr.get("confirmed_at") or task.get("confirmed_at"),
                    responsibility_holder=str(scbkr.get("confirmed_by") or "user"),
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
        text = self.guard_reply(content, session_id=session_id)
        return decorate_response(text, context, locale)

    def guard_reply(self, content: str, session_id: str = "default") -> str:
        """Block unauthorized rule-pack ownership language without claiming a rule was applied."""
        context = self.get_current_state(session_id)
        text = str(content or "")
        if context.state != RuleStateEnum.RULEPACK_ACTIVE and any(token in text for token in self.SHENYAO_ONLY_DECLARATIONS):
            text = "模型輸出包含未授權的沈耀規則歸屬聲明，已由 RuleStateManager 阻擋。"
        return text

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
