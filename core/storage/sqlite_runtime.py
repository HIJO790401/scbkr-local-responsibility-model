"""SQLite runtime persistence for P13-A.

SQLite stores mutable local task state and ledger indexes. JSONL remains the
append-only replay source.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any

from core.ledger.ledger_event import build_ledger_event
from core.storage.runtime_paths import REPO_ROOT, SQLITE_PATH, ensure_runtime_dirs


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _runtime_sqlite_path(sqlite_path: str | Path | None = None) -> Path:
    if sqlite_path is not None:
        return Path(sqlite_path)
    import os

    return Path(os.environ.get("SCBKR_DATA_DIR", REPO_ROOT / "data")).expanduser() / "scbkr.sqlite3"


def _connect(sqlite_path: str | Path | None = None) -> sqlite3.Connection:
    sqlite_path = _runtime_sqlite_path(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _bool_int(value: Any) -> int:
    return 1 if value is True else 0


def init_sqlite_runtime(sqlite_path: str | Path | None = None) -> dict[str, Any]:
    """Create P13-A SQLite tables when missing."""
    with _connect(sqlite_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                trace_id TEXT,
                ledger_id TEXT,
                task_name TEXT,
                task_type TEXT,
                raw_input TEXT,
                status TEXT,
                confirmed INTEGER,
                review_passed INTEGER,
                storage_confirmed INTEGER,
                physical_write_performed INTEGER,
                task_json TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS scbkr_confirmations (
                task_id TEXT PRIMARY KEY,
                confirmation_status TEXT,
                confirmed INTEGER,
                confirmed_snapshot_hash TEXT,
                scbkr_json TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS ledger_index (
                event_id TEXT PRIMARY KEY,
                event_type TEXT,
                task_id TEXT,
                trace_id TEXT,
                ledger_id TEXT,
                timestamp TEXT,
                status_before TEXT,
                status_after TEXT,
                layer TEXT,
                payload_hash TEXT,
                line_number INTEGER,
                jsonl_path TEXT
            );

            CREATE TABLE IF NOT EXISTS system_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT,
                timestamp TEXT,
                message TEXT,
                payload_json TEXT
            );

            CREATE TABLE IF NOT EXISTS storage_items (
                item_id TEXT PRIMARY KEY,
                task_id TEXT,
                target TEXT,
                relative_path TEXT,
                content_hash TEXT,
                source_event_id TEXT,
                physical_write_performed INTEGER,
                created_at TEXT,
                item_json TEXT
            );

            CREATE TABLE IF NOT EXISTS memory_rules (
                rule_id TEXT PRIMARY KEY,
                task_id TEXT,
                rule_hash TEXT,
                relative_path TEXT,
                reviewer_signature TEXT,
                scope TEXT,
                created_at TEXT,
                rule_json TEXT
            );
            """
        )
    return {"sqlite_path": str(_runtime_sqlite_path(sqlite_path)), "status": "ready"}


