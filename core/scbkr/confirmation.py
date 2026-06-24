"""Pure SCBKR five-dimension confirmation helpers.

These helpers only mutate caller-provided dictionaries in memory. They do not
perform IO, write ledgers/data stores, call APIs, or call models.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
from typing import Any

VALID_DIMENSIONS = ("S", "C", "B", "K", "R")
CONFIRMATION_METADATA_KEYS = (
    "confirmed",
    "confirmation_status",
    "confirmed_at",
    "confirmed_by",
    "confirmation_statement",
    "signature",
    "snapshot_hash",
    "confirmed_snapshot",
    "confirmed_snapshot_hash",
    "signature_status",
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_confirmation_statement(statement: str | None) -> str | None:
    """Normalize an optional user confirmation statement."""
    if statement is None:
        return None
    normalized = str(statement).strip()
    return normalized or None


def strip_confirmation_metadata(dimension_payload: dict[str, Any]) -> dict[str, Any]:
    """Return business payload without mutable confirmation/seal metadata."""
    return {
        key: deepcopy(value)
        for key, value in dimension_payload.items()
        if key not in CONFIRMATION_METADATA_KEYS and not key.startswith("confirmation_")
    }


def build_dimension_snapshot(dimension_key: str, dimension_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a stable replay snapshot for one SCBKR dimension business payload."""
    if dimension_key not in VALID_DIMENSIONS:
        raise ValueError("dimension_key must be one of S/C/B/K/R")
    return {"dimension_key": dimension_key, "payload": strip_confirmation_metadata(dimension_payload)}


def hash_snapshot(snapshot: dict[str, Any]) -> str:
    """Return a stable SHA-256 hash for a snapshot dictionary."""
    encoded = json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def confirm_dimension(
    scbkr: dict[str, Any],
    dimension_key: str,
    confirmed_by: str = "user",
    confirmation_statement: str | None = None,
    signature: str | None = None,
) -> dict[str, Any]:
    """Confirm and seal one SCBKR dimension with replay metadata."""
    if dimension_key not in VALID_DIMENSIONS:
        raise ValueError("dimension_key must be one of S/C/B/K/R")
    if dimension_key not in scbkr or not isinstance(scbkr[dimension_key], dict):
        raise ValueError(f"SCBKR dimension {dimension_key} is required before confirmation")

    dimension = scbkr[dimension_key]
    snapshot = build_dimension_snapshot(dimension_key, dimension)
    dimension["confirmed"] = True
    dimension["confirmation_status"] = "confirmed"
    dimension["confirmed_at"] = _now()
    dimension["confirmed_by"] = confirmed_by
    dimension["confirmation_statement"] = (
        normalize_confirmation_statement(confirmation_statement)
        or f"我確認本任務 {dimension_key} 維度責任鏈。"
    )
    dimension["signature"] = signature
    dimension["snapshot_hash"] = hash_snapshot(snapshot)
    dimension["confirmed_snapshot"] = snapshot
    return scbkr


def is_dimension_snapshot_valid(scbkr: dict[str, Any], dimension_key: str) -> bool:
    """Return True only when one live dimension still matches its sealed snapshot."""
    if dimension_key not in VALID_DIMENSIONS:
        return False
    dimension = scbkr.get(dimension_key)
    if not isinstance(dimension, dict):
        return False
    if dimension.get("confirmed") is not True:
        return False
    if dimension.get("confirmation_status") != "confirmed":
        return False

    snapshot_hash = dimension.get("snapshot_hash")
    confirmed_snapshot = dimension.get("confirmed_snapshot")
    if not snapshot_hash or not isinstance(confirmed_snapshot, dict):
        return False
    if hash_snapshot(confirmed_snapshot) != snapshot_hash:
        return False
    return build_dimension_snapshot(dimension_key, dimension) == confirmed_snapshot


def all_dimensions_confirmed(scbkr: dict[str, Any]) -> bool:
    """Return True only when all S/C/B/K/R dimensions have valid sealed snapshots."""
    return all(is_dimension_snapshot_valid(scbkr, dimension_key) for dimension_key in VALID_DIMENSIONS)


def get_confirmed_dimension_payload(scbkr: dict[str, Any], dimension_key: str) -> dict[str, Any]:
    """Return the sealed business payload for one confirmed dimension.

    The returned payload is a defensive copy of confirmed_snapshot.payload only;
    live dimension dictionaries and confirmation metadata are intentionally not
    exposed to model prompts.
    """
    if is_dimension_snapshot_valid(scbkr, dimension_key) is not True:
        raise ValueError(f"SCBKR dimension {dimension_key} sealed snapshot is invalid")
    confirmed_snapshot = scbkr[dimension_key]["confirmed_snapshot"]
    payload = confirmed_snapshot.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"SCBKR dimension {dimension_key} sealed snapshot payload is invalid")
    return deepcopy(payload)


def build_model_visible_scbkr_payload(scbkr: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build the only SCBKR payload allowed to be visible to generation models."""
    return {
        dimension_key: get_confirmed_dimension_payload(scbkr, dimension_key)
        for dimension_key in VALID_DIMENSIONS
    }


def build_scbkr_confirmed_snapshot(scbkr: dict[str, Any]) -> dict[str, Any]:
    """Build a replayable snapshot of the confirmed five-dimension chain."""
    return {
        "dimensions": {dimension_key: deepcopy(scbkr[dimension_key]) for dimension_key in VALID_DIMENSIONS},
        "confirmation_status": scbkr.get("confirmation_status"),
    }


def confirm_all_dimensions(
    scbkr: dict[str, Any],
    confirmed_by: str = "user",
    confirmation_statement: str | None = None,
    signature: str | None = None,
) -> dict[str, Any]:
    """Batch-confirm S/C/B/K/R while preserving per-dimension confirmation records."""
    for dimension_key in VALID_DIMENSIONS:
        confirm_dimension(
            scbkr,
            dimension_key,
            confirmed_by=confirmed_by,
            confirmation_statement=confirmation_statement,
            signature=signature,
        )

    if all_dimensions_confirmed(scbkr):
        scbkr["confirmation_status"] = "confirmed"
        scbkr["confirmed"] = True
        scbkr["confirmed_at"] = _now()
        scbkr["confirmed_by"] = confirmed_by
        scbkr["confirmation_statement"] = (
            normalize_confirmation_statement(confirmation_statement)
            or "我確認本任務 S/C/B/K/R 五維責任鏈。"
        )
        scbkr["signature"] = signature
        scbkr["confirmed_snapshot"] = build_scbkr_confirmed_snapshot(scbkr)
        scbkr["confirmed_snapshot_hash"] = hash_snapshot(scbkr["confirmed_snapshot"])
    return scbkr
