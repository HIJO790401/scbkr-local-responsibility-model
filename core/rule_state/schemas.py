"""Structured rule-state awareness contracts for every model call."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class RuleStateEnum(str, Enum):
    EMPTY = "EMPTY"
    DRAFTING = "DRAFTING"
    RULE_ACTIVE = "RULE_ACTIVE"
    RULEPACK_ACTIVE = "RULEPACK_ACTIVE"
    REVOKED = "REVOKED"
    ARCHIVED = "ARCHIVED"
    SUPERSEDED = "SUPERSEDED"


class SystemContextBlock(BaseModel):
    state: RuleStateEnum
    active_rule_id: str | None = None
    active_rule_version: str | None = None
    active_rulepack_id: str | None = None
    active_rulepack_version: str | None = None
    active_rulepack_stage: str | None = None
    owner_signature: str | None = None
    signed_at: datetime | None = None
    responsibility_holder: str | None = None
    self_declaration_required: bool = True

