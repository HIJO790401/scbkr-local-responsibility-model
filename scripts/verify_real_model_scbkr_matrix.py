"""Run repeatable SCBKR product checks against a real local model endpoint.

This script uses a temporary SCBKR data directory. It never stores test rules
in the user's normal product data and never substitutes a template for model
rulebook authorship.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


RULE_CASES = [
    {
        "id": "zh-explicit-document-release",
        "locale": "zh-TW",
        "request": "建立可重用文件發布規則：適用於我要公開文件時。先核對文件版本及收件對象，再確認我已核准；未核准不得發布，資料缺失就停止；只能引用我確認的文件與版本紀錄；由我驗收並簽名後才生效。",
        "full_workflow": True,
        "followup": "這份文件版本還沒核對，但對方催我現在公開，可以嗎？",
    },
    {
        "id": "zh-debt-civil-case",
        "locale": "zh-TW",
        "request": "幫我生成債務民事案件資料整理規則書：先核對當事人、借款證據、金額、日期與時效；資料不足時只能列待確認，不得替我判決勝敗。",
    },
    {
        "id": "zh-beauty-copy",
        "locale": "zh-TW",
        "request": "我要一個美容院商業文案規則：不得誇大療效、不得編造價格，發布前要由我確認，把它寫成可重複使用的本地規則。",
    },
    {
        "id": "en-refund-approval",
        "locale": "en",
        "request": "Create a reusable customer refund approval rule. Verify the order and evidence first, stop when records are missing, and require my signature before the rule becomes active.",
    },
    {
        "id": "zh-friend-advance",
        "locale": "zh-TW",
        "request": "以後凡是朋友要求我先墊錢，我要先判斷這是不是風險轉嫁，把這個寫成我的本地規則。",
    },
    {
        "id": "zh-code-deployment",
        "locale": "zh-TW",
        "request": "幫我建立程式部署規則：先跑測試再檢查版本與環境；測試失敗、依賴不明或沒有回滾方案時不得部署；依據只能用已確認的測試報告與版本紀錄；由專案負責人驗收簽名。",
    },
    {
        "id": "en-argument-review",
        "locale": "en",
        "request": "Create a reusable logic-review rule. First identify the claim and premises, then test inference and counterexamples. Stop when premises are missing. Cite only confirmed source material. The user must review and sign the rule.",
    },
]

CHAT_CASES = [
    {"id": "zh-identity", "message": "你好，請用一般人聽得懂的話介紹你是誰、誰建立你、你能做什麼。", "must_include": ["許文耀", "主體"]},
    {"id": "en-identity", "message": "Who created SCBKR, and what can this product do? Please answer in English.", "must_include": ["Wen-Yao Hsu", "Subject"]},
    {"id": "zh-four-store", "message": "四庫裡面的 VECTOR 可以直接當正式依據嗎？", "must_include": ["VECTOR", "不能"]},
    {"id": "zh-plain", "message": "SCBKR 是什麼？請用不懂技術的人也聽得懂的白話說。", "must_include": ["主體", "責任"]},
    {"id": "en-deep", "message": "Explain SCBKR's technical architecture in detail.", "must_include": ["Subject", "Responsibility"]},
    {"id": "zh-chat-only", "message": "先聊聊程式部署的風險，不要建立規則。", "expected_route": "general_chat", "must_not_create_task": True},
]


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _post(client: TestClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=payload)
    _expect(response.status_code == 200, f"{path} returned HTTP {response.status_code}: {response.text[:400]}")
    value = response.json()
    _expect(isinstance(value, dict), f"{path} did not return a JSON object")
    return value


def _save_progress(args: argparse.Namespace, result: dict[str, Any]) -> None:
    """Persist every completed step so a slow local model is observable."""
    if not args.output:
        return
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _task_summary(case: dict[str, Any], task: dict[str, Any], elapsed: float) -> dict[str, Any]:
    scbkr = task.get("scbkr") or {}
    return {
        "case_id": case["id"],
        "locale": case["locale"],
        "request": case["request"],
        "elapsed_seconds": round(elapsed, 2),
        "status": task.get("status"),
        "draft_source": task.get("draft_source"),
        "model_used": task.get("model_used"),
        "model_provider": task.get("model_provider"),
        "model_name": task.get("model_name"),
        "model_schema_valid": task.get("model_schema_valid"),
        "model_schema_repaired": task.get("model_schema_repaired"),
        "model_semantic_valid": task.get("model_semantic_valid"),
        "model_semantic_report": task.get("model_semantic_report"),
        "validator_passed": task.get("validator_passed"),
        "fallback_used": task.get("fallback_used"),
        "requires_user_signature": task.get("requires_user_signature"),
        "model_signature_allowed": task.get("model_signature_allowed"),
        "rule_summary": scbkr.get("rule_summary"),
        "dimensions": {
            dim: {
                "content": (scbkr.get(dim) or {}).get("model_draft_content"),
                "model_explanation": (scbkr.get(dim) or {}).get("model_explanation"),
            }
            for dim in ("S", "C", "B", "K", "R")
        },
        "missing_information": scbkr.get("missing_information"),
        "risk_reminders": scbkr.get("risk_reminders"),
        "token_metrics": scbkr.get("token_metrics"),
        "model_capability": task.get("model_capability") or scbkr.get("model_capability"),
        "next_required_action": task.get("next_required_action"),
        "model_raw_preview": task.get("model_raw_preview"),
        "attempt_audit": task.get("attempt_audit") or [],
    }


def _assert_model_rulebook(task: dict[str, Any], case_id: str) -> str:
    _expect(task.get("model_used") is True, f"{case_id}: model was not used")
    _expect(task.get("model_schema_valid") is True, f"{case_id}: schema failed")
    _expect(task.get("fallback_used") is False, f"{case_id}: fallback must never be used")
    _expect(task.get("requires_user_signature") is True, f"{case_id}: user signature is not required")
    _expect(task.get("model_signature_allowed") is False, f"{case_id}: model signature was allowed")
    scbkr = task.get("scbkr") or {}
    semantic_report = task.get("model_semantic_report") or {}
    _expect(
        not semantic_report.get("model_authority_overreach_paths"),
        f"{case_id}: model authority overreach survived validation",
    )
    for dim in ("S", "C", "B", "K", "R"):
        _expect(isinstance(scbkr.get(dim), dict), f"{case_id}: {dim} is missing")
        _expect(bool((scbkr[dim].get("model_explanation") or "").strip()), f"{case_id}: {dim} explanation is missing")
    if task.get("status") == "model_capability_limited":
        capability = task.get("model_capability") or scbkr.get("model_capability") or {}
        _expect(task.get("draft_source") == "model_capability_limited", f"{case_id}: limited draft source mismatch")
        _expect(task.get("model_semantic_valid") is False, f"{case_id}: limited task cannot be semantic-valid")
        _expect(task.get("validator_passed") is False, f"{case_id}: limited task cannot pass Kernel Validator")
        _expect(scbkr.get("signing_allowed") is False, f"{case_id}: limited task allowed signing")
        _expect(bool(capability.get("unresolved_gaps")), f"{case_id}: capability gaps are missing")
        _expect(capability.get("latency_triggered") is False, f"{case_id}: latency triggered escalation")
        _expect(capability.get("automatic_cloud_escalation") is False, f"{case_id}: automatic cloud escalation occurred")
        return "draft_only"
    _expect(task.get("status") == "waiting_user_confirm", f"{case_id}: status={task.get('status')}")
    _expect(task.get("draft_source") == "model_assisted_rulebook", f"{case_id}: wrong draft source")
    _expect(task.get("model_semantic_valid") is True, f"{case_id}: semantic role check failed")
    _expect(task.get("validator_passed") is True, f"{case_id}: Kernel Validator failed")
    return "closed_draft"


def _complete_rule(
    client: TestClient,
    task: dict[str, Any],
    followup: str,
    *,
    run_token_ab: bool = True,
) -> dict[str, Any]:
    task_id = task["task_id"]
    signed = _post(client, f"/api/tasks/{task_id}/confirm", {
        "scbkr": task["scbkr"],
        "confirmed_by": "user",
        "signature": "human-matrix-owner-signature",
    })
    _expect(signed.get("status") == "confirmed", "owner signature did not confirm the task")
    generated = _post(client, f"/api/tasks/{task_id}/generate", {})
    _expect(generated.get("status") == "waiting_review", "generation did not reach owner review")
    reviewed = _post(client, f"/api/tasks/{task_id}/review", {
        "review_decision": "pass",
        "review_message": "Human matrix owner review passed.",
        "reviewer_signature": "human-matrix-review-signature",
    })
    _expect(reviewed.get("review_passed") is True, "owner review did not pass")
    _post(client, f"/api/tasks/{task_id}/storage-request", {
        "selected_targets": ["logic", "corpus", "memory", "vector"],
        "user_decision": "custom",
        "signature": "human-matrix-storage-request",
    })
    stored = _post(client, f"/api/tasks/{task_id}/storage-confirm", {
        "storage_confirmed": True,
        "second_confirm": True,
        "confirmed_by": "user",
        "signature": "human-matrix-storage-signature",
        "selected_targets": ["logic", "corpus", "memory", "vector"],
    })
    written = set((stored.get("storage_result") or {}).get("written_targets") or [])
    _expect(written == {"logic", "corpus", "memory", "vector"}, f"four-store write mismatch: {written}")
    answer = _post(client, "/api/chat/general", {"message": followup, "locale": "zh-TW"})
    rule_package = answer.get("current_rule_package") or {}
    _expect(answer.get("route_mode") == "answer_with_rules", "follow-up did not route through rules")
    _expect(answer.get("chat_context_used") is False, "follow-up used chat history as formal basis")
    _expect(bool(rule_package.get("matched_rules")), "follow-up did not match the signed rule")
    _expect((answer.get("rule_state") or {}).get("awareness_state") == "RULE_ACTIVE", "rule state is not active")
    post_check = answer.get("post_check") or {}
    _expect(
        post_check.get("allowed") is True,
        "post-check did not allow the answer: "
        + json.dumps(
            {
                "reply": answer.get("reply"),
                "source": answer.get("source"),
                "post_check": post_check,
                "rule_package": rule_package,
            },
            ensure_ascii=False,
        )[:4000],
    )
    audit = answer.get("token_cost_audit") or {}
    _expect(audit.get("measurement_basis") in {"provider_usage", "tokenizer"}, "token audit is not measured")
    token_ab = None
    if run_token_ab:
        token_ab = _post(client, "/api/metrics/token-ab/run", {
            "question": followup,
            "current_rule_package": rule_package,
            "full_history": [],
            "locale": "zh-TW",
        })
        _expect(token_ab.get("savings_verified") is True, "same-model token A/B lacks provider usage")
        _expect(token_ab.get("same_provider") is True, "token A/B changed provider")
        _expect(token_ab.get("same_model") is True, "token A/B changed model")
    return {
        "signed_status": signed.get("status"),
        "review_passed": reviewed.get("review_passed"),
        "written_targets": sorted(written),
        "followup": followup,
        "route_mode": answer.get("route_mode"),
        "chat_context_used": answer.get("chat_context_used"),
        "matched_rule_count": len(rule_package.get("matched_rules") or []),
        "reply": answer.get("reply"),
        "post_check": answer.get("post_check"),
        "token_cost_audit": audit,
        "token_ab": None if token_ab is None else {
            "savings_verified": token_ab.get("savings_verified"),
            "comparison_basis": token_ab.get("comparison_basis"),
            "measurement_basis": token_ab.get("measurement_basis"),
            "provider": token_ab.get("provider"),
            "model_name": token_ab.get("model_name"),
            "variants": token_ab.get("variants"),
            "savings": token_ab.get("savings"),
            "input_evidence": token_ab.get("input_evidence"),
            "local_report": token_ab.get("local_report"),
        },
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="scbkr-real-model-matrix-", ignore_cleanup_errors=True) as data_dir:
        os.environ["SCBKR_DATA_DIR"] = data_dir
        import apps.api.main as main

        main = importlib.reload(main)
        client = TestClient(main.app)
        _post(client, "/api/settings/model", {
            "provider": args.provider,
            "mode": "local" if args.provider in {"lm_studio", "ollama"} else "external",
            "base_url": args.base_url,
            "api_key": args.api_key,
            "model_name": args.model,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "context_length": args.context_length,
            "timeout": args.timeout,
        })
        permissions = {"model_generate": True}
        if args.provider not in {"lm_studio", "ollama"}:
            permissions["external_api"] = True
        _post(client, "/api/settings/permissions", permissions)
        print(f"[model-test] {args.provider} / {args.model}", flush=True)
        model_test = _post(client, "/api/model/test", {})
        _expect(
            model_test.get("last_test_status") == "success" and model_test.get("enabled") is True,
            f"model test failed: {model_test}",
        )

        result: dict[str, Any] = {
            "started_at_epoch": time.time(),
            "isolated_data_dir": True,
            "provider": args.provider,
            "model": args.model,
            "model_test": model_test,
            "rule_cases": [],
            "chat_cases": [],
            "full_workflow": None,
            "passed": False,
        }
        _save_progress(args, result)

        selected_rule_cases = [] if args.skip_rules else [
            case for case in RULE_CASES
            if not args.case_id or case["id"] in set(args.case_id)
        ]
        if not args.skip_rules:
            _expect(bool(selected_rule_cases), "no rule cases matched --case-id")
        for case in selected_rule_cases:
            print(f"[rule-case:start] {case['id']}", flush=True)
            started = time.perf_counter()
            task: dict[str, Any] | None = None
            try:
                task = _post(client, "/api/tasks/create", {
                    "raw_input": case["request"],
                    "task_type": "general",
                    "create_scbkr_draft": True,
                    "locale": case["locale"],
                })
                elapsed = time.perf_counter() - started
                outcome = _assert_model_rulebook(task, case["id"])
                summary = _task_summary(case, task, elapsed)
                summary["outcome"] = outcome
                result["rule_cases"].append(summary)
                if case.get("full_workflow") and outcome == "closed_draft":
                    print(f"[full-workflow:start] {case['id']}", flush=True)
                    result["full_workflow"] = _complete_rule(
                        client,
                        task,
                        case["followup"],
                        run_token_ab=not args.skip_token_ab,
                    )
                print(f"[rule-case:done] {case['id']} outcome={outcome} elapsed={elapsed:.2f}s", flush=True)
                _save_progress(args, result)
            except Exception as exc:
                elapsed = time.perf_counter() - started
                failure = (
                    _task_summary(case, task, elapsed)
                    if isinstance(task, dict)
                    else {
                        "case_id": case["id"],
                        "locale": case["locale"],
                        "request": case["request"],
                        "elapsed_seconds": round(elapsed, 2),
                    }
                )
                failure["outcome"] = "failed"
                failure["error"] = f"{type(exc).__name__}: {exc}"
                result["rule_cases"].append(failure)
                result["finished_at_epoch"] = time.time()
                _save_progress(args, result)
                print(f"[rule-case:failed] {case['id']} elapsed={elapsed:.2f}s error={exc}", flush=True)
                raise

        for case in ([] if args.skip_chat else CHAT_CASES):
            print(f"[chat-case:start] {case['id']}", flush=True)
            started = time.perf_counter()
            answer = _post(client, "/api/chat/general", {"message": case["message"]})
            if case.get("expected_route"):
                _expect(answer.get("route_mode") == case["expected_route"], f"{case['id']}: wrong route {answer.get('route_mode')}")
            for term in case.get("must_include") or []:
                _expect(str(term).lower() in str(answer.get("reply") or "").lower(), f"{case['id']}: reply omitted {term}")
            if case.get("must_not_create_task"):
                _expect(answer.get("task_created") is False, f"{case['id']}: normal chat created a task")
                _expect(answer.get("data_center_written") is False, f"{case['id']}: normal chat wrote the four stores")
            result["chat_cases"].append({
                "case_id": case["id"],
                "message": case["message"],
                "elapsed_seconds": round(time.perf_counter() - started, 2),
                "route_mode": answer.get("route_mode"),
                "reply": answer.get("reply"),
                "reply_source": answer.get("reply_source"),
                "model_used": answer.get("model_used"),
                "task_created": answer.get("task_created"),
                "data_center_written": answer.get("data_center_written"),
                "chat_context_used": answer.get("chat_context_used"),
                "token_cost_audit": answer.get("token_cost_audit"),
            })
            _save_progress(args, result)
            print(f"[chat-case:done] {case['id']}", flush=True)

        result["finished_at_epoch"] = time.time()
        result["capability_summary"] = {
            "closed_drafts": sum(1 for item in result["rule_cases"] if item.get("outcome") == "closed_draft"),
            "draft_only": sum(1 for item in result["rule_cases"] if item.get("outcome") == "draft_only"),
            "latency_used_for_escalation": False,
            "automatic_cloud_escalation": False,
        }
        require_closed = bool(not args.skip_rules and (
            args.require_closed
            or not args.case_id
            or any(case.get("full_workflow") for case in selected_rule_cases)
        ))
        if require_closed:
            _expect(result["capability_summary"]["closed_drafts"] >= 1, "real model did not close any selected SCBKR case")
        if any(case.get("full_workflow") for case in selected_rule_cases):
            _expect(result["full_workflow"] is not None, "no closed draft completed the signed four-store workflow")
        result["passed"] = True
        _save_progress(args, result)
        return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="lm_studio")
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--model", default="qwen2.5-1.5b-instruct")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=700)
    parser.add_argument("--context-length", type=int, default=8192)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", default="")
    parser.add_argument("--case-id", action="append", default=[], help="Run only the named rule case; may be repeated.")
    parser.add_argument("--require-closed", action="store_true", help="Fail unless at least one selected case reaches a closed draft.")
    parser.add_argument("--skip-rules", action="store_true", help="Skip rulebook authoring and run chat checks only.")
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument("--skip-token-ab", action="store_true")
    args = parser.parse_args()
    result = run(args)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    _save_progress(args, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
