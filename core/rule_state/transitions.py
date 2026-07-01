"""Validated transitions for the SCBKR rule-state machine."""

from __future__ import annotations

from typing import Any

from core.rule_state.schemas import RuleStateEnum


ALLOWED_TRANSITIONS = {
    RuleStateEnum.EMPTY: {RuleStateEnum.DRAFTING, RuleStateEnum.RULEPACK_ACTIVE},
    RuleStateEnum.DRAFTING: {RuleStateEnum.EMPTY, RuleStateEnum.RULE_ACTIVE, RuleStateEnum.RULEPACK_ACTIVE, RuleStateEnum.ARCHIVED},
    RuleStateEnum.RULE_ACTIVE: {RuleStateEnum.DRAFTING, RuleStateEnum.RULEPACK_ACTIVE, RuleStateEnum.REVOKED, RuleStateEnum.ARCHIVED, RuleStateEnum.SUPERSEDED},
    RuleStateEnum.RULEPACK_ACTIVE: {RuleStateEnum.EMPTY, RuleStateEnum.DRAFTING, RuleStateEnum.RULE_ACTIVE, RuleStateEnum.REVOKED, RuleStateEnum.ARCHIVED, RuleStateEnum.SUPERSEDED},
    RuleStateEnum.REVOKED: {RuleStateEnum.EMPTY, RuleStateEnum.DRAFTING, RuleStateEnum.RULEPACK_ACTIVE},
    RuleStateEnum.ARCHIVED: {RuleStateEnum.EMPTY, RuleStateEnum.DRAFTING, RuleStateEnum.RULEPACK_ACTIVE},
    RuleStateEnum.SUPERSEDED: {RuleStateEnum.EMPTY, RuleStateEnum.DRAFTING, RuleStateEnum.RULEPACK_ACTIVE},
}


def validate_state_transition(from_state: RuleStateEnum | str, to_state: RuleStateEnum | str, evidence: dict[str, Any] | None = None) -> bool:
    current = RuleStateEnum(from_state)
    target = RuleStateEnum(to_state)
    proof = evidence or {}
    if current == target:
        return True
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"illegal rule-state transition: {current.value} -> {target.value}")
    if target == RuleStateEnum.RULE_ACTIVE:
        required = ("active_rule_id", "active_rule_version", "owner_signature", "signed_at")
        if any(not proof.get(field) for field in required):
            raise ValueError("RULE_ACTIVE requires a signed and versioned user rule")
    if target == RuleStateEnum.RULEPACK_ACTIVE:
        required = ("active_rulepack_id", "active_rulepack_version", "active_rulepack_stage", "rule_state_receipt")
        if any(not proof.get(field) for field in required):
            raise ValueError("RULEPACK_ACTIVE requires a verified runtime receipt, version, and stage")
        if proof.get("entitlement_status") not in {"active", "trialing", "developer_preview"}:
            raise ValueError("RULEPACK_ACTIVE requires a verified entitlement")
    return True

