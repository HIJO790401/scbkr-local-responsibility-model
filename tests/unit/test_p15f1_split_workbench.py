import json
from copy import deepcopy

from fastapi.testclient import TestClient

from apps.api import main
from core.scbkr.generator import create_scbkr_draft


def _valid_model_rulebook(subject: str) -> dict:
    return {
        "S": {
            "content": f"本規則處理「{subject}」，由使用者擔任規則擁有者與最終確認者。",
            "explanation": "S 鎖定本次任務、適用情境與規則擁有者。",
            "missing_information": ["實際交付範圍"],
            "needs_user_confirmation": ["確認適用情境"],
            "model_cannot_decide": ["使用者的最終目的"],
            "risk_notes": ["主體不清時可能套錯規則"],
        },
        "C": {
            "content": "先核對本次需求與資料，再產生草稿；若資料不足，則停止並向使用者追問。",
            "explanation": "C 寫出先核對、再草擬、缺資料就停止的判斷順序。",
            "missing_information": ["驗收順序"],
            "needs_user_confirmation": ["確認判斷順序"],
            "model_cannot_decide": ["是否接受草稿"],
            "risk_notes": ["跳過核對會造成錯誤輸出"],
        },
        "B": {
            "content": "未取得使用者確認前不得發布或執行；資料不足、範圍不明或越權時必須停止。",
            "explanation": "B 限制發布與執行，並定義停止條件。",
            "missing_information": ["禁止事項例外"],
            "needs_user_confirmation": ["確認禁止事項"],
            "model_cannot_decide": ["是否解除停止"],
            "risk_notes": ["越權可能造成外部影響"],
        },
        "K": {
            "content": "只可引用使用者已確認的本次需求與正式資料；未確認內容、聊天猜測與 VECTOR 候選不可引用。",
            "explanation": "K 區分可引用正式資料與不可引用候選。",
            "missing_information": ["正式資料清單"],
            "needs_user_confirmation": ["確認可引用資料"],
            "model_cannot_decide": ["資料是否真實"],
            "risk_notes": ["錯誤引用會污染規則"],
        },
        "R": {
            "content": "使用者逐欄驗收並簽名後規則才成立；模型不能簽名、入庫或啟用，錯誤時由使用者回放並修復。",
            "explanation": "R 把驗收、簽名、責任與修復留給使用者。",
            "missing_information": ["簽名聲明"],
            "needs_user_confirmation": ["使用者簽名"],
            "model_cannot_decide": ["現實行動責任"],
            "risk_notes": ["未簽名規則不得引用"],
        },
        "rule_summary": f"{subject}的可編輯 SCBKR 規則草稿。",
        "missing_information": ["實際交付範圍"],
        "user_confirmation_items": ["逐欄確認 S/C/B/K/R"],
        "model_cannot_decide": ["是否簽名與正式啟用"],
        "risk_reminders": ["模型不得代替使用者簽名"],
        "next_actions": ["使用者修改並簽名"],
    }


def _configure_connected_model(monkeypatch, subject: str) -> None:
    main.MODEL_SETTINGS.update({
        "enabled": True,
        "last_test_status": "success",
        "mode": "local",
        "provider": "lm_studio",
        "model_name": "fake-local-scbkr",
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key": "local",
    })
    main.PERMISSIONS["model_generate"] = True
    payload = _valid_model_rulebook(subject)
    monkeypatch.setattr(
        main,
        "_post_openai_compatible",
        lambda settings, messages, response_format=None: {
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 180},
        },
    )


def test_internal_draft_generator_is_domain_specific_and_not_p1_p4_templates():
    samples = [
        "我要寫一個滷肉飯商業文案",
        "我覺得情報類輸出如果沒有責任主體、沒有邊界判定、沒有框架判詞，就不該入庫。",
        "請把這個 UI 原則整理成可重用規則：一般聊天要像大模型，工作台放右側或手機抽屜。",
        "我要寫一個紫蘇梅冰沙開幕宣傳文案",
    ]
    drafts = [create_scbkr_draft(s) for s in samples]
    signatures = {(d["S"]["task_name"], d["S"]["task_subject"], d["S"]["output_format"]) for d in drafts}
    assert len(signatures) == 4
    serialized = json.dumps(drafts, ensure_ascii=False)
    for forbidden in ("一般任務草案", "P1", "P4", "不呼叫模型", "Python dict"):
        assert forbidden not in serialized
    assert "紫蘇梅冰沙開幕宣傳文案" in drafts[3]["S"]["task_subject"]
    assert "標題、短文案、行動呼籲 CTA" == drafts[3]["S"]["output_format"]


