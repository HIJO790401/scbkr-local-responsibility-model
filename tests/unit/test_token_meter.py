from core.metrics import token_meter
from core.metrics.token_meter import build_token_meter_report, measure_tokens, normalize_pricing


def test_provider_usage_is_authoritative_and_cost_is_transparent():
    report = build_token_meter_report(
        full_context={"old": "x" * 2000},
        current_rule_package={"rule": "short"},
        messages=[{"role": "user", "content": "short"}],
        provider_usages=[{"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40}],
        model_settings={"provider": "openai_compatible", "mode": "external", "model_name": "gpt-4o"},
        pricing={"currency": "USD", "input_per_million": 1, "output_per_million": 2, "source": "acceptance-test"},
    )

    assert report["measurement_basis"] == "provider_usage"
    assert report["actual_prompt_tokens"] == 30
    assert report["actual_completion_tokens"] == 10
    assert report["actual_total_tokens"] == 40
    assert report["actual_usage_verified"] is True
    assert report["comparison_basis"] == "counterfactual_local_count"
    assert report["savings_verified"] is False
    assert report["price_status"] == "configured"
    assert report["estimated_cost"] is not None
    assert report["cost_is_billed"] is True


def test_local_usage_reports_zero_api_charge_without_fake_cloud_price():
    report = build_token_meter_report(
        full_context="x" * 1000,
        current_rule_package="short",
        messages=[{"role": "user", "content": "short"}],
        provider_usages=[{"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28}],
        model_settings={"provider": "lm_studio", "mode": "local", "model_name": "qwen2.5-1.5b-instruct"},
    )

    assert report["measurement_basis"] == "provider_usage"
    assert report["local_execution"] is True
    assert report["price_status"] == "local_no_api_charge"
    assert report["api_cost"] == 0.0
    assert report["estimated_cost_saved"] is None


def test_missing_usage_is_explicitly_estimated():
    report = build_token_meter_report(
        full_context="x" * 100,
        current_rule_package="x" * 10,
        messages=[{"role": "user", "content": "x"}],
        model_settings={"provider": "custom", "mode": "external", "model_name": "unknown"},
    )

    assert report["provider_usage_available"] is False
    assert report["measurement_basis"] in {"tokenizer", "heuristic_estimate"}
    assert report["api_cost"] is None
    assert report["price_status"] == "not_configured"
    assert report["savings_verified"] is False


def test_pricing_normalization_does_not_accept_negative_values():
    pricing = normalize_pricing({"input_per_million": -1, "output_per_million": "0.6", "currency": "usd"})
    assert pricing["currency"] == "USD"
    assert pricing["input_per_million"] is None
    assert pricing["output_per_million"] == 0.6


def test_empty_measurement_does_not_load_a_model_tokenizer(monkeypatch):
    def fail_if_loaded(_model_name):
        raise AssertionError("empty values must not load a tokenizer")

    monkeypatch.setattr(token_meter, "_huggingface_tokenizer", fail_if_loaded)
    measured = measure_tokens([], provider="lm_studio", model_name="qwen3.5-4b", as_messages=True)

    assert measured == {
        "tokens": 0,
        "method": "empty",
        "tokenizer_name": "",
        "is_tokenizer_count": False,
    }


def test_provider_usage_skips_duplicate_request_tokenization(monkeypatch):
    calls = []

    def count_nonempty(value, *, provider, model_name, as_messages=False):
        calls.append((value, as_messages))
        return 12, "test_tokenizer", "test"

    monkeypatch.setattr(token_meter, "_tokenizer_count", count_nonempty)
    report = build_token_meter_report(
        full_context="full",
        current_rule_package="package",
        messages=[{"role": "user", "content": "hello"}],
        provider_usages=[{"prompt_tokens": 9, "completion_tokens": 3, "total_tokens": 12}],
        model_settings={"provider": "lm_studio", "mode": "local", "model_name": "qwen3.5-4b"},
    )

    assert len(calls) == 2
    assert all(as_messages is False for _, as_messages in calls)
    assert report["request_token_count_method"] == "provider_usage"
    assert report["compiled_prompt_tokens"] == 9
