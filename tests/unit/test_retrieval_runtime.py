import pytest
from core.retrieval.case_builder import build_success_case_from_storage_item, build_memory_rule_case
from core.retrieval.similarity import score_similarity, route_from_score
from core.retrieval.retrieval_runtime import query_retrieval_cases
from core.storage.sqlite_runtime import save_retrieval_case


def task(passed=True):
    return {"task_id":"t1","status":"storage_committed" if passed else "review_failed","physical_write_performed":True,"storage_confirmed":passed,"review_passed":passed,"task_type":"code","raw_input":"修正 API bug","review_result":{"review_passed":passed,"status":"review_passed" if passed else "review_failed"},"generation_result":{"output":"fixed api bug"},"scbkr":{"R":{"acceptance_criteria":["tests pass"]}}}

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


def test_chromadb_low_score_does_not_hide_sqlite_exact_match(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import core.retrieval.retrieval_runtime as runtime
    save_retrieval_case({"case_id":"sqlite-exact","case_type":"success_case","task_id":"t2","retrieval_text":"unique fallback exact match phrase","retrieval_text_hash":"h2"})
    monkeypatch.setattr(runtime, "is_chromadb_available", lambda: True)
    monkeypatch.setattr(runtime, "query_similar_cases", lambda *a, **k: {"backend":"chromadb","status":"ok","candidates":[{"case_id":"old","retrieval_text":"unrelated old candidate","score":0.01,"route":"C"}]})
    result = runtime.query_retrieval_cases("unique fallback exact match phrase", top_k=2)
    assert result["candidates"][0]["case_id"] == "sqlite-exact"
    assert result["candidates"][0]["route"] != "none"
    assert result["backend"] in ("merged_chromadb_sqlite", "chromadb+sqlite_fallback_checked")


def test_chromadb_candidates_still_check_sqlite_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import core.retrieval.retrieval_runtime as runtime
    save_retrieval_case({"case_id":"sqlite-used","case_type":"success_case","task_id":"t2","retrieval_text":"sqlite fallback participates","retrieval_text_hash":"h2"})
    called = {"sqlite": False}
    original = runtime.list_retrieval_cases
    def wrapped_list(*args, **kwargs):
        called["sqlite"] = True
        return original(*args, **kwargs)
    monkeypatch.setattr(runtime, "list_retrieval_cases", wrapped_list)
    monkeypatch.setattr(runtime, "is_chromadb_available", lambda: True)
    monkeypatch.setattr(runtime, "query_similar_cases", lambda *a, **k: {"backend":"chromadb","status":"ok","candidates":[{"case_id":"chroma","retrieval_text":"chroma result"}]})
    result = runtime.query_retrieval_cases("sqlite fallback participates", top_k=3)
    assert called["sqlite"] is True
    assert any(c["case_id"] == "sqlite-used" for c in result["candidates"])


def test_merge_deduplicates_same_case_id_and_scores_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import core.retrieval.retrieval_runtime as runtime
    save_retrieval_case({"case_id":"dupe","case_type":"success_case","task_id":"t2","retrieval_text":"duplicate exact match","retrieval_text_hash":"h2"})
    monkeypatch.setattr(runtime, "is_chromadb_available", lambda: True)
    monkeypatch.setattr(runtime, "query_similar_cases", lambda *a, **k: {"backend":"chromadb","status":"ok","candidates":[{"case_id":"dupe","retrieval_text":"duplicate exact match","score":0.2,"route":"C"}]})
    result = runtime.query_retrieval_cases("duplicate exact match", top_k=3)
    ids = [c["case_id"] for c in result["candidates"]]
    assert ids.count("dupe") == 1
    assert "score" in result["candidates"][0]
    assert "route" in result["candidates"][0]


def test_chromadb_candidate_without_score_gets_score_and_route(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import core.retrieval.retrieval_runtime as runtime
    monkeypatch.setattr(runtime, "is_chromadb_available", lambda: True)
    monkeypatch.setattr(runtime, "query_similar_cases", lambda *a, **k: {"backend":"chromadb","status":"ok","candidates":[{"case_id":"chroma","retrieval_text":"score route fill"}]})
    result = runtime.query_retrieval_cases("score route fill", top_k=1)
    assert result["candidates"][0]["case_id"] == "chroma"
    assert result["candidates"][0]["score"] > 0
    assert result["candidates"][0]["route"] != "none"


def test_sqlite_fallback_only_case_not_shadowed_by_nonempty_chromadb(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import core.retrieval.retrieval_runtime as runtime
    save_retrieval_case({"case_id":"fallback-only","case_type":"success_case","task_id":"t2","retrieval_text":"fallback only searchable exact","retrieval_text_hash":"h2"})
    monkeypatch.setattr(runtime, "is_chromadb_available", lambda: True)
    monkeypatch.setattr(runtime, "query_similar_cases", lambda *a, **k: {"backend":"chromadb","status":"ok","candidates":[{"case_id":"old-chroma","retrieval_text":"some nonempty stale chroma candidate"}]})
    result = runtime.query_retrieval_cases("fallback only searchable exact", top_k=2)
    assert any(c["case_id"] == "fallback-only" for c in result["candidates"])
    assert result["candidates"][0]["case_id"] == "fallback-only"


def test_sqlite_fallback_scores_all_rows_before_top_k_when_exact_match_is_old(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import core.ledger.jsonl_ledger as ledger
    import core.retrieval.retrieval_runtime as runtime

    exact_text = "old durable sqlite exact needle p13c fallback"
    save_retrieval_case({
        "case_id":"old-exact",
        "case_type":"success_case",
        "task_id":"old-task",
        "retrieval_text":exact_text,
        "retrieval_text_hash":"old-hash",
        "created_at":"2000-01-01T00:00:00+00:00",
    })
    for index in range(260):
        save_retrieval_case({
            "case_id":f"newer-{index:03d}",
            "case_type":"success_case",
            "task_id":f"newer-task-{index:03d}",
            "retrieval_text":f"newer unrelated retrieval row {index:03d}",
            "retrieval_text_hash":f"newer-hash-{index:03d}",
            "created_at":f"2026-01-01T00:{index // 60:02d}:{index % 60:02d}+00:00",
        })

    monkeypatch.setattr(runtime, "is_chromadb_available", lambda: True)
    monkeypatch.setattr(runtime, "query_similar_cases", lambda *a, **k: {"backend":"chromadb","status":"ok","candidates":[{"case_id":"stale-chroma","retrieval_text":"old stale chromadb candidate"}]})

    top_one = runtime.query_retrieval_cases(exact_text, top_k=1)
    assert [candidate["case_id"] for candidate in top_one["candidates"]] == ["old-exact"]
    assert top_one["route"] != "none"
    assert top_one["requires_user_confirmation"] is True
    assert top_one["auto_confirmed"] is False
    assert top_one["generation_allowed"] is False

    top_two = runtime.query_retrieval_cases(exact_text, top_k=2)
    ids = [candidate["case_id"] for candidate in top_two["candidates"]]
    assert "old-exact" in ids
    assert ids.index("old-exact") < ids.index("stale-chroma")
    assert "retrieval_query_completed" in [event["event_type"] for event in ledger.read_ledger_events()]



def test_index_task_storage_cases_allows_completed_and_enforces_gates(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import importlib
    import core.retrieval.retrieval_runtime as runtime
    runtime = importlib.reload(runtime)

    base = task(True)
    base.update({
        "status": "completed",
        "storage_items": [{"target": "corpus", "relative_path": "corpus/completed.json", "content_hash": "donehash"}],
    })
    payload_dir = tmp_path / "corpus"
    payload_dir.mkdir()
    (payload_dir / "completed.json").write_text('{"review_result":{"review_passed":true},"generation_result":{"output":"completed retrieval indexed case"}}', encoding="utf-8")

    indexed = runtime.index_task_storage_cases(base)
    assert indexed["indexed_cases"]

    for field in ("review_passed", "storage_confirmed", "physical_write_performed"):
        invalid = dict(base)
        invalid[field] = False
        with pytest.raises(ValueError):
            runtime.index_task_storage_cases(invalid)

    review_failed = dict(base, status="review_failed", review_passed=False)
    with pytest.raises(ValueError):
        runtime.index_task_storage_cases(review_failed)
