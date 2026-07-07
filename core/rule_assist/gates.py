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
        "human_capabilities": [
            "一般聊天與任務草稿",
            "自然語言建立未簽名規則草案",
            "四庫只能做候選搜尋，不能當正式引用結論",
        ],
        "model_scbr_fill": "不主動補完整 S/C/B/K/R；只提供基礎草稿與提示。",
        "formation_conditions": [
            "使用者提供任務或規則原句",
            "系統可產生草案",
            "正式成立前必須由使用者檢查與簽名",
        ],
        "failure_conditions": [
            "沒有使用者簽名不得成立規則",
            "沒有四庫正式引用不得宣稱已有依據",
            "模型不得自行 CLOSE、驗收或入庫",
        ],
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
        "human_capabilities": [
            "協助補 S/C/B/K/R 基本欄位",
            "擋掉空回覆、假因果、缺參數建議",
            "把使用者一句話整理成可檢查草案",
        ],
        "model_scbr_fill": "可補主體、流程、邊界、依據、驗收條件，但只能是草案。",
        "formation_conditions": [
            "通過第 0 原理：不是空話或只有『好』",
            "語意合法：有主語、目的、邊界或可追問缺口",
            "使用者簽名後才可進入生成或啟用",
        ],
        "failure_conditions": [
            "主語不明、邊界不明或責任不明",
            "只有空泛要求，沒有任務參數",
            "模型補欄位後未經使用者簽名",
        ],
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
        "human_capabilities": [
            "建立 CLOSE_CANDIDATE，而非替使用者終裁",
            "明列成立條件、失效條件與修復路徑",
            "高風險工具、發布、入庫、外部連線一律要求簽名",
        ],
        "model_scbr_fill": "可補完整 S/C/B/K/R、成立條件、失效條件、修復路徑與工具拒絕理由。",
        "formation_conditions": [
            "第 0 原理通過",
            "語意合法 Gate 通過",
            "有效性/失敗審計通過",
            "高風險操作已有使用者簽名",
            "若引用四庫，必須命中已簽名且已驗收資料",
        ],
        "failure_conditions": [
            "語意 Gate 未閉合",
            "高風險操作未簽名",
            "宣稱引用但四庫沒有正式資料",
            "模型自行簽名、驗收、入庫或宣稱 CLOSE",
            "服務對象、邊界、標準、責任、回放缺任一項",
        ],
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


