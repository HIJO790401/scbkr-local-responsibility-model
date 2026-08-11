import copy
import importlib
import json

import pytest
from fastapi import HTTPException


def load_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    main = importlib.reload(main)
    main.TASKS.clear()
    main.PERMISSIONS.update({"model_generate": True, "external_api": False, "dangerous_operation_confirmed": False})
    main.MODEL_SETTINGS.update({
        "enabled": True,
        "mode": "external",
        "provider": "openai_compatible",
        "base_url": "https://example.invalid/v1",
        "api_key": "secret",
        "model_name": "test-model",
        "timeout": 1,
        "last_test_status": "success",
    })
    return main


def make_draft(main):
    return main.create_scbkr_draft("請建立一個測試任務", "general")


def valid_model_rulebook():
    return {
        "S": {
            "content": "本規則處理測試任務，由使用者擔任規則擁有者與最終確認者。",
            "explanation": "鎖定測試任務與使用者主體。",
            "missing_information": ["測試範圍"],
            "needs_user_confirmation": ["確認測試範圍"],
            "model_cannot_decide": ["是否接受測試結果"],
            "risk_notes": ["範圍不清可能測錯目標"],
        },
        "C": {
            "content": "先核對測試範圍，再執行測試與記錄結果；若測試資料不足，則停止並要求補資料。",
            "explanation": "依序核對、執行、記錄，缺資料時停止。",
            "missing_information": ["驗收順序"],
            "needs_user_confirmation": ["確認測試順序"],
            "model_cannot_decide": ["最終是否通過"],
            "risk_notes": ["跳過核對會造成錯判"],
        },
        "B": {
            "content": "使用者未確認前不得發布或執行外部動作；資料不足或越權時必須停止。",
            "explanation": "定義禁止事項與停止條件。",
            "missing_information": ["例外條件"],
            "needs_user_confirmation": ["確認禁止事項"],
            "model_cannot_decide": ["是否解除停止"],
            "risk_notes": ["越權會造成外部影響"],
        },
        "K": {
            "content": "只可引用使用者已確認的測試需求與結果；未確認內容、聊天猜測與 VECTOR 候選不可引用。",
            "explanation": "區分正式依據與不可引用候選。",
            "missing_information": ["正式測試資料"],
            "needs_user_confirmation": ["確認可引用資料"],
            "model_cannot_decide": ["資料是否真實"],
            "risk_notes": ["錯誤引用會污染結果"],
        },
        "R": {
            "content": "使用者驗收並簽名後規則才成立；模型不能簽名、入庫或啟用，錯誤時由使用者回放並修復。",
            "explanation": "責任、驗收、簽名與修復都留給使用者。",
            "missing_information": ["簽名聲明"],
            "needs_user_confirmation": ["使用者簽名"],
            "model_cannot_decide": ["現實責任"],
            "risk_notes": ["未簽名規則不得引用"],
        },
        "rule_summary": "建立可驗收的測試任務規則。",
        "missing_information": ["測試範圍"],
        "user_confirmation_items": ["逐欄確認 S/C/B/K/R"],
        "model_cannot_decide": ["是否正式啟用"],
        "risk_reminders": ["模型不得代替使用者簽名"],
        "next_actions": ["使用者修改並簽名"],
    }


def configure_connected_local_model(main, monkeypatch):
    main.MODEL_SETTINGS.update({
        "enabled": True,
        "last_test_status": "success",
        "mode": "local",
        "provider": "lm_studio",
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key": "local",
        "model_name": "fake-local-scbkr",
    })
    main.PERMISSIONS["model_generate"] = True
    payload = valid_model_rulebook()
    monkeypatch.setattr(
        main,
        "_post_openai_compatible",
        lambda settings, messages, response_format=None: {
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 180},
        },
    )


def create_task_with_draft(main, monkeypatch):
    configure_connected_local_model(main, monkeypatch)
    task = main.create_task({"raw_input": "請建立一個測試任務", "task_type": "general", "create_scbkr_draft": True})
    assert task["scbkr"]
    return task


