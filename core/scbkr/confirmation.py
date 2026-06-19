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


def _now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_confirmation_statement(statement: str | None) -> str | None:
    """Normalize an optional user confirmation statement."""
    if statement is None:
        return None
    normalized = str(statement).strip()
    return normalized or None


def build_dimension_snapshot(dimension_key: str, dimension_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a replayable snapshot for one SCBKR dimension."""
    if dimension_key not in VALID_DIMENSIONS:
        raise ValueError("dimension_key must be one of S/C/B/K/R")
    return {"dimension_key": dimension_key, "payload": deepcopy(dimension_payload)}


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


def all_dimensions_confirmed(scbkr: dict[str, Any]) -> bool:
    """Return True only when all S/C/B/K/R dimensions have sealed confirmations."""
    for dimension_key in VALID_DIMENSIONS:
        dimension = scbkr.get(dimension_key)
        if not isinstance(dimension, dict):
            return False
        if dimension.get("confirmed") is not True:
            return False
        if dimension.get("confirmation_status") != "confirmed":
            return False
        if not dimension.get("snapshot_hash"):
            return False
        if not dimension.get("confirmed_snapshot"):
            return False
    return True


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
