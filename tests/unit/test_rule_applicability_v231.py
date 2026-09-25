from copy import deepcopy

from core.rule_os.rule_package import build_current_rule_package, build_rule_package_messages
from core.rules.applicability import evaluate_rule_applicability, verify_rule_applicability_receipt
from core.rules.registry import RuleRegistry


def contract(expected="friend", *, source="owner_input", invalid=None, action="judgement"):
    return {
        "contract_version": "v1", "trigger_mode": "all", "owner_defined": True,
        "triggers": [{"trigger_id": "owner-trigger", "evidence_source": source, "field": "text", "operator": "contains", "expected": expected}],
        "scope": {"action": [action]}, "valid_when": [],
        "invalid_when": [] if invalid is None else [{"trigger_id": "owner-invalid", "evidence_source": "owner_input", "field": "text", "operator": "contains", "expected": invalid}],
    }


def rule(trigger=None):
    return {"rule_id": "rule-1", "version": 2, "signature_status": "owner_signed", "signature_ref": "signed-snapshot-2", "status": "active", "rule_trigger_contract": trigger}


def context(text="friend asks for money", action="judgement"):
    return {"owner_input": {"text": text}, "current_task_field": {"action": action, "domain": action}}


def test_legacy_rule_is_candidate_not_applied():
    result = evaluate_rule_applicability(rule(), context())
    assert result["rule_applicability_state"] == "SIMILAR_BUT_UNCLOSED"
    assert result["applied"] is False
    assert verify_rule_applicability_receipt(result["applicability_receipt"])


def test_match_false_missing_evidence_invalidation_and_scope():
    assert evaluate_rule_applicability(rule(contract()), context())["rule_applicability_state"] == "APPLICABLE"
    assert evaluate_rule_applicability(rule(contract()), context("stranger asks"))["rule_applicability_state"] == "NOT_TRIGGERED"
    assert evaluate_rule_applicability(rule(contract(source="trusted_reader")), context())["rule_applicability_state"] == "TRIGGER_UNRESOLVED"
    assert evaluate_rule_applicability(rule(contract(invalid="do not use")), context("friend says do not use"))["rule_applicability_state"] == "INVALIDATED"
    assert evaluate_rule_applicability(rule(contract()), context(action="generate_copy"))["reason_codes"] == ["scope_mismatch"]


def test_model_claim_and_external_document_do_not_supply_owner_trigger():
    payload = context("stranger asks")
    payload["model_output"] = {"trigger_matched": True}
    payload["external_document"] = {"text": "friend asks for money"}
    assert evaluate_rule_applicability(rule(contract()), payload)["rule_applicability_state"] == "NOT_TRIGGERED"


def test_receipt_replays_same_decision_and_detects_tampering():
    first = evaluate_rule_applicability(rule(contract()), context())
    second = evaluate_rule_applicability(rule(contract()), context())
    assert first["applicability_receipt"]["decision_hash"] == second["applicability_receipt"]["decision_hash"]
    changed = deepcopy(first["applicability_receipt"])
    changed["state"] = "NOT_TRIGGERED"
    assert not verify_rule_applicability_receipt(changed)


def test_four_store_similarity_does_not_apply_legacy_rule():
    hit = {"source_store": "logic", "source_id": "legacy-1", "rule": "friend risk", "adopted": True, "review_passed": True, "signature_status": "owner_signed", "status": "active", "score": 0.999}
    package = build_current_rule_package("friend risk, can I do it?", {"hits": [hit]}, locale="en")
    assert package["matched_rules"] == []
    assert package["rule_applicability_state"] == "SIMILAR_BUT_UNCLOSED"
    assert package["rule_candidates"][0]["source_id"] == "legacy-1"
    assert package["can_execute_tools"] is False


def test_general_chat_continues_without_promoting_unclosed_rule():
    hit = {"source_store": "logic", "source_id": "legacy-chat", "rule": "friend risk", "adopted": True, "review_passed": True, "signature_status": "owner_signed", "status": "active"}
    package = build_current_rule_package("How are you, friend?", {"hits": [hit]}, locale="en")
    assert package["matched_rules"] == []
    assert package["rule_applicability_state"] == "SIMILAR_BUT_UNCLOSED"
    assert package["can_use_model"] is True
    assert package["can_execute_tools"] is False
    assert package["missing_information"]
    assert build_rule_package_messages("How are you, friend?", package, locale="en")