def assert_raises_400(fn):
    with pytest.raises(HTTPException) as exc:
        fn()
    assert exc.value.status_code == 400
    return str(exc.value.detail)


def test_external_api_permission_disabled_stops_without_model_or_fallback(tmp_path, monkeypatch):
    main = load_runtime(tmp_path, monkeypatch)
    called = {"value": False}

    def fail_if_called(*args, **kwargs):
        called["value"] = True
        raise AssertionError("raw task text must not be sent when external_api=false")

    monkeypatch.setattr(main, "_post_openai_compatible", fail_if_called)
    task = main.create_task({"raw_input": "請建立一個測試任務", "task_type": "general", "create_scbkr_draft": True})

    assert called["value"] is False
    assert task["fallback_used"] is False
    assert task["status"] == "model_unavailable"
    assert task["model_rulebook_authoring"]["failure_reason"] == "external_api_permission_required"
    assert "scbkr" not in task
    assert task["confirmed"] is False


def test_external_api_permission_enabled_allows_valid_remote_draft_call(tmp_path, monkeypatch):
    main = load_runtime(tmp_path, monkeypatch)
    main.PERMISSIONS["external_api"] = True
    expected = valid_model_rulebook()

    def model_response(settings, messages, response_format=None):
        assert "請建立一個測試任務" in json.dumps(messages, ensure_ascii=False)
        return {"choices": [{"message": {"content": json.dumps(expected, ensure_ascii=False)}}]}

    monkeypatch.setattr(main, "_post_openai_compatible", model_response)
    task = main.create_task({"raw_input": "請建立一個測試任務", "task_type": "general", "create_scbkr_draft": True})
    assert task["scbkr"]["fallback_used"] is False
    assert task["draft_source"] == "model_assisted_rulebook"
    assert task["model_used"] is True


def test_sandbox_cannot_author_product_rulebook_but_loopback_can(tmp_path, monkeypatch):
    main = load_runtime(tmp_path, monkeypatch)
    called = {"sandbox": False, "loopback": False}

    def sandbox_fail(*args, **kwargs):
        called["sandbox"] = True
        raise AssertionError("sandbox must not call model HTTP")

    monkeypatch.setattr(main, "_post_openai_compatible", sandbox_fail)
    main.MODEL_SETTINGS.update({"enabled": True, "mode": "sandbox", "provider": main.SANDBOX_PROVIDER})
    sandbox_task = main.create_task({"raw_input": "請建立一個測試任務", "task_type": "general", "create_scbkr_draft": True})
    assert called["sandbox"] is False
    assert sandbox_task["status"] == "model_unavailable"
    assert "scbkr" not in sandbox_task

    expected = valid_model_rulebook()

    def loopback_response(settings, messages, response_format=None):
        called["loopback"] = True
        return {"choices": [{"message": {"content": json.dumps(expected, ensure_ascii=False)}}]}

    main.MODEL_SETTINGS.update({"enabled": True, "last_test_status": "success", "mode": "local", "provider": "lm_studio", "base_url": "http://localhost:1234/v1", "model_name": "local"})
    monkeypatch.setattr(main, "_post_openai_compatible", loopback_response)
    loopback_task = main.create_task({"raw_input": "請建立一個測試任務", "task_type": "general", "create_scbkr_draft": True})
    assert called["loopback"] is True
    assert loopback_task["scbkr"]["fallback_used"] is False


