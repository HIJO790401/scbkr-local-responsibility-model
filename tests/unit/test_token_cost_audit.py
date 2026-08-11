import importlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api import main
from core.audit.token_cost_audit import (
    estimate_tokens,
    measure_context_compression,
    write_token_cost_audit_report,
)


RULE_INPUT = "以後凡是朋友要求我先墊錢，我要先判斷這是不是風險轉嫁，把這個寫成我的本地規則。"
FOLLOWUP_INPUT = "朋友說月底還我，要我今天先墊三萬，可以嗎？"


def _fake_rulebook_payload():
    return {
        "S": {"content": "朋友要求使用者先墊錢時的風險轉嫁判斷規則。", "explanation": "鎖定朋友要求墊款、金額與承諾的適用情境。"},
        "C": {"content": "先確認金額與請求，再核對還款時間及書面證據；若資訊不足，則停止並要求補充。", "explanation": "依序核對請求、證據與風險後才交由使用者決定。"},
        "B": {"content": "未確認金額、期限與證據前不得建議墊款；資料不足時停止，模型不得付款或替使用者決定。", "explanation": "限制模型越權，並設定資料不足時的停止條件。"},
        "K": {"content": "只可引用使用者確認的借款資料與已簽名規則；不可引用聊天猜測，VECTOR 只可召回候選。", "explanation": "把正式依據與候選檢索資料分開。"},
        "R": {"content": "使用者逐欄確認並簽名後規則才成立；模型不能簽名，使用者負責最終付款決定與後續修復。", "explanation": "模型只能草擬，簽名、驗收與現實責任都由使用者承擔。"},
        "rule_summary": "朋友要求先墊錢時的風險轉嫁判斷規則。",
        "missing_information": ["可接受金額上限", "書面證據要求"],
        "user_confirmation_items": ["金額上限", "停止條件", "五維內容"],
        "model_cannot_decide": ["是否實際付款", "是否承擔現實風險"],
        "risk_reminders": ["缺少憑證時不得把承諾當成正式依據"],
        "next_actions": ["owner_review_and_signature"],
    }


def fresh_client(tmp_path, monkeypatch, *, real_model=True):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    local_main = importlib.reload(main)
    client = TestClient(local_main.app)
    if real_model:
        local_main.MODEL_SETTINGS.update({
            "provider": "lm_studio",
            "mode": "local",
            "base_url": "http://127.0.0.1:1234/v1",
            "api_key": "local",
            "model_name": "fake-local-scbkr",
            "enabled": True,
            "last_test_status": "success",
            "timeout": 30,
        })
        local_main.PERMISSIONS["model_generate"] = True

        def fake_model(settings, messages, response_format=None):
            serialized = json.dumps(messages, ensure_ascii=False)
            if response_format is not None or "Model-assisted SCBKR Rulebook Authoring" in serialized:
                content = json.dumps(_fake_rulebook_payload(), ensure_ascii=False)
            else:
                content = "依照已簽名的墊錢規則，先核對金額、期限與書面證據；資料不足時不得建議直接付款。"
            return {
                "model": "fake-local-scbkr",
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 500, "completion_tokens": 120, "total_tokens": 620},
            }

        monkeypatch.setattr(local_main, "_post_openai_compatible", fake_model)
    else:
        client.post("/api/settings/model", json={"provider": "sandbox_mock_model", "mode": "sandbox"})
        client.post("/api/settings/permissions", json={"model_generate": True})
    return local_main, client


def create_signed_active_rule(client: TestClient):
    task = client.post(
        "/api/tasks/create",
        json={
            "raw_input": RULE_INPUT,
            "task_type": "general",
            "intent": "create_new_rule_confirmation",
            "object_type": "rule",
            "create_scbkr_draft": True,
            "rule_assist_plan": "FREE",
        },
    ).json()
    assert task["input_classification"]["mode"] == "generate_rule"
    assert task["status"] == "waiting_user_confirm"
    assert task["confirmed"] is False
    assert task["scbkr"]["meta"]["generated_under_kernel"]
    assert task["scbkr"]["R"]["model_cannot_sign"] is True

    confirmed = client.post(f"/api/tasks/{task['task_id']}/confirm", json={"signature": "owner-signature"}).json()
    assert confirmed["scbkr"]["signature_status"] == "owner_signed"

    generated = client.post(f"/api/tasks/{task['task_id']}/generate").json()
    assert generated["status"] == "waiting_review"

    reviewed = client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "pass", "review_message": "owner accepted", "reviewer_signature": "owner-review"},
    ).json()
    assert reviewed["review_passed"] is True

    client.post(
        f"/api/tasks/{task['task_id']}/storage-request",
        json={"selected_targets": ["logic", "corpus", "memory", "vector"], "user_decision": "custom", "signature": "owner-storage-request"},
    )
    stored = client.post(
        f"/api/tasks/{task['task_id']}/storage-confirm",
        json={
            "storage_confirmed": True,
            "second_confirm": True,
            "confirmed_by": "user",
            "signature": "owner-storage-confirm",
            "selected_targets": ["logic", "corpus", "memory", "vector"],
        },
    ).json()
    assert stored["compiled_rule"]["active"] is True
    return stored