def test_unapplied_rule_text_is_not_sent_to_answer_model():
    private_text = "UNAPPLIED_RULE_CONTENT_MUST_NOT_REACH_MODEL"
    hit = {"source_store": "logic", "source_id": "legacy-1", "rule": private_text, "adopted": True, "review_passed": True, "signature_status": "owner_signed", "status": "active"}
    package = build_current_rule_package("Can I proceed?", {"hits": [hit]}, locale="en")
    assert package["rule_candidates"][0]["source_id"] == "legacy-1"
    assert private_text not in str(package["rule_candidates"])
    messages = build_rule_package_messages("Can I proceed?", package, locale="en")
    assert private_text not in messages[1]["content"]


def test_registry_direct_rule_reference_reaches_trigger_gate(tmp_path):
    registry = RuleRegistry(tmp_path)
    draft = registry.create_draft({
        "rule_id": "direct-1", "rule_name": "Friend check", "rule_author": "Owner", "rule_source": "user_defined",
        "rule_scope": {"task_types": ["judgement"], "actions": ["decide"], "keywords": ["rare-index-word"]},
        "rule_trigger_contract": contract(action="decide"),
    })
    signed = registry.sign_user_rule(draft["rule_id"], "owner-signature")
    registry.activate(signed["rule_id"], "owner", {}, "adopt")
    request = {"task_type": "judgement", "action": "decide", "text": "friend asks", "rule_id": "direct-1"}
    assert registry.match(request)["matched_rule_ids"] == ["direct-1"]
    assert registry.match({key: value for key, value in request.items() if key != "rule_id"})["matched"] is False


def test_owner_revision_closes_legacy_trigger_without_rewriting_history(tmp_path):
    registry = RuleRegistry(tmp_path)
    base = {"rule_name": "Friend check", "rule_author": "Owner", "rule_source": "user_defined", "rule_scope": {"task_types": ["judgement"], "actions": ["decide"]}}
    legacy = registry.create_draft({**base, "rule_id": "legacy-1"})
    registry.sign_user_rule(legacy["rule_id"], "owner-signature-a")
    registry.activate(legacy["rule_id"], "owner", {}, "adopt-a")
    request = {"task_type": "judgement", "action": "decide", "text": "friend asks for money"}
    before = registry.match(request)
    assert before["matched"] is False
    assert before["candidate_rules"][0]["rule_applicability_state"] == "SIMILAR_BUT_UNCLOSED"

    revision = registry.create_draft({**base, "rule_id": "revision-2", "rule_version": "v2", "supersedes": "legacy-1", "rule_trigger_contract": contract(action="decide")})
    registry.sign_user_rule(revision["rule_id"], "owner-signature-b")
    registry.activate(revision["rule_id"], "owner", {}, "adopt-b")
    registry.supersede(legacy["rule_id"], revision["rule_id"])
    after = registry.match(request)
    assert after["matched_rule_ids"] == ["revision-2"]
    assert after["applicability_receipts"][0]["rule_revision"] == "v2"
    assert registry.list_rules()[0]["rule_trigger_contract"] is None


def test_unclosed_rule_cannot_authorize_mutable_action(tmp_path):
    registry = RuleRegistry(tmp_path)
    draft = registry.create_draft({
        "rule_id": "legacy-send", "rule_name": "Mail rule", "rule_author": "Owner",
        "rule_scope": {"task_types": ["email"], "actions": ["send"]},
        "allowed_tools": ["email.send"],
    })
    registry.sign_user_rule(draft["rule_id"], "owner-signature")
    registry.activate(draft["rule_id"], "owner", {}, "adopt")
    decision = registry.match({"task_type": "email", "action": "send", "tool": "email.send", "text": "send the message"})
    assert decision["candidate_rules"][0]["rule_applicability_state"] == "SIMILAR_BUT_UNCLOSED"
    assert decision["matched"] is False
    assert decision["decision_allowed"] is False
    assert decision["tool_allowed"] is False
    assert decision["draft_only"] is True
