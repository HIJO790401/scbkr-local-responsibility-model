from fastapi.testclient import TestClient

from apps.api import main
from core.permissions.permission_flags import DEFAULT_PERMISSION_SETTINGS
from core.rules.registry import RuleRegistry
from core.tools.registry import ToolGateEngine, list_tool_definitions
from core.tools.state_readers import read_tool_evidence_state


def permissions(**overrides):
    result = dict(DEFAULT_PERMISSION_SETTINGS)
    result.update(overrides)
    return result


def active_code_rule(registry: RuleRegistry):
    draft = registry.create_draft(
        {
            "rule_id": "rule:test:code-execute",
            "rule_name": "Allow adopted code execution",
            "rule_author": "Owner",
            "rule_source": "user_defined",
            "rule_version": "v1.0.0",
            "rule_scope": {
                "task_types": ["coding"],
                "tools": ["code_workspace"],
                "workflows": ["repair"],
                "keywords": ["fix"],
                "actions": ["execute"],
            },
            "allowed_tools": ["code_workspace"],
            "denied_tools": [],
            "automation_level": "semi_auto",
            "risk_level": "high",
            "changelog": [],
            "rule_trigger_contract": {
                "contract_version": "v1", "trigger_mode": "all", "owner_defined": True,
                "triggers": [{"trigger_id": "fix-phrase", "evidence_source": "owner_input", "field": "text", "operator": "contains", "expected": "fix"}],
                "scope": {"action": ["execute"]}, "valid_when": [], "invalid_when": [],
            },
        }
    )
    signed = registry.sign_user_rule(draft["rule_id"], "owner")
    return registry.activate(signed["rule_id"], "user", {"workflow": "repair"}, "adopt")


