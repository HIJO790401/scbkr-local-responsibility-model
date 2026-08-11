from pathlib import Path

from apps.api import main
from core.scbkr.draft_grammar import (
    build_scbkr_from_understanding,
    normalize_list,
    normalize_task_understanding,
)

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
    assert "狀態不可用：disabled / revoked / archived / superseded / deleted" in reasons
