"""Deterministic SCBKR 2.3 rule-assist gates.

The local model may help phrase text, but these gates define the product
contract for FREE / NT$690 / NT$3300 modes.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

PLAN_LEVELS = ("FREE", "NT690", "NT3300")

DEFAULT_RULE_ASSIST_SETTINGS: dict[str, Any] = {
    "plan_level": "FREE",
    "locale": "zh-TW",
    "rule_source": "local_user_defined",
    "author_signature_required": False,
    "cloud_subscription_enabled": False,
    "mock_model_enabled": True,
}

PLAN_CATALOG: dict[str, dict[str, Any]] = {
    "FREE": {
        "plan_level": "FREE",
        "price_label": "免費版",
        "name": {"zh-TW": "免費草稿層", "en": "Free Draft Layer"},
        "summary": {
            "zh-TW": "本機聊天、草案、四庫候選引用；使用者自行簽名，沒有沈耀規則完整性輔助。",
            "en": "Local chat, drafts, and four-store candidate reads. The user signs alone; no ShenYao completeness assist.",
        },
        "model_role": "chat_and_draft_only",
        "gates": ["DraftStateGate", "OwnerSignatureGate", "FourStoreCitationGate"],
        "can_fill_structure": False,
        "can_claim_close": False,
        "service_refusal_gate": False,
        "requires_owner_signature": True,
    },
    "NT690": {
        "plan_level": "NT690",
        "price_label": "NT$690",
        "name": {"zh-TW": "責任鏈結構輔助層", "en": "Responsibility Structure Assist"},
        "summary": {
            "zh-TW": "語意合法輸出硬閘：擋空回覆、假因果、無參數建議，協助補 S/C/B/K/R 基本結構。",
            "en": "Semantic legality gate: blocks empty replies, fake causality, and parameter-free advice while filling basic S/C/B/K/R.",
        },
        "model_role": "structured_draft_assistant",
        "gates": ["DraftStateGate", "ZerothPrincipleGate", "SemanticLegalityGate", "OwnerSignatureGate"],
        "can_fill_structure": True,
        "can_claim_close": False,
        "service_refusal_gate": False,
        "requires_owner_signature": True,
    },
    "NT3300": {
        "plan_level": "NT3300",
        "price_label": "NT$3300",
        "name": {"zh-TW": "規則書閉環審計層", "en": "Rulebook Closure Audit"},
        "summary": {
            "zh-TW": "有效性/失敗審計與服務拒絕閘；高風險工具、發布、入庫、付款、外部連線必須回使用者簽名。",
            "en": "Validity/failure audit plus service-refusal gate. High-risk tools, publishing, storage, payment, and external calls require user signature.",
        },
        "model_role": "closure_candidate_assistant",
        "gates": [
            "DraftStateGate",
            "ZerothPrincipleGate",
            "SemanticLegalityGate",
            "ValidityFailureAudit",
            "ServiceRefusalGate",
            "OwnerSignatureGate",
        ],
        "can_fill_structure": True,
        "can_claim_close": False,
        "service_refusal_gate": True,
        "requires_owner_signature": True,
    },
}

EMPTY_ACKNOWLEDGEMENTS = {
    "好",
    "好的",
    "可以",
    "ok",
    "okay",
    "yes",
    "y",
    "嗯",
    "恩",
    "了解",
    "收到",
}
RULE_TRIGGERS = (
    "規則",
    "記住",
    "以後",
    "之後",
    "必須",
    "不得",
    "不准",
    "禁止",
    "入庫",
    "簽名",
    "確認",
    "驗收",
    "rule",
    "remember",
    "always",
    "never",
    "must",
    "store",
    "sign",
)
HIGH_RISK_TERMS = (
    "刪除",
    "付款",
    "刷卡",
    "轉帳",
    "發佈",
    "發布",
    "公開",
    "寄信",
    "email",
    "mail",
    "delete",
    "payment",
    "purchase",
    "publish",
    "deploy",
    "external_api",
    "上網",
    "網路搜尋",
    "讀信箱",
    "信箱",
    "電腦",
    "檔案",
    "drive",
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_plan_level(value: str | None) -> str:
    raw = str(value or "").strip().upper().replace("$", "")
    aliases = {
        "690": "NT690",
        "NT690": "NT690",
        "NTD690": "NT690",
        "NT$690": "NT690",
        "3300": "NT3300",
        "NT3300": "NT3300",
        "NTD3300": "NT3300",
        "NT$3300": "NT3300",
        "FREE": "FREE",
        "免費": "FREE",
    }
    return aliases.get(raw, "FREE")


def plan_catalog(locale: str = "zh-TW") -> list[dict[str, Any]]:
    localized = []
    for plan in PLAN_LEVELS:
        item = deepcopy(PLAN_CATALOG[plan])
        item["display_name"] = item["name"].get(locale) or item["name"]["zh-TW"]
        item["display_summary"] = item["summary"].get(locale) or item["summary"]["zh-TW"]
        localized.append(item)
    return localized


def public_settings(settings: dict[str, Any] | None = None, locale: str = "zh-TW") -> dict[str, Any]:
    value = {**DEFAULT_RULE_ASSIST_SETTINGS, **(settings or {})}
    value["plan_level"] = normalize_plan_level(value.get("plan_level"))
    plan = deepcopy(PLAN_CATALOG[value["plan_level"]])
    plan["display_name"] = plan["name"].get(locale) or plan["name"]["zh-TW"]
    plan["display_summary"] = plan["summary"].get(locale) or plan["summary"]["zh-TW"]
    return {
        **value,
        "catalog": plan_catalog(locale),
        "active_plan": plan,
        "identity": {
            "product": "SCBKR 2.3 Responsibility Chain Language Model",
            "zh-TW": "我是 SCBKR 責任鏈語言模型 2.3；作者是沈耀／許文耀，語意防火牆創辦人。模型只協助輸出，規則與責任由使用者簽名確認。",
            "en": "I am SCBKR Responsibility Chain Language Model 2.3. The author is ShenYao / Wen-Yao Hsu, founder of Semantic Firewall. The model assists output; rules and responsibility require user signature.",
        },
        "updated_at": value.get("updated_at"),
    }


def validate_settings_update(current: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    next_settings = {**DEFAULT_RULE_ASSIST_SETTINGS, **current}
    if "plan_level" in payload:
        next_settings["plan_level"] = normalize_plan_level(str(payload.get("plan_level")))
    if "locale" in payload and str(payload.get("locale")) in {"zh-TW", "en", "ja", "ko", "auto"}:
        next_settings["locale"] = str(payload.get("locale"))
    if "mock_model_enabled" in payload:
        next_settings["mock_model_enabled"] = bool(payload.get("mock_model_enabled"))
    if "cloud_subscription_enabled" in payload:
        next_settings["cloud_subscription_enabled"] = bool(payload.get("cloud_subscription_enabled"))
    if "rule_source" in payload:
        next_settings["rule_source"] = str(payload.get("rule_source") or "local_user_defined")[:80]
    next_settings["author_signature_required"] = next_settings["plan_level"] in {"NT690", "NT3300"}
    next_settings["updated_at"] = _now()
    return next_settings


def _has_cjk(text: str) -> bool:
    return any("\u3400" <= ch <= "\u9fff" for ch in text)


def _word_count(text: str) -> int:
    if _has_cjk(text):
        return len([ch for ch in text if not ch.isspace()])
    return len([part for part in text.replace("\n", " ").split(" ") if part.strip()])


def _looks_like_question(text: str) -> bool:
    value = text.lower()
    return any(token in value for token in ("?", "？", "嗎", "怎么", "怎麼", "如何", "what", "how", "why", "can i"))


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in tokens)


def _zeroth_principle_gate(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    normalized = raw.lower().strip(" 。.!！?？")
    findings: list[str] = []
    if not raw:
        findings.append("EMPTY_INPUT")
    if normalized in EMPTY_ACKNOWLEDGEMENTS:
        findings.append("EMPTY_ACKNOWLEDGEMENT")
    if _word_count(raw) < 4 and not _looks_like_question(raw):
        findings.append("NO_DECISION_PARAMETER")
    status = "pass" if not findings else "needs_clarification"
    return {
        "gate_id": "L0-ZEROTH-PRINCIPLE-ADVISORY-GATE",
        "status": status,
        "score": 1.0 if status == "pass" else 0.32,
        "findings": findings,
        "advice": "資料不足，應追問主語、邊界、責任。" if findings else "可進入語意合法檢查。",
    }


def _semantic_legality_gate(text: str, target_mode: str = "chat") -> dict[str, Any]:
    raw = (text or "").strip()
    findings: list[str] = []
    lowered = raw.lower()
    if _word_count(raw) < 8 and not _looks_like_question(raw):
        findings.append("INSUFFICIENT_CONTENT")
    if any(token in lowered for token in ("為什麼可以", "為何可以", "是不是都可以", "can always")) and not _contains_any(raw, RULE_TRIGGERS):
        findings.append("FAKE_CAUSAL_QUESTION")
    if any(token in lowered for token in ("幫我", "做一個", "整理", "build", "make")) and not any(token in lowered for token in ("給誰", "目的", "格式", "限制", "target", "scope", "format")):
        findings.append("MISSING_PARAMETERS")
    if target_mode in {"rule", "store", "tool"} and not _contains_any(raw, RULE_TRIGGERS):
        findings.append("NO_RULE_OR_RESPONSIBILITY_LANGUAGE")
    status = "pass" if not findings else "needs_clarification"
    score = 0.82 if status == "pass" else max(0.38, 0.78 - len(findings) * 0.16)
    return {
        "gate_id": "P16-690-SEMANTIC-LEGALITY-GATE",
        "status": status,
        "score": round(score, 2),
        "findings": findings,
        "fills": {
            "S": "鎖定使用者原句中的任務主體；不足時回問誰要承擔。",
            "C": "抽出流程與因果，不讓模型用空泛理由代替。",
            "B": "列出不可自動做的事，尤其簽名、入庫、工具、公開。",
            "K": "引用四庫已簽名資料；沒有資料時標成草稿。",
            "R": "責任回使用者簽名，模型不可自行 CLOSE。",
        },
        "model_forbidden": ["auto_close", "auto_sign", "auto_store", "invent_citation", "claim_owner_decision"],
        "required_next_action": "ask_clarifying_question" if status != "pass" else "compile_draft_or_answer",
    }


def _validity_failure_audit(text: str, semantic_gate: dict[str, Any]) -> dict[str, Any]:
    raw = (text or "").strip()
    has_rule_language = _contains_any(raw, RULE_TRIGGERS)
    high_risk = _contains_any(raw, HIGH_RISK_TERMS)
    failure_cases = []
    if semantic_gate.get("status") != "pass":
        failure_cases.append("semantic_gate_not_closed")
    if high_risk:
        failure_cases.append("high_risk_action_requires_signature")
    if has_rule_language and "簽名" not in raw and "signature" not in raw.lower():
        failure_cases.append("rule_without_explicit_signature_path")
    status = "pass" if not failure_cases else "owner_review"
    return {
        "gate_id": "P17-3300-VALIDITY-FAILURE-AUDIT",
        "status": status,
        "score": 0.9 if status == "pass" else 0.62,
        "failure_cases": failure_cases,
        "validity": {
            "can_answer": semantic_gate.get("status") == "pass" or _looks_like_question(raw),
            "can_compile_draft": True,
            "can_close": False,
            "close_reason": "模型最多到 CLOSE_CANDIDATE；正式 CLOSE 必須使用者簽名、驗收、入庫。",
        },
        "repair_path": [
            "補主語與服務對象",
            "補不可越界條款",
            "補依據或四庫引用",
            "補使用者簽名與回放要求",
        ],
    }


def _service_refusal_gate(text: str, target_mode: str = "chat") -> dict[str, Any]:
    high_risk = _contains_any(text, HIGH_RISK_TERMS) or target_mode in {"tool", "store", "publish", "external"}
    status = "owner_signature_required" if high_risk else "pass"
    return {
        "gate_id": "P18-3300-SERVICE-REFUSAL-GATE",
        "status": status,
        "risk_level": "high" if high_risk else "normal",
        "blocked_until": "owner_signature" if high_risk else None,
        "allowed_without_signature": ["explain", "draft", "simulate", "ask_clarifying_question"],
        "blocked_without_signature": ["tool_execution", "external_send", "publish", "delete", "physical_store"] if high_risk else [],
    }


def _four_store_state(four_store_context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = four_store_context or {}
    authority_count = int(context.get("authority_count") or 0)
    adopted_hits = [hit for hit in context.get("hits", []) or [] if hit.get("adopted")]
    return {
        "authority_count": authority_count,
        "adopted_count": len(adopted_hits),
        "citation_policy": "four_store_first_when_signed",
        "context_role": "reference_only_until_signed_store",
        "answer_priority": "signed_four_store" if authority_count or adopted_hits else "basic_chat_or_draft_only",
    }


def evaluate_rule_assist(
    text: str,
    plan_level: str = "FREE",
    locale: str = "zh-TW",
    target_mode: str = "chat",
    four_store_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = normalize_plan_level(plan_level)
    text_hash = sha256((text or "").encode("utf-8")).hexdigest()[:16]
    zeroth = _zeroth_principle_gate(text)
    semantic = _semantic_legality_gate(text, target_mode)
    result: dict[str, Any] = {
        "evaluation_id": f"assist-{text_hash}",
        "evaluated_at": _now(),
        "plan_level": plan,
        "plan": deepcopy(PLAN_CATALOG[plan]),
        "target_mode": target_mode,
        "text_hash": text_hash,
        "four_store": _four_store_state(four_store_context),
        "gates": [],
        "state": "DRAFT",
        "model_claim_limit": "model_may_draft_never_sign_or_close",
        "owner_signature_required": True,
        "next_required_action": "owner_review",
    }
    result["plan"]["display_name"] = result["plan"]["name"].get(locale) or result["plan"]["name"]["zh-TW"]
    result["plan"]["display_summary"] = result["plan"]["summary"].get(locale) or result["plan"]["summary"]["zh-TW"]

    if plan == "FREE":
        result["gates"] = [{
            "gate_id": "FREE-DRAFT-STATE-GATE",
            "status": "draft_only",
            "score": 0.5,
            "findings": ["no_paid_structure_assist"],
            "advice": "可聊天、可產生草案；正式引用與入庫仍需使用者自行確認。",
        }]
        result["capability_state"] = "basic_chat_and_user_signed_draft"
        result["next_required_action"] = "user_manual_review"
        return result

    result["gates"].extend([zeroth, semantic])
    if semantic["status"] != "pass" or zeroth["status"] != "pass":
        result["state"] = "OWNER_REVIEW"
        result["next_required_action"] = "clarify_subject_boundary_responsibility"
    else:
        result["state"] = "DRAFT_STRUCTURED"
        result["next_required_action"] = "compile_structured_draft"
    result["capability_state"] = "semantic_structure_assist"

    if plan == "NT3300":
        validity = _validity_failure_audit(text, semantic)
        refusal = _service_refusal_gate(text, target_mode)
        result["gates"].extend([validity, refusal])
        result["capability_state"] = "rulebook_closure_candidate"
        if refusal["status"] != "pass":
            result["state"] = "OWNER_SIGNATURE_REQUIRED"
            result["next_required_action"] = "owner_signature_before_action"
        elif validity["status"] == "pass" and result["state"] == "DRAFT_STRUCTURED":
            result["state"] = "CLOSE_CANDIDATE"
            result["next_required_action"] = "owner_signature_and_replay"
    return result


def build_rule_assist_prompt(assessment: dict[str, Any], locale: str = "zh-TW") -> str:
    plan = assessment.get("plan_level", "FREE")
    four_store = assessment.get("four_store", {})
    if locale == "en":
        return (
            f"SCBKR 2.3 rule-assist mode: {plan}. "
            "Use signed four-store citations as authority when available; otherwise answer as basic chat or draft only. "
            "Never claim final CLOSE, never sign for the user, never invent citations, and never perform storage/tool/publish actions without owner signature. "
            f"Current gate state: {assessment.get('state')}. Four-store priority: {four_store.get('answer_priority')}."
        )
    return (
        f"SCBKR 2.3 規則輔助模式：{plan}。"
        "若四庫有已簽名引用，必須以四庫為準；若沒有，只能做基礎聊天或草案。"
        "模型不得自稱終局 CLOSE，不得替使用者簽名，不得偽造引用，不得未簽名就入庫、調工具、發布或外部送出。"
        f"目前 Gate 狀態：{assessment.get('state')}。四庫優先狀態：{four_store.get('answer_priority')}。"
    )


def build_local_rule_assist_reply(text: str, assessment: dict[str, Any], locale: str = "zh-TW") -> str:
    plan = assessment.get("plan_level", "FREE")
    state = assessment.get("state", "DRAFT")
    four_store = assessment.get("four_store", {})
    if locale == "en":
        if not text.strip():
            return "Please enter the task, rule, or question first. I can draft, but I cannot sign or store anything for you."
        if _looks_like_question(text):
            return (
                f"Local SCBKR rule layer is running in {plan} mode. "
                "When signed four-store material exists, it becomes the answer authority; otherwise I answer as basic chat or draft only. "
                f"Current gate state is {state}. The next action is {assessment.get('next_required_action')}."
            )
        return (
            f"I can turn this into a SCBKR draft under {plan} mode. "
            f"Four-store state: {four_store.get('answer_priority')}. "
            "Before it becomes a rule or memory, you must review, sign, and confirm storage."
        )
    if not text.strip():
        return "請先輸入任務、規則或問題。我可以整理草案，但不能替你簽名或入庫。"
    if _looks_like_question(text):
        return (
            f"本機 SCBKR 規則層正在以 {plan} 模式運作。"
            "有已簽名四庫資料時，以四庫為準；沒有四庫依據時，只能做基礎聊天或草案。"
            f"目前 Gate 狀態是 {state}，下一步是 {assessment.get('next_required_action')}。"
        )
    return (
        f"這段可以進入 SCBKR {plan} 草案流程。"
        f"四庫狀態：{four_store.get('answer_priority')}。"
        "正式成為規則或記憶前，仍必須由你檢查、簽名、驗收與確認入庫。"
    )
