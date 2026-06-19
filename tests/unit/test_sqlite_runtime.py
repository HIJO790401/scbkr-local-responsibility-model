import json
import sqlite3

import pytest

from core.ledger.ledger_event import build_ledger_event
from core.storage.sqlite_runtime import (
    clear_ledger_index,
    get_task_ledger,
    init_sqlite_runtime,
    list_tasks,
    load_task,
    save_ledger_index,
    save_scbkr_confirmation,
    save_task,
)


def make_task(task_id="task-1", **overrides):
    task = {
        "task_id": task_id,
        "trace_id": f"trace-{task_id}",
        "ledger_id": f"ledger-{task_id}",
        "task_name": "測試任務",
        "task_type": "general",
        "raw_input": "hello",
        "status": "waiting_scbkr",
        "confirmed": False,
        "review_passed": False,
        "storage_confirmed": False,
        "physical_write_performed": False,
    }
    task.update(overrides)
    return task


def table_names(sqlite_path):
    with sqlite3.connect(sqlite_path) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_init_sqlite_runtime_creates_required_tables(tmp_path):
    sqlite_path = tmp_path / "runtime.sqlite3"

    init_sqlite_runtime(sqlite_path)

    assert {"tasks", "scbkr_confirmations", "ledger_index", "system_events"} <= table_names(sqlite_path)


def test_save_task_and_load_task_round_trip(tmp_path):
    sqlite_path = tmp_path / "runtime.sqlite3"
    task = make_task()

    save_task(task, sqlite_path=sqlite_path)

    assert load_task("task-1", sqlite_path=sqlite_path) == task


def test_save_task_upserts_existing_row(tmp_path):
    sqlite_path = tmp_path / "runtime.sqlite3"
    save_task(make_task(status="waiting_scbkr"), sqlite_path=sqlite_path)
    save_task(make_task(status="confirmed", confirmed=True), sqlite_path=sqlite_path)

    loaded = load_task("task-1", sqlite_path=sqlite_path)
    assert loaded["status"] == "confirmed"
    assert loaded["confirmed"] is True


def test_save_scbkr_confirmation_saves_confirmed_snapshot_hash(tmp_path):
    sqlite_path = tmp_path / "runtime.sqlite3"
    scbkr = {"confirmation_status": "confirmed", "confirmed": True, "confirmed_snapshot_hash": "abc"}

    save_scbkr_confirmation("task-1", scbkr, sqlite_path=sqlite_path)

    with sqlite3.connect(sqlite_path) as conn:
        row = conn.execute("SELECT confirmed_snapshot_hash FROM scbkr_confirmations WHERE task_id = ?", ("task-1",)).fetchone()
    assert row[0] == "abc"


def test_save_ledger_index_and_get_task_ledger(tmp_path):
    sqlite_path = tmp_path / "runtime.sqlite3"
    event = build_ledger_event("task_created", task_id="task-1")

    save_ledger_index(event, line_number=7, sqlite_path=sqlite_path, jsonl_path="audit-log.jsonl")

    rows = get_task_ledger("task-1", sqlite_path=sqlite_path)
    assert rows[0]["event_id"] == event["event_id"]
    assert rows[0]["line_number"] == 7


def test_list_tasks_lists_persisted_tasks(tmp_path):
    sqlite_path = tmp_path / "runtime.sqlite3"
    save_task(make_task("task-1"), sqlite_path=sqlite_path)
    save_task(make_task("task-2"), sqlite_path=sqlite_path)

    task_ids = {task["task_id"] for task in list_tasks(sqlite_path=sqlite_path)}
    assert {"task-1", "task-2"} <= task_ids


def test_sqlite_error_does_not_delete_jsonl(tmp_path):
    sqlite_path = tmp_path / "missing" / "runtime.sqlite3"
    ledger_path = tmp_path / "audit-log.jsonl"
    ledger_path.write_text('{"event_id":"evt-existing"}\n', encoding="utf-8")
    sqlite_path.parent.write_text("not a directory", encoding="utf-8")

    with pytest.raises(Exception):
        init_sqlite_runtime(sqlite_path)

    assert ledger_path.read_text(encoding="utf-8") == '{"event_id":"evt-existing"}\n'


def test_clear_ledger_index_removes_only_index_rows(tmp_path):
    sqlite_path = tmp_path / "runtime.sqlite3"
    event = build_ledger_event("task_created", task_id="task-1")
    save_ledger_index(event, line_number=1, sqlite_path=sqlite_path, jsonl_path="audit-log.jsonl")

    result = clear_ledger_index(sqlite_path=sqlite_path)

    assert result["deleted_count"] == 1
    assert get_task_ledger("task-1", sqlite_path=sqlite_path) == []
