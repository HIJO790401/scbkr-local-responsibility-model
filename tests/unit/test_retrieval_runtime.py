import pytest
from core.retrieval.case_builder import build_success_case_from_storage_item, build_memory_rule_case
from core.retrieval.similarity import score_similarity, route_from_score
from core.retrieval.retrieval_runtime import query_retrieval_cases
from core.storage.sqlite_runtime import save_retrieval_case


def task(passed=True):
    return {"task_id":"t1","status":"storage_committed" if passed else "review_failed","physical_write_performed":True,"review_passed":passed,"task_type":"code","raw_input":"修正 API bug","review_result":{"review_passed":passed,"status":"review_passed" if passed else "review_failed"},"generation_result":{"output":"fixed api bug"},"scbkr":{"R":{"acceptance_criteria":["tests pass"]}}}

def item(): return {"target":"corpus","relative_path":"corpus/x.json","content_hash":"abc"}

def test_success_and_failed_case_building_sanitizes_secrets():
    case=build_success_case_from_storage_item(task(True), item(), {"review_result":{"review_passed":True},"api_key":"secret"})
    assert case["case_type"] == "success_case"
    assert "api_key" not in case["retrieval_text"].lower()
    assert "secret" not in case["retrieval_text"].lower()
    with pytest.raises(ValueError): build_success_case_from_storage_item(task(False), item(), {"review_result":{"review_passed":False}})

def test_memory_rule_draft_rejected_signed_rule_accepted():
    base={"task_id":"t1","rule_hash":"rh","relative_path":"memory/x.json"}
    for plan in ({"memory_rule_status":"draft"}, {"memory_rule_status":None}, {}):
        with pytest.raises(ValueError):
            build_memory_rule_case({**base,"reviewer_signature":"sig","payload":{"memory_rule_confirmed_plan":plan}})
    with pytest.raises(ValueError):
        build_memory_rule_case({**base,"reviewer_signature":"","payload":{"memory_rule_confirmed_plan":{"memory_rule_status":"confirmed_plan"}}})
    signed={**base,"reviewer_signature":"sig","payload":{"memory_rule_confirmed_plan":{"memory_rule_status":"confirmed_plan","rule_statement":"Always test","required_behavior":["test"],"forbidden_patterns":["skip"]}}}
    assert build_memory_rule_case(signed)["case_type"] == "signed_memory_rule"

def test_similarity_routes_and_query_flags(tmp_path):
    assert score_similarity("same content", "same content") >= 0.78
    assert score_similarity("apple", "汽車") < 0.35
    assert [route_from_score(x) for x in (0.8,0.45,0.1,0)] == ["A","B","C","none"]

def test_query_runtime_flags_and_empty_query(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    save_retrieval_case({"case_id":"c1","case_type":"success_case","task_id":"t0","retrieval_text":"python api bug fix","retrieval_text_hash":"h"})
    with pytest.raises(ValueError): query_retrieval_cases("   ")
    result=query_retrieval_cases("api bug", top_k=1)
    assert result["candidates"]
    assert result["requires_user_confirmation"] is True
    assert result["auto_confirmed"] is False
    assert result["generation_allowed"] is False
