import importlib

from fastapi.testclient import TestClient

from apps.api import main
from core.rule_os import classify_user_input
from core.storage.sqlite_runtime import list_storage_items


def fresh_main(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    return importlib.reload(main)


def test_hard_router_classifies_all_rule_os_modes():
    cases = {
        "你好，今天聊聊": "general_chat",
        "我要一個美容院商業文案，幫我生成規則。": "generate_rule",
        "幫我生成債務民事案件規則書": "generate_rule",
        "幫我寫臉部保養貼文": "answer_with_rules",
        "B 不對，幫我修改規則": "modify_existing_rule",
        "確認入庫並啟用規則": "confirm_storage",
        "查四庫裡面存了什麼": "query_four_stores",
        "幫我上網搜尋資料": "tool_execution",
        "幫我發布並寄給客戶": "high_risk_action",
    }
    for text, expected in cases.items():
        assert classify_user_input(text)["mode"] == expected


def test_beauty_salon_rule_os_flow_uses_signed_four_store_package(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(local_main.app)
    client.post("/api/rule-assist/settings", json={"plan_level": "NT3300"})
    client.post("/api/settings/model", json={"provider": "sandbox_mock_model", "mode": "sandbox"})
    client.post("/api/settings/permissions", json={"model_generate": True})

    task = client.post(
        "/api/tasks/create",
        json={
            "raw_input": "我要一個美容院商業文案，幫我生成規則。",
            "task_type": "general",
            "create_scbkr_draft": True,
        },
    ).json()

    assert task["input_classification"]["mode"] == "generate_rule"
    scbkr = task["scbkr"]
    assert scbkr["rule_os"]["model_role"] == "five_dimension_rule_drafter"
    assert scbkr["plan_depth"]["free"]["can_generate_basic_five_dimension_draft"] is True
    assert scbkr["plan_depth"]["nt690"]["enabled"] is True
    assert scbkr["plan_depth"]["nt3300"]["enabled"] is True
    assert scbkr["S"]["task_subject"] == "美容院商業文案規則"
    assert all(layer in scbkr for layer in ("S", "C", "B", "K", "R"))
    assert any("不得誇大療效" in item for item in scbkr["B"]["stop_conditions"])
    assert any("不得編造價格" in item for item in scbkr["B"]["stop_conditions"])
    assert scbkr["R"]["shenyao_forced_signature_required"] is True
    assert "dual_signature_conditions" in scbkr["R"]

    confirmed = client.post(f"/api/tasks/{task['task_id']}/confirm", json={"signature": "owner-signature"}).json()
    assert confirmed["confirmed"] is True
    assert confirmed["scbkr"]["signature_status"] == "owner_signed"

    generated = client.post(f"/api/tasks/{task['task_id']}/generate").json()
    assert generated["status"] == "waiting_review"
    assert generated["generation_result"]["post_check"]["checked"] is True

    reviewed = client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "pass", "review_message": "owner accepted", "reviewer_signature": "review-signature"},
    ).json()
    assert reviewed["review_passed"] is True

    requested = client.post(
        f"/api/tasks/{task['task_id']}/storage-request",
        json={"selected_targets": ["vector", "corpus", "logic", "memory"], "user_decision": "custom", "signature": "storage-request-signature"},
    ).json()
    assert requested["status"] == "waiting_storage_confirm"

    stored = client.post(
        f"/api/tasks/{task['task_id']}/storage-confirm",
        json={
            "storage_confirmed": True,
            "second_confirm": True,
            "confirmed_by": "user",
            "signature": "storage-signature",
            "selected_targets": ["vector", "corpus", "logic", "memory"],
        },
    ).json()
    assert stored["status"] == "storage_committed"
    assert set(stored["storage_result"]["written_targets"]) == {"vector", "corpus", "logic", "memory"}
    assert stored["compiled_rule"]["active"] is True
    assert {item["target"] for item in list_storage_items(task_id=task["task_id"])} == {"vector", "corpus", "logic", "memory"}

    local_main.MODEL_SETTINGS["enabled"] = False
    answer = client.post("/api/chat/general", json={"message": "幫我寫臉部保養貼文", "locale": "zh-TW"}).json()
    package = answer["current_rule_package"]

    assert answer["input_classification"]["mode"] == "answer_with_rules"
    assert answer["route_mode"] == "answer_with_rules"
    assert package["source"] == "local_four_store_rule_package"
    assert package["chat_context_used"] is False
    assert package["matched_rules"], package
    assert package["rule_status"] == "signed_rule_applied"
    assert "已套用你的美容院商業文案規則" in answer["reply"]
    assert "不得自動發布" in " ".join(package["forbidden_actions"])
    assert answer["post_check"]["checked"] is True
    assert answer["post_check"]["allowed"] is True


def test_free_690_3300_are_depth_not_button_only(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    local_main.MODEL_SETTINGS["enabled"] = False
    client = TestClient(local_main.app)
    raw = "我要一個美容院商業文案，幫我生成規則。"

    client.post("/api/rule-assist/settings", json={"plan_level": "FREE"})
    free = client.post("/api/tasks/create", json={"raw_input": raw, "task_type": "general", "create_scbkr_draft": True}).json()["scbkr"]
    assert free["plan_depth"]["free"]["can_generate_basic_five_dimension_draft"] is True
    assert "responsibility_chain_assist" not in free
    assert "rulebook_closure" not in free

    client.post("/api/rule-assist/settings", json={"plan_level": "NT690"})
    nt690 = client.post("/api/tasks/create", json={"raw_input": raw, "task_type": "general", "create_scbkr_draft": True}).json()["scbkr"]
    assert "responsibility_chain_assist" in nt690
    assert "rulebook_closure" not in nt690
    assert nt690["responsibility_chain_assist"]["actions_requiring_confirmation"]

    client.post("/api/rule-assist/settings", json={"plan_level": "NT3300"})
    nt3300 = client.post("/api/tasks/create", json={"raw_input": raw, "task_type": "general", "create_scbkr_draft": True}).json()["scbkr"]
    assert "responsibility_chain_assist" in nt3300
    assert "rulebook_closure" in nt3300
    assert nt3300["R"]["formal_citation_allowed"] == "only_when_signed_reviewed_active_logic_or_corpus_or_memory"


def test_debt_civil_rulebook_phrase_enters_rule_drafting_and_fills_legal_boundaries(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    local_main.MODEL_SETTINGS["enabled"] = False
    client = TestClient(local_main.app)
    client.post("/api/rule-assist/settings", json={"plan_level": "NT3300"})

    task = client.post(
        "/api/tasks/create",
        json={
            "raw_input": "幫我生成債務民事案件規則書",
            "task_type": "general",
            "create_scbkr_draft": True,
        },
    ).json()
    scbkr = task["scbkr"]

    assert task["input_classification"]["mode"] == "generate_rule"
    assert scbkr["S"]["task_subject"] == "債務民事案件規則書"
    assert any("當事人身分" in item for item in scbkr["B"]["stop_conditions"])
    assert any("不得編造借款金額" in item for item in scbkr["B"]["stop_conditions"])
    assert any("法院通知" in item for item in scbkr["K"]["references"])
    assert any("程序階段" in item for item in scbkr["R"]["formation_conditions"])
    assert any("送出法律文件" in item for item in scbkr["R"]["failure_conditions"])
