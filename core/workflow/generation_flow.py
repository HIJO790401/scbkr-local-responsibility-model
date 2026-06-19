"""Pure P6 generation gate helpers.

P6 prepares model request payloads and parses caller-supplied responses only.
It never sends requests, calls models, writes ledger events, writes data, or
persists task workflow runtime state.
"""

import json

from core.model_gateway.openai_compatible import build_chat_completion_payload
from core.scbkr.confirmation import all_dimensions_confirmed
from core.model_gateway.response_parser import parse_chat_completion_response
from core.model_gateway.settings import can_enable_generate
from core.workflow.generation_result import build_generation_result


def assert_task_can_generate(task, scbkr, model_settings, permissions):
    """Raise ValueError unless task, SCBKR, and model settings pass P6 safety gates."""
    if task.get("confirmed") is not True:
        raise ValueError("task.confirmed must be true before generation")
    if task.get("status") != "confirmed":
        raise ValueError("task.status must be confirmed before generation")
    if task.get("review_passed") is not False:
        raise ValueError("task.review_passed must remain false before generation")
    if task.get("storage_confirmed") is not False:
        raise ValueError("task.storage_confirmed must remain false before generation")
    if scbkr.get("confirmation_status") != "confirmed":
        raise ValueError("scbkr.confirmation_status must be confirmed before generation")
    if all_dimensions_confirmed(scbkr) is not True:
        raise ValueError("S/C/B/K/R dimensions must all be confirmed and match their sealed snapshots before generation")
    if can_enable_generate(model_settings, permissions) is not True:
        raise ValueError("model gateway is not enabled for generation")
    return True


def build_generation_messages(task, scbkr):
    """Build OpenAI-compatible messages from a confirmed task and SCBKR form."""
    system_message = (
        "你是 SCBKR 任務執行單元。只能依照已確認的 SCBKR 五維責任鏈執行；"
        "不得自行改變邊界；不得宣稱驗收通過；不得宣稱已入庫；"
        "不得寫 ledger、DB、四庫或記憶；輸出仍必須等待使用者驗收。"
    )
    user_payload = {
        "raw_input": task.get("raw_input", ""),
        "task_name": task.get("task_name", ""),
        "task_type": task.get("task_type", ""),
        "S": scbkr.get("S"),
        "C": scbkr.get("C"),
        "B": scbkr.get("B"),
        "K": scbkr.get("K"),
        "R": scbkr.get("R"),
        "acceptance_criteria": scbkr.get("R", {}).get("acceptance_criteria", []),
    }
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, sort_keys=True)},
    ]


def build_model_request_package(task, scbkr, model_settings, permissions):
    """Build a model request package without sending it."""
    assert_task_can_generate(task, scbkr, model_settings, permissions)
    messages = build_generation_messages(task, scbkr)
    model_payload = build_chat_completion_payload(messages, model_settings)
    return {
        "task_id": task.get("task_id"),
        "trace_id": task.get("trace_id"),
        "ledger_id": task.get("ledger_id"),
        "status": "generation_request_ready",
        "model_payload": model_payload,
        "next_required_action": "caller_must_send_to_model_explicitly",
    }


def parse_generation_response(task, scbkr, model_response):
    """Parse a caller-supplied model response into a waiting-review result."""
    parsed_content = parse_chat_completion_response(model_response)
    return build_generation_result(task, scbkr, parsed_content)


def run_generation_gate(task, scbkr, model_settings, permissions, model_response=None):
    """Run the P6 safety gate without executing any model request."""
    if model_response is None:
        return build_model_request_package(task, scbkr, model_settings, permissions)
    assert_task_can_generate(task, scbkr, model_settings, permissions)
    return parse_generation_response(task, scbkr, model_response)
