"""Tool Registry, permission/risk gates, and replayable execution traces."""
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.permissions.permission_checker import check_permission_for_operation
from core.rules.registry import RuleRegistry

TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {"tool_id": "web_search", "name": "Web Search", "operation": "web_search", "risk_level": "high", "capabilities": ["observe", "draft"], "external": True},
    {"tool_id": "email_read", "name": "Email Read", "operation": "external_api_call", "risk_level": "high", "capabilities": ["observe"], "external": True},
    {"tool_id": "email_draft", "name": "Email Draft", "operation": "external_api_call", "risk_level": "high", "capabilities": ["draft"], "external": True},
    {"tool_id": "email_send", "name": "Email Send", "operation": "external_api_call", "risk_level": "critical", "capabilities": ["execute"], "external": True},
    {"tool_id": "code_workspace", "name": "Code Workspace", "operation": "local_file_read", "risk_level": "high", "capabilities": ["observe", "draft", "execute"], "external": False},
    {"tool_id": "git_repo", "name": "Git / Repo", "operation": "local_file_read", "risk_level": "high", "capabilities": ["observe", "draft", "execute"], "external": True},
    {"tool_id": "image_generation", "name": "Image Generation", "operation": "external_api_call", "risk_level": "high", "capabilities": ["draft", "execute"], "external": True},
    {"tool_id": "voice_input", "name": "Voice Input", "operation": "local_file_read", "risk_level": "medium", "capabilities": ["observe"], "external": False},
    {"tool_id": "voice_output", "name": "Voice Output", "operation": "external_api_call", "risk_level": "high", "capabilities": ["draft", "execute"], "external": True},
    {"tool_id": "local_files", "name": "Local Files", "operation": "local_file_read", "risk_level": "high", "capabilities": ["observe", "draft", "execute"], "external": False},
    {"tool_id": "api_tools", "name": "API Tools", "operation": "external_api_call", "risk_level": "high", "capabilities": ["observe", "draft", "execute"], "external": True},
    {"tool_id": "scheduler", "name": "Scheduler", "operation": "high_risk_operation", "risk_level": "critical", "capabilities": ["draft", "execute"], "external": False},
    {"tool_id": "data_center_query", "name": "Data Center Query", "operation": "sqlite_runtime", "risk_level": "critical", "capabilities": ["observe"], "external": False},
    {"tool_id": "rule_registry_query", "name": "Rule Registry Query", "operation": "sqlite_runtime", "risk_level": "critical", "capabilities": ["observe"], "external": False},
)
LOW_RISK_ACTIONS_WITHOUT_RULE = {"observe", "search", "organize", "draft"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def list_tool_definitions() -> list[dict[str, Any]]:
    return [dict(item) for item in TOOL_DEFINITIONS]


def _tool(tool_id: str) -> dict[str, Any]:
    tool = next((dict(item) for item in TOOL_DEFINITIONS if item["tool_id"] == tool_id), None)
    if not tool:
        raise ValueError(f"unknown tool: {tool_id}")
    return tool


class ToolGateEngine:
    def __init__(self, rule_registry: RuleRegistry, permissions: dict[str, Any], trace_path: str | Path):
        self.rule_registry = rule_registry
        self.permissions = dict(permissions)
        self.trace_path = Path(trace_path)

    def _append_trace(self, trace: dict[str, Any]) -> None:
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trace, ensure_ascii=False, sort_keys=True) + "\n")

    def list_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.trace_path.exists():
            return []
        rows = [json.loads(line) for line in self.trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return rows[-max(1, min(limit, 1000)):][::-1]

    def record_execution(self, authorization: dict[str, Any], status: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if status not in {"execution_succeeded", "execution_failed"}:
            raise ValueError("invalid execution status")
        trace = {
            "trace_id": f"tooltrace:{uuid4().hex}",
            "parent_trace_id": authorization.get("trace_id"),
            "timestamp": _now(),
            "tool_id": authorization.get("tool_id"),
            "action": authorization.get("action"),
            "task_id": authorization.get("task_id"),
            "allowed": authorization.get("allowed") is True,
            "execution_status": status,
            "metadata": metadata or {},
        }
        trace["trace_hash"] = hashlib.sha256(json.dumps(trace, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        self._append_trace(trace)
        return trace

    def evaluate(self, request: dict[str, Any]) -> dict[str, Any]:
        tool = _tool(str(request.get("tool_id") or ""))
        action = str(request.get("action") or "observe")
        if action not in {"observe", "search", "organize", "draft", "decide", "execute", "store", "send", "publish", "delete", "archive", "pay"}:
            raise ValueError("unsupported tool action")
        match_request = {
            "task_type": request.get("task_type") or "general",
            "tool": tool["tool_id"],
            "workflow": request.get("workflow") or "",
            "action": action,
            "text": request.get("text") or "",
        }
        rule_gate = self.rule_registry.match(match_request)
        no_rule_low_risk = action in LOW_RISK_ACTIONS_WITHOUT_RULE and any(
            capability in tool["capabilities"] for capability in ("observe", "draft")
        )
        rule_allowed = (rule_gate["matched"] and rule_gate["tool_allowed"]) or no_rule_low_risk

        permissions = dict(self.permissions)
        permissions["dangerous_operation_confirmed"] = request.get("user_confirmation") is True
        permission_gate = check_permission_for_operation(permissions, tool["operation"], context=request)
        risk_level = tool["risk_level"]
        confirmation_required = risk_level in {"high", "critical"}
        risk_gate = {
            "risk_level": risk_level,
            "confirmation_required": confirmation_required,
            "user_confirmed": request.get("user_confirmation") is True,
            "allowed": not confirmation_required or request.get("user_confirmation") is True,
        }
        final_allowed = rule_allowed and permission_gate["allowed"] is True and risk_gate["allowed"] is True
        trace = {
            "trace_id": f"tooltrace:{uuid4().hex}",
            "timestamp": _now(),
            "tool_id": tool["tool_id"],
            "action": action,
            "task_id": request.get("task_id"),
            "rule_match_gate": rule_gate,
            "rule_allowed": rule_allowed,
            "tool_permission_gate": permission_gate,
            "risk_gate": risk_gate,
            "user_confirmation_gate": {
                "required": confirmation_required,
                "confirmed": request.get("user_confirmation") is True,
            },
            "allowed": final_allowed,
            "execution_status": "authorized_not_executed" if final_allowed else "blocked_not_executed",
            "reason": (
                "authorized_all_gates_passed"
                if final_allowed
                else "rule_match_required"
                if not rule_allowed
                else permission_gate["reason"]
                if permission_gate["allowed"] is not True
                else "user_confirmation_required"
            ),
        }
        trace["trace_hash"] = hashlib.sha256(
            json.dumps(trace, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self._append_trace(trace)
        return trace