def test_production_file_reader_requires_server_prepared_draft_and_rechecks(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_TOOL_WORKSPACE_ROOT", str(tmp_path))
    path = tmp_path / "sample.py"
    path.write_text("value = 1\n", encoding="utf-8")
    registry = RuleRegistry(tmp_path / "rules")
    active_code_rule(registry)
    engine = ToolGateEngine(registry, permissions(local_file_access=True), tmp_path / "traces" / "tool.jsonl", state_reader=read_tool_evidence_state, require_trusted_draft=True)
    request = {"tool_id": "code_workspace", "action": "execute", "task_type": "coding", "workflow": "repair", "text": "fix bug", "file_path": str(path), "user_confirmation": True}
    assert engine.evaluate({**request, "draft_evidence_state": {"resource_id": "fake"}})["reason"] == "trusted_draft_or_coverage_required"
    prepared = engine.prepare_stateful_draft(request)
    approved = engine.evaluate({**request, "prepared_draft_id": prepared["prepared_draft_id"]})
    assert approved["allowed"] is True
    assert approved["execution_status"] == "authorized_not_executed"
    path.write_text("value = 2\n", encoding="utf-8")
    blocked = engine.evaluate({**request, "prepared_draft_id": prepared["prepared_draft_id"]})
    assert blocked["allowed"] is False
    assert blocked["confirm_time_state_gate"]["reason"] == "relevant_evidence_changed"


def test_external_message_reader_remains_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_TOOL_WORKSPACE_ROOT", str(tmp_path))
    engine = ToolGateEngine(RuleRegistry(tmp_path / "rules"), permissions(external_api_call=True), tmp_path / "trace.jsonl", state_reader=read_tool_evidence_state, require_trusted_draft=True)
    import pytest
    with pytest.raises(ValueError, match="no trusted production reader"):
        engine.prepare_stateful_draft({"tool_id": "email_send", "action": "execute"})


def test_production_reader_requires_explicit_workspace_and_keeps_file_content_out_of_trace(tmp_path, monkeypatch):
    import pytest

    path = tmp_path / "private.txt"
    path.write_text("sensitive-file-content", encoding="utf-8")
    monkeypatch.delenv("SCBKR_TOOL_WORKSPACE_ROOT", raising=False)
    request = {"tool_id": "local_files", "action": "execute", "file_path": str(path)}
    engine = ToolGateEngine(RuleRegistry(tmp_path / "rules"), permissions(local_file_access=True), tmp_path / "traces" / "tool.jsonl", state_reader=read_tool_evidence_state, require_trusted_draft=True)
    with pytest.raises(ValueError, match="not configured"):
        engine.prepare_stateful_draft(request)

    monkeypatch.setenv("SCBKR_TOOL_WORKSPACE_ROOT", str(tmp_path))
    prepared = engine.prepare_stateful_draft(request)
    evidence_file = tmp_path / "traces" / "draft_evidence" / f"{prepared['prepared_draft_id']}.json"
    assert "sensitive-file-content" not in evidence_file.read_text(encoding="utf-8")


def test_confirm_time_file_reader_failure_blocks_authorization(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_TOOL_WORKSPACE_ROOT", str(tmp_path))
    path = tmp_path / "sample.py"
    path.write_text("value = 1\n", encoding="utf-8")
    registry = RuleRegistry(tmp_path / "rules")
    active_code_rule(registry)
    engine = ToolGateEngine(registry, permissions(local_file_access=True), tmp_path / "traces" / "tool.jsonl", state_reader=read_tool_evidence_state, require_trusted_draft=True)
    request = {"tool_id": "code_workspace", "action": "execute", "task_type": "coding", "workflow": "repair", "text": "fix bug", "file_path": str(path), "user_confirmation": True}
    prepared = engine.prepare_stateful_draft(request)
    path.unlink()
    result = engine.evaluate({**request, "prepared_draft_id": prepared["prepared_draft_id"]})
    assert result["allowed"] is False
    assert result["confirm_time_state_gate"]["reason"] == "confirm_time_state_read_failed"


def test_tool_registry_contains_master_plan_tools():
    definitions = {tool["tool_id"]: tool for tool in list_tool_definitions()}
    tool_ids = set(definitions)
    assert {"web_search", "email_read", "email_draft", "code_workspace", "git_repo", "image_generation", "voice_input", "voice_output", "local_files", "api_tools", "scheduler", "data_center_query", "rule_registry_query"} <= tool_ids
    assert definitions["email_send"]["state_scope"] == "external_message"
    assert definitions["code_workspace"]["state_scope"] == "file_modification"


def test_no_rule_blocks_execution_even_when_permission_and_confirmation_exist(tmp_path):
    engine = ToolGateEngine(
        RuleRegistry(tmp_path / "rules"),
        permissions(local_file_access=True),
        tmp_path / "traces.jsonl",
    )
    result = engine.evaluate({"tool_id": "code_workspace", "action": "execute", "task_type": "coding", "workflow": "repair", "text": "fix bug", "user_confirmation": True})
    assert result["allowed"] is False
    assert result["reason"] == "rule_match_required"
    assert result["execution_status"] == "blocked_not_executed"


def test_active_rule_permission_and_confirmation_pass_all_gates(tmp_path):
    registry = RuleRegistry(tmp_path / "rules")
    active_code_rule(registry)
    draft_state = {"resource_id": "file:main.py", "version": "v1", "content_hash": "abc", "read_at": "2026-08-01T10:00:00Z"}
    engine = ToolGateEngine(
        registry,
        permissions(local_file_access=True),
        tmp_path / "traces.jsonl",
        state_reader=lambda _request: {**draft_state, "read_at": "2026-08-01T10:05:00Z"},
    )
    result = engine.evaluate({"tool_id": "code_workspace", "action": "execute", "task_type": "coding", "workflow": "repair", "text": "fix bug", "user_confirmation": True, "draft_evidence_state": draft_state})
    assert result["allowed"] is True
    assert result["rule_match_gate"]["matched"] is True
    assert result["tool_permission_gate"]["allowed"] is True
    assert result["risk_gate"]["allowed"] is True
    assert result["confirm_time_state_gate"]["confirm_time_rechecked"] is True
    assert result["confirm_time_state_gate"]["conflict"] is False
    assert result["confirm_time_state_gate"]["expected_evidence_hash"] == result["confirm_time_state_gate"]["current_evidence_hash"]
    assert result["execution_status"] == "authorized_not_executed"
    assert engine.list_traces()[0]["trace_hash"] == result["trace_hash"]


def test_confirm_time_state_conflict_blocks_file_modification(tmp_path):
    registry = RuleRegistry(tmp_path / "rules")
    active_code_rule(registry)
    draft_state = {"resource_id": "file:main.py", "version": "v1", "content_hash": "abc", "read_at": "2026-08-01T10:00:00Z"}
    engine = ToolGateEngine(
        registry,
        permissions(local_file_access=True),
        tmp_path / "traces.jsonl",
        state_reader=lambda _request: {"resource_id": "file:main.py", "version": "v2", "content_hash": "def", "read_at": "2026-08-01T10:05:00Z"},
    )

    result = engine.evaluate({"tool_id": "code_workspace", "action": "execute", "task_type": "coding", "workflow": "repair", "text": "fix bug", "user_confirmation": True, "draft_evidence_state": draft_state})

    assert result["allowed"] is False
    assert result["reason"] == "state_conflict_reconfirmation_required"
    assert result["confirm_time_state_gate"]["conflict"] is True
    assert result["execution_status"] == "blocked_not_executed"


def test_stateful_tool_without_live_reader_is_fail_closed(tmp_path):
    registry = RuleRegistry(tmp_path / "rules")
    active_code_rule(registry)
    engine = ToolGateEngine(registry, permissions(local_file_access=True), tmp_path / "traces.jsonl")

    result = engine.evaluate({"tool_id": "code_workspace", "action": "execute", "task_type": "coding", "workflow": "repair", "text": "fix bug", "user_confirmation": True, "draft_evidence_state": {"resource_id": "file:main.py", "version": "v1", "content_hash": "abc"}})

    assert result["allowed"] is False
    assert result["reason"] == "confirm_time_state_recheck_unavailable"
    assert result["confirm_time_state_gate"]["confirm_time_rechecked"] is False


def test_high_risk_confirmation_is_per_call_not_only_global(tmp_path):
    registry = RuleRegistry(tmp_path / "rules")
    active_code_rule(registry)
    engine = ToolGateEngine(registry, permissions(local_file_access=True, dangerous_operation_confirmed=True), tmp_path / "traces.jsonl")
    result = engine.evaluate({"tool_id": "code_workspace", "action": "execute", "task_type": "coding", "workflow": "repair", "text": "fix bug", "user_confirmation": False})
    assert result["allowed"] is False
    assert result["risk_gate"]["confirmation_required"] is True
    assert result["reason"] in {"high_risk_operation_requires_user_confirmation", "user_confirmation_required"}


def test_tool_gate_api_records_trace(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    client = TestClient(main.app)
    main.PERMISSIONS.update(permissions(web_search=True))
    evaluated = client.post("/api/tools/evaluate", json={"tool_id": "web_search", "action": "search", "text": "SCBKR", "user_confirmation": True})
    assert evaluated.status_code == 200
    assert evaluated.json()["allowed"] is True
    traces = client.get("/api/tools/traces")
    assert traces.status_code == 200
    assert traces.json()["traces"][0]["tool_id"] == "web_search"
