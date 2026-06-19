import json

from core.ledger.ledger_event import build_ledger_event
from core.ledger.jsonl_ledger import append_ledger_event, read_ledger_events, rebuild_ledger_index_from_jsonl
from core.storage.sqlite_runtime import get_task_ledger, init_sqlite_runtime, save_ledger_index


def test_append_ledger_event_creates_jsonl(tmp_path):
    ledger_path = tmp_path / "ledger" / "audit-log.jsonl"
    event = build_ledger_event("task_created", task_id="task-1", payload={"ok": True})

    result = append_ledger_event(event, ledger_path=ledger_path)

    assert ledger_path.exists()
    assert result["event_id"] == event["event_id"]
    assert result["line_number"] == 1


def test_append_second_event_does_not_overwrite_first(tmp_path):
    ledger_path = tmp_path / "audit-log.jsonl"
    first = build_ledger_event("task_created", task_id="task-1")
    second = build_ledger_event("scbkr_draft_created", task_id="task-1")

    append_ledger_event(first, ledger_path=ledger_path)
    append_ledger_event(second, ledger_path=ledger_path)

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event_id"] == first["event_id"]
    assert json.loads(lines[1])["event_id"] == second["event_id"]


def test_read_ledger_events_reads_and_filters_by_task_id(tmp_path):
    ledger_path = tmp_path / "audit-log.jsonl"
    first = build_ledger_event("task_created", task_id="task-1")
    second = build_ledger_event("task_created", task_id="task-2")
    append_ledger_event(first, ledger_path=ledger_path)
    append_ledger_event(second, ledger_path=ledger_path)

    assert [event["event_id"] for event in read_ledger_events(ledger_path=ledger_path)] == [
        first["event_id"],
        second["event_id"],
    ]
    assert read_ledger_events(task_id="task-1", ledger_path=ledger_path)[0]["event_id"] == first["event_id"]


def test_event_payload_hash_exists_and_api_key_is_redacted():
    event = build_ledger_event("settings_changed", payload={"api_key": "secret", "nested": {"api_key": "nested"}})

    assert event["payload_hash"]
    assert "secret" not in json.dumps(event, ensure_ascii=False)
    assert event["payload"]["api_key"] == "***REDACTED***"
    assert event["payload"]["nested"]["api_key"] == "***REDACTED***"


def test_rebuild_ledger_index_from_jsonl_does_not_modify_jsonl(tmp_path):
    sqlite_path = tmp_path / "runtime.sqlite3"
    ledger_path = tmp_path / "audit-log.jsonl"
    event = build_ledger_event("task_created", task_id="task-1")
    append_ledger_event(event, ledger_path=ledger_path)
    before = ledger_path.read_bytes()

    init_sqlite_runtime(sqlite_path)
    result = rebuild_ledger_index_from_jsonl(sqlite_path=sqlite_path, ledger_path=ledger_path)

    assert ledger_path.read_bytes() == before
    assert result["jsonl_unchanged"] is True
    assert result["indexed_count"] == 1
    assert get_task_ledger("task-1", sqlite_path=sqlite_path)[0]["event_id"] == event["event_id"]


def test_rebuild_ledger_index_clears_dirty_rows_and_preserves_jsonl_bytes(tmp_path):
    sqlite_path = tmp_path / "runtime.sqlite3"
    ledger_path = tmp_path / "audit-log.jsonl"
    event = build_ledger_event("task_created", task_id="task-clean")
    dirty_event = build_ledger_event("task_created", task_id="task-dirty")
    append_ledger_event(event, ledger_path=ledger_path)
    before = ledger_path.read_bytes()
    save_ledger_index(dirty_event, line_number=99, sqlite_path=sqlite_path, jsonl_path=str(ledger_path))

    result = rebuild_ledger_index_from_jsonl(sqlite_path=sqlite_path, ledger_path=ledger_path)

    assert ledger_path.read_bytes() == before
    assert result["jsonl_unchanged"] is True
    assert result["indexed_count"] == 1
    assert get_task_ledger("task-dirty", sqlite_path=sqlite_path) == []
    assert get_task_ledger("task-clean", sqlite_path=sqlite_path)[0]["event_id"] == event["event_id"]


def test_rebuild_ledger_index_missing_jsonl_returns_zero_without_crashing(tmp_path):
    sqlite_path = tmp_path / "runtime.sqlite3"
    ledger_path = tmp_path / "missing-audit-log.jsonl"
    dirty_event = build_ledger_event("task_created", task_id="task-dirty")
    save_ledger_index(dirty_event, line_number=99, sqlite_path=sqlite_path, jsonl_path=str(ledger_path))

    result = rebuild_ledger_index_from_jsonl(sqlite_path=sqlite_path, ledger_path=ledger_path)

    assert result["indexed_count"] == 0
    assert result["skipped_count"] == 0
    assert result["jsonl_unchanged"] is True
    assert not ledger_path.exists()
    assert get_task_ledger("task-dirty", sqlite_path=sqlite_path) == []