def save_task(task: dict[str, Any], sqlite_path: str | Path | None = None) -> dict[str, Any]:
    """Upsert a task state snapshot into SQLite."""
    init_sqlite_runtime(sqlite_path)
    now = _now()
    task_json = _json(task)
    with _connect(sqlite_path) as conn:
        existing = conn.execute("SELECT created_at FROM tasks WHERE task_id = ?", (task["task_id"],)).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO tasks (
                task_id, trace_id, ledger_id, task_name, task_type, raw_input,
                status, confirmed, review_passed, storage_confirmed,
                physical_write_performed, task_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                trace_id=excluded.trace_id,
                ledger_id=excluded.ledger_id,
                task_name=excluded.task_name,
                task_type=excluded.task_type,
                raw_input=excluded.raw_input,
                status=excluded.status,
                confirmed=excluded.confirmed,
                review_passed=excluded.review_passed,
                storage_confirmed=excluded.storage_confirmed,
                physical_write_performed=excluded.physical_write_performed,
                task_json=excluded.task_json,
                updated_at=excluded.updated_at
            """,
            (
                task["task_id"],
                task.get("trace_id"),
                task.get("ledger_id"),
                task.get("task_name"),
                task.get("task_type"),
                task.get("raw_input"),
                task.get("status"),
                _bool_int(task.get("confirmed")),
                _bool_int(task.get("review_passed")),
                _bool_int(task.get("storage_confirmed")),
                _bool_int(task.get("physical_write_performed")),
                task_json,
                created_at,
                now,
            ),
        )
    return {"task_id": task["task_id"], "sqlite_path": str(_runtime_sqlite_path(sqlite_path)), "updated_at": now}


def load_task(task_id: str, sqlite_path: str | Path | None = None) -> dict[str, Any] | None:
    init_sqlite_runtime(sqlite_path)
    with _connect(sqlite_path) as conn:
        row = conn.execute("SELECT task_json FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if row is None:
        return None
    return json.loads(row["task_json"])


def list_tasks(sqlite_path: str | Path | None = None, limit: int = 50) -> list[dict[str, Any]]:
    init_sqlite_runtime(sqlite_path)
    with _connect(sqlite_path) as conn:
        rows = conn.execute(
            """
            SELECT task_json FROM tasks
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [json.loads(row["task_json"]) for row in rows]


def save_scbkr_confirmation(task_id: str, scbkr: dict[str, Any], sqlite_path: str | Path | None = None) -> dict[str, Any]:
    init_sqlite_runtime(sqlite_path)
    now = _now()
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO scbkr_confirmations (
                task_id, confirmation_status, confirmed, confirmed_snapshot_hash, scbkr_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                confirmation_status=excluded.confirmation_status,
                confirmed=excluded.confirmed,
                confirmed_snapshot_hash=excluded.confirmed_snapshot_hash,
                scbkr_json=excluded.scbkr_json,
                updated_at=excluded.updated_at
            """,
            (
                task_id,
                scbkr.get("confirmation_status"),
                _bool_int(scbkr.get("confirmed")),
                scbkr.get("confirmed_snapshot_hash"),
                _json(scbkr),
                now,
            ),
        )
    return {"task_id": task_id, "updated_at": now}


def save_ledger_index(
    event: dict[str, Any],
    line_number: int | None = None,
    sqlite_path: str | Path | None = None,
    jsonl_path: str | None = None,
) -> dict[str, Any]:
    init_sqlite_runtime(sqlite_path)
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO ledger_index (
                event_id, event_type, task_id, trace_id, ledger_id, timestamp,
                status_before, status_after, layer, payload_hash, line_number, jsonl_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                event_type=excluded.event_type,
                task_id=excluded.task_id,
                trace_id=excluded.trace_id,
                ledger_id=excluded.ledger_id,
                timestamp=excluded.timestamp,
                status_before=excluded.status_before,
                status_after=excluded.status_after,
                layer=excluded.layer,
                payload_hash=excluded.payload_hash,
                line_number=excluded.line_number,
                jsonl_path=excluded.jsonl_path
            """,
            (
                event["event_id"],
                event.get("event_type"),
                event.get("task_id"),
                event.get("trace_id"),
                event.get("ledger_id"),
                event.get("timestamp"),
                event.get("status_before"),
                event.get("status_after"),
                event.get("layer"),
                event.get("payload_hash"),
                line_number,
                jsonl_path,
            ),
        )
    return {"event_id": event["event_id"], "line_number": line_number}



def clear_ledger_index(sqlite_path: str | Path | None = None) -> dict[str, Any]:
    """Clear the rebuildable SQLite ledger index without touching JSONL."""
    init_sqlite_runtime(sqlite_path)
    with _connect(sqlite_path) as conn:
        deleted_count = conn.execute("SELECT COUNT(*) FROM ledger_index").fetchone()[0]
        conn.execute("DELETE FROM ledger_index")
    return {"sqlite_path": str(_runtime_sqlite_path(sqlite_path)), "deleted_count": deleted_count}

def get_task_ledger(task_id: str, sqlite_path: str | Path | None = None) -> list[dict[str, Any]]:
    init_sqlite_runtime(sqlite_path)
    with _connect(sqlite_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM ledger_index
            WHERE task_id = ?
            ORDER BY COALESCE(line_number, 0), timestamp
            """,
            (task_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_system_event(
    event_type: str,
    message: str,
    payload: dict[str, Any] | None = None,
    sqlite_path: str | Path | None = None,
) -> dict[str, Any]:
    init_sqlite_runtime(sqlite_path)
    event = build_ledger_event(event_type, message=message, payload=payload or {})
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO system_events (event_id, event_type, timestamp, message, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event["event_id"], event_type, event["timestamp"], message, _json(event["payload"])),
        )
    return event


def _sanitize_index_payload(value: Any) -> Any:
    sensitive_keys = {"api_key", "apikey", "authorization", "access_token", "refresh_token", "token", "secret"}
    if isinstance(value, dict):
        return {key: ("***REDACTED***" if str(key).lower() in sensitive_keys else _sanitize_index_payload(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_index_payload(item) for item in value]
    return value


def save_storage_item(item: dict[str, Any], sqlite_path: str | Path | None = None) -> dict[str, Any]:
    init_sqlite_runtime(sqlite_path)
    safe_item = _sanitize_index_payload(item)
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO storage_items (
                item_id, task_id, target, relative_path, content_hash, source_event_id,
                physical_write_performed, created_at, item_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                task_id=excluded.task_id,
                target=excluded.target,
                relative_path=excluded.relative_path,
                content_hash=excluded.content_hash,
                source_event_id=excluded.source_event_id,
                physical_write_performed=excluded.physical_write_performed,
                created_at=excluded.created_at,
                item_json=excluded.item_json
            """,
            (
                safe_item["item_id"],
                safe_item.get("task_id"),
                safe_item.get("target"),
                safe_item.get("relative_path"),
                safe_item.get("content_hash"),
                safe_item.get("source_event_id"),
                _bool_int(safe_item.get("physical_write_performed")),
                safe_item.get("created_at") or _now(),
                _json(safe_item),
            ),
        )
    return {"item_id": safe_item["item_id"]}


def list_storage_items(task_id: str | None = None, sqlite_path: str | Path | None = None, limit: int = 50) -> list[dict[str, Any]]:
    init_sqlite_runtime(sqlite_path)
    with _connect(sqlite_path) as conn:
        if task_id is None:
            rows = conn.execute("SELECT item_json FROM storage_items ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = conn.execute("SELECT item_json FROM storage_items WHERE task_id = ? ORDER BY created_at DESC LIMIT ?", (task_id, limit)).fetchall()
    return [json.loads(row["item_json"]) for row in rows]


def save_memory_rule(rule: dict[str, Any], sqlite_path: str | Path | None = None) -> dict[str, Any]:
    init_sqlite_runtime(sqlite_path)
    safe_rule = _sanitize_index_payload(rule)
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO memory_rules (
                rule_id, task_id, rule_hash, relative_path, reviewer_signature, scope, created_at, rule_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rule_id) DO UPDATE SET
                task_id=excluded.task_id,
                rule_hash=excluded.rule_hash,
                relative_path=excluded.relative_path,
                reviewer_signature=excluded.reviewer_signature,
                scope=excluded.scope,
                created_at=excluded.created_at,
                rule_json=excluded.rule_json
            """,
            (
                safe_rule["rule_id"],
                safe_rule.get("task_id"),
                safe_rule.get("rule_hash"),
                safe_rule.get("relative_path"),
                safe_rule.get("reviewer_signature"),
                safe_rule.get("scope"),
                safe_rule.get("created_at") or _now(),
                _json(safe_rule),
            ),
        )
    return {"rule_id": safe_rule["rule_id"]}


def list_memory_rules(task_id: str | None = None, sqlite_path: str | Path | None = None, limit: int = 50) -> list[dict[str, Any]]:
    init_sqlite_runtime(sqlite_path)
    with _connect(sqlite_path) as conn:
        if task_id is None:
            rows = conn.execute("SELECT rule_json FROM memory_rules ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = conn.execute("SELECT rule_json FROM memory_rules WHERE task_id = ? ORDER BY created_at DESC LIMIT ?", (task_id, limit)).fetchall()
    return [json.loads(row["rule_json"]) for row in rows]
