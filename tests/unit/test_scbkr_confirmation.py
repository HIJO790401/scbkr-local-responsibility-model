import pytest

from core.scbkr.confirmation import (
    VALID_DIMENSIONS,
    all_dimensions_confirmed,
    confirm_all_dimensions,
    confirm_dimension,
    hash_snapshot,
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


def test_all_dimensions_confirmed_is_false_when_only_one_dimension_is_confirmed():
    scbkr = confirm_dimension(make_scbkr(), "S")

    assert all_dimensions_confirmed(scbkr) is False


def test_confirm_all_dimensions_confirms_every_dimension_and_scbkr_snapshot_hash():
    scbkr = confirm_all_dimensions(make_scbkr())

    assert all_dimensions_confirmed(scbkr) is True
    assert scbkr["confirmed"] is True
    assert scbkr["confirmation_status"] == "confirmed"
    assert scbkr["confirmed_snapshot_hash"]


def test_hash_snapshot_is_stable_for_same_content():
    first = {"b": [2, 1], "a": "中文"}
    second = {"a": "中文", "b": [2, 1]}

    assert hash_snapshot(first) == hash_snapshot(second)
