"""Deterministic qualification of a signed rule for one request."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from typing import Any

TRUSTED_SOURCES = {"owner_input", "current_task_field", "signed_context", "trusted_reader"}
OPERATORS = {"eq", "neq", "in", "contains", "exists", "gt", "gte", "lt", "lte"}
STATES = {
    "NO_MATCH", "SIMILAR_BUT_UNCLOSED", "TRIGGER_UNRESOLVED",
    "NOT_TRIGGERED", "INVALIDATED", "APPLICABLE",
}


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_rule_trigger_contract(contract: Any) -> dict[str, Any]:
    if not isinstance(contract, dict) or contract.get("contract_version") != "v1":
        raise ValueError("rule_trigger_contract v1 is required")
    if contract.get("trigger_mode") not in {"all", "any"}:
        raise ValueError("trigger_mode must be all or any")
    triggers = contract.get("triggers")
    if not isinstance(triggers, list) or not triggers:
        raise ValueError("at least one trigger is required")
    ids: set[str] = set()
    for trigger in triggers + list(contract.get("valid_when") or []) + list(contract.get("invalid_when") or []):
        if not isinstance(trigger, dict) or not trigger.get("trigger_id") or trigger["trigger_id"] in ids:
            raise ValueError("trigger ids must be unique")
        ids.add(str(trigger["trigger_id"]))
        if trigger.get("evidence_source") not in TRUSTED_SOURCES or trigger.get("operator") not in OPERATORS:
            raise ValueError("unsupported trigger source or operator")
        if not isinstance(trigger.get("field"), str) or not trigger["field"].strip():
            raise ValueError("trigger field is required")
        if trigger.get("operator") != "exists" and "expected" not in trigger:
            raise ValueError("trigger expected value is required")
        if trigger.get("operator") == "contains" and not str(trigger.get("expected") or "").strip():
            raise ValueError("contains trigger cannot match an empty phrase")
    scope = contract.get("scope")
    if not isinstance(scope, dict) or not any(isinstance(scope.get(key), list) and scope[key] for key in ("domain", "action", "resource_kind", "effect")):
        raise ValueError("at least one explicit scope value is required")
    if not isinstance(contract.get("valid_when"), list) or not isinstance(contract.get("invalid_when"), list):
        raise ValueError("valid_when and invalid_when must be explicit lists")
    if contract.get("owner_defined") is not True:
        raise ValueError("owner must define the trigger contract")
    return contract


def evaluate_rule_closure(rule: dict[str, Any]) -> dict[str, Any]:
    contract = rule.get("rule_trigger_contract")
    try:
        validate_rule_trigger_contract(contract)
    except ValueError as exc:
        return {"complete": False, "missing_closure_fields": [str(exc)]}
    if not rule.get("signature") and str(rule.get("signature_status") or "") not in {"owner_signed", "verified", "valid"}:
        return {"complete": False, "missing_closure_fields": ["owner_signature"]}
    return {"complete": True, "missing_closure_fields": []}


def _field(source: Any, path: str) -> tuple[bool, Any]:
    value = source
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return False, None
    return True, value


def _match(value: Any, operator: str, expected: Any) -> bool:
    if operator == "exists":
        return value is not None
    if operator == "eq":
        return value == expected
    if operator == "neq":
        return value != expected
    if operator == "in":
        return value in expected if isinstance(expected, (list, tuple, set)) else False
    if operator == "contains":
        return str(expected).casefold() in str(value).casefold()
    try:
        actual_number, expected_number = float(value), float(expected)
    except (TypeError, ValueError):
        return False
    return {"gt": actual_number > expected_number, "gte": actual_number >= expected_number,
            "lt": actual_number < expected_number, "lte": actual_number <= expected_number}.get(operator, False)


def _check_clause(clause: dict[str, Any], context: dict[str, Any]) -> tuple[bool | None, str | None]:
    source_name = str(clause["evidence_source"])
    source = context.get(source_name)
    if not isinstance(source, dict):
        return None, None
    found, value = _field(source, str(clause["field"]))
    if not found:
        return None, None
    if source_name in {"signed_context", "trusted_reader"} and not source.get("provenance_ref"):
        return None, None
    return _match(value, str(clause["operator"]), clause.get("expected")), _hash({"source": source_name, "field": clause["field"], "value": value})


def _scope_matches(scope: dict[str, Any], context: dict[str, Any]) -> bool | None:
    request = context.get("current_task_field") or {}
    for key in ("domain", "action", "resource_kind", "effect"):
        allowed = scope.get(key) or []
        if not allowed or "*" in allowed:
            continue
        current = request.get(key)
        if current is None:
            return None
        if current not in allowed:
            return False
    return True


def evaluate_rule_applicability(
    rule: dict[str, Any], context: dict[str, Any], *, retrieval_source: str = "vector"
) -> dict[str, Any]:
    closure = evaluate_rule_closure(rule)
    contract = rule.get("rule_trigger_contract") or {}
    state = "SIMILAR_BUT_UNCLOSED"
    reason_codes = list(closure["missing_closure_fields"])
    evidence_refs: list[str] = []
    trigger_match: bool | None = None
    scope_match: bool | None = None
    invalidated = False
    if closure["complete"]:
        checks = [_check_clause(clause, context) for clause in contract["triggers"]]
        evidence_refs.extend(ref for _, ref in checks if ref)
        values = [value for value, _ in checks]
        if contract["trigger_mode"] == "any" and True in values:
            trigger_match = True
        elif contract["trigger_mode"] == "all" and False in values:
            trigger_match = False
        elif None in values:
            state, reason_codes = "TRIGGER_UNRESOLVED", ["trigger_evidence_missing"]
        else:
            trigger_match = all(values) if contract["trigger_mode"] == "all" else any(values)
        if trigger_match is False:
            state, reason_codes = "NOT_TRIGGERED", ["trigger_not_matched"]
        elif trigger_match is True:
            valid_checks = [_check_clause(clause, context) for clause in contract["valid_when"]]
            invalid_checks = [_check_clause(clause, context) for clause in contract["invalid_when"]]
            evidence_refs.extend(ref for _, ref in valid_checks + invalid_checks if ref)
            if any(value is True for value, _ in invalid_checks):
                state, reason_codes, invalidated = "INVALIDATED", ["invalid_when_triggered"], True
            elif any(value is None for value, _ in valid_checks + invalid_checks):
                state, reason_codes = "TRIGGER_UNRESOLVED", ["validity_evidence_missing"]
            elif any(value is False for value, _ in valid_checks):
                state, reason_codes = "NOT_TRIGGERED", ["valid_when_not_met"]
            else:
                scope_match = _scope_matches(contract["scope"], context)
                if scope_match is True:
                    state, reason_codes = "APPLICABLE", []
                elif scope_match is None:
                    state, reason_codes = "TRIGGER_UNRESOLVED", ["scope_evidence_missing"]
                else:
                    state, reason_codes = "NOT_TRIGGERED", ["scope_mismatch"]
    receipt = {
        "receipt_version": "v1",
        "request_id": context.get("request_id"),
        "rule_id": rule.get("rule_id") or rule.get("source_id"),
        "rule_revision": rule.get("rule_version") or rule.get("version"),
        "rule_signature_ref": rule.get("signature_ref") or rule.get("signature"),
        "retrieval_source": retrieval_source,
        "trigger_definition_hash": _hash(contract) if contract else None,
        "trigger_evidence_refs": evidence_refs,
        "trigger_match": trigger_match,
        "scope_match": scope_match,
        "invalid_when_triggered": invalidated,
        "state": state,
        "missing_closure_fields": closure["missing_closure_fields"],
        "reason_codes": reason_codes,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "evaluator_version": "scbkr.rule-applicability.v1",
    }
    receipt["decision_hash"] = _hash({key: value for key, value in receipt.items() if key != "evaluated_at"})
    receipt["receipt_hash"] = _hash(receipt)
    return {
        "rule_applicability_state": state,
        "rule_closure_complete": closure["complete"],
        "trigger_defined": bool(contract.get("triggers")),
        "trigger_match": trigger_match,
        "scope_match": scope_match,
        "missing_closure_fields": closure["missing_closure_fields"],
        "reason_codes": reason_codes,
        "applied": state == "APPLICABLE",
        "applicability_receipt": receipt,
        "applicability_receipt_id": receipt["receipt_hash"],
    }


def verify_rule_applicability_receipt(receipt: dict[str, Any]) -> bool:
    if receipt.get("receipt_version") != "v1":
        return False
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    decision = {key: value for key, value in body.items() if key not in {"decision_hash", "evaluated_at"}}
    return receipt.get("decision_hash") == _hash(decision) and receipt.get("receipt_hash") == _hash(body)
