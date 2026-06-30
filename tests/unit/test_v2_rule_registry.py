import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api import main
from core.rules.registry import RuleRegistry, verify_rulepack


def rule_payload():
    return {
        "rule_id": "rule:test:publish",
        "rule_name": "Publish only after owner adoption",
        "rule_author": "Owner",
        "rule_source": "user_defined",
        "rule_version": "v1.0.0",
        "rule_scope": {
            "task_types": ["content"],
            "tools": ["publish"],
            "workflows": ["release"],
            "keywords": ["release"],
            "actions": ["publish"],
        },
        "allowed_tools": ["publish"],
        "denied_tools": [],
        "automation_level": "manual",
        "risk_level": "high",
        "changelog": ["Initial rule"],
    }


def test_rule_lifecycle_and_match_gate(tmp_path):
    registry = RuleRegistry(tmp_path)
    draft = registry.create_draft(rule_payload())
    assert draft["activation_status"] == "waiting_owner_signature"
    assert registry.match({"task_type": "content", "tool": "publish", "workflow": "release", "action": "publish", "text": "release"})["draft_only"] is True

    signed = registry.sign_user_rule(draft["rule_id"], "owner signature")
    assert signed["activation_status"] == "owner_signed"
    active = registry.activate(signed["rule_id"], "user-1", {"workflow": "release"}, "adopt this rule")
    assert active["activation_status"] == "active"

    match = registry.match({"task_type": "content", "tool": "publish", "workflow": "release", "action": "publish", "text": "release now"})
    assert match["matched"] is True
    assert match["tool_allowed"] is True
    assert match["decision_allowed"] is True

    registry.set_status(active["rule_id"], "revoked")
    revoked = registry.match({"task_type": "content", "tool": "publish", "workflow": "release", "action": "publish", "text": "release now"})
    assert revoked["matched"] is False
    assert revoked["draft_only"] is True


def test_unsigned_shenyao_pack_cannot_claim_signed_status(tmp_path):
    pack = json.loads((Path(__file__).resolve().parents[2] / "config" / "rulepacks" / "shen-an-black-shield.v2.draft.json").read_text(encoding="utf-8"))
    registry = RuleRegistry(tmp_path)
    imported = registry.import_pack(pack)
    assert imported["verification"]["signature_verified"] is False
    assert {rule["activation_status"] for rule in registry.list_rules()} == {"waiting_owner_signature"}
    with pytest.raises(ValueError, match="Ed25519"):
        registry.sign_user_rule(pack["rules"][0]["rule_id"], "typed signature")
    with pytest.raises(ValueError, match="author-verified"):
        registry.subscribe_pack(pack["pack_id"], pack["version"], "user", {}, "adopt")


def test_valid_ed25519_pack_is_verified(tmp_path):
    cryptography = pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    pack = {
        "pack_id": "rulepack:test:signed",
        "name": "Signed test pack",
        "author": "Test Author",
        "version": "v1.0.0",
        "signature_algorithm": "ed25519",
        "public_key": base64.b64encode(public_key).decode(),
        "signed_at": "2026-06-30T00:00:00Z",
        "rules": [{**rule_payload(), "rule_id": "rule:test:signed", "rule_source": "third_party"}],
    }
    canonical = json.dumps(pack, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    pack["signature"] = base64.b64encode(private_key.sign(canonical)).decode()
    assert verify_rulepack(pack)["signature_verified"] is True
    registry = RuleRegistry(tmp_path)
    imported = registry.import_pack(pack)
    assert imported["verification"]["verification_status"] == "verified"
    subscription = registry.subscribe_pack(pack["pack_id"], pack["version"], "user", {"workflow": "release"}, "adopt")
    assert subscription["status"] == "active"
    assert subscription["activated_rule_ids"] == ["rule:test:signed"]
    disabled = registry.unsubscribe_pack(subscription["subscription_id"])
    assert disabled["status"] == "disabled"


def test_rule_registry_api_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    client = TestClient(main.app)
    created = client.post("/api/rules/draft", json=rule_payload())
    assert created.status_code == 200
    rule_id = created.json()["rule"]["rule_id"]
    assert client.post(f"/api/rules/{rule_id}/sign", json={"owner_signature": "owner"}).status_code == 200
    assert client.post(f"/api/rules/{rule_id}/activate", json={"adopted_by": "user", "adoption_signature": "adopt", "adoption_scope": {"workflow": "release"}}).status_code == 200
    matched = client.post("/api/rules/match", json={"task_type": "content", "tool": "publish", "workflow": "release", "action": "publish", "text": "release"})
    assert matched.status_code == 200
    assert matched.json()["matched_rule_ids"] == [rule_id]
