"""Authoritative SCBKR product identity and localized product replies."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_MANIFEST_PATH = REPO_ROOT / "config" / "product_manifest.json"
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
    required = ("schema_version", "product_id", "version", "name", "creator", "identity", "capabilities", "hard_limits", "stores")
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
    for key in ("name", "identity"):
        localized = manifest.get(key) or {}
        if not all(localized.get(locale) for locale in SUPPORTED_LOCALES):
            raise ValueError(f"{key} must provide zh-TW and en")
    return manifest


@lru_cache(maxsize=1)
def load_product_manifest() -> dict[str, Any]:
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
        "author": ("作者", "誰做的", "誰開發", "創辦人", "who made", "who created", "author", "founder"),
        "collaboration": ("合作", "聯絡", "聯繫", "授權", "商務", "contact", "collaborate", "license"),
        "rule_import": ("規則導入", "匯入規則", "規則包", "訂閱規則", "import rule", "rulepack", "rule pack", "subscribe"),
        "capabilities": ("能做什麼", "可以做什麼", "有什麼功能", "what can you do", "capabilities"),
        "identity": ("你是誰", "你是什麼", "你是什么", "什麼是scbkr", "什麼是 scbkr", "介紹你自己", "who are you", "what is scbkr", "introduce yourself"),
    }
    for topic, tokens in topic_tokens.items():
        if any(token in lowered or token in raw for token in tokens):
            return topic
    return None


def build_product_reply(topic: str, locale: str | None = None) -> str:
    lang = normalize_locale(locale)
    manifest = load_product_manifest()
    creator = manifest["creator"]
    if topic == "author":
        if lang == "en":
            return f"SCBKR was created by {creator['name']['en']}, founder of {creator['organization']['en']} in {creator['location']}. Contact: {creator['contact_email']}."
        return f"SCBKR 由{creator['name']['zh-TW']}建立；他是{creator['organization']['zh-TW']}創辦人、產品作者與規則作者，所在地為台灣台中。聯絡信箱：{creator['contact_email']}。"
    if topic == "collaboration":
        if lang == "en":
            return f"SCBKR is open to rule-pack licensing, custom rule design, local AI integration, and enterprise proofs of concept. Contact {manifest['collaboration']['email']}."
        return f"SCBKR 開放規則包授權、客製規則設計、本地 AI 整合與企業 PoC 合作。請聯絡 {manifest['collaboration']['email']}。"
    if topic == "rule_import":
        if lang == "en":
            return "Rule imports enter as drafts: import, parse, attribute the author and version, define scope, preview, obtain owner signature, activate, audit, and retain rollback. Imported text never becomes an active rule automatically."
        return "規則導入只會先形成草案：匯入、解析、標示作者與版本、設定範圍、預覽、使用者簽名、啟用、審計並保留回滾。匯入文字不會自動變成有效規則。"
    if topic == "capabilities":
        lines = [item["title"][lang] + "：" + item["description"][lang] for item in manifest["capabilities"]]
        return ("SCBKR capabilities:\n" if lang == "en" else "SCBKR 能做的事：\n") + "\n".join(f"- {line}" for line in lines)
    return manifest["identity"][lang] + " " + manifest["tagline"][lang]
