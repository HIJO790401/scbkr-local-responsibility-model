"""Versioned Rule State selection, entitlement, and overlay validation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import hmac
import json
import os
from typing import Any

from core.runtime_settings import load_runtime_section, save_runtime_section

RUNTIME_CATALOG = (
    {
        "runtime_id": "shenyao-rule-state",
        "name": {"zh-TW": "沈耀規則狀態", "en": "ShenYao Rule State"},
        "author": "沈耀888pi／許文耀",
        "description": {
            "zh-TW": "以主語、因果、邊界、依據與責任驗算使用者自訂規則。私有規則核心不隨客戶端散布。",
            "en": "Validates custom rules through subject, causality, boundary, key, and responsibility gates. The private rule core is not distributed to clients.",
        },
        "versions": [
            {
                "version": "1.2.0",
                "channel": "stable",
                "released_at": "2025-08-10T21:02:18+08:00",
                "modes": ["black_shield_strict", "responsibility_audit", "draft_compiler"],
                "changelog": ["Subject lock", "SCBKR weighted audit", "RETURN/VOID routing", "OwnerRecall"],
            }
        ],
        "billing": {"monthly": "pending_stripe_price", "annual": "pending_stripe_price"},
        "source_visibility": "protected_runtime",
    },
)

DEFAULT_RULE_STATE = {
    "state": "independent",
    "runtime_id": None,
    "runtime_version": None,
    "mode": "independent_user_rules",
    "update_channel": "stable",
    "entitlement_status": "not_configured",
    "subscriber_id": None,
    "expires_at": None,
    "offline_grace_until": None,
    "selected_at": None,
    "updated_at": None,
}

DEFAULT_ENTITLEMENT = {
    "status": "not_configured",
    "runtime_id": None,
    "subscriber_id": None,
    "allowed_versions": [],
    "expires_at": None,
    "offline_grace_until": None,
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _entitlement_is_current(record: dict[str, Any]) -> bool:
    if str(record.get("status") or "") not in {"active", "trialing"}:
        return False
    deadline = record.get("offline_grace_until") or record.get("expires_at")
    if not deadline:
        return True
    try:
        parsed = datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
    except ValueError:
        return False
    return parsed >= datetime.now(UTC)


class RuleStateRuntime:
    def status(self) -> dict[str, Any]:
        state = load_runtime_section("rule_state", DEFAULT_RULE_STATE)
        return {**state, "effective_label": "沈耀規則狀態" if state.get("state") == "shenyao_active" else "獨立使用者規則", "receipt_hash": _hash(state)}

    def catalog(self) -> list[dict[str, Any]]:
        return deepcopy(list(RUNTIME_CATALOG))

    def select(self, payload: dict[str, Any]) -> dict[str, Any]:
        runtime_id = str(payload.get("runtime_id") or "")
        runtime = next((item for item in RUNTIME_CATALOG if item["runtime_id"] == runtime_id), None)
        if not runtime:
            raise ValueError("unknown rule state runtime")
        version = str(payload.get("version") or "")
        release = next((item for item in runtime["versions"] if item["version"] == version), None)
        if not release:
            raise ValueError("unknown runtime version")
        mode = str(payload.get("mode") or "")
        if mode not in release["modes"]:
            raise ValueError("mode is not available in this version")
        preview_requested = payload.get("developer_preview") is True
        preview_secret = os.environ.get("SCBKR_OWNER_PREVIEW_TOKEN", "")
        supplied_preview_secret = str(payload.get("preview_token") or "")
        preview = bool(preview_secret) and preview_requested and hmac.compare_digest(supplied_preview_secret, preview_secret)
        if preview_requested and not preview_secret:
            raise PermissionError("owner developer preview is not configured on this runtime")
        if preview_requested and not preview:
            raise PermissionError("invalid owner developer preview authorization")

        entitlement_record = load_runtime_section("rule_state_entitlement", DEFAULT_ENTITLEMENT)
        entitlement_status = str(entitlement_record.get("status") or "")
        allowed_versions = entitlement_record.get("allowed_versions") or []
        entitled = (
            _entitlement_is_current(entitlement_record)
            and entitlement_record.get("runtime_id") == runtime_id
            and (not allowed_versions or version in allowed_versions)
        )
        if not entitled and not preview:
            raise PermissionError("verified subscription entitlement or authorized developer preview is required")
        selected = {
            **DEFAULT_RULE_STATE,
            "state": "shenyao_active",
            "runtime_id": runtime_id,
            "runtime_version": version,
            "mode": mode,
            "update_channel": str(payload.get("update_channel") or release["channel"]),
            "entitlement_status": "developer_preview" if preview else entitlement_status,
            "subscriber_id": None if preview else entitlement_record.get("subscriber_id"),
            "expires_at": None if preview else entitlement_record.get("expires_at"),
            "offline_grace_until": None if preview else entitlement_record.get("offline_grace_until"),
            "selected_at": _now(),
            "updated_at": _now(),
        }
        save_runtime_section("rule_state", selected)
        return self.status()

    def deactivate(self, reason: str = "user_selected_independent") -> dict[str, Any]:
        state = {**DEFAULT_RULE_STATE, "updated_at": _now(), "deactivation_reason": reason}
        save_runtime_section("rule_state", state)
        return self.status()

    def validate_overlay(self, rule_text: str) -> dict[str, Any]:
        text = str(rule_text or "").strip()
        if not text:
            raise ValueError("rule_text is required")
        state = self.status()
        checks = {
            "S": any(token in text for token in ("我", "使用者", "作者", "主體", "誰")),
            "C": any(token in text for token in ("如果", "當", "因為", "才", "流程", "之後")),
            "B": any(token in text for token in ("不得", "只能", "禁止", "範圍", "邊界", "除非")),
            "K": any(token in text for token in ("依據", "引用", "證據", "簽名", "版本", "來源")),
            "R": any(token in text for token in ("負責", "承擔", "驗收", "修復", "簽收", "責任")),
        }
        missing = [key for key, passed in checks.items() if not passed]
        protected = state["state"] == "shenyao_active"
        return {
            "rule_text": text,
            "rule_state": state,
            "checks": checks,
            "missing_dimensions": missing,
            "status": "rule_state_validated" if protected and not missing else "owner_review" if protected else "independent_unverified",
            "shenyao_verified": protected and not missing,
            "claim_allowed": protected and not missing,
            "message": "已通過沈耀規則狀態驗算。" if protected and not missing else "已偵測缺漏，需補齊後再簽名。" if protected else "未套用沈耀規則狀態，不提供沈耀邏輯完整性保證。",
            "validation_hash": _hash({"text": text, "checks": checks, "state": state.get("receipt_hash")}),
        }