def plan_contract(plan_level: str, locale: str = "zh-TW") -> dict[str, Any]:
    plan = deepcopy(PLAN_CATALOG[normalize_plan_level(plan_level)])
    return {
        "plan_level": plan["plan_level"],
        "display_name": plan["name"].get(locale) or plan["name"]["zh-TW"],
        "display_summary": plan["summary"].get(locale) or plan["summary"]["zh-TW"],
        "human_capabilities": plan.get("human_capabilities", []),
        "model_scbr_fill": plan.get("model_scbr_fill", ""),
        "formation_conditions": plan.get("formation_conditions", []),
        "failure_conditions": plan.get("failure_conditions", []),
        "requires_owner_signature": plan.get("requires_owner_signature", True),
        "can_fill_structure": plan.get("can_fill_structure", False),
        "can_claim_close": plan.get("can_claim_close", False),
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


def _append_unique(target: list[Any], values: list[Any]) -> list[Any]:
    seen = {str(item) for item in target}
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in seen:
            target.append(text)
            seen.add(text)
    return target


def _ensure_list(container: dict[str, Any], key: str) -> list[Any]:
    value = container.get(key)
    if isinstance(value, list):
        return value
    if value in (None, "", {}):
        container[key] = []
    else:
        container[key] = [value]
    return container[key]


def _is_business_copy_task(text: str) -> bool:
    lowered = (text or "").lower()
    return any(token in lowered for token in ("商業文案", "文案", "廣告", "銷售", "landing page", "copywriting", "marketing copy"))


def _is_rule_form_task(text: str) -> bool:
    lowered = (text or "").lower()
    return any(token in lowered for token in ("規則表單", "規則", "表單", "確認單", "rule form", "policy", "checklist"))


def _semantic_task_profile(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    business_copy = _is_business_copy_task(raw)
    rule_form = _is_rule_form_task(raw)
    if business_copy and rule_form:
        return {
            "subject": "商業文案規則表單",
            "goal": "把商業文案需求編譯成可檢查的 SCBKR 規則確認單，讓使用者確認後再生成正式文案。",
            "outputs": ["商業文案規則確認單", "文案生成前檢查表", "可驗收的文案輸出條件"],
            "logic": [
                "先確認商業目的、商品/服務、受眾、通路、語氣與禁止宣稱。",
                "再把需求拆成 S/C/B/K/R 五鏈，使用者簽名後才可當規則使用。",
                "若要發布、寄出、上架或入庫，必須另經使用者簽名確認。",
            ],
            "boundaries": [
                "不得在缺少商品、受眾、通路、價格或品牌限制時宣稱已完成正式商業文案。",
                "不得編造價格、保證、療效、法規、實測成果、客戶背書或競品資料。",
                "不得把文案草稿當成已簽名規則、已驗收內容或可直接發布內容。",
                "涉及公開發布、寄送、上架、付款或外部工具時，必須要求使用者簽名。",
            ],
            "basis": [
                "使用者原始指令",
                "SCBKR 五鏈語法",
                "第0原理：主語、邊界、責任不足時不得硬編",
                "四庫資料只有在已簽名且已驗收時才能當正式引用",
            ],
            "acceptance": [
                "表單清楚列出商業目的、受眾、輸出格式、禁止事項與驗收標準。",
                "B 層明確阻止編造商業事實、保證與未授權發布。",
                "K 層明確區分使用者原句、SCBKR 語法與四庫正式引用。",
                "R 層要求使用者簽名後才成立，模型不得自行 CLOSE。",
            ],
            "formation": [
                "使用者明確要求建立商業文案規則或確認單。",
                "S/C/B/K/R 五鏈都有可檢查內容。",
                "B 層已列出不可編造、不可發布、不可代簽等邊界。",
                "K 層已標清依據來源，沒有四庫正式資料時不得宣稱引用。",
                "R 層保留使用者簽名與驗收條件。",
            ],
            "failure": [
                "缺少商品/服務、目標受眾、通路、格式或禁止宣稱時只能停在草案。",
                "模型編造價格、保證、療效、法規、實測或引用來源時失效。",
                "模型未經使用者簽名就發布、入庫、寄送或宣稱規則成立時失效。",
                "B 或 K 層沒有寫出邊界與依據時不得確認。",
            ],
            "repair": [
                "補商品/服務、受眾、通路、語氣、禁止宣稱與輸出格式。",
                "補 B 層停止條件與 K 層依據來源。",
                "補 R 層驗收標準與使用者簽名要求。",
                "重新生成確認單，交使用者審查後再簽名。",
            ],
        }
    if rule_form:
        return {
            "subject": raw[:48] or "使用者規則確認單",
            "goal": "把使用者原句整理成可簽名、可驗收、可回放的 SCBKR 規則草案。",
            "outputs": ["規則確認單", "成立條件", "失效條件", "驗收標準"],
            "logic": [
                "先鎖定使用者要建立的規則主體。",
                "再拆成 S/C/B/K/R 五鏈草案。",
                "使用者簽名後才可進入生成、驗收或入庫。",
            ],
            "boundaries": [
                "不得把未簽名草案當成已啟用規則。",
                "不得替使用者簽名、驗收或入庫。",
                "不得偽造四庫引用或外部依據。",
            ],
            "basis": ["使用者原始指令", "SCBKR 五鏈語法", "第0原理"],
            "acceptance": [
                "S/C/B/K/R 欄位可被普通使用者讀懂。",
                "成立條件與失效條件明確。",
                "使用者簽名後才成立。",
            ],
            "formation": ["使用者有明確規則意圖", "五鏈欄位完整", "使用者完成簽名"],
            "failure": ["主語不明", "邊界不明", "依據不明", "模型代簽或宣稱 CLOSE"],
            "repair": ["補主語", "補邊界", "補依據", "補驗收與簽名條件"],
        }
    return {
        "subject": raw[:48] or "SCBKR 任務確認單",
        "goal": "把使用者需求整理成可檢查、可簽名、可回放的責任鏈草案。",
        "outputs": ["SCBKR 確認單", "任務草案", "驗收條件"],
        "logic": [
            "先抽取任務主體與目的。",
            "再補流程、邊界、依據與責任。",
            "使用者簽名後才可生成正式結果。",
        ],
        "boundaries": [
            "不得把草案當正式結果。",
            "不得替使用者簽名、驗收、入庫或發布。",
            "資料不足時必須標示待補，不得硬編。",
        ],
        "basis": ["使用者原始指令", "SCBKR 五鏈語法", "第0原理"],
        "acceptance": ["五鏈欄位完整", "使用者能看懂", "使用者簽名後才成立"],
        "formation": ["使用者提供任務原句", "五鏈欄位完整", "使用者確認並簽名"],
        "failure": ["主語不明", "邊界不明", "責任不明", "模型代簽或宣稱完成"],
        "repair": ["補主語/目的", "補邊界/依據", "補驗收/簽名要求"],
    }


def _gate_summary(assessment: dict[str, Any]) -> list[str]:
    summary: list[str] = []
    for gate in assessment.get("gates", []) or []:
        gate_id = str(gate.get("gate_id") or "Gate")
        status = str(gate.get("status") or "unknown")
        findings = gate.get("findings") or gate.get("failure_cases") or []
        suffix = f"：{', '.join(map(str, findings))}" if findings else ""
        summary.append(f"{gate_id} = {status}{suffix}")
    return summary


def apply_rule_assist_to_scbkr(raw_input: str, scbkr: dict[str, Any], assessment: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply FREE / NT690 / NT3300 structure-assist rules to a SCBKR draft.

    This is deterministic backend logic. A local LLM may supply phrasing before
    this step, but the product contract is enforced here.
    """
    draft = deepcopy(scbkr or {})
    assessment = assessment or evaluate_rule_assist(raw_input, "FREE", target_mode="task")
    plan = normalize_plan_level(str(assessment.get("plan_level") or "FREE"))
    profile = _semantic_task_profile(raw_input)
    contract = assessment.get("plan_contract") or plan_contract(plan)
    draft["rule_assist_plan"] = plan
    draft["rule_assist_state"] = assessment.get("state", "DRAFT")
    draft["structure_assist"] = {
        "plan_level": plan,
        "state": assessment.get("state", "DRAFT"),
        "model_can_fill": contract.get("model_scbr_fill", ""),
        "gate_summary": _gate_summary(assessment),
        "owner_signature_required": True,
    }
    if plan == "FREE":
        return draft

    draft.setdefault("S", {})
    draft.setdefault("C", {})
    draft.setdefault("B", {})
    draft.setdefault("K", {})
    draft.setdefault("R", {})
    draft["S"]["task_subject"] = draft["S"].get("task_subject") or profile["subject"]
    if _is_business_copy_task(raw_input) and _is_rule_form_task(raw_input):
        draft["S"]["task_name"] = "商業文案規則表單確認草案"
        draft["S"]["task_subject"] = profile["subject"]
        draft["S"]["output_format"] = profile["outputs"]
    _append_unique(_ensure_list(draft["C"], "core_logic"), profile["logic"])
    _append_unique(_ensure_list(draft["C"], "test_conditions"), [
        "第0原理通過：不是空泛口令，有主語、目的、邊界或待補問題。",
        "五鏈欄位可由使用者逐項確認。",
    ])
    _append_unique(_ensure_list(draft["B"], "stop_conditions"), profile["boundaries"])
    _append_unique(_ensure_list(draft["B"], "error_handling"), [
        "若主語、邊界、依據或責任不足，必須停在 OWNER_REVIEW，請使用者補資料。",
        "若模型草案與使用者原句衝突，以使用者原句與已簽名四庫資料為準。",
    ])
    _append_unique(_ensure_list(draft["K"], "references"), profile["basis"])
    _append_unique(_ensure_list(draft["K"], "source_credibility"), [
        "使用者原句是本次草案的主要依據。",
        "沒有已簽名、已驗收四庫資料時，不得宣稱正式引用。",
        "模型輸出只能作為草案，不是終局依據。",
    ])
    draft["K"]["evidence_policy"] = "signed_four_store_required_for_formal_citation"
    _append_unique(_ensure_list(draft["R"], "acceptance_criteria"), profile["acceptance"])
    draft["R"]["owner_signature_required"] = True
    draft["R"]["model_signature_allowed"] = False
    draft["R"]["required_signer"] = "user"

    if plan == "NT3300":
        formation = list(contract.get("formation_conditions") or []) + profile["formation"]
        failure = list(contract.get("failure_conditions") or []) + profile["failure"]
        repair = profile["repair"]
        for gate in assessment.get("gates", []) or []:
            if isinstance(gate.get("repair_path"), list):
                repair.extend(gate["repair_path"])
        draft["B"]["formation_conditions"] = _append_unique([], formation)
        draft["B"]["failure_conditions"] = _append_unique([], failure)
        draft["R"]["formation_conditions"] = _append_unique([], formation)
        draft["R"]["failure_conditions"] = _append_unique([], failure)
        draft["R"]["repair_path"] = _append_unique([], repair)
        draft["R"]["closure_state"] = "CLOSE_CANDIDATE_ONLY_BEFORE_OWNER_SIGNATURE"
        draft["structure_assist"]["closure_limit"] = "模型可補完整條件，但正式 CLOSE 必須使用者簽名、驗收與回放。"
    return draft


def build_scbkr_layer_patch(
    *,
    raw_input: str,
    scbkr: dict[str, Any],
    layer: str,
    instruction: str,
    assessment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a user-reviewable patch for one SCBKR dimension."""
    layer = str(layer or "B").upper()
    if layer not in {"S", "C", "B", "K", "R"}:
        raise ValueError("layer must be S/C/B/K/R")
    assessment = assessment or evaluate_rule_assist(raw_input, "FREE", target_mode="task")
    plan = normalize_plan_level(str(assessment.get("plan_level") or "FREE"))
    profile = _semantic_task_profile(raw_input)
    after = deepcopy((scbkr or {}).get(layer) or {})
    _append_unique(_ensure_list(after, "pending_questions"), [f"使用者要求修改：{instruction or '請依使用者指令調整此層。'}"])

    if layer == "S":
        after["task_subject"] = profile["subject"]
        after["output_format"] = profile["outputs"]
        after["task_name"] = after.get("task_name") or f"{profile['subject']}確認草案"
    elif layer == "C":
        _append_unique(_ensure_list(after, "core_logic"), profile["logic"])
        _append_unique(_ensure_list(after, "flow_steps"), ["理解使用者原句", "補齊五鏈草案", "等待使用者簽名確認"])
        _append_unique(_ensure_list(after, "test_conditions"), ["第0原理通過", "使用者可逐項驗收"])
    elif layer == "B":
        _append_unique(_ensure_list(after, "stop_conditions"), profile["boundaries"])
        _append_unique(_ensure_list(after, "data_write_scope"), ["未簽名不得寫入四庫", "未驗收不得入庫", "未簽名不得發布或寄出"])
        _append_unique(_ensure_list(after, "error_handling"), ["B 層不完整時進 OWNER_REVIEW，不得讓模型硬編。"])
        if plan == "NT3300":
            after["formation_conditions"] = _append_unique([], profile["formation"])
            after["failure_conditions"] = _append_unique([], profile["failure"])
    elif layer == "K":
        _append_unique(_ensure_list(after, "references"), profile["basis"])
        _append_unique(_ensure_list(after, "source_credibility"), [
            "使用者原始指令可作草案依據。",
            "第0原理與 SCBKR 語法可作結構依據。",
            "四庫正式引用必須是已簽名、已驗收資料。",
            "沒有正式引用時要明講：本次不是引用四庫結論。",
        ])
        after["evidence_policy"] = "signed_four_store_required_for_formal_citation"
    elif layer == "R":
        _append_unique(_ensure_list(after, "acceptance_criteria"), profile["acceptance"])
        after["owner_signature_required"] = True
        after["model_signature_allowed"] = False
        after["required_signer"] = "user"
        if plan == "NT3300":
            after["formation_conditions"] = _append_unique([], profile["formation"])
            after["failure_conditions"] = _append_unique([], profile["failure"])
            after["repair_path"] = _append_unique([], profile["repair"])
            after["closure_state"] = "CLOSE_CANDIDATE_ONLY_BEFORE_OWNER_SIGNATURE"
    return after


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
        "plan_contract": plan_contract(plan, locale),
        "formation_conditions": deepcopy(PLAN_CATALOG[plan].get("formation_conditions", [])),
        "failure_conditions": deepcopy(PLAN_CATALOG[plan].get("failure_conditions", [])),
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
