"""Public FREE rule-state runtime.

The public repository validates user-owned local rules only. Commercial
entitlements and protected author runtimes are intentionally not included.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
from typing import Any

from core.runtime_settings import load_runtime_section, save_runtime_section

RUNTIME_CATALOG = (
    {
        "runtime_id": "scbkr-free-local",
        "name": {"zh-TW": "SCBKR 免費本機規則", "en": "SCBKR FREE Local Rules"},
        "author": "許文耀／沈耀888pi",
        "description": {
            "zh-TW": "驗證使用者自己的 S/C/B/K/R 草案；只有使用者簽名後才能成為正式本機規則。",
            "en": "Validates user-owned S/C/B/K/R drafts. Only user-signed rules can become formal local authority.",
        },
        "versions": [{"version": "2.3.0", "channel": "public", "modes": ["free_local_rules"]}],
        "source_visibility": "public_free_edition",
    },
)

DEFAULT_RULE_STATE = {
    "state": "independent",
    "runtime_id": "scbkr-free-local",
    "runtime_version": "2.3.0",
    "mode": "free_local_rules",
    "update_channel": "public",
    "selected_at": None,
    "updated_at": None,
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


class RuleStateRuntime:
    def status(self) -> dict[str, Any]:
        stored = load_runtime_section("rule_state", DEFAULT_RULE_STATE)
        if stored.get("state") != "independent" or stored.get("runtime_id") != "scbkr-free-local":
            stored = {**DEFAULT_RULE_STATE, "updated_at": _now(), "deactivation_reason": "public_free_edition"}
            save_runtime_section("rule_state", stored)
        return {**stored, "effective_label": "本機使用者規則", "receipt_hash": _hash(stored)}

    def catalog(self) -> list[dict[str, Any]]:
        return deepcopy(list(RUNTIME_CATALOG))

    def select(self, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        raise PermissionError("the public FREE edition has no protected runtime selector")

    def deactivate(self, reason: str = "public_free_edition") -> dict[str, Any]:
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
        return {
            "rule_text": text,
            "rule_state": state,
            "checks": checks,
            "missing_dimensions": missing,
            "status": "free_structure_validated" if not missing else "owner_review",
            "shenyao_verified": False,
            "claim_allowed": False,
            "message": "五維結構完整，仍需使用者審查與簽名。" if not missing else "已偵測缺漏，需補齊後再簽名。",
            "validation_hash": _hash({"text": text, "checks": checks, "state": state.get("receipt_hash")}),
        }