def test_fake_model_valid_draft_is_written_to_task_and_workbench(monkeypatch):
    client = TestClient(main.app)
    _configure_connected_model(monkeypatch, "紫蘇梅冰沙開幕宣傳文案")
    response = client.post("/api/tasks/create", json={"raw_input": "我要寫一個紫蘇梅冰沙開幕宣傳文案", "task_type": "general", "create_scbkr_draft": True})
    assert response.status_code == 200
    task = response.json()
    assert task["scbkr"]["draft_source"] == "model_assisted_rulebook"
    assert task["scbkr"]["fallback_used"] is False
    assert task["model_used"] is True
    readback = main.get_task(task["task_id"])
    assert readback["scbkr"]["draft_source"] == "model_assisted_rulebook"


def test_remote_external_disabled_stops_and_loopback_model_can_author(monkeypatch):
    client = TestClient(main.app)
    monkeypatch.setitem(main.PERMISSIONS, "external_api", False)
    monkeypatch.setitem(main.MODEL_SETTINGS, "enabled", True)
    monkeypatch.setitem(main.MODEL_SETTINGS, "last_test_status", "success")
    monkeypatch.setitem(main.MODEL_SETTINGS, "mode", "external")
    monkeypatch.setitem(main.MODEL_SETTINGS, "provider", "openai_compatible")
    monkeypatch.setitem(main.MODEL_SETTINGS, "model_name", "remote-test-model")
    monkeypatch.setitem(main.MODEL_SETTINGS, "base_url", "https://api.example.com/v1")
    called = {"value": False}
    monkeypatch.setattr(main, "_post_openai_compatible", lambda *a, **k: called.__setitem__("value", True))
    r = client.post("/api/tasks/create", json={"raw_input": "我要寫一個滷肉飯商業文案", "task_type": "general", "create_scbkr_draft": True})
    assert r.status_code == 200
    assert called["value"] is False
    assert r.json()["status"] == "model_unavailable"
    assert r.json()["fallback_used"] is False
    assert "scbkr" not in r.json()

    _configure_connected_model(monkeypatch, "紫蘇梅冰沙開幕宣傳文案")
    r2 = client.post("/api/tasks/create", json={"raw_input": "我要寫一個紫蘇梅冰沙開幕宣傳文案", "task_type": "general", "create_scbkr_draft": True})
    assert r2.status_code == 200
    assert r2.json()["scbkr"]["fallback_used"] is False
    assert r2.json()["draft_source"] == "model_assisted_rulebook"


def test_generation_contract_violation_stops_before_waiting_review(monkeypatch):
    client = TestClient(main.app)
    _configure_connected_model(monkeypatch, "紫蘇梅冰沙開幕宣傳文案")
    task = client.post("/api/tasks/create", json={"raw_input": "我要寫一個紫蘇梅冰沙開幕宣傳文案", "task_type": "general", "create_scbkr_draft": True}).json()
    confirmed = client.post(f"/api/tasks/{task['task_id']}/confirm", json={"scbkr": task["scbkr"], "confirmed_by": "user", "signature": "user"}).json()
    assert confirmed["status"] == "confirmed"
    monkeypatch.setitem(main.MODEL_SETTINGS, "provider", "sandbox_mock_model")
    monkeypatch.setitem(main.MODEL_SETTINGS, "mode", "sandbox")
    monkeypatch.setattr(main, "generate_with_sandbox_model", lambda task, scbkr: {"generated_text": "SCBKR 草案 confirmation_status 等待使用者確認", "content": "SCBKR 草案 confirmation_status 等待使用者確認"})
    out = client.post(f"/api/tasks/{task['task_id']}/generate").json()
    assert out["status"] == "confirmed"
    assert out["generation_result"]["status"] == "generation_contract_violation"
