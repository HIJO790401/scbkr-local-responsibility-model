"""Append-only JSONL ledger runtime for P13-A."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.storage.runtime_paths import LEDGER_JSONL_PATH, REPO_ROOT, SQLITE_PATH, ensure_runtime_dirs

REQUIRED_P13_EVENT_FIELDS = (
    "event_id",
    "event_type",
    "task_id",
    "trace_id",
    "ledger_id",
    "timestamp",
    "status_before",
    "status_after",
    "layer",
    "message",
    "payload",
    "payload_hash",
)

# P2 compatibility fields. Kept so older unit tests and pure helpers continue to work.
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


def validate_ledger_event_shape(event: dict[str, Any]) -> bool:
    """Validate the older P2 dry-run ledger event shape."""
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


def _validate_p13_event(event: dict[str, Any]) -> bool:
    if not isinstance(event, dict):
        raise ValueError("ledger event must be a JSON object")
    missing_fields = [field for field in REQUIRED_P13_EVENT_FIELDS if field not in event]
    if missing_fields:
        raise ValueError(f"ledger event missing required fields: {', '.join(missing_fields)}")
    if not isinstance(event["payload"], dict):
        raise ValueError("ledger event payload must be an object")
    return True


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as ledger_file:
        return sum(1 for _ in ledger_file)


def _runtime_ledger_path(ledger_path: str | Path | None = None) -> Path:
    if ledger_path is not None:
        return Path(ledger_path)
    import os

    return Path(os.environ.get("SCBKR_DATA_DIR", REPO_ROOT / "data")).expanduser() / "ledger" / "audit-log.jsonl"


def append_ledger_event(event: dict[str, Any] | str | Path, ledger_path: str | Path | None = None) -> dict[str, Any] | None:
    """Append one event to JSONL without truncating existing ledger content.

    P13-A signature is append_ledger_event(event, ledger_path=...). For backward
    compatibility with P2 tests, append_ledger_event(path, event) is also
    accepted and returns None after performing the append.
    """
    legacy_call = isinstance(event, (str, Path)) and isinstance(ledger_path, dict)
    if legacy_call:
        path = Path(event)
        event_obj = ledger_path
        validate_ledger_event_shape(event_obj)
    else:
        path = _runtime_ledger_path(ledger_path)
        event_obj = event
        _validate_p13_event(event_obj)

    path.parent.mkdir(parents=True, exist_ok=True)
    line_number = _line_count(path) + 1
    with path.open("a", encoding="utf-8") as ledger_file:
        ledger_file.write(json.dumps(event_obj, ensure_ascii=False, sort_keys=True))
        ledger_file.write("\n")

    if legacy_call:
        return None
    return {
        "event_id": event_obj["event_id"],
        "line_number": line_number,
        "timestamp": event_obj["timestamp"],
        "ledger_path": str(path),
    }


def read_ledger_events(task_id: str | Path | None = None, ledger_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Read JSONL ledger events, optionally filtering by task_id.

    For P2 compatibility, read_ledger_events(path) is treated as path-only when
    the first argument points to a JSONL path and ledger_path is left as default.
    """
    if isinstance(task_id, (str, Path)) and Path(task_id).suffix == ".jsonl" and ledger_path is None:
        path = Path(task_id)
        task_filter = None
    else:
        path = _runtime_ledger_path(ledger_path)
        task_filter = task_id

    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as ledger_file:
        for line_number, line in enumerate(ledger_file, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                continue
            try:
                event = json.loads(stripped_line)
            except json.JSONDecodeError as exc:
                event = {
                    "event_id": f"jsonl-parse-error-{line_number}",
                    "event_type": "ledger_parse_error",
                    "task_id": None,
                    "line_number": line_number,
                    "error": str(exc),
                    "raw_line": stripped_line,
                }
            if task_filter is None or event.get("task_id") == task_filter:
                events.append(event)
    return events


def rebuild_ledger_index_from_jsonl(
    sqlite_path: str | Path | None = None,
    ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    """Rebuild the SQLite ledger_index from JSONL without modifying JSONL."""
    from core.storage.sqlite_runtime import clear_ledger_index, init_sqlite_runtime, save_ledger_index

    path = _runtime_ledger_path(ledger_path)
    before_bytes = path.read_bytes() if path.exists() else b""
    init_sqlite_runtime(sqlite_path)
    clear_ledger_index(sqlite_path)

    indexed_count = 0
    skipped_count = 0
    if path.exists():
        with path.open("r", encoding="utf-8") as ledger_file:
            for line_number, line in enumerate(ledger_file, start=1):
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                try:
                    event = json.loads(stripped_line)
                    _validate_p13_event(event)
                    save_ledger_index(event, line_number=line_number, sqlite_path=sqlite_path, jsonl_path=str(path))
                    indexed_count += 1
                except Exception:
                    skipped_count += 1

    after_bytes = path.read_bytes() if path.exists() else b""
    return {
        "status": "rebuilt",
        "indexed_count": indexed_count,
        "skipped_count": skipped_count,
        "jsonl_unchanged": before_bytes == after_bytes,
        "ledger_path": str(path),
        "sqlite_path": str(sqlite_path),
    }
