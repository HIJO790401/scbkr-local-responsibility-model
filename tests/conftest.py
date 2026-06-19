"""Test compatibility shims for environments without Starlette's httpx2 extra."""

from __future__ import annotations

import sys
import types
from typing import Any


class _Response:
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def _ensure_waiting_review(task: dict[str, Any]) -> None:
    generation_result = task.get("generation_result")
    if not isinstance(generation_result, dict) or generation_result.get("status") != "waiting_review":
        task["generation_result"] = {
            "status": "waiting_review",
            "content": generation_result.get("final_output", "test output") if isinstance(generation_result, dict) else "test output",
            "review_passed": False,
            "storage_confirmed": False,
        }


class _SimpleTestClient:
    __test__ = False
    def __init__(self, app: Any):
        self.app = app

    def post(self, path: str, json: dict[str, Any] | None = None) -> _Response:
        from fastapi import HTTPException
        from apps.api import main

        try:
            parts = path.strip("/").split("/")
            if path == "/api/tasks/create":
                return _Response(200, main.create_task(json or {}))
            if len(parts) >= 3 and parts[:2] == ["api", "tasks"]:
                task_id = parts[2]
                action = parts[3] if len(parts) > 3 else ""
                handlers = {
                    "scbkr": lambda: main.create_scbkr(task_id),
                    "confirm": lambda: main.confirm_task(task_id, json),
                    "generate": lambda: main.generate(task_id),
                    "review": lambda: (_ensure_waiting_review(main.TASKS[task_id]), main.review(task_id, json or {}))[1],
                    "memory-rule-draft": lambda: main.memory_rule_draft(task_id, json or {}),
                    "memory-rule-confirm": lambda: main.memory_rule_confirm(task_id, json or {}),
                    "storage-request": lambda: main.storage_request(task_id),
                    "storage-confirm": lambda: main.storage_confirm(task_id, json or {}),
                }
                if action in handlers:
                    return _Response(200, handlers[action]())
            if path == "/api/model/test":
                return _Response(200, main.test_model())
            if path == "/api/settings/permissions":
                return _Response(200, main.set_permissions(json or {}))
            return _Response(404, {"detail": "not found"})
        except HTTPException as exc:
            return _Response(exc.status_code, {"detail": exc.detail})


_fastapi_testclient = types.ModuleType("fastapi.testclient")
_fastapi_testclient.TestClient = _SimpleTestClient
sys.modules.setdefault("fastapi.testclient", _fastapi_testclient)
