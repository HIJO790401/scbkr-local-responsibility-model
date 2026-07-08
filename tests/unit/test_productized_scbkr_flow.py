import importlib

from fastapi.testclient import TestClient

from apps.api import main
from core.rule_os.post_check import check_model_answer_against_rule_package
from core.storage.sqlite_runtime import list_storage_items


def fresh_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    local_main = importlib.reload(main)
    client = TestClient(local_main.app)
    client.post("/api/settings/model", json={"provider": "sandbox_mock_model", "mode": "sandbox"})
    client.post("/api/settings/permissions", json={"model_generate": True})
    return local_main, client


def create_signed_product_launch_rule(client: TestClient):
    raw = "我要一個新品上市推廣計畫，幫我生成規則。"
    intent = client.post("/api/chat/intent", json={"message": raw, "locale": "zh-TW"}).json()
    assert intent["rule_os_classification"]["mode"] == "generate_rule"
    assert intent["intent"] == "create_new_rule_confirmation"

    task = client.post(
        "/api/tasks/create",
        json={
            "raw_input": raw,
            "task_type": "general",
            "intent": "create_new_rule_confirmation",
            "object_type": "rule",
            "create_scbkr_draft": True,
        },
    ).json()
    assert task["input_classification"]["mode"] == "generate_rule"
    assert task["status"] == "waiting_user_confirm"
    assert task["confirmed"] is False
    assert task["storage_confirmed"] is False
    assert all(layer in task["scbkr"] for layer in ("S", "C", "B", "K", "R"))
    assert task["scbkr"]["R"]["model_signature_allowed"] is False

    confirmed = client.post(f"/api/tasks/{task['task_id']}/confirm", json={"signature": "owner-signature"}).json()
    assert confirmed["scbkr"]["signature_status"] == "owner_signed"

    generated = client.post(f"/api/tasks/{task['task_id']}/generate").json()
    assert generated["status"] == "waiting_review"
    assert generated["storage_confirmed"] is False

    reviewed = client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "pass", "review_message": "owner accepted", "reviewer_signature": "owner-review"},
    ).json()
    assert reviewed["review_passed"] is True

    requested = client.post(
        f"/api/tasks/{task['task_id']}/storage-request",
        json={"selected_targets": ["logic", "corpus", "memory", "vector"], "user_decision": "custom", "signature": "owner-storage-request"},
    ).json()
    assert requested["status"] == "waiting_storage_confirm"

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
    assert set(stored["storage_result"]["written_targets"]) == {"logic", "corpus", "memory", "vector"}
    return stored


def test_chinese_product_launch_rule_generation_to_active_rule_center(tmp_path, monkeypatch):
    _local_main, client = fresh_client(tmp_path, monkeypatch)
    stored = create_signed_product_launch_rule(client)

    rules = client.get("/api/rules").json()["rules"]
    compiled = [rule for rule in rules if rule.get("rule_id") == stored["compiled_rule"]["rule_id"]]
    assert compiled
    assert compiled[0]["activation_status"] == "active"
    assert compiled[0]["signature_status"] == "owner_signed"
    assert compiled[0]["review_passed"] is True
    assert "logic" in compiled[0]["four_store_locations"]
    assert compiled[0]["version_history"][0]["version"] == "v1.0"


def test_four_store_data_center_status_and_vector_boundary(tmp_path, monkeypatch):
    _local_main, client = fresh_client(tmp_path, monkeypatch)
    stored = create_signed_product_launch_rule(client)
    items = list_storage_items(task_id=stored["task_id"])
    targets = {item["target"]: item for item in items}

    assert targets["corpus"]["payload"]["status"] == "active"
    assert targets["memory"]["payload"]["signature_status"] == "owner_signed"
    assert targets["vector"]["payload"]["citation_policy"] == "discovery_index_only_not_formal_basis"

    vector = client.get("/api/data-center/vector").json()["items"][0]
    assert "不可直接" in vector["citation_policy"] or "discovery" in vector["citation_policy"]


