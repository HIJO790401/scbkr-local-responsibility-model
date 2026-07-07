from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[2]
V2_APP = (ROOT / "apps/web/src/V2App.tsx").read_text(encoding="utf-8")
MAIN = (ROOT / "apps/web/src/main.tsx").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "config/product_manifest.json").read_text(encoding="utf-8"))


def test_v2_app_is_formal_chat_first_entry():
    assert 'import V2App from "./V2App"' in MAIN
    assert "<V2App />" in MAIN
    assert "一般聊天" in V2_APP
    assert "像一般模型一樣輸入" in V2_APP


def test_rule_intent_stays_in_chat_until_user_chooses_draft():
    assert 'kind: "advisory"' in V2_APP
    assert "zerothGateCard(routed, text)" in V2_APP
    assert "draftFromAdvisoryGate" in V2_APP
    assert "草擬確認單" in V2_APP
    assert "保持一般聊天" in V2_APP
    assert "補角色與邊界" in V2_APP


def test_docs_and_manifest_describe_chat_first_product():
    assert "一般 AI 聊天產品 + 使用者規則責任鏈能力" in README
    assert "NT$690 是責任鏈結構輔助層，不是確認單生成門檻" in README
    assert "NT$3,300 是規則書閉環層" in README
    assert MANIFEST["version"] == "2.3.0"
    assert MANIFEST["release_stage"] == "2.3-chat-first-ui-alignment"
    assert "一般 AI 聊天產品" in MANIFEST["category"]["zh-TW"]
