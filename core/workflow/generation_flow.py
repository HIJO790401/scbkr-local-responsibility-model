"""Pure P6 generation gate helpers.

P6 prepares model request payloads and parses caller-supplied responses only.
It never sends requests, calls models, writes ledger events, writes data, or
persists task workflow runtime state.
"""

import json

from core.model_gateway.openai_compatible import build_chat_completion_payload
from core.scbkr.confirmation import all_dimensions_confirmed, build_model_visible_scbkr_payload
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
        if model_settings.get("mode") == "sandbox" and permissions.get("model_generate") is not True:
            raise PermissionError("model_generate permission is required before sandbox generation")
        raise ValueError("model gateway is not enabled for generation")
    return True


def build_scbkr_draft_generation_messages(raw_input, task_type="general", retrieval_context=None):
    """Build local/API prompt messages for SCBKR draft generation without executing the task."""
    system_message = (
        "你正在 SCBKR 草案生成階段。你的任務是根據使用者輸入，產生 S/C/B/K/R 五維確認單草案。"
        "所有欄位都必須標註為待使用者確認。你不得直接執行任務。你不得輸出最終成果。"
        "你不得自行將 confirmed 設為 true。你只負責填寫草案，等待使用者修改或確認。\n"
        "You are in the SCBKR draft generation stage. Your task is to generate a draft S/C/B/K/R confirmation sheet from the user input. "
        "All fields must be treated as waiting for user confirmation. Do not execute the task. Do not produce the final output. "
        "Do not set confirmed to true. Only fill the draft and wait for user edit or confirmation."
    )
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": json.dumps({"raw_input": raw_input, "task_type": task_type, "required_dimensions": ["S", "C", "B", "K", "R"], "status": "draft/waiting_user_confirm", "four_store_retrieval_context": retrieval_context or {"hits": [], "must_cite_confirmed_rules": []}}, ensure_ascii=False, sort_keys=True)},
    ]


def build_generation_messages(task, scbkr):
    """Build OpenAI-compatible messages from a confirmed task and SCBKR form."""
    system_message = (
        "你現在處於 confirmed execution 真生成階段。S/C/B/K/R 已由使用者確認。"
        "你現在不是建立確認單，不是解釋 SCBKR，只能根據 confirmed SCBKR 生成正式任務結果。"
        "你不得重新建立確認單；不得輸出 SCBKR JSON；不得輸出確認單草案；不得把狀態改回 draft；不得要求使用者重新確認 S/C/B/K/R。"
        "You are now in the SCBKR task execution stage. Do not recreate the confirmation sheet. "
        "Do not change the status back to draft. Do not ask the user to reconfirm S/C/B/K/R. "
        "不得自行改變邊界；不得宣稱驗收通過；不得宣稱已入庫；"
        "不得寫 ledger、DB、四庫或記憶；輸出仍必須等待使用者驗收。"
    )
    if all_dimensions_confirmed(scbkr) is not True:
        raise ValueError("S/C/B/K/R dimensions must all be confirmed and match their sealed snapshots before generation")

    sealed_scbkr_payload = build_model_visible_scbkr_payload(scbkr)
    sealed_r_payload = sealed_scbkr_payload["R"]
    user_payload = {
        "raw_input": task.get("raw_input", ""),
        "task_name": task.get("task_name", ""),
        "task_type": task.get("task_type", ""),
        "S": sealed_scbkr_payload["S"],
        "C": sealed_scbkr_payload["C"],
        "B": sealed_scbkr_payload["B"],
        "K": sealed_scbkr_payload["K"],
        "R": sealed_r_payload,
        "acceptance_criteria": sealed_r_payload.get("acceptance_criteria", []),
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
