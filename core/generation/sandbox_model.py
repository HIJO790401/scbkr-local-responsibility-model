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
def _formal_result_text(task: dict[str, Any], scbkr: dict[str, Any]) -> str:
    raw = str(task.get("raw_input") or scbkr.get("S", {}).get("user_instruction") or "").strip()
    if "心靈雞湯" in raw or "chicken soup" in raw.lower():
        return "心靈雞湯文案初稿：\n你不需要一次抵達終點，只要今天比昨天更靠近自己一點。把焦慮交給行動，把懷疑留給時間；每一步微小前進，都正在替未來的你鋪路。"
    return f"正式任務結果初稿：\n已根據使用者確認的責任鏈生成內容。任務內容：{raw}"


def generate_with_sandbox_model(task: dict[str, Any], scbkr: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic mock output for a gated, confirmed SCBKR task."""
    sealed_scbkr_payload = build_model_visible_scbkr_payload(scbkr)
    return {
        "task_id": task.get("task_id"),
        "task_type": task.get("task_type"),
        "sandbox_notice": SANDBOX_NOTICE,
        "generated_text": _formal_result_text(task, scbkr),
        "content": _formal_result_text(task, scbkr),
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
