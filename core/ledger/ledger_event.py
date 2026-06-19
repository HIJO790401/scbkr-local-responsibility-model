"""Pure P13-A ledger event builders.

The functions here do not perform IO, write files, write SQLite, call models, or
read environment settings. They only build sanitized event dictionaries.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
from typing import Any
from uuid import uuid4

SENSITIVE_KEYS = {"api_key", "apikey", "authorization", "access_token", "refresh_token", "token", "secret"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = _sanitize_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    return deepcopy(value)


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_ledger_event(
    event_type: str,
    task_id: str | None = None,
    trace_id: str | None = None,
    ledger_id: str | None = None,
    status_before: str | None = None,
    status_after: str | None = None,
    layer: str = "SYSTEM",
    payload: dict[str, Any] | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """Build a sanitized, hash-addressable ledger event without side effects."""
    safe_payload = _sanitize_payload(payload or {})
    if not isinstance(safe_payload, dict):
        safe_payload = {"value": safe_payload}
    return {
        "event_id": f"evt-{event_type}-{uuid4().hex[:12]}",
        "event_type": event_type,
        "task_id": task_id,
        "trace_id": trace_id,
        "ledger_id": ledger_id,
        "timestamp": _now(),
        "status_before": status_before,
        "status_after": status_after,
        "layer": layer,
        "message": message,
        "payload": safe_payload,
        "payload_hash": _payload_hash(safe_payload),
    }
