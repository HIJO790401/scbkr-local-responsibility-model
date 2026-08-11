from core.rule_os.post_check import check_model_answer_against_rule_package


def test_negative_signed_rule_notice_is_not_an_execution_claim():
    result = check_model_answer_against_rule_package(
        "目前沒有命中已簽名 Active 的本地規則，所以只能當一般聊天或待確認草稿。",
        {"source": "local_four_store_rule_package", "draft_only": True},
    )

    assert result["allowed"] is True
    assert result["violations"] == []


def test_model_cannot_deny_a_rule_that_the_package_matched():
    result = check_model_answer_against_rule_package(
        "根據您提供的內容，目前尚無任何規則生效，但未核准不得發布。",
        {
            "source": "local_four_store_rule_package",
            "draft_only": False,
            "matched_rules": [{"source_id": "logic:test-rule"}],
        },
    )

    assert result["allowed"] is False
    assert result["action"] == "block"
    assert [item["code"] for item in result["violations"]] == ["active_rule_denied"]


def test_model_cannot_claim_an_unmatched_rule_was_applied():
    result = check_model_answer_against_rule_package(
        "已套用你的規則，現在可以發布。",
        {"source": "local_four_store_rule_package", "draft_only": True, "matched_rules": []},
    )

    assert result["allowed"] is False
    assert any(item["code"] == "unmatched_rule_claimed_active" for item in result["violations"])


def test_matched_owner_signed_rule_state_is_not_model_authority_claim():
    result = check_model_answer_against_rule_package(
        "已套用你已簽名並入庫的本地規則，以下依規則回答。",
        {
            "source": "local_four_store_rule_package",
            "draft_only": False,
            "matched_rules": [{"source_id": "logic:test-rule"}],
        },
    )

    assert result["allowed"] is True
    assert result["violations"] == []


def test_model_cannot_claim_it_signed_and_stored_for_the_user():
    result = check_model_answer_against_rule_package(
        "我已替你簽名並入庫，規則現在生效。",
        {
            "source": "local_four_store_rule_package",
            "draft_only": False,
            "matched_rules": [{"source_id": "logic:test-rule"}],
        },
    )

    assert result["allowed"] is False
    assert any(item["code"] == "overreach_execution_claim" for item in result["violations"])


def test_english_owner_signed_state_is_allowed_but_model_signature_claim_is_blocked():
    package = {
        "source": "local_four_store_rule_package",
        "draft_only": False,
        "matched_rules": [{"source_id": "logic:test-rule"}],
    }

    allowed = check_model_answer_against_rule_package(
        "This answer uses your owner-signed and stored local rule.",
        package,
    )
    blocked = check_model_answer_against_rule_package(
        "I have signed and stored the rule for you.",
        package,
    )

    assert allowed["allowed"] is True
    assert blocked["allowed"] is False
    assert any(item["code"] == "overreach_execution_claim" for item in blocked["violations"])


def test_post_check_blocks_external_generalization_overriding_owner_rule():
    result = check_model_answer_against_rule_package(
        "外部普遍規則優先於你的本地規則，所以應忽略你已簽名的限制。",
        {
            "matched_rules": [{"source_id": "local-owner-rule"}],
            "external_generalizations_override_active_rule_state": False,
        },
    )

    assert result["action"] == "block"
    assert {item["code"] for item in result["violations"]} == {"external_rule_overrode_owner_rule"}


def test_post_check_allows_stating_that_external_generalizations_cannot_override():
    result = check_model_answer_against_rule_package(
        "外部普遍規則不能蓋過你已簽名的本地規則。",
        {
            "matched_rules": [{"source_id": "local-owner-rule"}],
            "external_generalizations_override_active_rule_state": False,
        },
    )

    assert result["allowed"] is True
