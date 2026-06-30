from fastapi.testclient import TestClient

from apps.api import main
from core.permissions.permission_flags import DEFAULT_PERMISSION_SETTINGS
from core.rules.registry import RuleRegistry
from core.tools.registry import ToolGateEngine, list_tool_definitions


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
        }
    )
    signed = registry.sign_user_rule(draft["rule_id"], "owner")
    return registry.activate(signed["rule_id"], "user", {"workflow": "repair"}, "adopt")


def test_tool_registry_contains_master_plan_tools():
    tool_ids = {tool["tool_id"] for tool in list_tool_definitions()}
    assert {"web_search", "email_read", "email_draft", "code_workspace", "git_repo", "image_generation", "voice_input", "voice_output", "local_files", "api_tools", "scheduler", "data_center_query", "rule_registry_query"} <= tool_ids


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
    engine = ToolGateEngine(registry, permissions(local_file_access=True), tmp_path / "traces.jsonl")
    result = engine.evaluate({"tool_id": "code_workspace", "action": "execute", "task_type": "coding", "workflow": "repair", "text": "fix bug", "user_confirmation": True})
    assert result["allowed"] is True
    assert result["rule_match_gate"]["matched"] is True
    assert result["tool_permission_gate"]["allowed"] is True
    assert result["risk_gate"]["allowed"] is True
    assert result["execution_status"] == "authorized_not_executed"
    assert engine.list_traces()[0]["trace_hash"] == result["trace_hash"]


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