def test_answer_with_signed_product_launch_rule_uses_minimal_package(tmp_path, monkeypatch):
    local_main, client = fresh_client(tmp_path, monkeypatch)
    stored = create_signed_product_launch_rule(client)
    local_main.MODEL_SETTINGS["enabled"] = False

    answer = client.post("/api/chat/general", json={"message": "幫我寫新品上市推廣貼文。", "locale": "zh-TW"}).json()
    package = answer["current_rule_package"]

    assert answer["route_mode"] == "answer_with_rules"
    assert answer["chat_context_used"] is False
    assert package["chat_context_used"] is False
    assert package["task_type"] == "product_launch_marketing_copy"
    assert package["matched_rules"]
    assert len(package["matched_rules"]) <= package["package_budget"]["limits"]["matched_rules"]
    assert "已套用你的新品上市推廣文案規則" in answer["reply"]
    assert answer["post_check"]["checked"] is True
    assert answer["post_check"]["allowed"] is True
    assert stored["storage_result"]["storage_item_ids"]


def test_product_launch_post_check_blocks_overreach():
    package = {
        "task_type": "product_launch_marketing_copy",
        "source": "local_four_store_rule_package",
        "chat_context_used": False,
        "draft_only": False,
        "citable_data": [],
    }
    unsafe = check_model_answer_against_rule_package("新品已發布，NT$990 限時買一送一，保證熱賣。", package)
    assert unsafe["allowed"] is False
    assert {item["code"] for item in unsafe["violations"]} >= {
        "invented_launch_commercial_data",
        "launch_overreach_execution_claim",
        "launch_unverified_performance_claim",
    }


def test_english_product_launch_rulebook_and_followup_are_english(tmp_path, monkeypatch):
    local_main, client = fresh_client(tmp_path, monkeypatch)
    client.post("/api/rule-assist/settings", json={"plan_level": "FREE", "locale": "en"})

    routed = client.post("/api/chat/intent", json={"message": "Create a product launch marketing rulebook.", "locale": "en"}).json()
    assert routed["rule_os_classification"]["mode"] == "generate_rule"
    assert routed["intent"] == "create_new_rule_confirmation"

    task = client.post(
        "/api/tasks/create",
        json={"raw_input": "Create a product launch marketing rulebook.", "task_type": "general", "create_scbkr_draft": True, "locale": "en"},
    ).json()
    assert task["scbkr"]["S"]["task_subject"] == "product launch marketing rulebook"
    assert any("Do not invent product specs" in item for item in task["scbkr"]["B"]["stop_conditions"])
    assert "新品" not in task["scbkr"]["S"]["task_subject"]

    client.post(f"/api/tasks/{task['task_id']}/confirm", json={"signature": "owner-signature"})
    client.post(f"/api/tasks/{task['task_id']}/generate")
    client.post(
        f"/api/tasks/{task['task_id']}/review",
        json={"review_decision": "pass", "review_message": "owner accepted", "reviewer_signature": "owner-review"},
    )
    client.post(
        f"/api/tasks/{task['task_id']}/storage-request",
        json={"selected_targets": ["logic", "corpus", "memory"], "user_decision": "custom", "signature": "owner-storage-request"},
    )
    client.post(
        f"/api/tasks/{task['task_id']}/storage-confirm",
        json={
            "storage_confirmed": True,
            "second_confirm": True,
            "confirmed_by": "user",
            "signature": "owner-storage-confirm",
            "selected_targets": ["logic", "corpus", "memory"],
        },
    )
    local_main.MODEL_SETTINGS["enabled"] = False

    answer = client.post(
        "/api/chat/general",
        json={"message": "Use my existing product launch rulebook to draft a launch post.", "locale": "en"},
    ).json()
    assert answer["route_mode"] == "answer_with_rules"
    assert answer["current_rule_package"]["chat_context_used"] is False
    assert answer["current_rule_package"]["task_type"] == "product_launch_marketing_copy"
    assert answer["current_rule_package"]["matched_rules"]
    assert "Applied your product launch marketing rule" in answer["reply"]
    assert "已套用" not in answer["reply"]
