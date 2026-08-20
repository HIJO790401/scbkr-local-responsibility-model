from fastapi.testclient import TestClient

from apps.api.main import app
from core.product_manifest import build_product_reply, detect_product_topic, load_product_manifest, localized_product_manifest


def test_product_manifest_is_bilingual_and_has_formal_four_stores():
    manifest = load_product_manifest()
    assert manifest["product_id"] == "scbkr"
    assert manifest["stores"] == ["vector", "corpus", "logic", "memory"]
    assert manifest["identity"]["zh-TW"]
    assert manifest["identity"]["en"]
    assert "語意防火牆創辦人" in manifest["welcome"]["zh-TW"]
    assert "Traditional Chinese and English" in manifest["welcome"]["en"]
    assert manifest["supported_languages"]["interface"] == ["zh-TW", "en"]
    assert manifest["creator"]["name"]["zh-TW"] == "許文耀／沈耀888π"
    assert list(manifest["scbkr_definition"]["dimensions"]) == ["S", "C", "B", "K", "R"]
    assert "停止" in manifest["scbkr_definition"]["dimensions"]["B"]["description"]["zh-TW"]
    assert "formal authority" in manifest["scbkr_definition"]["dimensions"]["K"]["description"]["en"]
    assert manifest["distribution_policy"]["edition_type"] == "experience"
    assert manifest["distribution_policy"]["author_official_rulepacks_included"] is False
    assert manifest["distribution_policy"]["external_generalizations_override_active_rule_state"] is False
    assert "不是普遍定律" in manifest["benchmark_disclaimer"]["zh-TW"]


def test_localized_manifest_resolves_display_text_without_changing_internal_keys():
    manifest = localized_product_manifest("en-US")
    assert manifest["locale"] == "en"
    assert manifest["name"] == "SCBKR Responsibility Chain Language Model"
    assert "I can chat normally" in manifest["welcome"]
    assert manifest["stores"] == ["vector", "corpus", "logic", "memory"]


def test_product_topics_are_deterministic_and_not_delegated_to_model():
    assert detect_product_topic("作者是誰？") == "author"
    assert detect_product_topic("How can we collaborate?") == "collaboration"
    assert detect_product_topic("怎麼匯入規則包？") == "rule_import"
    assert detect_product_topic("SCBKR 是什麼？") == "scbkr"
    assert detect_product_topic("How do I start using this?") == "usage"
    assert detect_product_topic("What is SCBKR, who created it, and what do the five dimensions mean?") == "identity"
    assert "許文耀／沈耀888π" in build_product_reply("author", "zh-TW")
    assert "S／C／B／K／R" in build_product_reply("identity", "zh-TW")
    assert "B 邊界、禁止與停止" in build_product_reply("scbkr", "zh-TW")
    assert "minimal rule package" in build_product_reply("usage", "en")
    assert "不包含沈耀正式規則包" in build_product_reply("collaboration", "zh-TW")
    assert "future product or commercial collaboration" in build_product_reply("rule_import", "en")


def test_product_manifest_api_and_chat_identity_reply():
    client = TestClient(app)
    manifest_response = client.get("/api/product/manifest?locale=en")
    assert manifest_response.status_code == 200
    assert manifest_response.json()["locale"] == "en"
    chat_response = client.post("/api/chat/general", json={"message": "Who created SCBKR?"})
    assert chat_response.status_code == 200
    data = chat_response.json()
    assert data["reply_source"] == "product_manifest:author"
    assert "Wen-Yao Hsu" in data["reply"]


def test_combined_identity_question_is_fast_local_authority_without_false_rule_claim(monkeypatch):
    import apps.api.main as main

    def fail_retrieval(*_args, **_kwargs):
        raise AssertionError("product identity must not scan the four stores")

    monkeypatch.setattr(main, "_build_four_store_context", fail_retrieval)
    data = main.general_chat(
        {
            "message": "What is SCBKR, who created it, and what do S, C, B, K, and R mean?",
            "locale": "en",
        }
    )

    assert data["reply_source"] == "product_manifest:identity"
    assert "Wen-Yao Hsu" in data["reply"]
    assert "S/C/B/K/R" in data["reply"]
    assert data["rule_applied"] is False
    assert "Produced under the signed user rule" not in data["reply"]
    assert "Four-store state" not in data["reply"]
