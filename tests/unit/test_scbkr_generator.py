import copy

import pytest

from core.scbkr.dimensions import SCBKR_DIMENSIONS, SCBKR_REQUIRED_FIELDS
from core.scbkr.generator import create_scbkr_draft
from core.scbkr.modifier import apply_scbkr_modifications, set_confirmation_status
from core.scbkr.templates import TASK_TYPE_HINTS


def test_create_scbkr_draft_has_complete_dimensions_and_required_fields():
    draft = create_scbkr_draft("請建立一個本地工作流程", task_type="workflow")

    for dimension in SCBKR_DIMENSIONS:
        assert dimension in draft
        assert set(SCBKR_REQUIRED_FIELDS[dimension]).issubset(draft[dimension])


def test_create_scbkr_draft_defaults_are_waiting_confirmation_draft():
    draft = create_scbkr_draft("請整理任務")

    assert draft["confirmation_status"] == "draft"
    assert draft["source_mode"] == "new"
    assert draft["similarity_route"] == "none"
    assert draft["source_case_ids"] == []
    assert "confirmed" not in draft


def test_task_type_hints_cover_p1_task_type_enum():
    assert tuple(TASK_TYPE_HINTS) == (
        "general",
        "coding",
        "info_search",
        "fraud_audit",
        "document_audit",
        "app_design",
        "game_design",
        "animation",
        "music",
        "privacy",
        "workflow",
        "private_memory",
    )


def test_invalid_inputs_raise_value_error():
    with pytest.raises(ValueError):
        create_scbkr_draft("   ")

    with pytest.raises(ValueError):
        create_scbkr_draft("請整理任務", task_type="unknown")

    with pytest.raises(ValueError):
        create_scbkr_draft("請整理任務", source_mode="database")

    with pytest.raises(ValueError):
        create_scbkr_draft("請整理任務", similarity_route="D")


def test_similarity_routes_only_mark_fields_without_retrieval():
    for route in ("A", "B", "C", "none"):
        draft = create_scbkr_draft(
            "請建立參考草案",
            source_mode="manual",
            similarity_route=route,
            source_case_ids=["case-1"],
        )

        assert draft["similarity_route"] == route
        assert draft["source_case_ids"] == ["case-1"]
        assert draft["K"]["history_cases"] == []
        assert draft["K"]["corpus_sources"] == []
        assert draft["B"]["external_scope"] == [
            "不呼叫 API",
            "不呼叫模型",
            "不進行外部搜尋",
            "不進行真 RAG 檢索",
        ]


def test_apply_scbkr_modifications_returns_copy_without_confirming():
    draft = create_scbkr_draft("請修改 S 維度")
    original_draft = copy.deepcopy(draft)

    modified = apply_scbkr_modifications(
        draft,
        {"S": {"task_name": "使用者修改後名稱"}, "pending_questions": ["新的確認問題"]},
    )

    assert draft == original_draft
    assert modified is not draft
    assert modified["S"]["task_name"] == "使用者修改後名稱"
    assert modified["pending_questions"] == ["新的確認問題"]
    assert modified["confirmation_status"] == "draft"


def test_set_confirmation_status_only_changes_status_field():
    draft = create_scbkr_draft("請設定狀態")
    updated = set_confirmation_status(draft, "confirmed")

    expected = copy.deepcopy(draft)
    expected["confirmation_status"] = "confirmed"

    assert updated == expected
    assert draft["confirmation_status"] == "draft"
    assert "generated_answer" not in updated


def test_set_confirmation_status_rejects_unknown_status():
    draft = create_scbkr_draft("請設定狀態")

    with pytest.raises(ValueError):
        set_confirmation_status(draft, "generating")
