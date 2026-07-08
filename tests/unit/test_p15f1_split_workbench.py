import json
from copy import deepcopy

from fastapi.testclient import TestClient

from apps.api import main
from core.scbkr.generator import create_scbkr_draft


def test_fallback_drafts_are_semantic_and_not_p1_p4_templates():
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
    fake = create_scbkr_draft("我要寫一個紫蘇梅冰沙開幕宣傳文案")
    fake["S"]["task_name"] = "FAKE_MODEL_DRAFT_紫蘇梅冰沙開幕宣傳"
    fake["S"]["output_format"] = "FAKE_MODEL_OUTPUT_標題_短文案_CTA"
    monkeypatch.setitem(main.MODEL_SETTINGS, "enabled", True)
    monkeypatch.setitem(main.MODEL_SETTINGS, "mode", "local")
    monkeypatch.setitem(main.MODEL_SETTINGS, "base_url", "http://127.0.0.1:1234/v1")
    monkeypatch.setattr(main, "_post_openai_compatible", lambda settings, messages: {"choices": [{"message": {"content": json.dumps(fake, ensure_ascii=False)}}]})
    response = client.post("/api/tasks/create", json={"raw_input": "我要寫一個紫蘇梅冰沙開幕宣傳文案", "task_type": "general", "create_scbkr_draft": True})
    assert response.status_code == 200
    task = response.json()
    assert task["scbkr"]["draft_source"] in {"model_assisted_structured", "scbkr_base_logic", "direct_scbkr_kernel_compiler"}
    assert task["scbkr"]["fallback_used"] is False
    readback = main.get_task(task["task_id"])
    assert readback["scbkr"]["draft_source"] in {"model_assisted_structured", "scbkr_base_logic", "direct_scbkr_kernel_compiler"}


def test_remote_external_disabled_fallback_and_loopback_not_blocked(monkeypatch):
    client = TestClient(main.app)
    monkeypatch.setitem(main.PERMISSIONS, "external_api", False)
    monkeypatch.setitem(main.MODEL_SETTINGS, "enabled", True)
    monkeypatch.setitem(main.MODEL_SETTINGS, "mode", "external")
    monkeypatch.setitem(main.MODEL_SETTINGS, "base_url", "https://api.example.com/v1")
    called = {"value": False}
    monkeypatch.setattr(main, "_post_openai_compatible", lambda *a, **k: called.__setitem__("value", True))
    r = client.post("/api/tasks/create", json={"raw_input": "我要寫一個滷肉飯商業文案", "task_type": "general", "create_scbkr_draft": True})
    assert r.status_code == 200
    assert called["value"] is False
    assert r.json()["scbkr"]["fallback_used"] is False
    assert r.json()["scbkr"]["draft_source"] == "direct_scbkr_kernel_compiler"
    assert r.json()["draft_model_call_skipped_reason"] == "direct_scbkr_kernel_compiler"

    fake = create_scbkr_draft("我要寫一個紫蘇梅冰沙開幕宣傳文案")
    monkeypatch.setitem(main.MODEL_SETTINGS, "base_url", "http://127.0.0.1:1234/v1")
    monkeypatch.setattr(main, "_post_openai_compatible", lambda *a, **k: {"choices": [{"message": {"content": json.dumps(fake, ensure_ascii=False)}}]})
    r2 = client.post("/api/tasks/create", json={"raw_input": "我要寫一個紫蘇梅冰沙開幕宣傳文案", "task_type": "general", "create_scbkr_draft": True})
    assert r2.status_code == 200
    assert r2.json()["scbkr"]["fallback_used"] is False


def test_generation_contract_violation_stops_before_waiting_review(monkeypatch):
    client = TestClient(main.app)
    monkeypatch.setitem(main.MODEL_SETTINGS, "provider", "sandbox_mock_model")
    monkeypatch.setitem(main.MODEL_SETTINGS, "mode", "sandbox")
    monkeypatch.setitem(main.MODEL_SETTINGS, "model_name", "sandbox_mock_model")
    monkeypatch.setitem(main.MODEL_SETTINGS, "enabled", False)
    monkeypatch.setitem(main.PERMISSIONS, "model_generate", True)
    task = client.post("/api/tasks/create", json={"raw_input": "我要寫一個紫蘇梅冰沙開幕宣傳文案", "task_type": "general", "create_scbkr_draft": True}).json()
    confirmed = client.post(f"/api/tasks/{task['task_id']}/confirm", json={"scbkr": task["scbkr"], "confirmed_by": "user", "signature": "user"}).json()
    assert confirmed["status"] == "confirmed"
    monkeypatch.setattr(main, "generate_with_sandbox_model", lambda task, scbkr: {"generated_text": "SCBKR 草案 confirmation_status 等待使用者確認", "content": "SCBKR 草案 confirmation_status 等待使用者確認"})
    out = client.post(f"/api/tasks/{task['task_id']}/generate").json()
    assert out["status"] == "confirmed"
    assert out["generation_result"]["status"] == "generation_contract_violation"
