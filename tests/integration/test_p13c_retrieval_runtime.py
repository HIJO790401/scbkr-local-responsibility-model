import importlib
import sqlite3
from pathlib import Path


def test_p13c_retrieval_runtime_api_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    import core.ledger.jsonl_ledger as ledger
    main = importlib.reload(main); ledger = importlib.reload(ledger)
    main.MODEL_SETTINGS.update({"mode":"local","enabled":True})
    t=main.create_task({"raw_input":"build local retrieval API", "task_type":"coding"})
    assert not (tmp_path/"vector_db").exists()
    t=main.create_scbkr(t["task_id"]); t=main.confirm_task(t["task_id"], {"signature":"sig"})
    t["generation_result"]={"status":"waiting_review","review_passed":False,"storage_confirmed":False,"output":"local retrieval API implementation"}; t["status"]="waiting_review"; main.save_task(t)
    t=main.review(t["task_id"], {"review_decision":"pass","reviewer_signature":"sig"})
    t=main.storage_request(t["task_id"])
    t=main.storage_confirm(t["task_id"], {"storage_confirmed":True,"confirmed_by":"user","signature":"sig","selected_targets":["corpus","logic","exports"]})
    assert not (tmp_path/"vector_db").exists()
    indexed=main.index_task_retrieval(t["task_id"])
    assert indexed["indexed_cases"]
    with sqlite3.connect(tmp_path/"scbkr.sqlite3") as conn:
        assert conn.execute("select count(*) from retrieval_cases").fetchone()[0] > 0
    assert "retrieval_case_index_completed" in [e["event_type"] for e in ledger.read_ledger_events(task_id=t["task_id"])]
    q=main.retrieval_query({"query_text":"local retrieval API", "top_k":3, "case_type":"any"})
    assert q["candidates"] and q["route"] in ("A","B","C","none")
    tq=main.task_retrieval_query(t["task_id"], {"top_k":2})
    updated=main.get_task(t["task_id"])
    assert updated["retrieval_result"]["query_id"] == tq["query_id"]
    assert updated["confirmed"] is True
    assert updated["retrieval_result"]["auto_confirmed"] is False
    assert updated["retrieval_result"]["generation_allowed"] is False


def test_p13c_review_failed_and_memory_rule_index(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    main = importlib.reload(main)
    t=main.create_task({"raw_input":"bad output", "task_type":"coding"})
    t["review_result"]={"status":"review_failed","review_passed":False,"storage_confirmed":False,"failure_report_draft":{}}; t["review_passed"]=False; t["status"]="review_failed"; main.save_task(t)
    try:
        main.index_task_retrieval(t["task_id"])
        assert False
    except Exception:
        pass
    main.memory_rule_draft(t["task_id"], {"user_failure_judgement":"failed","rule_statement":"Do not skip tests","applies_to_task_types":["coding"],"trigger_conditions":["coding"],"forbidden_patterns":["skip tests"],"required_behavior":["run tests"]})
    before=main.index_memory_rules()["indexed_cases"]
    assert before == []
    main.memory_rule_confirm(t["task_id"], {"reviewer_signature":"sig"})
    after=main.index_memory_rules()["indexed_cases"]
    assert any(c["case_type"] == "signed_memory_rule" for c in after)
