"""Authoritative SCBKR product identity and localized product replies."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from core.resource_paths import product_resource_path


PRODUCT_MANIFEST_PATH = product_resource_path("config", "product_manifest.json")
SUPPORTED_LOCALES = ("zh-TW", "en")


def normalize_locale(locale: str | None) -> str:
    value = (locale or "").lower()
    return "en" if value.startswith("en") else "zh-TW"


def _localized(value: Any, locale: str) -> Any:
    if isinstance(value, dict) and set(value).issubset(set(SUPPORTED_LOCALES)) and value:
        return value.get(locale) or value.get("zh-TW") or next(iter(value.values()))
    if isinstance(value, dict):
        return {key: _localized(item, locale) for key, item in value.items()}
    if isinstance(value, list):
        return [_localized(item, locale) for item in value]
    return value


def validate_product_manifest(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("product manifest must be an object")
    required = ("schema_version", "product_id", "version", "name", "creator", "identity", "scbkr_definition", "welcome", "capabilities", "hard_limits", "stores")
    missing = [key for key in required if not manifest.get(key)]
    if missing:
        raise ValueError(f"product manifest missing required fields: {', '.join(missing)}")
    if manifest.get("product_id") != "scbkr":
        raise ValueError("product_id must be scbkr")
    if manifest.get("stores") != ["vector", "corpus", "logic", "memory"]:
        raise ValueError("product manifest stores must be vector/corpus/logic/memory")
    creator = manifest.get("creator") or {}
    if not creator.get("author_id") or not creator.get("contact_email"):
        raise ValueError("creator author_id and contact_email are required")
    for key in ("name", "identity", "welcome"):
        localized = manifest.get(key) or {}
        if not all(localized.get(locale) for locale in SUPPORTED_LOCALES):
            raise ValueError(f"{key} must provide zh-TW and en")
    definition = manifest.get("scbkr_definition") or {}
    if not all((definition.get("summary") or {}).get(locale) for locale in SUPPORTED_LOCALES):
        raise ValueError("scbkr_definition.summary must provide zh-TW and en")
    dimensions = definition.get("dimensions") or {}
    if tuple(dimensions) != ("S", "C", "B", "K", "R"):
        raise ValueError("scbkr_definition dimensions must be ordered S/C/B/K/R")
    for code, item in dimensions.items():
        if not all((item.get(field) or {}).get(locale) for field in ("name", "description", "question") for locale in SUPPORTED_LOCALES):
            raise ValueError(f"scbkr_definition.{code} must provide localized name, description, and question")
    return manifest


@lru_cache(maxsize=1)
def load_product_manifest() -> dict[str, Any]:
    if not PRODUCT_MANIFEST_PATH.is_file():
        raise FileNotFoundError(
            f"SCBKR product manifest is missing from this installation: {PRODUCT_MANIFEST_PATH}"
        )
    with PRODUCT_MANIFEST_PATH.open(encoding="utf-8") as handle:
        return validate_product_manifest(json.load(handle))


def localized_product_manifest(locale: str | None = None) -> dict[str, Any]:
    lang = normalize_locale(locale)
    manifest = deepcopy(load_product_manifest())
    return {**_localized(manifest, lang), "locale": lang}


def detect_product_topic(text: str) -> str | None:
    raw = (text or "").strip()
    lowered = raw.lower()
    topic_tokens = {
        # A combined question such as "what is SCBKR and who created it" needs
        # the full identity answer, which already includes the creator and all
        # five dimensions. Narrow author-only questions still route to author.
        "identity": ("你是誰", "你是什麼", "你是什么", "什麼是scbkr", "什麼是 scbkr", "介紹你自己", "who are you", "what is scbkr", "introduce yourself"),
        "scbkr": ("scbkr是什麼", "scbkr 是什麼", "五維是什麼", "主體因果邊界", "what does scbkr mean", "five dimensions"),
        "author": ("作者", "誰做的", "誰開發", "創辦人", "who made", "who created", "author", "founder"),
        "collaboration": ("合作", "聯絡", "聯繫", "授權", "商務", "contact", "collaborate", "license"),
        "rule_import": ("規則導入", "匯入規則", "規則包", "訂閱規則", "import rule", "rulepack", "rule pack", "subscribe"),
        "capabilities": ("能做什麼", "可以做什麼", "有什麼功能", "what can you do", "capabilities"),
        "usage": ("怎麼使用", "如何使用", "怎麼開始", "使用方法", "操作教學", "how to use", "get started", "how do i start"),
    }
    for topic, tokens in topic_tokens.items():
        if any(token in lowered or token in raw for token in tokens):
            return topic
    return None


def detect_explanation_depth(text: str) -> str:
    raw = (text or "").strip().lower()
    deep_tokens = ("深入", "詳細", "技術層", "架構層", "原理", "完整說明", "deep", "technical", "architecture", "in detail")
    simple_tokens = ("白話", "簡單", "一句話", "給長輩", "不懂技術", "plain language", "simple", "brief", "one sentence")
    if any(token in raw for token in deep_tokens):
        return "deep"
    if any(token in raw for token in simple_tokens):
        return "simple"
    return "standard"


def build_product_reply(topic: str, locale: str | None = None, *, depth: str = "standard") -> str:
    lang = normalize_locale(locale)
    manifest = load_product_manifest()
    creator = manifest["creator"]
    definition = manifest["scbkr_definition"]
    dimension_lines = [
        f"{code} {item['name'][lang]}：{item['description'][lang]}"
        for code, item in definition["dimensions"].items()
    ]
    if depth == "simple" and topic in {"identity", "capabilities", "scbkr", "usage"}:
        if lang == "en":
            return (
                f"SCBKR is a local responsibility-chain AI system created by {creator['name']['en']}. "
                "You can chat normally, or ask the model to turn your judgement into an editable rule sheet: "
                "S says who and when it applies, C says why and in what order, B says what is forbidden or when to stop, "
                "K says what evidence may be cited, and R says who reviews, accepts, and signs. "
                "Only your signed rule becomes the main basis for later answers."
            )
        return (
            f"SCBKR 是{creator['name']['zh-TW']}建立的本地責任鏈 AI 系統。你可以正常聊天，也能叫模型把你的判斷整理成確認單："
            "S 管誰與何時適用，C 管原因與順序，B 管禁止與停止，K 管證據與引用，R 管誰驗收、承擔與簽名。"
            "只有你確認簽名的規則，才會成為之後回答的主要依據。"
        )
    if topic == "author":
        if lang == "en":
            return f"SCBKR was created by {creator['name']['en']}, founder of {creator['organization']['en']} in {creator['location']}. Contact: {creator['contact_email']}."
        return f"SCBKR 由{creator['name']['zh-TW']}建立；他是{creator['organization']['zh-TW']}創辦人、產品作者與規則作者，所在地為台灣台中。聯絡信箱：{creator['contact_email']}。"
    if topic == "collaboration":
        if lang == "en":
            return f"The public FREE edition does not include ShenYao official rule packs. For future official rule-pack products, custom rule design, local AI integration, or commercial workflows, contact {manifest['collaboration']['email']}."
        return f"公開 FREE 體驗版不包含沈耀正式規則包。如需後續正式規則包產品、客製規則設計、本地 AI 整合或商業流程，請聯絡 {manifest['collaboration']['email']}。"
    if topic == "rule_import":
        if lang == "en":
            return "FREE lets users import and own their own rule drafts. Imports are parsed, attributed, scoped, previewed, owner-signed, activated, audited, and rollback-capable; imported text never becomes active automatically. ShenYao official rule packs are not bundled and require a future product or commercial collaboration."
        return "FREE 讓使用者匯入並承擔自己的規則草案。流程包含解析、標示作者與版本、設定範圍、預覽、使用者簽名、啟用、審計與回滾；匯入文字不會自動生效。沈耀正式規則包不隨公開版提供，需等待後續產品或洽商業合作。"
    if topic == "capabilities":
        lines = [item["title"][lang] + "：" + item["description"][lang] for item in manifest["capabilities"]]
        heading = "SCBKR capabilities and its five-dimension contract:\n" if lang == "en" else "SCBKR 能做的事與五維責任鏈：\n"
        return heading + "\n".join(f"- {line}" for line in [*dimension_lines, *lines])
    if topic == "scbkr":
        return definition["summary"][lang] + "\n\n" + "\n".join(f"- {line}" for line in dimension_lines)
    if topic == "usage":
        if lang == "en":
            return (
                "How to use SCBKR:\n"
                "1. Connect and test an LM Studio, Ollama, or OpenAI-compatible model.\n"
                "2. Chat normally, or ask SCBKR to create a reusable rule.\n"
                "3. Review the model-authored S/C/B/K/R confirmation sheet and edit any field.\n"
                "4. Sign it yourself, review the generated result, then second-confirm four-store storage.\n"
                "5. Ask a later question. SCBKR first builds a minimal rule package from active signed records, then lets the model answer and shows the token/context audit.\n\n"
                "The model may explain and draft, but it cannot sign or activate a rule."
            )
        return (
            "SCBKR 使用方式：\n"
            "1. 到模型設定連接並測試 LM Studio、Ollama 或 OpenAI-compatible 模型。\n"
            "2. 可以先一般聊天；要建立可重用規則時，直接用人話提出需求。\n"
            "3. 在工作台逐欄閱讀模型草擬的 S／C／B／K／R，哪裡不對就修改。\n"
            "4. 由你親自簽名、驗收生成結果，再二次確認四庫入庫。\n"
            "5. 下次提問時，系統先從已簽名生效資料建立本次最小規則包，再讓模型回答並顯示 Token／Context 審計。\n\n"
            "模型能解釋與草擬，但不能替你簽名或啟用規則。"
        )
    if depth == "deep" and topic == "identity":
        heading = manifest["welcome"][lang]
        if lang == "en":
            return (
                heading
                + "\n\nArchitecture: every input first enters a deterministic router. Rule authoring uses model-authored S/C/B/K/R plus semantic and Kernel validation. "
                "A task-scoped capability gap keeps the output as an unsigned draft and may recommend one stronger-model compilation pass; response time never triggers escalation. "
                "After owner signature, review, and four-store compilation, later questions use a minimal rule package instead of replaying the whole conversation."
            )
        return (
            heading
            + "\n\n架構層：每次輸入先經硬路由；建規則時由模型實際填寫 S／C／B／K／R，再通過語意分工與 Kernel 驗證。"
            "若本次結構仍有缺口，系統只保留未簽名草稿，並可建議用較強模型做一次補鏈收束；不會因為模型回得慢就升級。"
            "使用者簽名、驗收並編譯四庫後，後續問題只載入本次最小規則包，不重塞整段聊天。"
        )
    return manifest["welcome"][lang]
