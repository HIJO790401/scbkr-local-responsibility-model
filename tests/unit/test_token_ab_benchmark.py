import json

import pytest

from core.metrics.token_ab_benchmark import (
    render_token_ab_markdown,
    run_token_ab_benchmark,
    write_token_ab_report,
)


def benchmark_inputs():
    return {
        "question": "Can this document be published now?",
        "full_history": [
            {"role": "user", "content": "Earlier discussion " + "x" * 500},
            {"role": "assistant", "content": "Earlier answer " + "y" * 500},
        ],
        "full_rule_context": {"rules": [{"id": "rule-1", "content": "full rule " + "z" * 1000}]},
        "current_rule_package": {
            "matched_rules": ["rule-1"],
            "prohibitions": ["Do not publish before owner approval."],
            "missing_information": ["owner approval"],
        },
        "provider": "lm_studio",
        "model_name": "qwen-test",
    }


def test_verified_same_model_ab_uses_provider_usage_and_records_outputs():
    calls = []

    def model_call(**kwargs):
        calls.append(kwargs)
        if kwargs["variant"] == "A":
            return {
                "model": "qwen-test",
                "choices": [{"message": {"content": "A full-context answer"}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100},
            }
        return {
            "model": "qwen-test",
            "choices": [{"message": {"content": "B package answer"}}],
            "usage": {"prompt_tokens": 250, "completion_tokens": 80, "total_tokens": 330},
        }

    report = run_token_ab_benchmark(**benchmark_inputs(), model_call=model_call)

    assert len(calls) == 2
    assert {(call["provider"], call["model"]) for call in calls} == {("lm_studio", "qwen-test")}
    assert calls[0]["variant"] == "A"
    assert calls[1]["variant"] == "B"
    assert any("FULL_RULE_CONTEXT" in item["content"] for item in calls[0]["messages"])
    assert any("CURRENT_RULE_PACKAGE" in item["content"] for item in calls[1]["messages"])
    assert not any("Earlier discussion" in item["content"] for item in calls[1]["messages"])
    assert calls[0]["messages"][-1] == calls[1]["messages"][-1]
    assert report["savings_verified"] is True
    assert report["measurement_basis"] == "provider_usage"
    assert report["comparison_basis"] == "same_provider_same_model_two_real_calls"
    assert report["variants"]["A"]["prompt_tokens"] == 1000
    assert report["variants"]["B"]["completion_tokens"] == 80
    assert report["variants"]["A"]["output"] == "A full-context answer"
    assert report["variants"]["B"]["output"] == "B package answer"
    assert report["savings"]["prompt"] == {"a": 1000, "b": 250, "saved": 750, "reduction_percent": 75.0}
    assert report["savings"]["total"]["reduction_percent"] == 70.0
    assert report["savings"]["model_calls"] == {"a": 1, "b": 1, "total": 2}
    assert report["variants"]["A"]["latency_ms"] >= 0


def test_missing_provider_usage_is_unverified_local_measurement():
    def model_call(**kwargs):
        return {"model": "qwen-test", "choices": [{"message": {"content": f"output-{kwargs['variant']}"}}]}

    report = run_token_ab_benchmark(**benchmark_inputs(), model_call=model_call)

    assert report["savings_verified"] is False
    assert report["measurement_basis"] in {"tokenizer", "heuristic_estimate"}
    assert report["comparison_basis"] == "same_provider_same_model_local_count"
    assert "unverified" in report["verification_note"].lower()
    assert report["variants"]["A"]["provider_usage_available"] is False
    assert report["variants"]["A"]["prompt_tokens"] > report["variants"]["B"]["prompt_tokens"]


def test_responses_api_usage_names_are_accepted_as_provider_evidence():
    def model_call(**kwargs):
        prompt = 500 if kwargs["variant"] == "A" else 100
        return {
            "model": "qwen-test",
            "output_text": kwargs["variant"],
            "usage": {"input_tokens": prompt, "output_tokens": 25, "total_tokens": prompt + 25},
        }

    report = run_token_ab_benchmark(**benchmark_inputs(), model_call=model_call)

    assert report["savings_verified"] is True
    assert report["variants"]["A"]["prompt_tokens"] == 500
    assert report["savings"]["prompt"]["reduction_percent"] == 80.0


def test_full_context_is_bounded_to_the_connected_model_window_without_truncating_rule_package():
    inputs = benchmark_inputs()
    inputs["full_rule_context"] = {
        "rules": [{"id": "rule-1", "content": "very large context " + "z" * 20_000}]
    }
    calls = []

    def model_call(**kwargs):
        calls.append(kwargs)
        prompt = 220 if kwargs["variant"] == "A" else 90
        return {
            "model": "qwen-test",
            "output_text": f"answer-{kwargs['variant']}",
            "usage": {"prompt_tokens": prompt, "completion_tokens": 10, "total_tokens": prompt + 10},
        }

    report = run_token_ab_benchmark(
        **inputs,
        model_call=model_call,
        max_prompt_tokens=300,
    )

    budget = report["input_evidence"]["context_budget"]
    assert budget["bounded"] is True
    assert budget["original_prompt_tokens_estimate"] > 300
    assert budget["bounded_prompt_tokens_estimate"] <= 300
    assert budget["retained_snapshot_characters"] < budget["original_snapshot_characters"]
    assert report["variants"]["A"]["context_mode"] == "bounded_full_history_and_full_rule_context"
    assert "BOUNDED_FULL_CONTEXT_SNAPSHOT" in calls[0]["messages"][1]["content"]
    assert "CURRENT_RULE_PACKAGE" in calls[1]["messages"][1]["content"]
    assert report["savings_verified"] is True


def test_different_provider_reported_models_fail_instead_of_claiming_savings():
    def model_call(**kwargs):
        return {
            "model": "qwen-test" if kwargs["variant"] == "A" else "other-model",
            "output_text": "answer",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }

    with pytest.raises(ValueError, match="different models"):
        run_token_ab_benchmark(**benchmark_inputs(), model_call=model_call)


def test_markdown_and_json_reports_disclose_verification_and_outputs(tmp_path):
    def model_call(**kwargs):
        prompt = 200 if kwargs["variant"] == "A" else 100
        return {
            "model": "qwen-test",
            "output_text": f"answer-{kwargs['variant']}",
            "usage": {"prompt_tokens": prompt, "completion_tokens": 10, "total_tokens": prompt + 10},
        }

    report = run_token_ab_benchmark(**benchmark_inputs(), model_call=model_call)
    markdown = render_token_ab_markdown(report)
    assert "Verified by provider usage" in markdown
    assert "answer-A" in markdown and "answer-B" in markdown
    assert "50.0%" in markdown

    json_path, markdown_path = write_token_ab_report(
        report,
        json_path=tmp_path / "benchmark.json",
        markdown_path=tmp_path / "benchmark.md",
    )
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["savings_verified"] is True
    assert saved["variants"]["B"]["output"] == "answer-B"
    assert markdown_path.read_text(encoding="utf-8") == markdown


def test_required_inputs_are_validated_before_model_calls():
    inputs = benchmark_inputs()
    inputs["question"] = " "
    with pytest.raises(ValueError, match="question"):
        run_token_ab_benchmark(**inputs, model_call=lambda **_: {})
