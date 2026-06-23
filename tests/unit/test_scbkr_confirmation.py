import pytest

from core.scbkr.confirmation import (
    VALID_DIMENSIONS,
    all_dimensions_confirmed,
    confirm_all_dimensions,
    confirm_dimension,
    hash_snapshot,
    is_dimension_snapshot_valid,
    strip_confirmation_metadata,
)
from core.scbkr.generator import create_scbkr_draft


def make_scbkr():
    return create_scbkr_draft("請建立測試任務", "workflow")


def test_confirm_dimension_only_accepts_valid_dimensions():
    scbkr = make_scbkr()

    for dimension in VALID_DIMENSIONS:
        confirm_dimension(scbkr, dimension)

    with pytest.raises(ValueError, match="S/C/B/K/R"):
        confirm_dimension(scbkr, "X")


def test_confirm_dimension_writes_confirmation_metadata():
    scbkr = confirm_dimension(make_scbkr(), "S")
    dimension = scbkr["S"]

    assert dimension["confirmed"] is True
    assert dimension["confirmation_status"] == "confirmed"
    assert dimension["confirmed_at"]
    assert dimension["snapshot_hash"]
    assert dimension["confirmed_snapshot"]
    assert is_dimension_snapshot_valid(scbkr, "S") is True


def test_strip_confirmation_metadata_removes_seal_fields_only():
    payload = {"task_name": "x", "confirmed": True, "confirmed_at": "now", "snapshot_hash": "hash"}

    assert strip_confirmation_metadata(payload) == {"task_name": "x"}


def test_all_dimensions_confirmed_is_false_when_only_one_dimension_is_confirmed():
    scbkr = confirm_dimension(make_scbkr(), "S")

    assert all_dimensions_confirmed(scbkr) is False


def test_confirm_all_dimensions_confirms_every_dimension_and_scbkr_snapshot_hash():
    scbkr = confirm_all_dimensions(make_scbkr())

    assert all_dimensions_confirmed(scbkr) is True
    assert scbkr["confirmed"] is True
    assert scbkr["confirmation_status"] == "confirmed"
    assert scbkr["confirmed_snapshot_hash"]


def test_live_s_dimension_tamper_invalidates_all_dimensions_confirmed():
    scbkr = confirm_all_dimensions(make_scbkr())
    scbkr["S"]["task_name"] = "竄改後任務名稱"

    assert all_dimensions_confirmed(scbkr) is False


def test_live_b_dimension_boundary_tamper_invalidates_all_dimensions_confirmed():
    scbkr = confirm_all_dimensions(make_scbkr())
    scbkr["B"]["data_write_scope"].append("竄改：允許寫入 data")

    assert all_dimensions_confirmed(scbkr) is False


def test_confirmed_snapshot_tamper_invalidates_all_dimensions_confirmed():
    scbkr = confirm_all_dimensions(make_scbkr())
    scbkr["C"]["confirmed_snapshot"]["payload"]["flow_steps"] = ["竄改流程"]

    assert all_dimensions_confirmed(scbkr) is False


def test_snapshot_hash_tamper_invalidates_all_dimensions_confirmed():
    scbkr = confirm_all_dimensions(make_scbkr())
    scbkr["R"]["snapshot_hash"] = "0" * 64

    assert all_dimensions_confirmed(scbkr) is False


def test_confirmation_metadata_tamper_does_not_invalidate_snapshot():
    scbkr = confirm_all_dimensions(make_scbkr())
    scbkr["K"]["confirmation_statement"] = "更新確認文字，不改業務 payload"
    scbkr["K"]["confirmed_at"] = "2099-01-01T00:00:00+00:00"

    assert all_dimensions_confirmed(scbkr) is True


def test_hash_snapshot_is_stable_for_same_content():
    first = {"b": [2, 1], "a": "中文"}
    second = {"a": "中文", "b": [2, 1]}

    assert hash_snapshot(first) == hash_snapshot(second)


def test_get_confirmed_dimension_payload_returns_only_sealed_business_payload():
    from core.scbkr.confirmation import get_confirmed_dimension_payload

    scbkr = confirm_all_dimensions(make_scbkr())
    scbkr["S"]["confirmation_statement"] = "metadata must not leak"
    payload = get_confirmed_dimension_payload(scbkr, "S")

    assert payload == scbkr["S"]["confirmed_snapshot"]["payload"]
    for metadata_key in (
        "confirmed",
        "confirmed_at",
        "confirmed_by",
        "confirmation_statement",
        "signature",
        "snapshot_hash",
        "confirmed_snapshot",
    ):
        assert metadata_key not in payload


def test_get_confirmed_dimension_payload_raises_when_snapshot_invalid():
    from core.scbkr.confirmation import get_confirmed_dimension_payload

    scbkr = confirm_all_dimensions(make_scbkr())
    scbkr["S"]["task_name"] = "竄改後任務名稱"

    with pytest.raises(ValueError, match="sealed snapshot is invalid"):
        get_confirmed_dimension_payload(scbkr, "S")


def test_scbkr_schema_accepts_draft_and_confirmed_dimensions():
    import json
    from pathlib import Path

    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(Path("schemas/scbkr.schema.json").read_text(encoding="utf-8"))

    draft = make_scbkr()
    jsonschema.Draft202012Validator(schema).validate(draft)

    confirmed = confirm_all_dimensions(make_scbkr())
    jsonschema.Draft202012Validator(schema).validate(confirmed)
    for dimension in VALID_DIMENSIONS:
        assert confirmed[dimension]["confirmed"] is True
        assert confirmed[dimension]["snapshot_hash"]
        assert confirmed[dimension]["confirmed_snapshot"]
