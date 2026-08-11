import pytest

from apps.api.main import route_chat_intent
from core.product_manifest import build_product_reply, detect_explanation_depth, detect_product_topic
from core.rule_os.classifier import classify_user_input


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("請建立一套 Python 部署規則：測試沒過就不能發布。", "generate_rule"),
        ("證據不足時不得下法律結論，把這個判斷寫成民事案件規則書。", "generate_rule"),
        ("我要一套檢查論證前提、推論與反例的邏輯規則。", "generate_rule"),
        ("Create a reusable code-review rulebook for pull requests.", "generate_rule"),
        ("幫我解釋 Python 的命名規則，先不要建立規則。", "general_chat"),
        ("這只是聊天：法律上證據能力是什麼？不要做成規則。", "general_chat"),
        ("Let's just discuss deployment rules; don't turn this into a rule.", "general_chat"),
        ("足球的越位規則是什麼？", "general_chat"),
        ("幫我比較這兩套邏輯規則的差異。", "general_chat"),
        ("請依照我已建立的程式發布規則檢查這次部署。", "answer_with_rules"),
        ("這份文件版本還沒核對，但對方催我現在公開，可以嗎？", "answer_with_rules"),
        ("Should I publish this document before the version is verified?", "answer_with_rules"),
        ("請幫我公開這份文件。", "high_risk_action"),
        ("請幫我直接發布這份文件。", "high_risk_action"),
        ("Please publish this document now.", "high_risk_action"),
        ("Please pay the invoice now.", "high_risk_action"),
        ("Help me review a civil debt case and repayment evidence.", "general_chat"),
        ("Explain repayment evidence in a debt dispute.", "general_chat"),
        ("修改既有規則的 B，加入測試失敗就停止。", "modify_existing_rule"),
        ("四庫裡有哪些已簽名規則？", "query_four_stores"),
        ("Show me the signed rules in the four stores.", "query_four_stores"),
        ("List the rules stored in the rule store.", "query_four_stores"),
        ("Use my signed rule in the four stores to answer this.", "answer_with_rules"),
    ],
)
def test_domain_general_router_handles_varied_language_and_negation(text, expected):
    result = classify_user_input(text)
    assert result["mode"] == expected


@pytest.mark.parametrize(
    "text",
    [
        "這個判斷下次也要照這樣，但先讓我決定要不要正式化。",
        "I want to reuse this decision next time, but do not create anything yet.",
    ],
)
def test_reusable_but_not_explicit_requests_only_suggest(text):
    routed = route_chat_intent(text)
    assert routed["intent"] in {"suggest_create_confirmation", "suggest_new_rule_confirmation", "normal_chat"}
    assert routed["requires_draft"] is False


@pytest.mark.parametrize(
    ("text", "classification", "intent"),
    [
        ("幫我依照已建立的規則寫一篇貼文。", "answer_with_rules", "normal_chat"),
        ("四庫裡有哪些已簽名規則？", "query_four_stores", "data_center_query"),
        ("Show me the signed rules in the four stores.", "query_four_stores", "data_center_query"),
        ("請幫我直接發布這份文件。", "high_risk_action", "normal_chat"),
        ("修改既有規則的 B，加入測試失敗就停止。", "modify_existing_rule", "normal_chat"),
        ("確認入庫這條規則。", "confirm_storage", "normal_chat"),
        ("Create a reusable code review rulebook.", "generate_rule", "create_new_rule_confirmation"),
    ],
)
def test_ui_intent_router_preserves_hard_route_semantics(text, classification, intent):
    routed = route_chat_intent(text)
    assert routed["rule_os_classification"]["mode"] == classification
    assert routed["intent"] == intent


def test_product_explanation_depth_is_language_aware():
    assert detect_product_topic("SCBKR 是什麼？請用白話說") == "scbkr"
    assert detect_explanation_depth("SCBKR 是什麼？請用白話說") == "simple"
    assert detect_explanation_depth("Explain the technical architecture in detail") == "deep"
    simple = build_product_reply("identity", "zh-TW", depth="simple")
    deep = build_product_reply("identity", "en", depth="deep")
    assert "S 管誰" in simple
    assert "deterministic router" in deep
    assert "response time never triggers escalation" in deep
