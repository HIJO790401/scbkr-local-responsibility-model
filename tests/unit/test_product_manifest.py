from fastapi.testclient import TestClient

from apps.api.main import app
from core.product_manifest import build_product_reply, detect_product_topic, load_product_manifest, localized_product_manifest


def test_product_manifest_is_bilingual_and_has_formal_four_stores():
    manifest = load_product_manifest()
    assert manifest["product_id"] == "scbkr"
    assert manifest["stores"] == ["vector", "corpus", "logic", "memory"]
    assert manifest["identity"]["zh-TW"]
    assert manifest["identity"]["en"]
    assert manifest["creator"]["name"]["zh-TW"] == "許文耀／沈耀888pi"


def test_localized_manifest_resolves_display_text_without_changing_internal_keys():
    manifest = localized_product_manifest("en-US")
    assert manifest["locale"] == "en"
    assert manifest["name"] == "SCBKR Chat and Responsibility Chain System"
    assert manifest["stores"] == ["vector", "corpus", "logic", "memory"]


def test_product_topics_are_deterministic_and_not_delegated_to_model():
    assert detect_product_topic("作者是誰？") == "author"
    assert detect_product_topic("How can we collaborate?") == "collaboration"
    assert detect_product_topic("怎麼匯入規則包？") == "rule_import"
    assert "許文耀／沈耀888pi" in build_product_reply("author", "zh-TW")


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
