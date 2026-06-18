import copy
import json
from pathlib import Path


from core.ledger.event_types import (
    LEDGER_ACTORS,
    LEDGER_EVENT_TYPES,
    LEDGER_LAYERS,
    is_valid_actor,
    is_valid_event_type,
    is_valid_layer,
)
from core.ledger.hashing import hash_ledger_event
from core.ledger.jsonl_ledger import append_ledger_event, read_ledger_events


EXPECTED_EVENT_TYPES = (
    "task_created",
    "scbkr_generated",
    "scbkr_modified",
    "user_confirmed",
    "generation_started",
    "generation_finished",
    "review_passed",
    "review_failed",
    "rollback_requested",
    "storage_requested",
    "storage_confirmed",
    "memory_rule_drafted",
    "memory_rule_confirmed",
    "task_completed",
    "task_paused",
    "task_error",
    "system_note",
)

EXPECTED_ACTORS = ("user", "system", "model", "tool")
EXPECTED_LAYERS = ("S", "C", "B", "K", "R", "SYSTEM")


def make_event(event_id="event-1", previous_hash=None):
    event = {
        "event_id": event_id,
        "ledger_id": "ledger-test",
        "task_id": None,
        "trace_id": None,
        "event_type": "system_note",
        "actor": "system",
        "layer": "SYSTEM",
        "message": "P2 temp-directory test event",
        "payload": {"source": "unit-test"},
        "status": "recorded",
        "hash": "placeholder",
        "previous_hash": previous_hash,
        "dry_run": False,
        "simulated": False,
        "timestamp": "2026-06-18T00:00:00Z",
    }
    event["hash"] = hash_ledger_event(event)
    return event


def test_ledger_schema_is_valid_json_schema():
    schema_path = Path("schemas/ledger.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert isinstance(schema["properties"], dict)
    assert isinstance(schema["required"], list)
    assert set(schema["required"]) == set(schema["properties"])


def test_event_type_actor_layer_helpers_are_complete():
    assert LEDGER_EVENT_TYPES == EXPECTED_EVENT_TYPES
    assert LEDGER_ACTORS == EXPECTED_ACTORS
    assert LEDGER_LAYERS == EXPECTED_LAYERS

    assert is_valid_event_type("task_created")
    assert is_valid_event_type("system_note")
    assert not is_valid_event_type("generate")

    assert is_valid_actor("user")
    assert is_valid_actor("tool")
    assert not is_valid_actor("database")

    assert is_valid_layer("S")
    assert is_valid_layer("SYSTEM")
    assert not is_valid_layer("P3")


def test_hash_is_deterministic_and_does_not_modify_event():
    event = make_event()
    original_event = copy.deepcopy(event)

    first_hash = hash_ledger_event(event)
    second_hash = hash_ledger_event(event)

    assert first_hash == second_hash
    assert event == original_event


def test_hash_excludes_hash_field_and_includes_previous_hash():
    event = make_event(previous_hash="previous")
    changed_hash_field = dict(event)
    changed_hash_field["hash"] = "different-local-hash-value"

    changed_previous_hash = dict(event)
    changed_previous_hash["previous_hash"] = "different-previous-hash"

    assert hash_ledger_event(event) == hash_ledger_event(changed_hash_field)
    assert hash_ledger_event(event) != hash_ledger_event(changed_previous_hash)


def test_append_ledger_event_is_append_only_and_readable(tmp_path):
    ledger_path = tmp_path / "ledger" / "test-ledger.jsonl"
    first_event = make_event("event-1")
    second_event = make_event("event-2", previous_hash=first_event["hash"])

    append_ledger_event(ledger_path, first_event)
    append_ledger_event(ledger_path, second_event)

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == first_event
    assert json.loads(lines[1]) == second_event
    assert read_ledger_events(ledger_path) == [first_event, second_event]


def test_read_missing_jsonl_path_returns_empty_list(tmp_path):
    assert read_ledger_events(tmp_path / "missing" / "ledger.jsonl") == []
