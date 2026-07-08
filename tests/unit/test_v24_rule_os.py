import importlib

from fastapi.testclient import TestClient

from apps.api import main
from core.rule_os import classify_user_input
from core.rule_os.post_check import check_model_answer_against_rule_package
from core.storage.sqlite_runtime import list_storage_items


def fresh_main(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    return importlib.reload(main)


def test_hard_router_classifies_all_rule_os_modes():
    cases = {
        "你好，今天聊聊": "general_chat",
        "我要一個美容院商業文案，幫我生成規則。": "generate_rule",
        "幫我生成債務民事案件規則書": "generate_rule",
        "請依我已建立的債務民事案件規則書，幫我整理一份借款欠款催告草稿": "answer_with_rules",
        "Create a debt civil case rulebook": "generate_rule",
        "Use my existing debt civil case rulebook to draft a payment demand letter": "answer_with_rules",
        "幫我寫臉部保養貼文": "answer_with_rules",
        "B 不對，幫我修改規則": "modify_existing_rule",
        "確認入庫並啟用規則": "confirm_storage",
        "查四庫裡面存了什麼": "query_four_stores",
        "幫我上網搜尋資料": "tool_execution",
        "幫我發布並寄給客戶": "high_risk_action",
    }
    for text, expected in cases.items():
        assert classify_user_input(text)["mode"] == expected


def test_english_rule_os_route_and_package_are_localized(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(local_main.app)
    client.post("/api/settings/model", json={"provider": "sandbox_mock_model", "mode": "sandbox"})

    generate = client.post(
        "/api/chat/general",
        json={"message": "I want a beauty salon marketing copy rulebook. Please generate a rule.", "locale": "en"},
    ).json()

    assert generate["route_mode"] == "generate_rule"
    assert "Classified as" in generate["reply"]
    assert "five-dimension rule draft" in generate["reply"]
    assert "已分類" not in generate["reply"]

    answer = client.post(
        "/api/chat/general",
        json={"message": "Use my existing debt civil case rulebook to draft a payment demand letter.", "locale": "en"},
    ).json()

    package = answer["current_rule_package"]
    assert answer["route_mode"] == "answer_with_rules"
    assert package["task_type"] == "debt_civil_case_draft"
    assert package["chat_context_used"] is False
    assert any("Do not present the draft as legal advice" in item for item in package["forbidden_actions"])
    assert any("No signed rule matched" in item for item in package["missing_information"])
    assert "目前沒有命中" not in answer["reply"]


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


def test_debt_civil_followup_uses_signed_rule_package(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(local_main.app)
    client.post("/api/rule-assist/settings", json={"plan_level": "NT3300"})
    client.post("/api/settings/model", json={"provider": "sandbox_mock_model", "mode": "sandbox"})
    client.post("/api/settings/permissions", json={"model_generate": True})

    task = client.post(
        "/api/tasks/create",
        json={
            "raw_input": "幫我生成債務民事案件規則書",
            "task_type": "general",
            "object_type": "rulebook",
            "create_scbkr_draft": True,
        },
    ).json()
    client.post(f"/api/tasks/{task['task_id']}/confirm", json={"signature": "owner-signature"})
    client.post(f"/api/tasks/{task['task_id']}/generate")
    client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "pass", "review_message": "owner accepted", "reviewer_signature": "review-signature"},
    )
    client.post(
        f"/api/tasks/{task['task_id']}/storage-request",
        json={"selected_targets": ["vector", "corpus", "logic", "memory"], "user_decision": "custom", "signature": "storage-request-signature"},
    )
    client.post(
        f"/api/tasks/{task['task_id']}/storage-confirm",
        json={
            "storage_confirmed": True,
            "second_confirm": True,
            "confirmed_by": "user",
            "signature": "storage-signature",
            "selected_targets": ["vector", "corpus", "logic", "memory"],
        },
    )

    answer = client.post(
        "/api/chat/general",
        json={
            "message": "請依我已建立的債務民事案件規則書，幫我整理一份借款欠款催告草稿；只能當草稿，不要法律終判。",
            "locale": "zh-TW",
        },
    ).json()
    package = answer["current_rule_package"]

    assert answer["route_mode"] == "answer_with_rules"
    assert package["task_type"] == "debt_civil_case_draft"
    assert package["chat_context_used"] is False
    assert package["matched_rules"], package
    assert package["rule_status"] == "signed_rule_applied"
    assert "已套用你的債務民事案件規則" in answer["reply"]
    assert any("不得編造借款金額" in item for item in package["forbidden_actions"])
    assert answer["post_check"]["checked"] is True
    assert answer["post_check"]["allowed"] is True


def test_rule_answer_falls_back_when_local_model_fails(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(local_main.app)
    client.post("/api/rule-assist/settings", json={"plan_level": "NT3300"})
    client.post("/api/settings/model", json={"provider": "sandbox_mock_model", "mode": "sandbox"})
    client.post("/api/settings/permissions", json={"model_generate": True})

    task = client.post(
        "/api/tasks/create",
        json={"raw_input": "幫我生成債務民事案件規則書", "task_type": "general", "create_scbkr_draft": True},
    ).json()
    client.post(f"/api/tasks/{task['task_id']}/confirm", json={"signature": "owner-signature"})
    client.post(f"/api/tasks/{task['task_id']}/generate")
    client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "pass", "review_message": "owner accepted", "reviewer_signature": "review-signature"},
    )
    client.post(
        f"/api/tasks/{task['task_id']}/storage-request",
        json={"selected_targets": ["logic", "corpus", "memory"], "user_decision": "custom", "signature": "storage-request-signature"},
    )
    client.post(
        f"/api/tasks/{task['task_id']}/storage-confirm",
        json={
            "storage_confirmed": True,
            "second_confirm": True,
            "confirmed_by": "user",
            "signature": "storage-signature",
            "selected_targets": ["logic", "corpus", "memory"],
        },
    )

    def fail_model(*_args, **_kwargs):
        raise TimeoutError("local model timeout")

    monkeypatch.setattr(local_main, "_post_openai_compatible", fail_model)
    local_main.MODEL_SETTINGS.update(
        {
            "provider": "lm_studio",
            "mode": "local",
            "base_url": "http://127.0.0.1:1234/v1",
            "model_name": "qwen2.5-0.5b-instruct",
            "enabled": True,
            "last_test_status": "success",
        }
    )

    answer = client.post(
        "/api/chat/general",
        json={"message": "請依我已建立的債務民事案件規則書，幫我整理一份借款欠款催告草稿", "locale": "zh-TW"},
    ).json()

    assert answer["route_mode"] == "answer_with_rules"
    assert answer["reply_source"] == "model_gateway_failed_local_rule_package"
    assert answer["current_rule_package"]["matched_rules"]
    assert answer["chat_context_used"] is False
    assert "已套用你的債務民事案件規則" in answer["reply"]


