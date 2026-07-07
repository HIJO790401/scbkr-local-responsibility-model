from pathlib import Path

import pytest
from fastapi import HTTPException

from apps.api import main
from core.scbkr.draft_grammar import (
    build_scbkr_from_understanding,
    normalize_list,
    normalize_task_understanding,
)
from core.storage.sqlite_runtime import list_storage_items as list_persisted_storage_items

APP = Path("apps/web/src/V2App.tsx").read_text(encoding="utf-8")


def test_task_understanding_scalar_strings_are_not_split():
    draft = build_scbkr_from_understanding(
        "請建立日期確認規則確認單",
        "general",
        {
            "task_subject": "日期確認規則",
            "boundary_rules": "不得自行確認日期",
            "acceptance_criteria": "使用者簽名後才成立",
            "causal_chain": "輸入不足 → 無法驗收",
            "output_format": "短文案",
            "model_role": "describe_compile_only",
        },
        {"adopted_hits": []},
    )
    assert "不得自行確認日期" in draft["B"]["stop_conditions"]
    assert "不得" not in draft["B"]["stop_conditions"][-8:]
    assert "使用者簽名後才成立" in draft["R"]["acceptance_criteria"]
    assert draft["C"]["core_logic"] == ["輸入不足 → 無法驗收"]
    assert draft["S"]["output_format"] == ["短文案"]


def test_normalizer_removes_nulls_and_prevents_none_core_logic():
    normalized = normalize_task_understanding({"task_subject": "測試", "output_format": "短文案", "boundary_rules": [None, "", "null", "不得自行確認日期"], "model_role": "describe_compile_only"})
    assert normalized["output_format"] == ["短文案"]
    assert normalized["boundary_rules"] == ["不得自行確認日期"]
    assert normalize_list([None, "", "None", "null", "A", ["A", "B"]]) == ["A", "B"]
    draft = build_scbkr_from_understanding("請建立測試確認單", "general", {"task_subject": "測試", "core_claim": None, "model_role": "describe_compile_only"}, {"adopted_hits": []})
    assert draft["C"]["core_logic"] != [None]


def test_frontend_owner_signature_contract():
    assert 'signature: "user"' not in APP
    assert 'const [ownerSignature, setOwnerSignature] = useState("")' in APP
    assert "使用者簽名" in APP
    assert "模型不能簽名" in APP
    assert "signature: ownerSignature.trim()" in APP
    assert "reviewer_signature: ownerSignature.trim()" in APP
    assert "disabled={!ownerSignature.trim()}" in APP


def test_patch_resets_signature_and_downstream(monkeypatch):
    task = main.create_task({"raw_input": "請建立交易防詐規則確認單", "task_type": "general", "create_scbkr_draft": True})
    confirmed = main.confirm_task(task["task_id"], {"confirmed_by": "user", "signature": "owner"})
    confirmed["generation_result"] = {"content": "old"}
    confirmed["review_result"] = {"review_passed": True}
    confirmed["storage_plan"] = {"selected_targets": ["vector"]}
    confirmed["storage_result"] = {"written_items": []}
    confirmed["review_passed"] = True
    main.save_task(confirmed)
    patch = main.scbkr_patch_draft(confirmed["task_id"], {"layer": "B", "instruction": "補上行動邊界、後果與實體查證"})["patch"]
    result = main.apply_scbkr_patch(confirmed["task_id"], {"patch": patch})
    assert result["confirmed"] is False
    assert result["scbkr"]["signature_status"] == "waiting_owner_signature"
    assert result["scbkr"]["R"]["signature_status"] == "waiting_owner_signature"
    for key in ("generation_result", "review_result", "storage_plan", "storage_result"):
        assert key not in result


def test_unsigned_and_unavailable_storage_items_are_not_adopted(monkeypatch):
    unsigned_item = {"item_id": "u1", "target": "logic", "status": "active", "payload": {"summary": "二手手機交易防詐檢查規則", "signature_status": "waiting_owner_signature", "review_passed": True}}
    revoked_item = {"item_id": "r1", "target": "logic", "status": "revoked", "payload": {"summary": "二手手機交易防詐檢查規則", "signature_status": "owner_signed", "review_passed": True}}
    monkeypatch.setattr(main, "query_retrieval_cases", lambda *a, **k: {"candidates": []})
    monkeypatch.setattr(main, "list_persisted_storage_items", lambda limit=50: [unsigned_item, revoked_item])
    monkeypatch.setattr(main, "list_persisted_memory_rules", lambda limit=20: [])
    context = main._build_four_store_context("二手手機交易防詐檢查規則")
    assert context["hits"] == []
    reasons = [hit["reason"] for hit in context["rejected_hits"]]
    assert "未完成使用者簽名" in reasons
    assert "狀態不可用：revoked / archived / superseded" in reasons


def test_signed_storage_e2e_then_followup_adopts(monkeypatch, tmp_path):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    main.TASKS.clear()
    main.PERMISSIONS["model_generate"] = True
    main.MODEL_SETTINGS.update({"mode": "sandbox", "provider": "sandbox_mock_model", "enabled": True, "model_name": "sandbox_mock_model"})
    task = main.create_task({"raw_input": "我想做一套二手手機交易防詐檢查規則，以後遇到買賣對話可以先審一遍，幫我生成確認單。", "task_type": "general", "create_scbkr_draft": True})
    patch = main.scbkr_patch_draft(task["task_id"], {"layer": "B", "instruction": "這個交易核心判斷沒有明確說明行動邊界、後果與實體查證，幫我改好。"})["patch"]
    task = main.apply_scbkr_patch(task["task_id"], {"patch": patch})
    assert task["scbkr"]["signature_status"] == "waiting_owner_signature"
    task = main.confirm_task(task["task_id"], {"confirmed_by": "user", "signature": "owner-trade"})
    assert task["confirmed"] is True and task["scbkr"]["signature_status"] == "owner_signed"
    task = main.generate(task["task_id"])
    task = main.review(task["task_id"], {"review_decision": "pass", "reviewer_signature": "owner-trade"})
    suggestion = main.storage_suggestion(task["task_id"])
    assert suggestion["suggestions"]["vector"]["recommended"] is True
    assert suggestion["suggestions"]["corpus"]["recommended"] is False
    assert suggestion["suggestions"]["logic"]["recommended"] is True
    assert suggestion["suggestions"]["memory"]["recommended"] is True
    task = main.storage_request(task["task_id"], {"selected_targets": ["vector", "logic", "memory"], "user_decision": "custom", "signature": "owner-trade"})
    task = main.storage_confirm(task["task_id"], {"storage_confirmed": True, "second_confirm": True, "confirmed_by": "user", "signature": "owner-trade", "selected_targets": ["vector", "logic", "memory"]})
    assert set(task["storage_result"]["written_targets"]) == {"vector", "logic", "memory"}
    stored = list_persisted_storage_items(limit=20)
    assert {item["target"] for item in stored} >= {"vector", "logic", "memory"}
    context = main._build_four_store_context("幫我看這段二手手機交易對話有沒有風險")
    assert context["hits"]
    hit = context["hits"][0]
    assert hit["adopted"] is True
    assert hit["signature_status"] == "owner_signed"
    assert hit["content_hash"]
