"""Deterministic hashing helpers for SCBKR ledger events."""

import hashlib
import json


def canonical_json(data):
    """Return deterministic JSON text for data."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text):
    """Return a SHA-256 hex digest for text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_ledger_event(event):
    """Hash a ledger event without including the event's own hash field."""
    event_for_hash = dict(event)
    event_for_hash.pop("hash", None)
    return sha256_text(canonical_json(event_for_hash))
