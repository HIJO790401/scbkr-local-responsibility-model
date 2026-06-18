import json
from pathlib import Path

import pytest

from core.retrieval.retrieval_result import build_empty_retrieval_result, build_retrieval_result
from core.retrieval.similarity import rank_candidate_cases, route_from_score, score_case_similarity
from core.retrieval.vector_case import (
    assert_case_eligible_for_retrieval,
    build_vector_case_from_storage_plan,
)


def make_task(**overrides):
    task = {
        "task_id": "task-1",
        "task_type": "workflow",
        "task_name": "local workflow audit",
        "raw_input": "local workflow audit",
    }
    task.update(overrides)
    return task


def make_scbkr(text="local workflow audit boundary review"):
    return {dimension: text for dimension in ("S", "C", "B", "K", "R")}


def make_storage_plan(**overrides):
    plan = {
        "storage_plan_status": "storage_confirmed_plan",
        "storage_confirmed": True,
        "physical_write_performed": False,
    }
    plan.update(overrides)
    return plan


def make_case(**overrides):
    case = build_vector_case_from_storage_plan(
        make_task(),
        make_scbkr(),
        make_storage_plan(),
        case_id="case-1",
    )
    case.update(overrides)
    return case


def test_vector_case_schema_is_valid_json_schema_shape():
    schema = json.loads(Path("schemas/vector_case.schema.json").read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert set(schema["properties"]["scbkr_summary"]["required"]) == {"S", "C", "B", "K", "R"}
    assert schema["properties"]["embedding_status"]["enum"] == ["not_created", "created_later"]


def test_build_vector_case_from_storage_plan_defaults_are_eligible_shape():
    case = make_case()

    assert case["review_passed"] is True
    assert case["storage_confirmed"] is True
    assert case["storage_plan_status"] == "storage_confirmed_plan"
    assert case["source"] == "storage_commit_plan"
    assert case["embedding_status"] == "not_created"
    assert case["physical_write_performed"] is False


def test_case_eligibility_rejects_untrusted_or_failed_content():
    rejected_cases = [
        make_case(review_passed=False),
        make_case(storage_confirmed=False),
        make_case(storage_plan_status="draft"),
        make_case(source="manual"),
        make_case(failure_report_draft={}),
        make_case(memory_rule_status="not_created"),
        make_case(memory_rule_confirmed=True),
        make_case(memory_rule_stored=True),
        make_case(rule_candidate_status="draft_only"),
    ]

    for case in rejected_cases:
        with pytest.raises(ValueError):
            assert_case_eligible_for_retrieval(case)


def test_similarity_routes_for_score_thresholds():
    assert route_from_score(0.75) == "A"
    assert route_from_score(0.45) == "B"
    assert route_from_score(0.01) == "C"
    assert route_from_score(0) == "none"


def test_score_case_similarity_can_produce_high_route_a():
    case = make_case()
    score = score_case_similarity("local workflow audit", "workflow", make_scbkr(), case)

    assert score >= 0.75
    assert route_from_score(score) == "A"


def test_rank_candidate_cases_returns_top_three_and_rejects_ineligible():
    cases = [
        make_case(case_id="case-a", task_summary="local workflow audit"),
        make_case(case_id="case-b", task_summary="workflow audit"),
        make_case(case_id="case-c", task_summary="audit"),
        make_case(case_id="case-d", task_summary="other"),
    ]
    ranked = rank_candidate_cases("local workflow audit", "workflow", make_scbkr(), cases, top_k=3)

    assert len(ranked) == 3
    assert ranked[0]["score"] >= ranked[1]["score"] >= ranked[2]["score"]

    with pytest.raises(ValueError):
        rank_candidate_cases("query", "workflow", make_scbkr(), [make_case(review_passed=False)])


def test_retrieval_result_always_requires_user_confirmation():
    ranked = rank_candidate_cases("local workflow audit", "workflow", make_scbkr(), [make_case()], top_k=3)
    result = build_retrieval_result("local workflow audit", ranked)

    assert result["similarity_route"] == "A"
    assert result["usable_as_reference"] is True
    assert result["requires_user_confirmation"] is True
    assert result["physical_vector_search_performed"] is False
    assert result["embedding_created"] is False
    assert "不得跳過 SCBKR 使用者確認" in result["route_reason"]


def test_empty_retrieval_result_none_route_is_not_usable_reference():
    result = build_empty_retrieval_result("全新任務")

    assert result["similarity_route"] == "none"
    assert result["usable_as_reference"] is False
    assert result["requires_user_confirmation"] is True
    assert result["physical_vector_search_performed"] is False
    assert result["embedding_created"] is False
