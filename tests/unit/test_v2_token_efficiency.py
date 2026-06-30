from core.metrics.token_efficiency import build_token_efficiency_metrics, estimate_tokens, summarize_metrics


def test_estimator_handles_chinese_and_ascii():
    assert estimate_tokens("SCBKR responsibility") > 1
    assert estimate_tokens("責任鏈模型") > 1


def test_metrics_count_provider_usage_and_excluded_candidates():
    metrics = build_token_efficiency_metrics(
        raw_input="compile task",
        messages=[{"role": "user", "content": "compile task"}],
        retrieval_context={"evidence_packet": {"authority_count": 2, "candidate_count": 7}},
        full_rule_registry=[{"rule": "x" * 2000}],
        provider_usages=[{"prompt_tokens": 20, "completion_tokens": 10}],
        attempts=1,
    )
    assert metrics["provider_total_tokens"] == 30
    assert metrics["estimated_tokens_avoided"] > 0
    assert metrics["authoritative_citations_loaded"] == 2
    assert metrics["candidate_evidence_excluded"] == 7


def test_summary_aggregates_task_metrics():
    summary = summarize_metrics([
        {"scbkr": {"token_metrics": {"estimated_tokens_avoided": 100, "provider_total_tokens": 30, "model_attempts": 1, "candidate_evidence_excluded": 4}}},
        {"scbkr": {"token_metrics": {"estimated_tokens_avoided": 50, "provider_total_tokens": None, "model_attempts": 0, "candidate_evidence_excluded": 2}}},
    ])
    assert summary["task_count"] == 2
    assert summary["estimated_tokens_avoided"] == 150
    assert summary["candidate_evidence_excluded"] == 6
