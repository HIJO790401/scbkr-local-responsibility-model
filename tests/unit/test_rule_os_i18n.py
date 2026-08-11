from core.rule_os.i18n import normalize_locale_text, rule_os_text


def test_zh_tw_model_text_is_normalized_with_opencc():
    converted = normalize_locale_text("发布商业文案，不得夸大疗效或编造价格信息。", "zh-TW")

    assert "發佈" in converted or "釋出" in converted
    assert "商業" in converted
    assert "誇大療效" in converted
    assert "價格資訊" in converted
    assert "发布" not in converted


def test_english_text_is_not_rewritten():
    value = "Create a reusable rule and let the user sign it."
    assert normalize_locale_text(value, "en") == value
    assert rule_os_text("en")["modes"]["generate_rule"] == "Generate rule"


def test_storage_state_conflict_has_human_zh_tw_and_english_copy():
    zh = rule_os_text("zh-TW")
    en = rule_os_text("en")

    assert zh["statuses"]["storage_conflict"] == "來源規則已更新，入庫已停止"
    assert "未寫入四庫" in zh["state_conflict_prompt"]
    assert en["statuses"]["storage_conflict"] == "Source rule changed; storage stopped"
    assert "Nothing was written" in en["state_conflict_prompt"]
