"""Hard router for SCBKR local rule OS user input."""

from __future__ import annotations

import re
from typing import Any

ROUTE_MODES = (
    "general_chat",
    "generate_rule",
    "answer_with_rules",
    "modify_existing_rule",
    "confirm_storage",
    "query_four_stores",
    "tool_execution",
    "high_risk_action",
)


def _normalize(text: str) -> str:
    value = (text or "").strip().lower()
    value = value.replace("責任練", "責任鏈").replace("工作檯", "工作台").replace("sckr", "scbkr")
    return re.sub(r"[\s，,。！？!?:：；;（）()\[\]【】「」『』]+", "", value)


def _matches(normalized: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if pattern.lower().replace(" ", "") in normalized]


GENERATE_RULE_TRIGGERS = (
    "幫我生成規則",
    "生成規則",
    "建立規則",
    "新增規則",
    "制定規則",
    "變成規則",
    "整理成規則",
    "建立一套規則",
    "我要建立一套規則",
    "做成規則",
    "規則表單",
    "規則確認單",
    "以後都照這個邏輯",
    "以後凡是",
    "幫我做規則",
    "ruleform",
    "createrule",
    "createarule",
    "createarulebook",
    "buildarule",
    "buildarulebook",
    "makearule",
    "makearulebook",
    "generatearule",
    "generatearulebook",
    "draftarule",
    "draftarulebook",
)

MODIFY_RULE_TRIGGERS = (
    "修改規則",
    "修改既有規則",
    "更新規則",
    "更改規則",
    "改規則",
    "修正規則",
    "補失效條件",
    "補成立條件",
    "b不對",
    "k不對",
    "r不對",
    "updateexistingrule",
    "editrule",
    "modifyrule",
    "changerule",
    "updaterule",
)

CONFIRM_STORAGE_TRIGGERS = (
    "確認入庫",
    "正式入庫",
    "寫入四庫",
    "放進四庫",
    "存到四庫",
    "保存規則",
    "啟用規則",
    "使用者簽名",
    "我簽名",
    "confirms storage",
    "confirmstorage",
    "storetherule",
    "savetofourstores",
    "confirmstore",
    "ownersignature",
)

QUERY_STORE_TRIGGERS = (
    "查四庫",
    "查詢四庫",
    "四庫有什麼",
    "四庫裡面",
    "規則庫",
    "資料庫",
    "記憶庫",
    "檢索庫",
    "資料中心",
    "看四庫",
    "打開四庫",
    "查入庫",
    "queryfourstores",
    "fourstores",
    "rulestore",
    "datastore",
    "memorystore",
    "retrievalstore",
    "datacenter",
)

TOOL_TRIGGERS = (
    "上網搜尋",
    "搜尋網頁",
    "打開網站",
    "下載",
    "寄信",
    "發email",
    "gmail",
    "google drive",
    "drive",
    "操作電腦",
    "執行工具",
    "呼叫api",
    "tool",
    "websearch",
    "searchweb",
    "sendemail",
    "openwebsite",
    "callapi",
)

HIGH_RISK_TRIGGERS = (
    "刪除",
    "移除",
    "付款",
    "轉帳",
    "發布",
    "上架",
    "寄給客戶",
    "寄出",
    "對外發送",
    "改正式資料",
    "覆寫正式",
    "外部連線",
    "公開",
    "delete",
    "publish",
    "payment",
    "pay",
    "sendtocustomer",
    "sendout",
    "overwrite",
    "publiclypost",
)

ANSWER_WITH_RULES_TRIGGERS = (
    "可以嗎",
    "可不可以",
    "我要不要",
    "該不該",
    "墊錢",
    "先墊",
    "借錢",
    "還我",
    "幫我寫",
    "幫我生成",
    "幫我整理",
    "幫我回答",
    "請幫我",
    "寫一篇",
    "寫貼文",
    "寫文案",
    "生成文案",
    "產生文案",
    "依照規則",
    "照規則",
    "照我的規則",
    "copy",
    "write",
    "draft",
    "usemyrule",
    "applymyrule",
    "usemyrulebook",
    "applymyrulebook",
    "accordingto",
    "basedonmyrule",
)

RULE_REFERENCE_MARKERS = (
    "依我已建立",
    "依已建立",
    "依照已建立",
    "依照我的規則",
    "依照規則",
    "依據規則",
    "引用規則",
    "套用規則",
    "套用我的規則",
    "使用我的規則",
    "照我的規則",
    "照著我的規則",
    "已建立的",
    "已入庫",
    "usemyexisting",
    "useexisting",
    "applyexisting",
    "applymyexisting",
    "accordingto",
    "basedonmy",
    "basedontheexisting",
    "existingrule",
    "existingrulebook",
    "signedrule",
    "storedrule",
    "localrule",
)