def test_general_chat_falls_back_when_local_model_fails(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(local_main.app)
    client.post("/api/settings/permissions", json={"model_generate": True})

    def fail_model(*_args, **_kwargs):
        raise ConnectionError("local model unavailable")

    monkeypatch.setattr(local_main, "_post_openai_compatible", fail_model)
    local_main.MODEL_SETTINGS.update(
        {
            "provider": "lm_studio",
            "mode": "local",
            "base_url": "http://127.0.0.1:1234/v1",
            "model_name": "qwen2.5-0.5b-instruct",
            "enabled": True,
            "last_test_status": "success",
        }
    )

    answer = client.post("/api/chat/general", json={"message": "你好，今天聊聊", "locale": "zh-TW"}).json()

    assert answer["route_mode"] == "general_chat"
    assert answer["reply_source"] == "model_gateway_failed_local_fallback"
    assert answer["task_created"] is False
    assert answer["data_center_written"] is False


def test_english_debt_rulebook_and_followup_are_supported(tmp_path, monkeypatch):
    local_main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(local_main.app)
    client.post("/api/rule-assist/settings", json={"plan_level": "NT3300", "locale": "en"})
    client.post("/api/settings/model", json={"provider": "sandbox_mock_model", "mode": "sandbox"})
    client.post("/api/settings/permissions", json={"model_generate": True})

    task = client.post(
        "/api/tasks/create",
        json={"raw_input": "Create a debt civil case rulebook", "task_type": "general", "create_scbkr_draft": True, "locale": "en"},
    ).json()

    assert task["input_classification"]["mode"] == "generate_rule"
    assert task["scbkr"]["S"]["task_subject"] == "debt civil case rulebook"
    assert any("Do not invent loan amounts" in item for item in task["scbkr"]["B"]["stop_conditions"])

    client.post(f"/api/tasks/{task['task_id']}/confirm", json={"signature": "owner-signature"})
    client.post(f"/api/tasks/{task['task_id']}/generate")
    client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "pass", "review_message": "owner accepted", "reviewer_signature": "review-signature"},
    )
    client.post(
        f"/api/tasks/{task['task_id']}/storage-request",
        json={"selected_targets": ["vector", "corpus", "logic", "memory"], "user_decision": "custom", "signature": "storage-request-signature"},
    )
    client.post(
        f"/api/tasks/{task['task_id']}/storage-confirm",
        json={
            "storage_confirmed": True,
            "second_confirm": True,
            "confirmed_by": "user",
            "signature": "storage-signature",
            "selected_targets": ["vector", "corpus", "logic", "memory"],
        },
    )

    answer = client.post(
        "/api/chat/general",
        json={"message": "Use my existing debt civil case rulebook to draft a payment demand letter.", "locale": "en"},
    ).json()

    assert answer["route_mode"] == "answer_with_rules"
    assert answer["current_rule_package"]["task_type"] == "debt_civil_case_draft"
    assert answer["current_rule_package"]["matched_rules"]
    assert answer["current_rule_package"]["chat_context_used"] is False
    assert "Applied your debt civil case rule" in answer["reply"]


def test_debt_post_check_requires_review_guard():
    package = {
        "source": "local_four_store_rule_package",
        "task_type": "debt_civil_case_draft",
        "chat_context_used": False,
        "draft_only": False,
        "non_citable_data": [],
    }

    unsafe = check_model_answer_against_rule_package(
        "以下是債務民事案件規則書：貸款金額、利息率、逾期罰息、法院案號。",
        package,
    )
    safe = check_model_answer_against_rule_package(
        "待確認草稿：請確認債務金額、日期與證據；此內容不是法律意見，不得自動送件。",
        package,
    )

    assert unsafe["allowed"] is False
    assert any(v["code"] == "debt_missing_review_guard" for v in unsafe["violations"])
    assert safe["allowed"] is True