@pytest.mark.parametrize("mutation", [
    {"physical_write_performed": True},
    {"storage_confirmed": True, "storage_result": {"written_items": [{"id": "x"}]}},
    {"status": "storage_committed"},
    {"status": "completed"},
    {"memory_rule_physical_write_performed": True},
    {"memory_rule_stored": True},
    {"status": "memory_rule_stored"},
    {"memory_rule_confirmed": True, "memory_rule_result": {"rule": "x"}},
    {"memory_rule_confirmed": True, "memory_rule_write_result": {"rule": "x"}},
])
def test_committed_physical_write_blocks_scbkr_edit_and_apply_patch_atomically(tmp_path, monkeypatch, mutation):
    main = load_runtime(tmp_path, monkeypatch)
    task = create_task_with_draft(main, monkeypatch)
    task_id = task["task_id"]
    main.TASKS[task_id].update(mutation)
    main.TASKS[task_id]["storage_result"] = main.TASKS[task_id].get("storage_result") or {"written_items": [{"id": "keep"}]}
    main.TASKS[task_id]["written_items"] = [{"id": "keep"}]
    before = copy.deepcopy(main.TASKS[task_id])

    detail = assert_raises_400(lambda: main.edit_scbkr(task_id, {"scbkr": make_draft(main)}))
    assert "不能直接改寫原 SCBKR" in detail
    assert main.TASKS[task_id]["scbkr"] == before["scbkr"]
    assert main.TASKS[task_id]["storage_result"] == before["storage_result"]
    assert main.TASKS[task_id]["written_items"] == before["written_items"]
    assert main.TASKS[task_id]["status"] == before["status"]

    assert_raises_400(lambda: main.apply_scbkr_patch(task_id, {"patch": {"layer": "S", "after_draft": before["scbkr"]["S"]}}))
    assert main.TASKS[task_id]["scbkr"] == before["scbkr"]
    assert main.TASKS[task_id]["status"] == before["status"]


@pytest.mark.parametrize("after_draft", [
    {},
    {"task_name": "缺欄位"},
    None,
])
def test_apply_patch_invalid_after_draft_does_not_mutate_task(tmp_path, monkeypatch, after_draft):
    main = load_runtime(tmp_path, monkeypatch)
    task = create_task_with_draft(main, monkeypatch)
    task_id = task["task_id"]
    main.TASKS[task_id]["confirmed"] = True
    main.TASKS[task_id]["status"] = "confirmed"
    before_scbkr = copy.deepcopy(main.TASKS[task_id]["scbkr"])
    before_events = main.get_task_ledger(task_id) if hasattr(main, "get_task_ledger") else []

    detail = assert_raises_400(lambda: main.apply_scbkr_patch(task_id, {"patch": {"layer": "S", "after_draft": after_draft}}))
    assert "修改草案不完整" in detail
    assert main.TASKS[task_id]["scbkr"] == before_scbkr
    assert main.TASKS[task_id]["status"] == "confirmed"
    assert main.TASKS[task_id]["confirmed"] is True
    events = main.get_task_ledger(task_id) if hasattr(main, "get_task_ledger") else before_events
    assert not any(event.get("event_type") == "scbkr_patch_applied" for event in events[len(before_events):])


def test_apply_patch_rejects_high_privilege_state_without_mutation(tmp_path, monkeypatch):
    main = load_runtime(tmp_path, monkeypatch)
    task = create_task_with_draft(main, monkeypatch)
    task_id = task["task_id"]
    bad = copy.deepcopy(task["scbkr"]["S"])
    bad["confirmed"] = True
    before = copy.deepcopy(main.TASKS[task_id]["scbkr"])
    assert_raises_400(lambda: main.apply_scbkr_patch(task_id, {"patch": {"layer": "S", "after_draft": bad}}))
    assert main.TASKS[task_id]["scbkr"] == before


def test_apply_patch_valid_patch_updates_scbkr_and_writes_ledger(tmp_path, monkeypatch):
    main = load_runtime(tmp_path, monkeypatch)
    task = create_task_with_draft(main, monkeypatch)
    task_id = task["task_id"]
    after = copy.deepcopy(task["scbkr"]["S"])
    after["task_name"] = "更新後任務名稱"

    result = main.apply_scbkr_patch(task_id, {"patch": {"layer": "S", "after_draft": after}})

    assert result["scbkr"]["S"]["task_name"] == "更新後任務名稱"
    assert result["confirmed"] is False
    assert result["status"] == "waiting_user_confirm"
    assert result["auto_confirmed"] is False
    assert any(event.get("event_type") == "scbkr_patch_applied" for event in main.get_task_ledger(task_id))
