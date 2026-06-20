"""Deterministic sandbox generation for P14-A.

The sandbox model never calls external APIs, local model servers, or downloads
models. It only creates a clearly marked mock output after the normal SCBKR
responsibility-chain gates have already passed.
"""
from __future__ import annotations

from typing import Any

from core.scbkr.confirmation import build_model_visible_scbkr_payload

SANDBOX_PROVIDER = "sandbox_mock_model"
SANDBOX_NOTICE = "Sandbox Mode: workflow test only. No external model or API was called."
SANDBOX_GENERATED_TEXT = (
    "This is a sandbox-generated response for testing the SCBKR responsibility-chain workflow. "
    "No external model or API was called.\n"
    "這是 SCBKR 沙盒模式產生的測試輸出，沒有呼叫外部模型或 API。"
)


def generate_with_sandbox_model(task: dict[str, Any], scbkr: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic mock output for a gated, confirmed SCBKR task."""
    sealed_scbkr_payload = build_model_visible_scbkr_payload(scbkr)
    return {
        "task_id": task.get("task_id"),
        "task_type": task.get("task_type"),
        "sandbox_notice": SANDBOX_NOTICE,
        "generated_text": SANDBOX_GENERATED_TEXT,
        "content": SANDBOX_GENERATED_TEXT,
        "scbkr_summary": {
            "S": sealed_scbkr_payload.get("S"),
            "C": sealed_scbkr_payload.get("C"),
            "B": sealed_scbkr_payload.get("B"),
            "K": sealed_scbkr_payload.get("K"),
            "R": sealed_scbkr_payload.get("R"),
        },
        "model_provider": SANDBOX_PROVIDER,
        "provider": SANDBOX_PROVIDER,
        "sandbox": True,
        "external_call_performed": False,
    }
