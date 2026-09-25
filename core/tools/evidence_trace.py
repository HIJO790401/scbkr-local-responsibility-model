"""Trusted read lineage and coverage for state-dependent drafts."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def record_evidence_read(
    draft_id: str,
    resource_id: str,
    *,
    state_scope: str,
    selector_type: str,
    selector: str,
    value: Any,
    reader_kind: str,
    derived_from_event_ids: list[str] | None = None,
    read_result_status: str = "ok",
) -> dict[str, Any]:
    if not draft_id or not resource_id or not reader_kind:
        raise ValueError("trusted read identity is required")
    return {
        "read_event_id": f"read:{uuid4().hex}",
        "draft_id": draft_id,
        "resource_id": resource_id,
        "state_scope": state_scope,
        "selector_type": selector_type,
        "selector": selector,
        "content_hash": _digest(value) if read_result_status == "ok" else None,
        "reader_kind": reader_kind,
        "derived_from_event_ids": list(derived_from_event_ids or []),
        "read_result_status": read_result_status,
        "required_for_draft": True,
    }


def build_evidence_read_trace(draft_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    if not draft_id or not events or any(event.get("draft_id") != draft_id for event in events):
        raise ValueError("read events must belong to one draft")
    trace = {"contract_version": "v1", "draft_id": draft_id, "events": events}
    trace["read_trace_hash"] = _digest(trace)
    return trace


def verify_evidence_read_trace(trace: dict[str, Any], draft_id: str) -> bool:
    if trace.get("contract_version") != "v1" or trace.get("draft_id") != draft_id:
        return False
    events = trace.get("events")
    if not isinstance(events, list) or not events or any(event.get("draft_id") != draft_id for event in events):
        return False
    expected = _digest({key: value for key, value in trace.items() if key != "read_trace_hash"})
    return trace.get("read_trace_hash") == expected


def build_dependency_closure(trace: dict[str, Any]) -> dict[str, Any]:
    events = trace.get("events") or []
    by_id = {str(event.get("read_event_id")): event for event in events}
    if len(by_id) != len(events):
        raise ValueError("duplicate read event id")
    source_ids: set[str] = set()
    missing: set[str] = set()
    visiting: set[str] = set()

    def visit(event_id: str) -> None:
        if event_id in visiting:
            raise ValueError("dependency lineage cycle")
        event = by_id.get(event_id)
        if event is None:
            missing.add(event_id)
            return
        visiting.add(event_id)
        parents = event.get("derived_from_event_ids") or []
        if parents:
            for parent_id in parents:
                visit(str(parent_id))
        elif event.get("reader_kind") == "derived":
            missing.add(event_id)
        else:
            source_ids.add(event_id)
        visiting.remove(event_id)

    for event in events:
        if event.get("required_for_draft") is True:
            visit(str(event.get("read_event_id")))
        if event.get("read_result_status") != "ok":
            missing.add(str(event.get("read_event_id")))
    return {
        "source_event_ids": sorted(source_ids),
        "lineage_missing_event_ids": sorted(missing),
        "closure_hash": _digest({"source_event_ids": sorted(source_ids), "lineage_missing_event_ids": sorted(missing)}),
    }


def build_dependency_coverage_receipt(
    trace: dict[str, Any], manifest: dict[str, Any], *, bypass_detected: bool = False
) -> dict[str, Any]:
    draft_id = str(trace.get("draft_id") or "")
    trace_valid = verify_evidence_read_trace(trace, draft_id)
    try:
        closure = build_dependency_closure(trace) if trace_valid else {"source_event_ids": [], "lineage_missing_event_ids": ["trace_invalid"], "closure_hash": ""}
    except ValueError:
        closure = {"source_event_ids": [], "lineage_missing_event_ids": ["lineage_cycle"], "closure_hash": ""}
    covered = {
        str(selector.get("read_event_id"))
        for selector in manifest.get("dependency_selectors") or []
        if isinstance(selector, dict)
    }
    uncovered = sorted(set(closure["source_event_ids"]) - covered)
    receipt = {
        "coverage_version": "v1",
        "draft_id": draft_id,
        "read_trace_hash": trace.get("read_trace_hash"),
        "manifest_hash": manifest.get("manifest_hash"),
        "closure_hash": closure["closure_hash"],
        "source_dependency_count": len(closure["source_event_ids"]),
        "manifest_covered_source_count": len(set(closure["source_event_ids"]) & covered),
        "uncovered_read_event_ids": uncovered,
        "lineage_missing_event_ids": closure["lineage_missing_event_ids"],
        "bypass_detected": bypass_detected,
        "coverage_complete": trace_valid and not uncovered and not closure["lineage_missing_event_ids"] and not bypass_detected,
    }
    receipt["reason"] = (
        "dependency_capture_complete" if receipt["coverage_complete"] else
        "read_path_bypassed" if bypass_detected else
        "dependency_trace_missing" if not trace_valid else
        "dependency_lineage_missing" if closure["lineage_missing_event_ids"] else
        "dependency_capture_incomplete"
    )
    receipt["receipt_hash"] = _digest(receipt)
    return receipt


def verify_dependency_coverage(
    trace: dict[str, Any], manifest: dict[str, Any], receipt: dict[str, Any]
) -> bool:
    if receipt.get("coverage_complete") is not True or receipt.get("draft_id") != trace.get("draft_id"):
        return False
    if receipt.get("read_trace_hash") != trace.get("read_trace_hash") or receipt.get("manifest_hash") != manifest.get("manifest_hash"):
        return False
    expected = build_dependency_coverage_receipt(trace, manifest)
    return expected == receipt
