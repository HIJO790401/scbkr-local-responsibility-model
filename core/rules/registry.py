"""Persistent, versioned SCBKR 2.0 Rule Registry."""
from __future__ import annotations

import base64
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.storage.runtime_paths import current_data_dir

RULE_SOURCES = {
    "user_defined",
    "shenyao_signed_rulepack",
    "enterprise_internal",
    "third_party",
    "model_draft",
}
RULE_STATUSES = {
    "draft",
    "waiting_owner_signature",
    "owner_signed",
    "active",
    "disabled",
    "revoked",
    "archived",
    "superseded",
}
AUTOMATION_LEVELS = {"draft_only", "manual", "semi_auto", "full_auto"}
RISK_LEVELS = {"low", "medium", "high", "critical"}
IMMUTABLE_RULE_FIELDS = (
    "rule_id",
    "rule_name",
    "rule_text",
    "rule_author",
    "rule_source",
    "rule_version",
    "rule_scope",
    "allowed_tools",
    "denied_tools",
    "automation_level",
    "risk_level",
    "supersedes",
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_rule_hash(rule: dict[str, Any]) -> str:
    immutable = {key: rule.get(key) for key in IMMUTABLE_RULE_FIELDS if key in rule}
    return hashlib.sha256(_canonical(immutable)).hexdigest()


def _safe_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("rule list fields must be arrays of strings")
    return list(dict.fromkeys(item.strip() for item in value if item.strip()))


def normalize_rule(payload: dict[str, Any], *, source_pack_id: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("rule must be an object")
    now = _now()
    source = str(payload.get("rule_source") or "user_defined")
    if source not in RULE_SOURCES:
        raise ValueError("invalid rule_source")
    automation = str(payload.get("automation_level") or "manual")
    risk = str(payload.get("risk_level") or "medium")
    if automation not in AUTOMATION_LEVELS:
        raise ValueError("invalid automation_level")
    if risk not in RISK_LEVELS:
        raise ValueError("invalid risk_level")
    scope = payload.get("rule_scope") or {}
    if not isinstance(scope, dict):
        raise ValueError("rule_scope must be an object")
    rule = {
        "rule_id": str(payload.get("rule_id") or f"rule:{uuid4().hex}"),
        "rule_name": str(payload.get("rule_name") or "").strip(),
        "rule_text": str(payload.get("rule_text") or payload.get("rule_name") or "").strip(),
        "rule_author": str(payload.get("rule_author") or "").strip(),
        "rule_source": source,
        "rule_version": str(payload.get("rule_version") or "v0.1.0"),
        "rule_scope": {
            "task_types": _safe_list(scope.get("task_types")),
            "tools": _safe_list(scope.get("tools")),
            "workflows": _safe_list(scope.get("workflows")),
            "keywords": _safe_list(scope.get("keywords")),
            "actions": _safe_list(scope.get("actions")),
        },
        "allowed_tools": _safe_list(payload.get("allowed_tools")),
        "denied_tools": _safe_list(payload.get("denied_tools")),
        "automation_level": automation,
        "risk_level": risk,
        "activation_status": str(payload.get("activation_status") or "waiting_owner_signature"),
        "created_at": str(payload.get("created_at") or now),
        "updated_at": str(payload.get("updated_at") or now),
        "signed_at": payload.get("signed_at"),
        "signature": payload.get("signature"),
        "signature_algorithm": payload.get("signature_algorithm") or "owner_ack_sha256",
        "adopted_by": payload.get("adopted_by"),
        "adoption_scope": payload.get("adoption_scope") or {},
        "supersedes": payload.get("supersedes"),
        "superseded_by": payload.get("superseded_by"),
        "changelog": _safe_list(payload.get("changelog")),
        "source_pack_id": source_pack_id or payload.get("source_pack_id"),
    }
    if not rule["rule_name"] or not rule["rule_text"] or not rule["rule_author"]:
        raise ValueError("rule_name, rule_text, and rule_author are required")
    if rule["activation_status"] not in RULE_STATUSES:
        raise ValueError("invalid activation_status")
    rule["hash"] = compute_rule_hash(rule)
    return rule


def validate_rule_integrity(rule: dict[str, Any]) -> dict[str, Any]:
    if rule.get("activation_status") not in RULE_STATUSES:
        raise ValueError("invalid activation_status")
    if rule.get("hash") != compute_rule_hash(rule):
        raise ValueError("rule hash mismatch")
    if rule.get("activation_status") in {"owner_signed", "active"} and not rule.get("signature"):
        raise ValueError("signed or active rule requires signature")
    return rule


def _verify_ed25519(public_key_b64: str, signature_b64: str, payload: bytes) -> bool:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        public_key.verify(base64.b64decode(signature_b64), payload)
        return True
    except Exception:
        return False


def verify_rulepack(pack: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(pack, dict) or not isinstance(pack.get("rules"), list):
        raise ValueError("rulepack and rules are required")
    manifest = {key: value for key, value in pack.items() if key not in {"signature", "verification"}}
    content_hash = hashlib.sha256(_canonical(manifest)).hexdigest()
    signature = str(pack.get("signature") or "")
    public_key = str(pack.get("public_key") or "")
    algorithm = str(pack.get("signature_algorithm") or "ed25519").lower()
    verified = algorithm == "ed25519" and bool(signature and public_key) and _verify_ed25519(public_key, signature, _canonical(manifest))
    return {
        "content_hash": content_hash,
        "signature_algorithm": algorithm,
        "signature_verified": verified,
        "verification_status": "verified" if verified else "waiting_author_signature",
    }


class RuleRegistry:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else current_data_dir() / "rule_registry"
        self.rules_path = self.root / "rules.json"
        self.packs_path = self.root / "rulepacks.json"
        self.subscriptions_path = self.root / "subscriptions.json"

    @staticmethod
    def _read(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"registry file must contain an array: {path}")
        return payload

    @staticmethod
    def _write(path: Path, payload: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)

    def list_rules(self) -> list[dict[str, Any]]:
        return [validate_rule_integrity(rule) for rule in self._read(self.rules_path)]

    def list_packs(self) -> list[dict[str, Any]]:
        return self._read(self.packs_path)

    def list_subscriptions(self) -> list[dict[str, Any]]:
        return self._read(self.subscriptions_path)

    def _save_rules(self, rules: list[dict[str, Any]]) -> None:
        self._write(self.rules_path, rules)

    def create_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        rule = normalize_rule(payload)
        rule["activation_status"] = "waiting_owner_signature"
        rules = self.list_rules()
        if any(item["rule_id"] == rule["rule_id"] for item in rules):
            raise ValueError("rule_id already exists")
        rules.append(rule)
        self._save_rules(rules)
        return rule

    def _mutate(self, rule_id: str, mutator) -> dict[str, Any]:
        rules = self.list_rules()
        for index, rule in enumerate(rules):
            if rule["rule_id"] == rule_id:
                updated = mutator(dict(rule))
                updated["updated_at"] = _now()
                validate_rule_integrity(updated)
                rules[index] = updated
                self._save_rules(rules)
                return updated
        raise KeyError(rule_id)

    def sign_user_rule(self, rule_id: str, owner_signature: str) -> dict[str, Any]:
        if not owner_signature.strip():
            raise ValueError("owner_signature is required")

        def sign(rule: dict[str, Any]) -> dict[str, Any]:
            if rule["rule_source"] == "shenyao_signed_rulepack":
                raise ValueError("ShenYao rulepacks require verified Ed25519 author signature")
            rule["signature"] = "owner_ack:" + hashlib.sha256(owner_signature.encode("utf-8")).hexdigest()
            rule["signature_algorithm"] = "owner_ack_sha256"
            rule["signed_at"] = _now()
            rule["activation_status"] = "owner_signed"
            return rule

        return self._mutate(rule_id, sign)

    def activate(self, rule_id: str, adopted_by: str, adoption_scope: dict[str, Any], adoption_signature: str) -> dict[str, Any]:
        if not adopted_by.strip() or not adoption_signature.strip():
            raise ValueError("adopted_by and adoption_signature are required")

        def activate_rule(rule: dict[str, Any]) -> dict[str, Any]:
            if rule["activation_status"] != "owner_signed":
                raise ValueError("only owner_signed rules can be activated")
            rule["activation_status"] = "active"
            rule["adopted_by"] = adopted_by
            rule["adoption_scope"] = adoption_scope or {}
            rule["adoption_signature_hash"] = hashlib.sha256(adoption_signature.encode("utf-8")).hexdigest()
            return rule

        return self._mutate(rule_id, activate_rule)

    def set_status(self, rule_id: str, status: str) -> dict[str, Any]:
        if status not in {"disabled", "revoked", "archived"}:
            raise ValueError("status must be disabled, revoked, or archived")
        return self._mutate(rule_id, lambda rule: {**rule, "activation_status": status})

    def import_pack(self, pack: dict[str, Any]) -> dict[str, Any]:
        verification = verify_rulepack(pack)
        pack_id = str(pack.get("pack_id") or "").strip()
        if not pack_id:
            raise ValueError("pack_id is required")
        author = str(pack.get("author") or "").strip()
        if not author:
            raise ValueError("pack author is required")
        packs = self.list_packs()
        if any(item["pack_id"] == pack_id and item.get("version") == pack.get("version") for item in packs):
            raise ValueError("rulepack version already imported")
        stored_pack = {**pack, "verification": verification, "imported_at": _now()}
        packs.append(stored_pack)
        self._write(self.packs_path, packs)

        rules = self.list_rules()
        for raw_rule in pack["rules"]:
            source = str(raw_rule.get("rule_source") or "third_party")
            if source == "shenyao_signed_rulepack" and not verification["signature_verified"]:
                status = "waiting_owner_signature"
                signature = None
            else:
                status = "owner_signed" if verification["signature_verified"] else "waiting_owner_signature"
                signature = pack.get("signature") if verification["signature_verified"] else None
            rule = normalize_rule(
                {
                    **raw_rule,
                    "rule_author": raw_rule.get("rule_author") or author,
                    "rule_version": raw_rule.get("rule_version") or pack.get("version"),
                    "rule_source": source,
                    "activation_status": status,
                    "signature": signature,
                    "signature_algorithm": pack.get("signature_algorithm") or "ed25519",
                    "signed_at": pack.get("signed_at") if verification["signature_verified"] else None,
                },
                source_pack_id=pack_id,
            )
            if any(item["rule_id"] == rule["rule_id"] for item in rules):
                raise ValueError(f"duplicate rule_id: {rule['rule_id']}")
            rules.append(rule)
        self._save_rules(rules)
        return stored_pack

    def subscribe_pack(
        self,
        pack_id: str,
        version: str,
        adopted_by: str,
        adoption_scope: dict[str, Any],
        adoption_signature: str,
    ) -> dict[str, Any]:
        if not adopted_by.strip() or not adoption_signature.strip():
            raise ValueError("adopted_by and adoption_signature are required")
        pack = next(
            (item for item in self.list_packs() if item.get("pack_id") == pack_id and item.get("version") == version),
            None,
        )
        if not pack:
            raise KeyError(pack_id)
        if pack.get("verification", {}).get("signature_verified") is not True:
            raise ValueError("only author-verified RulePacks can be subscribed")
        rules = self.list_rules()
        activated_rule_ids: list[str] = []
        signature_hash = hashlib.sha256(adoption_signature.encode("utf-8")).hexdigest()
        for rule in rules:
            if rule.get("source_pack_id") != pack_id or rule.get("rule_version") != version:
                continue
            if rule["activation_status"] not in {"owner_signed", "active"}:
                raise ValueError(f"pack rule is not author-signed: {rule['rule_id']}")
            rule["activation_status"] = "active"
            rule["adopted_by"] = adopted_by
            rule["adoption_scope"] = adoption_scope or {}
            rule["adoption_signature_hash"] = signature_hash
            rule["updated_at"] = _now()
            activated_rule_ids.append(rule["rule_id"])
        self._save_rules(rules)
        subscription = {
            "subscription_id": f"subscription:{uuid4().hex}",
            "pack_id": pack_id,
            "version": version,
            "author": pack.get("author"),
            "adopted_by": adopted_by,
            "adoption_scope": adoption_scope or {},
            "adoption_signature_hash": signature_hash,
            "status": "active",
            "activated_rule_ids": activated_rule_ids,
            "created_at": _now(),
        }
        subscriptions = self.list_subscriptions()
        subscriptions.append(subscription)
        self._write(self.subscriptions_path, subscriptions)
        return subscription

    def unsubscribe_pack(self, subscription_id: str) -> dict[str, Any]:
        subscriptions = self.list_subscriptions()
        subscription = next((item for item in subscriptions if item.get("subscription_id") == subscription_id), None)
        if not subscription:
            raise KeyError(subscription_id)
        subscription["status"] = "disabled"
        subscription["updated_at"] = _now()
        rule_ids = set(subscription.get("activated_rule_ids") or [])
        rules = self.list_rules()
        for rule in rules:
            if rule["rule_id"] in rule_ids and rule["activation_status"] == "active":
                rule["activation_status"] = "disabled"
                rule["updated_at"] = _now()
        self._save_rules(rules)
        self._write(self.subscriptions_path, subscriptions)
        return subscription

    def match(self, request: dict[str, Any]) -> dict[str, Any]:
        task_type = str(request.get("task_type") or "general")
        tool = str(request.get("tool") or "")
        workflow = str(request.get("workflow") or "")
        action = str(request.get("action") or "draft")
        text = str(request.get("text") or "").lower()
        matched: list[dict[str, Any]] = []
        for rule in self.list_rules():
            if rule["activation_status"] != "active":
                continue
            scope = rule["rule_scope"]
            checks = []
            if scope["task_types"]:
                checks.append(task_type in scope["task_types"] or "*" in scope["task_types"])
            if scope["tools"]:
                checks.append(tool in scope["tools"] or "*" in scope["tools"])
            if scope["workflows"]:
                checks.append(workflow in scope["workflows"] or "*" in scope["workflows"])
            if scope["actions"]:
                checks.append(action in scope["actions"] or "*" in scope["actions"])
            if scope["keywords"]:
                checks.append(any(keyword.lower() in text for keyword in scope["keywords"]))
            if checks and all(checks):
                matched.append(rule)

        denied = sorted({item for rule in matched for item in rule["denied_tools"]})
        allowed = sorted({item for rule in matched for item in rule["allowed_tools"] if item not in denied})
        tool_allowed = bool(matched) and (not tool or tool in allowed or "*" in allowed) and tool not in denied
        decision_actions = {"decide", "store", "send", "publish", "delete", "archive", "pay", "execute"}
        draft_only = not matched and action in decision_actions
        return {
            "gate_version": "scbkr.rule-match.v2",
            "matched": bool(matched),
            "matched_rule_ids": [rule["rule_id"] for rule in matched],
            "matched_rules": matched,
            "allowed_tools": allowed,
            "denied_tools": denied,
            "tool_allowed": tool_allowed,
            "decision_allowed": bool(matched) and not draft_only,
            "draft_only": draft_only,
            "reason": "active_rule_matched" if matched else "no_active_rule_matched",
            "next_required_action": "tool_permission_gate" if matched else "search_organize_or_draft_only",
        }
