import json
import os

import pytest

from core.review_rules.rule_confirmation import confirm_memory_rule_plan
from core.review_rules.rule_draft import build_memory_rule_draft
from core.storage.physical_store import (
    build_success_corpus_payload,
    commit_memory_rule,
    commit_storage_items,
    hash_payload,
    prepare_storage_payloads,
    write_json_atomic,
)


def make_passed_task():
    return {
        "task_id": "task-physical-1",
        "trace_id": "trace-physical-1",
        "ledger_id": "ledger-physical-1",
        "task_type": "general",
        "raw_input": "hello",
        "review_passed": True,
        "scbkr": {
            "confirmation_status": "confirmed",
            "confirmed_snapshot_hash": "hash123",
            "confirmed_snapshot": {"R": {"acceptance_criteria": ["ok"]}},
            "R": {"acceptance_criteria": ["ok"]},
        },
        "generation_result": {"status": "waiting_review", "content": "success", "api_key": "secret"},
        "review_result": {"status": "review_passed", "review_passed": True, "review_message": "ok"},
        "storage_plan": {"selected_targets": ["corpus", "logic", "vector"], "storage_items": []},
    }


def make_failed_task():
    task = make_passed_task()
    task.update({"task_id": "task-failed-1", "review_passed": False, "status": "review_failed"})
    task["review_result"] = {
        "status": "review_failed",
        "review_passed": False,
        "failure_report_draft": {"failure_summary": "bad output"},
        "storage_confirmed": False,
    }
    return task


def test_hash_payload_same_content_stable():
    assert hash_payload({"b": 2, "a": 1}) == hash_payload({"a": 1, "b": 2})


def test_write_json_atomic_creates_json_and_removes_tmp(tmp_path):
    path = tmp_path / "item.json"

    result = write_json_atomic(path, {"ok": True})

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["ok"] is True
    assert not list(tmp_path.glob("*.tmp"))
    assert result["content_hash"]


def test_build_success_corpus_payload_redacts_api_key():
    payload = build_success_corpus_payload(make_passed_task())

    encoded = json.dumps(payload, ensure_ascii=False)
    assert "secret" not in encoded
    assert payload["generation_result"]["api_key"] == "***REDACTED***"


def test_commit_storage_items_writes_corpus_logic_without_unapproved_vector(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    task = make_passed_task()

    items = commit_storage_items(task, task["storage_plan"])

    assert {item["target"] for item in items} == {"corpus", "logic"}
    for item in items:
        assert item["relative_path"].startswith(f"{item['target']}/")
        assert "\\" not in item["relative_path"]
        assert (tmp_path / item["relative_path"]).exists()
    assert (tmp_path / "corpus").is_dir()
    assert (tmp_path / "logic").is_dir()
    assert not (tmp_path / "exports").exists()
    assert not (tmp_path / "vector").exists()


def test_prepare_storage_payloads_gives_each_four_store_a_distinct_contract():
    task = make_passed_task()
    task["raw_input"] = "幫我生成商業文案規則表單"
    task["generation_result"]["content"] = "已驗收的商業文案規則輸出"
    task["scbkr"]["S"] = {"task_subject": "商業文案規則表單"}
    task["scbkr"]["C"] = {"core_logic": ["先確認受眾，再生成文案"], "flow_steps": ["確認需求", "生成文案"], "test_conditions": ["可驗收"]}
    task["scbkr"]["B"] = {"stop_conditions": ["不得編造價格"], "formation_conditions": ["使用者簽名"], "failure_conditions": ["模型代簽"]}
    task["scbkr"]["K"] = {"source_credibility": ["沒有四庫不得宣稱引用"]}
    task["scbkr"]["R"] = {"acceptance_criteria": ["使用者可驗收"], "failure_conditions": ["未簽名失效"]}

    payloads = prepare_storage_payloads(task, ["vector", "corpus", "logic", "memory"], task["ledger_id"])

    assert payloads["vector"]["store_role"] == "相似候選召回庫"
    assert payloads["vector"]["citation_policy"] == "discovery_index_only_not_formal_basis"
    assert "retrieval_text" in payloads["vector"]
    assert payloads["corpus"]["store_role"] == "正式資料庫"
    assert payloads["corpus"]["source_material"] == "已驗收的商業文案規則輸出"
    assert payloads["logic"]["store_role"] == "可執行規則判準庫"
    assert "不得編造價格" in payloads["logic"]["content"]
    assert payloads["memory"]["store_role"] == "長期偏好與使用者規則記憶"
    assert payloads["memory"]["memory_statement"] == "幫我生成商業文案規則表單"
    assert len({payloads[target]["content"] for target in payloads}) == 4


def test_commit_storage_items_idempotent_for_same_content(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    task = make_passed_task()

    first = commit_storage_items(task, task["storage_plan"])
    second = commit_storage_items(task, task["storage_plan"])

    assert [item["relative_path"] for item in first] == [item["relative_path"] for item in second]
    assert len(list((tmp_path / "corpus").glob("*.json"))) == 1


def test_commit_memory_rule_requires_confirmed_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    task = make_failed_task()
    task["memory_rule_confirmed_plan"] = {"memory_rule_status": "draft", "reviewer_signature": "sig"}

    with pytest.raises(ValueError):
        commit_memory_rule(task)


def test_commit_memory_rule_rejects_missing_signature(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    task = make_failed_task()
    task["memory_rule_confirmed_plan"] = {"memory_rule_status": "confirmed_plan", "reviewer_signature": ""}

    with pytest.raises(ValueError):
        commit_memory_rule(task)


def test_commit_memory_rule_writes_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    task = make_failed_task()
    draft = build_memory_rule_draft(
        task,
        task["review_result"],
        "user says bad",
        "ask for confirmation first",
        ["general"],
        ["same issue"],
        ["bad pattern"],
        ["ask first"],
    )
    task["memory_rule_confirmed_plan"] = confirm_memory_rule_plan(draft, "signed-by-user")

    rule = commit_memory_rule(task)

    assert rule["relative_path"].startswith("memory/")
    assert "\\" not in rule["relative_path"]
    assert (tmp_path / rule["relative_path"]).exists()


def test_review_failed_output_cannot_enter_corpus(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))

    with pytest.raises(ValueError):
        build_success_corpus_payload(make_failed_task())
