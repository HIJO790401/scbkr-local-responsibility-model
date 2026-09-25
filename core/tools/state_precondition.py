"""Confirm-time evidence-state checks for mutable tool targets."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.tools.evidence_trace import build_dependency_closure, verify_evidence_read_trace


OBSERVATION_CLOCK_FIELDS = {
    "read_at",
    "observed_at",
    "fetched_at",
    "checked_at",
    "rechecked_at",
    "observation_time",
}


def canonical_evidence_state(value: Any) -> Any:
    """Remove read clocks while preserving evidence versions and modification data."""

    if isinstance(value, dict):
        return {
            str(key): canonical_evidence_state(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key).lower() not in OBSERVATION_CLOCK_FIELDS
        }
    if isinstance(value, list):
        return [canonical_evidence_state(item) for item in value]
    return value


def evidence_state_hash(value: Any) -> str:
    canonical = canonical_evidence_state(value or {})
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compare_evidence_state(
    draft_state: dict[str, Any],
    current_state: dict[str, Any],
    *,
    state_scope: str,
) -> dict[str, Any]:
    expected_hash = evidence_state_hash(draft_state)
    current_hash = evidence_state_hash(current_state)
    conflict = expected_hash != current_hash
    return {
        "required": True,
        "state_scope": state_scope,
        "confirm_time_rechecked": True,
        "expected_evidence_hash": expected_hash,
        "current_evidence_hash": current_hash,
        "conflict": conflict,
        "allowed": not conflict,
        "reason": "state_conflict_reconfirmation_required" if conflict else "confirm_time_state_matches_draft",
        "observation_clock_ignored": sorted(OBSERVATION_CLOCK_FIELDS),
    }


class EvidenceProjectionError(ValueError):
    def __init__(self, reason: str, selector_id: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.selector_id = selector_id


def _select(state: dict[str, Any], selector: dict[str, Any]) -> Any:
    selector_type = selector.get("selector_type")
    path = str(selector.get("selector") or "")
    selector_id = str(selector.get("selector_id") or "")
    if selector_type == "whole_resource":
        return state
    if selector_type in {"field", "rule_field", "json_pointer"}:
        parts = path.split("/")[1:] if selector_type == "json_pointer" and path.startswith("/") else path.split(".")
        if not parts or not all(parts):
            raise EvidenceProjectionError("dependency_selector_invalid", selector_id)
        value: Any = state
        for part in parts:
            part = part.replace("~1", "/").replace("~0", "~") if selector_type == "json_pointer" else part
            if isinstance(value, dict) and part in value:
                value = value[part]
            elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
                value = value[int(part)]
            else:
                raise EvidenceProjectionError("relevant_evidence_missing", selector_id)
        return value
    if selector_type == "text_anchor":
        content = state.get("content")
        if not isinstance(content, str) or not path:
            raise EvidenceProjectionError("relevant_evidence_missing", selector_id)
        count = content.count(path)
        if count != 1:
            raise EvidenceProjectionError("dependency_anchor_ambiguous" if count > 1 else "relevant_evidence_missing", selector_id)
        return path
    if selector_type == "recipient_set":
        recipients = state.get("recipient_set")
        if not isinstance(recipients, list) or not all(isinstance(item, str) for item in recipients):
            raise EvidenceProjectionError("relevant_evidence_missing", selector_id)
        return sorted({item.strip().casefold() for item in recipients})
    if selector_type == "thread_latest_message_id":
        threads = state.get("threads")
        thread = threads.get(path) if isinstance(threads, dict) else None
        if not isinstance(thread, dict) or not thread.get("latest_message_id"):
            raise EvidenceProjectionError("relevant_evidence_missing", selector_id)
        return thread["latest_message_id"]
    if selector_type in {"message_id", "attachment_id"}:
        collection = state.get("messages" if selector_type == "message_id" else "attachments")
        if not isinstance(collection, list):
            raise EvidenceProjectionError("relevant_evidence_missing", selector_id)
        matches = [item for item in collection if isinstance(item, dict) and str(item.get("id")) == path]
        if len(matches) != 1:
            raise EvidenceProjectionError("relevant_evidence_missing", selector_id)
        return matches[0]
    raise EvidenceProjectionError("dependency_selector_invalid", selector_id)


def project_evidence_state(state: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(state, dict) or not state:
        raise EvidenceProjectionError("confirm_time_state_read_empty")
    if state.get("resource_id") != manifest.get("resource_id"):
        raise EvidenceProjectionError("resource_identity_changed")
    selectors = manifest.get("dependency_selectors")
    if not isinstance(selectors, list) or not selectors:
        raise EvidenceProjectionError("dependency_manifest_missing")
    projected: dict[str, Any] = {}
    for selector in selectors:
        if not isinstance(selector, dict) or not selector.get("selector_id"):
            raise EvidenceProjectionError("dependency_selector_invalid")
        projected[str(selector["selector_id"])] = canonical_evidence_state(_select(state, selector))
    return projected


def evidence_projection_hash(projection: dict[str, Any]) -> str:
    return evidence_state_hash(projection)


def build_evidence_dependency_manifest(
    trace: dict[str, Any], draft_state: dict[str, Any], *, state_scope: str, resource_kind: str
) -> dict[str, Any]:
    draft_id = str(trace.get("draft_id") or "")
    if not verify_evidence_read_trace(trace, draft_id):
        raise ValueError("dependency_trace_missing")
    resource_id = str(draft_state.get("resource_id") or "")
    closure = build_dependency_closure(trace)
    if closure["lineage_missing_event_ids"]:
        raise ValueError("dependency_lineage_missing")
    by_id = {event["read_event_id"]: event for event in trace["events"]}
    selectors: list[dict[str, Any]] = []
    for event_id in closure["source_event_ids"]:
        event = by_id[event_id]
        if event.get("resource_id") != resource_id or event.get("state_scope") != state_scope:
            raise ValueError("resource_identity_changed")
        selectors.append({
            "selector_id": f"dep-{len(selectors) + 1:03d}",
            "read_event_id": event_id,
            "selector_type": event["selector_type"],
            "selector": event["selector"],
            "semantic_role": "draft_basis",
            "required": True,
        })
        selected_value = _select(draft_state, selectors[-1])
        read_value_hash = hashlib.sha256(json.dumps(selected_value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if event.get("content_hash") != read_value_hash:
            raise ValueError("trace_manifest_hash_mismatch")
    manifest = {
        "manifest_version": "v1",
        "draft_id": draft_id,
        "state_scope": state_scope,
        "resource_id": resource_id,
        "resource_kind": resource_kind,
        "dependency_selectors": selectors,
        "canonicalization_version": "scbkr-evidence-v2",
    }
    draft_projection = project_evidence_state(draft_state, manifest)
    manifest["draft_selector_hashes"] = {key: evidence_state_hash(value) for key, value in draft_projection.items()}
    manifest["draft_projection_hash"] = evidence_projection_hash(draft_projection)
    manifest["manifest_hash"] = evidence_state_hash(manifest)
    return manifest


def compare_scoped_evidence_state(
    manifest: dict[str, Any], draft_projection_hash: str, current_state: dict[str, Any]
) -> dict[str, Any]:
    base = {
        "required": True,
        "state_scope": manifest.get("state_scope"),
        "resource_id": manifest.get("resource_id"),
        "manifest_version": manifest.get("manifest_version"),
        "manifest_hash": manifest.get("manifest_hash"),
        "draft_projection_hash": draft_projection_hash,
        "confirm_time_rechecked": True,
        "allowed": False,
        "conflict": True,
        "changed_selector_ids": [],
        "missing_selector_ids": [],
    }
    if manifest.get("manifest_version") != "v1":
        return {**base, "reason": "dependency_manifest_version_unsupported"}
    if evidence_state_hash({key: value for key, value in manifest.items() if key != "manifest_hash"}) != manifest.get("manifest_hash"):
        return {**base, "reason": "dependency_manifest_invalid"}
    if draft_projection_hash != manifest.get("draft_projection_hash"):
        return {**base, "reason": "trace_manifest_hash_mismatch"}
    try:
        projection = project_evidence_state(current_state, manifest)
    except EvidenceProjectionError as exc:
        return {
            **base,
            "reason": exc.reason,
            "missing_selector_ids": [exc.selector_id] if exc.selector_id else [],
        }
    current_hash = evidence_projection_hash(projection)
    if current_hash != draft_projection_hash:
        expected_selectors = manifest.get("draft_selector_hashes") or {}
        changed = [selector_id for selector_id, value in projection.items() if evidence_state_hash(value) != expected_selectors.get(selector_id)]
        return {
            **base,
            "current_projection_hash": current_hash,
            "changed_selector_ids": changed,
            "reason": "relevant_evidence_changed",
        }
    return {
        **base,
        "current_projection_hash": current_hash,
        "allowed": True,
        "conflict": False,
        "reason": "confirm_time_relevant_evidence_matches",
    }
