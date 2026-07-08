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


def create_task_with_draft(main):
    task = main.create_task({"raw_input": "請建立一個測試任務", "task_type": "general", "create_scbkr_draft": True})
    assert task["scbkr"]
    return task


def assert_raises_400(fn):
    with pytest.raises(HTTPException) as exc:
        fn()
    assert exc.value.status_code == 400
    return str(exc.value.detail)


def test_external_api_permission_disabled_skips_remote_draft_call_and_falls_back(tmp_path, monkeypatch):
    main = load_runtime(tmp_path, monkeypatch)
    called = {"value": False}

    def fail_if_called(*args, **kwargs):
        called["value"] = True
        raise AssertionError("raw task text must not be sent when external_api=false")

    monkeypatch.setattr(main, "_post_openai_compatible", fail_if_called)
    task = create_task_with_draft(main)

    assert called["value"] is False
    assert task["scbkr"]["fallback_used"] is False
    assert task["scbkr"]["draft_model_call_skipped_reason"] == "direct_scbkr_kernel_compiler"
    assert task["draft_model_call_skipped_reason"] == "direct_scbkr_kernel_compiler"
    assert task["confirmed"] is False
    assert task["status"] == "waiting_user_confirm"


def test_external_api_permission_enabled_allows_valid_remote_draft_call(tmp_path, monkeypatch):
    main = load_runtime(tmp_path, monkeypatch)
    main.PERMISSIONS["external_api"] = True
    expected = {
        "task_domain": "testing", "task_subject": "請建立一個測試任務", "user_original_judgement": "",
        "user_goal": "建立可驗收的測試任務", "output_format": ["SCBKR draft"], "core_claim": "先建立草案再由使用者確認",
        "causal_chain": ["輸入", "草案", "確認"], "boundary_rules": ["模型不得簽名"], "forbidden_dilutions": [],
        "basis_sources": ["使用者原始指令"], "evidence_relation_notes": [], "acceptance_criteria": ["五維完整"],
        "storage_candidates": ["logic"], "owner_signature_required": True, "model_role": "describe_compile_only",
    }

    def model_response(settings, messages):
        assert "請建立一個測試任務" in json.dumps(messages, ensure_ascii=False)
        return {"choices": [{"message": {"content": json.dumps(expected, ensure_ascii=False)}}]}

    monkeypatch.setattr(main, "_post_openai_compatible", model_response)
    task = create_task_with_draft(main)
    assert task["scbkr"]["fallback_used"] is False
    assert task["scbkr"]["draft_model_call_skipped_reason"] == "direct_scbkr_kernel_compiler"


def test_sandbox_and_loopback_draft_do_not_require_external_api_permission(tmp_path, monkeypatch):
    main = load_runtime(tmp_path, monkeypatch)
    called = {"sandbox": False, "loopback": False}

    def sandbox_fail(*args, **kwargs):
        called["sandbox"] = True
        raise AssertionError("sandbox must not call model HTTP")

    monkeypatch.setattr(main, "_post_openai_compatible", sandbox_fail)
    main.MODEL_SETTINGS.update({"enabled": True, "mode": "sandbox", "provider": main.SANDBOX_PROVIDER})
    sandbox_task = create_task_with_draft(main)
    assert called["sandbox"] is False
    assert sandbox_task["scbkr"]["fallback_used"] is False

    expected = make_draft(main)

    def loopback_response(settings, messages):
        called["loopback"] = True
        return {"choices": [{"message": {"content": json.dumps(expected, ensure_ascii=False)}}]}

    main.MODEL_SETTINGS.update({"enabled": True, "mode": "local", "provider": "lm_studio", "base_url": "http://localhost:1234/v1", "model_name": "local"})
    monkeypatch.setattr(main, "_post_openai_compatible", loopback_response)
    loopback_task = create_task_with_draft(main)
    assert called["loopback"] is False
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
    main.MODEL_SETTINGS.update({"enabled": False, "mode": "sandbox"})
    task = create_task_with_draft(main)
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
    main.MODEL_SETTINGS.update({"enabled": False, "mode": "sandbox"})
    task = create_task_with_draft(main)
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
    main.MODEL_SETTINGS.update({"enabled": False, "mode": "sandbox"})
    task = create_task_with_draft(main)
    task_id = task["task_id"]
    bad = copy.deepcopy(task["scbkr"]["S"])
    bad["confirmed"] = True
    before = copy.deepcopy(main.TASKS[task_id]["scbkr"])
    assert_raises_400(lambda: main.apply_scbkr_patch(task_id, {"patch": {"layer": "S", "after_draft": bad}}))
    assert main.TASKS[task_id]["scbkr"] == before


def test_apply_patch_valid_patch_updates_scbkr_and_writes_ledger(tmp_path, monkeypatch):
    main = load_runtime(tmp_path, monkeypatch)
    main.MODEL_SETTINGS.update({"enabled": False, "mode": "sandbox"})
    task = create_task_with_draft(main)
    task_id = task["task_id"]
    after = copy.deepcopy(task["scbkr"]["S"])
    after["task_name"] = "更新後任務名稱"

    result = main.apply_scbkr_patch(task_id, {"patch": {"layer": "S", "after_draft": after}})

    assert result["scbkr"]["S"]["task_name"] == "更新後任務名稱"
    assert result["confirmed"] is False
    assert result["status"] == "waiting_user_confirm"
    assert result["auto_confirmed"] is False
    assert any(event.get("event_type") == "scbkr_patch_applied" for event in main.get_task_ledger(task_id))
