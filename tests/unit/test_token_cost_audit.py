import importlib
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


def fresh_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    local_main = importlib.reload(main)
    client = TestClient(local_main.app)
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
    audit = measure_context_compression("x" * 200, {"chat_context_used": False, "rule": "x"})
    assert audit["full_context_tokens_est"] == 100
    assert audit["current_rule_package_tokens_est"] > 0
    assert audit["compression_percent"] != 98.06
    assert audit["formal_basis"] == "signed_active_four_store_rules_only"


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
    assert audit["status"] in {"PASS_98_06", "NEEDS_OPTIMIZATION"}
    assert audit["compression_percent"] != 98.06 or audit["status"] == "PASS_98_06"

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
