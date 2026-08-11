import pytest

from core.evidence.contracts import build_evidence_packet, validate_evidence_packet
from core.model_gateway.openai_compatible import build_chat_completion_payload
from core.scbkr.compiler import (
    TASK_UNDERSTANDING_CONTRACT_VERSION,
    task_understanding_json_schema,
    task_understanding_response_format,
    validate_task_understanding_strict,
)
from core.scbkr.draft_grammar import classify_evidence_relation


def valid_understanding():
    return {
        "task_domain": "workflow",
        "task_subject": "Compile an owner request into an SCBKR draft.",
        "user_original_judgement": "Only signed rules are authoritative.",
        "user_goal": "Create a reviewable draft.",
        "output_format": ["SCBKR draft"],
        "core_claim": "The model describes; the owner confirms.",
        "causal_chain": ["owner input", "draft", "owner review"],
        "boundary_rules": ["no model signature"],
        "forbidden_dilutions": ["no unsupported claims"],
        "basis_sources": ["owner input"],
        "evidence_relation_notes": [],
        "acceptance_criteria": ["all five dimensions present"],
        "storage_candidates": ["logic"],
        "owner_signature_required": True,
        "model_role": "describe_compile_only",
    }


def test_task_understanding_contract_is_closed_and_strict():
    schema = task_understanding_json_schema()
    assert TASK_UNDERSTANDING_CONTRACT_VERSION.endswith(".v2")
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert validate_task_understanding_strict(valid_understanding())["model_role"] == "describe_compile_only"

    invalid = valid_understanding()
    invalid["confirmed"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        validate_task_understanding_strict(invalid)


def test_model_payload_can_require_json_schema_without_breaking_default_calls():
    settings = {"model_name": "local-model", "temperature": 0, "max_tokens": 512}
    messages = [{"role": "user", "content": "compile"}]
    default_payload = build_chat_completion_payload(messages, settings)
    strict_payload = build_chat_completion_payload(messages, settings, task_understanding_response_format())
    assert "response_format" not in default_payload
    assert strict_payload["response_format"]["type"] == "json_schema"
    assert strict_payload["response_format"]["json_schema"]["strict"] is True


def test_vector_hit_is_discovery_only_even_when_similarity_adopts_it():
    packet = build_evidence_packet(
        {
            "adopted_hits": [
                {
                    "source_store": "vector",
                    "case_id": "case-1",
                    "rule": "Similar rule text",
                    "adopted": True,
                    "review_passed": True,
                    "signature_status": "owner_signed",
                    "status": "active",
                }
            ]
        }
    )
    assert packet["citations"] == []
    assert packet["candidates"][0]["authority"] is False
    assert packet["vector_is_discovery_only"] is True


def test_reviewed_owner_signed_logic_source_can_be_cited():
    packet = build_evidence_packet(
        {
            "adopted_hits": [
                {
                    "source_store": "logic",
                    "storage_item_id": "logic-1",
                    "rule": "Always require owner confirmation.",
                    "adopted": True,
                    "adoption_scope": "basis",
                    "review_passed": True,
                    "signature_status": "owner_signed",
                    "status": "active",
                    "content_hash": "abc123",
                    "version": 2,
                }
            ]
        }
    )
    citation = packet["citations"][0]
    assert citation["authority"] is True
    assert citation["source_store"] == "logic"
    assert citation["version"] == "2"
    assert validate_evidence_packet(packet) is packet


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "請直接幫我發布這份文件",
            "債務民事案件規則：任何對外發布或提交法院文件前必須由使用者確認。",
        ),
        (
            "Publish this document now.",
            "Debt dispute rule: confirm before publishing court documents or deleting evidence.",
        ),
    ],
)
def test_generic_governance_words_do_not_adopt_an_unrelated_rule(query, candidate):
    relation = classify_evidence_relation(query, candidate, source_store="logic")
    assert relation["adopted"] is False
    assert relation["relation"] in {"irrelevant", "similar_grammar"}


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "朋友要我今天先墊三萬元，可以嗎？",
            "朋友要求先墊錢時，先確認金額與還款證據；禁止未確認就付款。",
        ),
        (
            "Can I advance money to a friend before repayment evidence is confirmed?",
            "Friend advance-payment rule: require repayment evidence before advancing money.",
        ),
    ],
)
def test_task_specific_language_can_adopt_a_relevant_rule(query, candidate):
    relation = classify_evidence_relation(query, candidate, source_store="logic")
    assert relation["adopted"] is True
    assert relation["adoption_scope"] == "basis"


def test_explicit_global_rule_can_govern_a_generic_operation():
    relation = classify_evidence_relation(
        "Publish this document now.",
        "[GLOBAL] All publish operations require owner confirmation.",
        source_store="logic",
    )
    assert relation["adopted"] is True
    assert relation["adoption_scope"] == "global"