def test_estimate_tokens_and_measurement_are_not_fixed_to_98_06():
    assert estimate_tokens("abcdef") == 3
    audit = measure_context_compression(
        "x" * 200,
        {"chat_context_used": False, "matched_rules": [{"rule_id": "signed-rule"}]},
    )
    assert audit["full_context_tokens_est"] == 100
    assert audit["current_rule_package_tokens_est"] > 0
    assert audit["compression_percent"] != 98.06
    assert audit["formal_basis"] == "signed_active_four_store_rules_only"


def test_general_chat_never_claims_rule_compression_without_signed_rule():
    audit = measure_context_compression(
        {"chat_history": ["x" * 200]},
        {"chat_context_used": False, "matched_rules": []},
        measurement_scope="general_chat",
    )

    assert audit["status"] == "NOT_APPLICABLE"
    assert audit["comparison_basis"] == "not_applicable_without_signed_rule"
    assert audit["tokens_saved"] is None
    assert audit["compression_percent"] is None
    assert audit["savings_verified"] is False
    assert audit["full_context_chars"] == 0
    assert audit["full_context_tokens_est"] == 0


def test_token_cost_audit_full_lifecycle_reports_actual_compression(tmp_path, monkeypatch):
    local_main, client = fresh_client(tmp_path, monkeypatch)
    stored = create_signed_active_rule(client)
    local_main.MODEL_SETTINGS["enabled"] = False

    answer = client.post("/api/chat/general", json={"message": FOLLOWUP_INPUT, "locale": "zh-TW"}).json()
    package = answer["current_rule_package"]
    audit = answer["token_cost_audit"]

    assert answer["route_mode"] == "answer_with_rules"
    assert package["chat_context_used"] is False
    assert audit["chat_context_used"] is False
    assert audit["formal_basis"] == "signed_active_four_store_rules_only"
    assert audit["full_context_tokens_est"] > audit["current_rule_package_tokens_est"]
    assert "compression_percent" in audit
    assert audit["status"] == "ESTIMATE_ONLY"
    assert audit["savings_verified"] is False
    assert audit["threshold_percent"] is None
    assert "same-model A/B" in audit["verification_note"]

    assert package["matched_rules"]
    assert all(rule.get("signature_status") == "owner_signed" for rule in package["matched_rules"])
    assert all(rule.get("review_passed") is True for rule in package["matched_rules"])
    assert all(rule.get("active") is True for rule in package["matched_rules"])
    assert all(item.get("source_store") != "vector" for item in package.get("citable_data", []))
    assert all(item.get("source_store") != "vector" for item in package.get("user_preferences", []))
    assert "VECTOR is recall only" in package["citation_policy"]
    assert audit["formal_source_summary"]["vector_recall_only"] is True

    rules = client.get("/api/rules").json()["rules"]
    report_path = write_token_cost_audit_report(
        Path("reports/token_cost_audit_report.md"),
        audit=audit,
        test_input=RULE_INPUT,
        followup_input=FOLLOWUP_INPUT,
        used_rules=rules,
    )
    report = report_path.read_text(encoding="utf-8")
    assert RULE_INPUT in report
    assert FOLLOWUP_INPUT in report
    assert "Compression:" in report
    assert "Chat context used as formal basis: No" in report
    assert "VECTOR recall only: Yes" in report
    assert stored["storage_result"]["storage_item_ids"]


def test_token_ab_api_requires_a_connected_real_model(tmp_path, monkeypatch):
    _, client = fresh_client(tmp_path, monkeypatch, real_model=False)
    response = client.post("/api/metrics/token-ab/run", json={"question": "請依規則回答"})
    assert response.status_code == 409
    assert "connected real model" in response.json()["detail"]


def test_token_ab_api_persists_provider_verified_evidence(tmp_path, monkeypatch):
    local_main, client = fresh_client(tmp_path, monkeypatch)
    local_main.MODEL_SETTINGS.update({
        "enabled": True,
        "last_test_status": "success",
        "provider": "lm_studio",
        "mode": "local",
        "model_name": "qwen-test",
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key": "local",
        "timeout": 30,
    })
    local_main.PERMISSIONS["model_generate"] = True

    def fake_model_call(settings, messages, response_format=None):
        is_full = any("FULL_RULE_CONTEXT" in str(item.get("content") or "") for item in messages)
        prompt_tokens = 500 if is_full else 100
        return {
            "model": "qwen-test",
            "choices": [{"message": {"content": "同一模型的測試回答"}}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": 20,
                "total_tokens": prompt_tokens + 20,
            },
        }

    monkeypatch.setattr(local_main, "_post_openai_compatible", fake_model_call)
    response = client.post(
        "/api/metrics/token-ab/run",
        json={
            "question": "請依已簽名規則回答",
            "full_history": [{"role": "user", "content": "過去對話" * 50}],
            "full_rule_context": {"rules": ["完整規則" * 100]},
            "current_rule_package": {"matched_rules": ["rule-1"], "prohibitions": ["不得編造"]},
        },
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["savings_verified"] is True
    assert report["same_provider"] is True
    assert report["same_model"] is True
    assert report["savings"]["prompt"]["reduction_percent"] == 80.0
    assert Path(report["local_report"]["json"]).exists()
    assert Path(report["local_report"]["markdown"]).exists()

    latest = client.get("/api/metrics/token-ab/latest").json()
    assert latest["status"] == "completed"
    assert latest["savings_verified"] is True
