import pytest
from fastapi import HTTPException

from apps.api import main
from core.scbkr.draft_grammar import build_scbkr_from_understanding, classify_evidence_relation


def test_base_logic_not_fallback_and_human_logic_complete():
    draft = build_scbkr_from_understanding("我要把我對人類只有描述，沒有確定性邏輯的生成一個責任確認單", "general", None, {"adopted_hits": []})
    assert draft["draft_source"] == "scbkr_base_logic"
    assert draft["fallback_used"] is False
    assert draft["model_participated"] is False
    for dim in "SCBKR":
        assert dim in draft
    assert "不得把使用者主體判斷稀釋成外部中立描述" in "\n".join(draft["B"]["stop_conditions"])
    assert "VOID" in "\n".join(draft["B"]["stop_conditions"])
    assert draft["R"]["owner_signature_required"] is True
    assert "本次未採用四庫資料" in draft["K"]["source_credibility"]


def test_model_understanding_success_source():
    draft = build_scbkr_from_understanding("請建立工作流程確認單", "general", {"task_subject": "工作流程", "model_role": "describe_compile_only"}, {"adopted_hits": []})
    assert draft["draft_source"] == "model_assisted_structured"
    assert draft["model_participated"] is True


def test_missing_subject_draft_failed():
    draft = build_scbkr_from_understanding("嗯", "general", None, {})
    assert draft["draft_source"] == "draft_failed"
    assert "S" not in draft


def test_evidence_generic_copywriting_not_adopted():
    relation = classify_evidence_relation("我要做一個商業文案", "滷肉飯文案範例")
    assert relation["adopted"] is False
    assert relation["relation"] in {"candidate_only", "irrelevant"}
    grammar = classify_evidence_relation("我要做滷肉飯文案", "SCBKR UI 工作台規則")
    assert grammar["adopted"] is False


def test_confirm_requires_owner_signature(monkeypatch):
    task = {"task_id": "t-p15o", "trace_id": "tr", "ledger_id": "lg", "task_type": "general", "raw_input": "請建立工作流程確認單", "status": "waiting_user_confirm", "confirmed": False}
    task["scbkr"] = build_scbkr_from_understanding(task["raw_input"], "general", None, {})
    main.TASKS[task["task_id"]] = task
    monkeypatch.setattr(main, "save_task", lambda t: t)
    monkeypatch.setattr(main, "save_scbkr_confirmation", lambda *a, **k: {})
    monkeypatch.setattr(main, "_append_task_event", lambda *a, **k: {})
    with pytest.raises(HTTPException) as missing:
        main.confirm_task(task["task_id"], {"confirmed_by": "user"})
    assert missing.value.status_code == 400
    assert missing.value.detail == "owner signature is required before SCBKR confirmation"
    for signer in ("model", "assistant", "system"):
        with pytest.raises(HTTPException) as blocked:
            main.confirm_task(task["task_id"], {"confirmed_by": signer, "signature": signer})
        assert blocked.value.detail == "model cannot sign or confirm SCBKR"
    result = main.confirm_task(task["task_id"], {"confirmed_by": "user", "signature": "owner"})
    assert result["confirmed"] is True
    assert result["scbkr"]["signature_status"] == "owner_signed"