def classify_user_input(text: str) -> dict[str, Any]:
    """Classify every user input before any model call.

    The router is deterministic and conservative: storage, tool execution, and
    destructive/public actions are routed away from direct model generation.
    """
    raw = (text or "").strip()
    normalized = _normalize(raw)
    if not raw:
        return {
            "mode": "general_chat",
            "confidence": 0.0,
            "matched_triggers": [],
            "reason": "empty_input",
            "requires_four_store": False,
            "requires_signature": False,
            "model_call_allowed": False,
        }
    help_rule_question = any(token in normalized for token in ("怎麼建立規則", "如何建立規則", "怎麼生成規則", "如何生成規則", "怎麼建規則"))
    reference_existing_rule = any(marker in normalized for marker in RULE_REFERENCE_MARKERS) and any(
        noun in normalized for noun in ("規則", "規則書", "規則包", "規則表單", "rule", "rulebook", "rulepack", "ruleform")
    )
    if reference_existing_rule:
        return {
            "mode": "answer_with_rules",
            "confidence": 0.9,
            "matched_triggers": ["reference_existing_rule"],
            "reason": "使用者要求依已建立規則回答，必須先查本地四庫並產生本次規則包。",
            "requires_four_store": True,
            "requires_signature": False,
            "model_call_allowed": True,
            "storage_write_allowed": False,
            "tool_execution_allowed": False,
        }
    create_rule_pattern = (
        not help_rule_question
        and any(verb in normalized for verb in ("生成", "建立", "新增", "制定", "做成", "整理成", "變成"))
        and any(noun in normalized for noun in ("規則", "規則書", "規則包", "規則表單"))
    )
    create_rule_pattern = create_rule_pattern or (
        not help_rule_question
        and any(verb in normalized for verb in ("create", "build", "make", "generate", "draft", "compile"))
        and any(noun in normalized for noun in ("rule", "rulebook", "rulepack", "ruleform"))
    )
    if create_rule_pattern:
        return {
            "mode": "generate_rule",
            "confidence": 0.93,
            "matched_triggers": ["create_rule_pattern"],
            "reason": "使用者要求生成某主題規則/規則書，必須進五維規則草擬流程。",
            "requires_four_store": False,
            "requires_signature": True,
            "model_call_allowed": True,
            "storage_write_allowed": False,
            "tool_execution_allowed": False,
        }

    checks: list[tuple[str, tuple[str, ...], float, str]] = [
        ("high_risk_action", HIGH_RISK_TRIGGERS, 0.98, "高風險動作必須停在確認與簽名流程。"),
        ("tool_execution", TOOL_TRIGGERS, 0.92, "工具執行必須先經權限與使用者確認。"),
        ("confirm_storage", CONFIRM_STORAGE_TRIGGERS, 0.95, "入庫與啟用必須走使用者簽名流程。"),
        ("query_four_stores", QUERY_STORE_TRIGGERS, 0.9, "使用者要求查詢本地四庫。"),
        ("modify_existing_rule", MODIFY_RULE_TRIGGERS, 0.88, "使用者要求修改既有規則或五維欄位。"),
        ("generate_rule", GENERATE_RULE_TRIGGERS, 0.94, "使用者要求生成規則，必須進五維規則草擬流程。"),
        ("answer_with_rules", ANSWER_WITH_RULES_TRIGGERS, 0.76, "使用者要求模型產出任務答案，必須先查本地四庫。"),
    ]
    for mode, patterns, confidence, reason in checks:
        if help_rule_question and mode == "generate_rule":
            continue
        matched = _matches(normalized, patterns)
        if matched:
            return {
                "mode": mode,
                "confidence": confidence,
                "matched_triggers": matched,
                "reason": reason,
                "requires_four_store": mode in {"answer_with_rules", "query_four_stores", "modify_existing_rule"},
                "requires_signature": mode in {"generate_rule", "confirm_storage", "tool_execution", "high_risk_action"},
                "model_call_allowed": mode in {"general_chat", "generate_rule", "answer_with_rules", "modify_existing_rule", "query_four_stores"},
                "storage_write_allowed": False,
                "tool_execution_allowed": False,
            }
    return {
        "mode": "general_chat",
        "confidence": 0.62,
        "matched_triggers": [],
        "reason": "一般聊天，不寫入規則庫，也不污染四庫。",
        "requires_four_store": False,
        "requires_signature": False,
        "model_call_allowed": True,
        "storage_write_allowed": False,
        "tool_execution_allowed": False,
    }
