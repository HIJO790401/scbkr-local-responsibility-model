"""Append-only JSONL helper for SCBKR P2 ledger events."""

import json
from pathlib import Path

REQUIRED_LEDGER_EVENT_FIELDS = (
    "event_id",
    "ledger_id",
    "task_id",
    "trace_id",
    "event_type",
    "actor",
    "layer",
    "message",
    "payload",
    "status",
    "hash",
    "previous_hash",
    "dry_run",
    "simulated",
    "timestamp",
)


def validate_ledger_event_shape(event):
    """Validate only the basic ledger event shape required before JSONL append."""
    if not isinstance(event, dict):
        raise ValueError("ledger event must be a JSON object")

    missing_fields = [field for field in REQUIRED_LEDGER_EVENT_FIELDS if field not in event]
    if missing_fields:
        raise ValueError(f"ledger event missing required fields: {', '.join(missing_fields)}")

    if not isinstance(event["payload"], dict):
        raise ValueError("ledger event payload must be an object")

    if not isinstance(event["dry_run"], bool):
        raise ValueError("ledger event dry_run must be a boolean")

    if not isinstance(event["simulated"], bool):
        raise ValueError("ledger event simulated must be a boolean")

    return True


def append_ledger_event(path, event):
    """Append one UTF-8 JSON object line to the caller-specified ledger path."""
    validate_ledger_event_shape(event)
    ledger_path = Path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as ledger_file:
        ledger_file.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
        ledger_file.write("\n")


def read_ledger_events(path):
    """Read JSONL events only from the caller-specified ledger path."""
    ledger_path = Path(path)
    if not ledger_path.exists():
        return []

    events = []
    with ledger_path.open("r", encoding="utf-8") as ledger_file:
        for line in ledger_file:
            stripped_line = line.strip()
            if stripped_line:
                events.append(json.loads(stripped_line))
    return events
