"""Confirm-time evidence-state checks for mutable tool targets."""

from __future__ import annotations

import hashlib
import json
from typing import Any


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
