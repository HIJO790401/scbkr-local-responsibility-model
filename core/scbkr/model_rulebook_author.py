"""Model-assisted SCBKR rulebook authoring.

The model may draft S/C/B/K/R content, explanations, gaps, and risks. It may
not sign, store, activate, or claim the rule is established.
"""

from __future__ import annotations

import json
import re
from typing import Any

from core.rule_os.i18n import normalize_locale_text

from core.kernel.scbkr_kernel_compiler import KERNEL_NAME

DIMENSIONS = ("S", "C", "B", "K", "R")


class ModelRulebookAuthoringError(ValueError):
    """Raised when the model did not produce a valid rulebook draft."""

    def __init__(
        self,
        code: str,
        *,
        candidate: dict[str, Any] | None = None,
        semantic_report: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.candidate = candidate
        self.semantic_report = semantic_report or {}


def _estimate_tokens(value: str) -> int:
    return (len(value or "") + 3) // 4


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [f"{key}: {item}" for key, item in value.items()]
    text = str(value).strip()
    return [text] if text else []


def _has_meaningful_items(value: Any) -> bool:
    placeholders = {"", "無", "沒有", "未知", "待定", "none", "n/a", "na", "unknown", "tbd"}
    placeholder_prefixes = (
        "無缺失", "無缺少", "沒有缺", "無確認", "無需確認", "不需確認",
        "無風險", "沒有風險", "無下一步", "無決定", "沒有決定", "無模型",
        "no missing", "no confirmation", "no risk", "no next", "no decision",
        "nothing missing", "not applicable",
    )
    return any(
        item.strip().lower() not in placeholders
        and not item.strip().lower().startswith(placeholder_prefixes)
        for item in _as_list(value)
    )


def _dim_payload(authoring: dict[str, Any], dim: str) -> dict[str, Any]:
    value = authoring.get(dim)
    if not isinstance(value, dict):
        raise ModelRulebookAuthoringError(f"{dim}_must_be_object")
    content = str(value.get("content") or value.get("draft") or value.get("summary") or "").strip()
    explanation = str(value.get("explanation") or "").strip()
    if len(content) < 2:
        raise ModelRulebookAuthoringError(f"{dim}_missing_content")
    if len(explanation) < 4:
        raise ModelRulebookAuthoringError(f"{dim}_missing_explanation")
    return {
        "content": content,
        "explanation": explanation,
        "missing_information": _as_list(value.get("missing_information")),
        "needs_user_confirmation": _as_list(value.get("needs_user_confirmation")),
        "model_cannot_decide": _as_list(value.get("model_cannot_decide")),
        "risk_notes": _as_list(value.get("risk_notes")),
        "schema_adapter_generated": bool(value.get("schema_adapter_generated")),
        "model_explanation_derived_from_fields": bool(value.get("model_explanation_derived_from_fields")),
        "model_explanation_preserved_from_alias": bool(value.get("model_explanation_preserved_from_alias")),
        "model_explanation_repaired_by_model": bool(value.get("model_explanation_repaired_by_model")),
        "model_task_fragment": str(value.get("model_task_fragment") or "").strip(),
        "model_original_content_before_kernel_compile": str(
            value.get("model_original_content_before_kernel_compile") or ""
        ).strip(),
        "kernel_required_clauses": _as_list(value.get("kernel_required_clauses")),
        "kernel_structure_compiled": bool(value.get("kernel_structure_compiled")),
    }


def _is_english(locale: str) -> bool:
    return str(locale or "").lower().startswith("en")


def _canonicalize_compact_dimension(value: Any, dim: str, locale: str) -> dict[str, Any]:
    """Turn a small model's compact dimension into the editable SCBKR shape.

    This is a schema adapter, not a rule fallback: the model must still supply
    non-empty S/C/B/K/R meaning. Missing governance metadata remains visible as
    confirmation work instead of being presented as model certainty.
    """
    original_fields: dict[str, Any] | None = None
    content_parts: list[str] = []
    preserved_explanation = ""
    preserved_support: dict[str, list[str]] = {}
    if isinstance(value, dict):
        if str(value.get("content") or value.get("draft") or value.get("summary") or "").strip():
            return value
        original_fields = dict(value)
        for alias in ("rule_content", "rule_text", "value", "text"):
            alias_content = str(value.get(alias) or "").strip()
            if alias_content:
                value = alias_content
                break
        preserved_explanation = str(original_fields.get("explanation") or "").strip()
        preserved_support = {
            key: _as_list(original_fields.get(key))
            for key in (
                "missing_information",
                "needs_user_confirmation",
                "model_cannot_decide",
                "risk_notes",
            )
        }
        aliases = {
            "subject": ("Subject", "主體"),
            "situation": ("Situation", "情境"),
            "why_the_rule_exists": ("Cause", "原因"),
            "causality": ("Causality", "因果"),
            "decision_order": ("Decision order", "判斷順序"),
            "boundaries": ("Boundaries", "邊界"),
            "forbidden_actions": ("Prohibitions", "禁止事項"),
            "stop_conditions": ("Stop conditions", "停止條件"),
            "basis_policy": ("Basis", "依據"),
            "logic_corpus_memory_vector": ("Citable-source policy", "可引用來源政策"),
            "sources": ("Sources", "來源"),
            "responsibility": ("Responsibility", "責任"),
            "failure_replay": ("Failure and replay", "失效與回放"),
            "repair": ("Repair", "修復"),
            "signature": ("Signature", "簽名"),
        }
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {
                    "explanation",
                    "missing_information",
                    "needs_user_confirmation",
                    "model_cannot_decide",
                    "risk_notes",
                }:
                    continue
                item_text = "；".join(_as_list(item)).strip()
                if not item_text:
                    continue
                labels = aliases.get(str(key), (str(key).replace("_", " "), str(key).replace("_", " ")))
                content_parts.append(f"{labels[0 if _is_english(locale) else 1]}：{item_text}")
            value = "；".join(content_parts)
    content_items = _as_list(value)
    content = "；".join(content_items).strip()
    if not content:
        raise ModelRulebookAuthoringError(f"{dim}_missing_content")
    if _is_english(locale):
        labels = {"S": "subject", "C": "causality", "B": "boundary", "K": "basis", "R": "responsibility"}
        explanation = f"The model filled the {labels.get(dim, dim)} field; the user must confirm that it matches the intended judgement."
        missing = f"Add concrete exceptions or usage conditions for the {labels.get(dim, dim)} field."
        confirmation = f"Confirm the {labels.get(dim, dim)} field."
        cannot_decide = "The model cannot make the owner's final judgement."
        risk = "This remains a draft until the user signs it."
    else:
        labels = {"S": "主體", "C": "因果", "B": "邊界", "K": "依據", "R": "責任"}
        explanation = f"模型已填入{labels.get(dim, dim)}欄位；請使用者確認這段判斷是否符合原意。"
        missing = f"請補充{labels.get(dim, dim)}欄位的具體例外或適用條件。"
        confirmation = f"確認{labels.get(dim, dim)}欄位內容。"
        cannot_decide = "模型不能替使用者做終局判定。"
        risk = "使用者簽名前只能作為規則草稿。"
    derived_from_fields = original_fields is not None and len(content_parts) >= 2
    if derived_from_fields:
        if _is_english(locale):
            explanation = f"The model decomposed this dimension into task-specific fields: {content}."
        else:
            explanation = f"模型將此維拆成任務專用子欄位：{content}。"
    explanation_preserved = len(preserved_explanation) >= 4
    if explanation_preserved:
        explanation = preserved_explanation
    normalized = {
        "content": content,
        "explanation": explanation,
        "missing_information": preserved_support.get("missing_information") or [missing],
        "needs_user_confirmation": preserved_support.get("needs_user_confirmation") or [confirmation],
        "model_cannot_decide": preserved_support.get("model_cannot_decide") or [cannot_decide],
        "risk_notes": preserved_support.get("risk_notes") or [risk],
        "schema_adapter_generated": True,
        "model_explanation_derived_from_fields": derived_from_fields,
        "model_explanation_preserved_from_alias": explanation_preserved,
    }
    if original_fields is not None:
        normalized["model_original_fields"] = original_fields
    return normalized


def _canonicalize_compact_authoring(authoring: dict[str, Any], locale: str) -> tuple[dict[str, Any], bool]:
    """Accept compact model S/C/B/K/R while preserving a visible repair flag."""
    repaired = False
    normalized = dict(authoring)
    # Small local models are materially more reliable with a flat strict
    # schema. Rehydrate their model-authored content/explanations before the
    # ordinary SCBKR adapter runs; no rule meaning is generated here.
    for dim in DIMENSIONS:
        explanation_key = f"{dim}_explanation"
        explanation = str(normalized.get(explanation_key) or "").strip()
        value = normalized.get(dim)
        if not isinstance(value, dict) and explanation:
            normalized[dim] = {
                "content": str(value or "").strip(),
                "explanation": explanation,
            }
            normalized.pop(explanation_key, None)
            repaired = True
    global_field_names = (
        "rule_summary",
        "missing_information",
        "user_confirmation_items",
        "model_cannot_decide",
        "risk_reminders",
        "next_actions",
    )
    normalized["model_global_fields_present"] = {
        key: key in authoring
        for key in global_field_names
    }
    normalized["model_original_global_fields"] = {
        key: authoring.get(key)
        for key in global_field_names
        if key in authoring
    }
    for dim in DIMENSIONS:
        value = normalized.get(dim)
        if not isinstance(value, dict):
            repaired = True
        normalized[dim] = _canonicalize_compact_dimension(value, dim, locale)
    normalized.setdefault("rule_summary", "；".join(normalized[dim]["content"] for dim in DIMENSIONS))
    normalized.setdefault("missing_information", [])
    normalized.setdefault("user_confirmation_items", [])
    normalized.setdefault("model_cannot_decide", [])
    normalized.setdefault("risk_reminders", [])
    normalized.setdefault("next_actions", ["owner_review_and_signature"])
    if not isinstance(normalized.get("rule_summary"), str) or not normalized["rule_summary"].strip():
        normalized["rule_summary"] = "；".join(normalized[dim]["content"] for dim in DIMENSIONS)
        repaired = True
    for key in ("missing_information", "user_confirmation_items", "model_cannot_decide", "risk_reminders", "next_actions"):
        if not isinstance(normalized.get(key), list):
            normalized[key] = _as_list(normalized.get(key))
            repaired = True
        normalized[key] = [
            item for item in normalized.get(key, [])
            if _has_meaningful_items([item])
        ]
    normalized["model_support_fields_derived"] = {}
    responsibility = normalized.get("R") or {}
    responsibility_text = " ".join(
        str(responsibility.get(key) or "")
        for key in ("content", "explanation")
    ).lower()
    owner_signature_authored = _responsibility_owner_signs(responsibility_text)
    model_authority_boundary_authored = any(
        token in responsibility_text
        for token in ("模型不能", "模型不得", "模型無法", "model cannot", "model must not")
    )
    if not _has_meaningful_items(normalized.get("model_cannot_decide")):
        if owner_signature_authored and model_authority_boundary_authored:
            normalized["model_cannot_decide"] = [
                "The model cannot sign, approve, or replace the user's final judgement."
                if _is_english(locale)
                else "模型不能替使用者簽名、核准或取代使用者的最終判斷。"
            ]
            normalized["model_support_fields_derived"]["model_cannot_decide"] = "model_R_plus_kernel_authority_boundary"
            repaired = True
    if not _has_meaningful_items(normalized.get("next_actions")):
        if owner_signature_authored:
            normalized["next_actions"] = [
                "The user reviews every field and signs; until then, keep the rule as a draft."
                if _is_english(locale)
                else "由使用者逐欄確認後簽名；簽名前保持草稿。"
            ]
            normalized["model_support_fields_derived"]["next_actions"] = "model_R_owner_signature_workflow"
            repaired = True
    if (
        not _has_meaningful_items(normalized.get("missing_information"))
        and _has_meaningful_items(normalized.get("user_confirmation_items"))
    ):
        first_confirmation = _as_list(normalized.get("user_confirmation_items"))[0]
        normalized["missing_information"] = [
            f"Verify before acceptance: {first_confirmation}"
            if _is_english(locale)
            else f"驗收前待核對：{first_confirmation}"
        ]
        normalized["model_support_fields_derived"]["missing_information"] = "model_user_confirmation_item"
        repaired = True
    dimension_sources = {
        "missing_information": "missing_information",
        "user_confirmation_items": "needs_user_confirmation",
        "model_cannot_decide": "model_cannot_decide",
        "risk_reminders": "risk_notes",
    }
    for global_key, dimension_key in dimension_sources.items():
        if normalized.get(global_key):
            continue
        aggregated: list[str] = []
        for dim in DIMENSIONS:
            for item in _as_list(normalized[dim].get(dimension_key)):
                if item not in aggregated:
                    aggregated.append(item)
        if aggregated:
            normalized[global_key] = aggregated[:10]
            repaired = True
    return normalized, repaired


def refresh_model_rulebook_support_fields(
    candidate: dict[str, Any],
    *,
    locale: str = "zh-TW",
) -> dict[str, Any]:
    """Re-evaluate model support fields after transparent dimension compilation."""
    refreshed, repaired = _canonicalize_compact_authoring(candidate, locale)
    refreshed["model_schema_repaired"] = bool(
        candidate.get("model_schema_repaired") or repaired
    )
    return refreshed


ROLE_SIGNALS = {
    "C": ("先", "再", "流程", "順序", "原因", "因果", "判斷", "若", "則", "first", "then", "process", "sequence", "because", "cause", "if", "evaluate", "check", "decide"),
    "B": ("不得", "禁止", "邊界", "停止", "限制", "不能", "不可", "例外", "must not", "cannot", "do not", "boundary", "stop", "limit", "prohibit", "only", "exception"),
    "K": ("依據", "證據", "來源", "資料", "引用", "文件", "紀錄", "規範", "經驗", "basis", "evidence", "source", "data", "cite", "reference", "record", "policy", "document", "kernel"),
    "R": ("責任", "簽名", "確認", "承擔", "驗收", "使用者", "負責", "審核", "responsibility", "signature", "sign", "confirm", "owner", "user", "accountable", "review", "accept"),
}


def _responsibility_owner_signs(text: str) -> bool:
    value = str(text or "").lower()
    has_owner = any(
        token in value
        for token in (
            "使用者", "擁有者", "負責人", "承擔者",
            "owner", "user", "accountable", "responsible",
        )
    )
    has_signature = any(token in value for token in ("簽名", "簽署", "signature", "sign"))
    user_signs = bool(
        re.search(
            r"(?:使用者|擁有者|負責人|承擔者).{0,80}(?:簽名|簽署)|"
            r"(?:owner|user|accountable|responsible|reviewer).{0,300}(?:signature|sign)|"
            r"(?:signature|signing).{0,48}(?:by|from|required from)\s+(?:the\s+)?"
            r"(?:owner|user|accountable person|responsible person|reviewer)",
            value,
            flags=re.IGNORECASE,
        )
    )
    if has_owner and any(token in value for token in ("我的簽名", "由我簽名", "my signature", "signed by me")):
        user_signs = True
    return has_owner and has_signature and user_signs


def _dimension_role_complete(layer: str, text: str) -> bool:
    """Check one model-authored sentence against its cross-domain SCBKR role."""
    layer = str(layer or "").upper()
    value = str(text or "").lower()
    if layer == "C":
        ordered_path = (
            ("先" in value and any(token in value for token in ("再", "最後")))
            or ("first" in value and any(token in value for token in ("then", "finally", "next")))
        )
        conditional_path = (
            any(token in value for token in ("若", "如果", "倘若"))
            and any(token in value for token in ("則", "就", "便", "即"))
        ) or bool(
            re.search(r"\bif\b.{1,500}\bthen\b", value, flags=re.IGNORECASE | re.DOTALL)
        )
        return ordered_path or conditional_path
    if layer == "B":
        claims_no_boundary = any(
            token in value
            for token in (
                "沒有禁止", "無禁止", "未提及禁止", "沒有明確禁止",
                "no forbidden", "no specific forbidden", "no prohibition", "no explicit prohibition",
            )
        )
        has_prohibition = any(
            token in value
            for token in (
                "不得", "不能", "不可", "禁止", "不應",
                "must not", "cannot", "do not", "should not", "prohibit",
            )
        )
        has_stop = any(
            token in value
            for token in (
                "停止", "停在", "待確認", "未確認", "沒有確認", "資料不足",
                "stop", "halt", "pending confirmation", "unconfirmed",
                "without confirmation", "missing data", "records are missing",
                "record is missing", "draft",
            )
        )
        return has_prohibition and has_stop and not claims_no_boundary
    if layer == "K":
        has_citable = any(
            token in value
            for token in (
                "只可引用", "可引用", "只能使用", "正式依據",
                "may cite", "may be cited", "cite only", "formal basis",
            )
        )
        has_non_citable = any(
            token in value
            for token in (
                "不可引用", "不得引用", "不能當正式依據", "不是正式依據",
                "recall only", "may not cite", "may not be cited", "must not cite",
                "must not be cited", "cannot cite", "cannot be cited", "not formal basis",
            )
        )
        has_confirmed_source = any(
            token in value
            for token in (
                "使用者已確認", "使用者確認", "已確認", "正式資料",
                "owner-confirmed", "user-confirmed", "confirmed record", "confirmed data",
            )
        )
        return has_citable and has_non_citable and has_confirmed_source
    if layer == "R":
        model_unsigned = any(
            token in value
            for token in ("模型不能", "模型不得", "模型助理不能", "模型無法", "model cannot", "model must not")
        )
        unsigned_acceptance = any(
            token in value
            for token in ("未簽名則視為同意", "未簽名視為同意", "unsigned means accepted", "unsigned is accepted")
        )
        return _responsibility_owner_signs(value) and model_unsigned and not unsigned_acceptance
    return layer == "S" and bool(value.strip())


def _semantic_terms(text: str) -> set[str]:
    value = str(text or "").lower()
    terms = {word for word in re.findall(r"[a-z][a-z0-9_-]{3,}", value)}
    generic_en = {"rule", "rules", "create", "local", "please", "want", "make", "generate", "write", "future", "model"}
    terms.difference_update(generic_en)
    generic_zh = {
        "幫我", "規則", "建立", "生成", "本地", "一個", "我要", "以後", "凡是", "模型",
        "主體", "情境", "因果", "判斷", "順序", "邊界", "禁止", "停止", "依據", "引用", "來源",
        "責任", "驗收", "簽名", "條件", "草稿", "使用", "用戶",
    }
    for run in re.findall(r"[\u3400-\u9fff]{2,}", value):
        for index in range(len(run) - 1):
            token = run[index : index + 2]
            if token not in generic_zh:
                terms.add(token)
    return terms


def _grounding_candidates(text: str) -> list[str]:
    """Return readable request anchors for a small model, preserving task nouns."""
    value = str(text or "").strip()
    allowed = _semantic_terms(value)
    if not re.search(r"[\u3400-\u9fff]", value):
        ordered: list[str] = []
        for word in re.findall(r"[a-z][a-z0-9_-]{3,}", value.lower()):
            if word in allowed and word not in ordered:
                ordered.append(word)
        return ordered[:20]

    prefixes = re.compile(
        r"^(?:(?:幫我|請|我要|建立|生成|製作|先|再|最後|然後|核對|確認|"
        r"檢查|只能|需要|必須|若|如果|資料不足時|不得替我|不得|替我))+"
    )
    candidates: list[str] = []
    chunks = re.split(r"[：:，,、；;。！？\n]|\s+", value)
    for chunk in chunks:
        for part in re.split(r"(?:以及|或者|與|和|及|或)", chunk):
            item = part.strip(" ：:()（）[]「」『』'\"")
            item = prefixes.sub("", item).strip(" ：:()（）[]「」『』'\"")
            if 2 <= len(item) <= 24 and item not in candidates:
                candidates.append(item)
    return candidates[:20]


def _unrequested_non_citable_sources(k_text: str, user_input: str) -> list[str]:
    """Find named K-source restrictions that the owner never requested."""
    markers = (
        "不可引用",
        "不得引用",
        "不能引用",
        "may not cite",
        "must not cite",
        "cannot cite",
    )
    lowered = str(k_text or "").lower()
    owner_text = re.sub(r"\s+", "", str(user_input or "").lower())
    clauses: list[str] = []
    for marker in markers:
        offset = 0
        while True:
            index = lowered.find(marker, offset)
            if index < 0:
                break
            value = lowered[index + len(marker):]
            clauses.append(re.split(r"[；;。.\n]", value, maxsplit=1)[0])
            offset = index + len(marker)
    allowed_fragments = (
        "未確認",
        "未核准",
        "聊天",
        "上下文",
        "模型猜測",
        "猜測",
        "向量召回",
        "vector",
        "候選",
        "草稿",
        "未簽名",
        "不明來源",
        "無來源",
        "不得作正式依據",
        "不能當正式依據",
        "不是正式依據",
        "unconfirmed",
        "unsigned",
        "chat",
        "context",
        "model guess",
        "vector",
        "candidate",
        "draft",
        "recall only",
        "not formal basis",
        "unknown source",
    )
    generic_tail = {
        "內容",
        "資料",
        "紀錄",
        "記錄",
        "來源",
        "content",
        "data",
        "record",
        "records",
        "source",
        "sources",
    }
    unrequested: list[str] = []
    for clause in clauses:
        for fragment in re.split(r"[、,，/]|\s+(?:or|and)\s+|或|以及|及|與|和", clause, flags=re.IGNORECASE):
            value = fragment.strip(" ：:()（）[]「」『』'\"")
            lowered_value = value.lower()
            if "vector" in lowered_value or "向量召回" in lowered_value:
                # VECTOR is always retrieval-only under the SCBKR Kernel. A
                # model repeating that invariant is not inventing a new named
                # source restriction.
                continue
            for allowed in allowed_fragments:
                value = value.replace(allowed, "")
            value = re.sub(r"^(?:的|等|任何|所有|other|any)\s*", "", value, flags=re.IGNORECASE)
            value = value.strip(" ：:()（）[]「」『』'\"")
            if not value or value in generic_tail:
                continue
            compact = re.sub(r"\s+", "", value)
            terms = _semantic_terms(value)
            if compact in owner_text or (terms and terms.issubset(_semantic_terms(user_input))):
                continue
            if len(re.sub(r"[^\u3400-\u9fffa-z0-9]", "", compact)) >= 2:
                unrequested.append(value)
    return list(dict.fromkeys(unrequested))


def _has_model_authority_claim(text: str) -> bool:
    """Detect positive model signature/approval claims while allowing prohibitions."""
    value = str(text or "").lower()
    negations = (
        "不能", "不得", "不可", "無法", "無權", "不具備", "禁止",
        "未簽名", "未簽署", "未核准", "未入庫", "未啟用",
        "cannot", "can't", "must not", "may not", "is not allowed",
        "has no authority", "does not have authority", "never", "unsigned",
    )
    patterns = (
        r"由模型.{0,12}(?:簽名|簽署|驗收|核准|入庫|啟用)",
        r"模型(?:可以|可|將|會|應|須|必須|自行|代為|負責|進行|執行|完成|直接).{0,12}(?:簽名|簽署|驗收|核准|入庫|啟用)",
        r"模型(?:簽名|簽署|驗收|核准|入庫|啟用)",
        r"(?:the )?model\s+(?:can|may|will|should|must|shall|is allowed to|is to|handles?|performs?|executes?)\s*.{0,20}(?:sign|approve|accept|store|activate)",
        r"(?:the )?model\s+(?:signs|approves|accepts|stores|activates)\b",
        r"(?:signed|approved|accepted|stored|activated)\s+by\s+(?:the\s+)?model",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, value, flags=re.IGNORECASE | re.DOTALL):
            snippet = match.group(0)
            if not any(token in snippet for token in negations):
                return True
    return False


def _model_authority_overreach_paths(authoring: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in (
        "rule_summary",
        "missing_information",
        "user_confirmation_items",
        "model_cannot_decide",
        "risk_reminders",
        "next_actions",
    ):
        for item in _as_list(authoring.get(key)):
            if _has_model_authority_claim(item):
                paths.append(key)
                break
    for dim in DIMENSIONS:
        payload = authoring.get(dim)
        if not isinstance(payload, dict):
            continue
        for key in (
            "content",
            "explanation",
            "missing_information",
            "needs_user_confirmation",
            "model_cannot_decide",
            "risk_notes",
        ):
            for item in _as_list(payload.get(key)):
                if _has_model_authority_claim(item):
                    paths.append(f"{dim}.{key}")
                    break
    return list(dict.fromkeys(paths))


def validate_model_rulebook_semantics(
    authoring: dict[str, Any],
    *,
    user_input: str = "",
) -> dict[str, Any]:
    """Check that the model separated SCBKR roles and stayed on the request.

    This is intentionally language-light: it rejects duplicated dimensions and
    obvious role confusion without pretending a keyword check is human review.
    """
    contents = {dim: str((authoring.get(dim) or {}).get("content") or "").strip() for dim in DIMENSIONS}
    normalized = {dim: re.sub(r"\W+", "", value.lower(), flags=re.UNICODE) for dim, value in contents.items()}
    distinct_dimensions = len({value for value in normalized.values() if value}) == len(DIMENSIONS)
    definition_fragments = {
        "S": ("主體與情境", "subjectandsituation"),
        "C": ("因果與判斷順序", "causalityanddecisionorder"),
        "B": ("邊界禁止與停止", "boundariesprohibitionsandstops"),
        "K": ("依據與引用來源", "basisandcitablesources"),
        "R": ("責任驗收與簽名", "responsibilityreviewandsignature"),
    }
    copied_field_definitions = sum(
        1
        for dim, fragments in definition_fragments.items()
        if any(fragment in normalized.get(dim, "") for fragment in fragments)
        and len(normalized.get(dim, "")) <= max(len(fragment) for fragment in fragments) + 8
    ) >= 3
    placeholder_patterns = (
        r"\.{3,}",
        r"…{1,}",
        r"\bmust not\s*/\s*cannot\b",
        r"\bmay cite owner-confirmed\b",
        r"\bmay not cite\s*(?:\.{3}|…)",
    )
    placeholder_dimensions = [
        dim
        for dim, value in contents.items()
        if any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in placeholder_patterns)
    ]
    # Only model-authored content may prove role separation. These are the
    # cross-domain SCBKR contracts, not a domain-specific answer template.
    role_texts = {
        dim: " ".join(
            (
                contents[dim],
                str((authoring.get(dim) or {}).get("explanation") or "").strip(),
            )
        ).lower()
        for dim in DIMENSIONS
    }
    role_alignment = {
        dim: _dimension_role_complete(dim, role_texts[dim])
        for dim in ("C", "B", "K", "R")
    }
    model_explanation_alignment = {
        dim: (
            len(str((authoring.get(dim) or {}).get("explanation") or "").strip()) >= 4
            and (
                not bool((authoring.get(dim) or {}).get("schema_adapter_generated"))
                or bool((authoring.get(dim) or {}).get("model_explanation_derived_from_fields"))
                or bool((authoring.get(dim) or {}).get("model_explanation_preserved_from_alias"))
                or bool((authoring.get(dim) or {}).get("model_explanation_repaired_by_model"))
            )
        )
        for dim in DIMENSIONS
    }
    model_explanations_present = all(model_explanation_alignment.values())
    request_terms = _semantic_terms(user_input)
    output_terms = _semantic_terms(" ".join(contents.values()))
    matched_terms = sorted(request_terms & output_terms)
    request_alignment = not request_terms or bool(matched_terms)
    subject_terms = _semantic_terms(contents["S"])
    subject_request_alignment = not request_terms or bool(subject_terms & request_terms)
    c_terms = _semantic_terms(contents["C"])
    b_terms = _semantic_terms(contents["B"])
    c_b_union = c_terms | b_terms
    c_b_overlap = round(len(c_terms & b_terms) / len(c_b_union), 4) if c_b_union else 0.0
    c_b_roles_distinct = c_b_overlap < 0.72
    identity_tokens = ("沈耀", "許文耀", "wen-yao", "wen yao", "shenyao", "888π")
    input_lower = str(user_input or "").lower()
    output_lower = " ".join(contents.values()).lower()
    unrequested_identity_injection = any(
        token.lower() in output_lower and token.lower() not in input_lower
        for token in identity_tokens
    )
    k_for_role_check = re.sub(
        r"(?:使用者)?已簽名(?:且已驗收)?(?:的)?(?:正式)?規則|"
        r"未簽名草稿|signed(?: and reviewed)? rule|unsigned drafts?",
        "",
        contents["K"],
        flags=re.IGNORECASE,
    )
    k_signature_as_basis = bool(re.search(
        r"(?:引用|依據|cite|basis|source).{0,28}(?:簽名|審核|驗收|signature|review)",
        k_for_role_check,
        flags=re.IGNORECASE,
    ))
    k_unrequested_non_citable_sources = _unrequested_non_citable_sources(contents["K"], user_input)
    global_presence = authoring.get("model_global_fields_present") or {}
    model_support_fields_present = all(
        global_presence.get(key) is True
        for key in (
            "rule_summary",
            "missing_information",
            "user_confirmation_items",
            "model_cannot_decide",
            "risk_reminders",
            "next_actions",
        )
    )
    model_support_fields_useful = all(
        _has_meaningful_items(authoring.get(key))
        for key in ("missing_information", "user_confirmation_items", "model_cannot_decide", "risk_reminders", "next_actions")
    )
    model_authority_overreach_paths = _model_authority_overreach_paths(authoring)
    passed = (
        distinct_dimensions
        and not copied_field_definitions
        and not placeholder_dimensions
        and request_alignment
        and subject_request_alignment
        and all(role_alignment.values())
        and model_explanations_present
        and c_b_roles_distinct
        and not unrequested_identity_injection
        and not k_signature_as_basis
        and not k_unrequested_non_citable_sources
        and model_support_fields_present
        and model_support_fields_useful
        and not model_authority_overreach_paths
    )
    return {
        "passed": passed,
        "distinct_dimensions": distinct_dimensions,
        "copied_field_definitions": copied_field_definitions,
        "placeholder_dimensions": placeholder_dimensions,
        "request_alignment": request_alignment,
        "subject_request_alignment": subject_request_alignment,
        "matched_request_terms": matched_terms[:12],
        "dimension_role_alignment": role_alignment,
        "model_explanations_present": model_explanations_present,
        "model_explanation_alignment": model_explanation_alignment,
        "c_b_term_overlap": c_b_overlap,
        "c_b_roles_distinct": c_b_roles_distinct,
        "unrequested_identity_injection": unrequested_identity_injection,
        "k_signature_as_basis": k_signature_as_basis,
        "k_unrequested_non_citable_sources": k_unrequested_non_citable_sources,
        "model_support_fields_present": model_support_fields_present,
        "model_support_fields_useful": model_support_fields_useful,
        "model_support_fields_derived": authoring.get("model_support_fields_derived") or {},
        "model_authority_overreach_paths": model_authority_overreach_paths,
        "note": "Automated semantic separation check; owner review remains required.",
    }


def semantic_gap_codes(report: dict[str, Any]) -> list[str]:
    """Return stable capability-gap codes for the current authoring attempt."""
    gaps: list[str] = []
    if report.get("distinct_dimensions") is not True:
        gaps.append("dimensions_not_distinct")
    if report.get("copied_field_definitions") is True:
        gaps.append("copied_field_definitions")
    if report.get("placeholder_dimensions"):
        gaps.append("unresolved_placeholders")
    if report.get("request_alignment") is not True:
        gaps.append("request_not_grounded")
    if report.get("subject_request_alignment") is not True:
        gaps.append("s_role_unresolved")
    if report.get("model_explanations_present") is not True:
        gaps.append("model_explanations_missing")
    if report.get("c_b_roles_distinct") is not True:
        gaps.append("c_b_roles_overlapping")
    if report.get("unrequested_identity_injection") is True:
        gaps.append("unrequested_identity_injection")
    if report.get("k_signature_as_basis") is True:
        gaps.append("k_signature_as_basis")
    if report.get("k_unrequested_non_citable_sources"):
        gaps.append("k_unrequested_source_restriction")
    if report.get("model_support_fields_present") is not True or report.get("model_support_fields_useful") is not True:
        gaps.append("support_fields_missing")
    if report.get("model_authority_overreach_paths"):
        gaps.append("model_authority_overreach")
    role_alignment = report.get("dimension_role_alignment") or {}
    for dim in ("C", "B", "K", "R"):
        if role_alignment.get(dim) is not True:
            gaps.append(f"{dim.lower()}_role_unresolved")
    return gaps


def model_rulebook_repair_targets(report: dict[str, Any], *, limit: int = 3) -> list[str]:
    """Return only unresolved model-authored dimensions for the next pass."""
    role_alignment = report.get("dimension_role_alignment") or {}
    targets = [dim for dim in ("C", "B", "K", "R") if role_alignment.get(dim) is not True]
    for dim in report.get("placeholder_dimensions") or []:
        if dim in ("C", "B", "K", "R") and dim not in targets:
            targets.append(dim)
    if (
        report.get("k_signature_as_basis")
        or report.get("k_unrequested_non_citable_sources")
    ) and "K" not in targets:
        targets.append("K")
    if report.get("model_support_fields_useful") is not True and "R" not in targets:
        targets.append("R")
    if report.get("model_authority_overreach_paths") and "R" not in targets:
        targets.append("R")
    explanation_alignment = report.get("model_explanation_alignment") or {}
    for dim in DIMENSIONS:
        if explanation_alignment.get(dim) is not True and dim not in targets:
            targets.append(dim)
    return targets[: max(0, int(limit))]


def model_dimension_repair_instruction(layer: str, *, locale: str = "zh-TW") -> str:
    """Build a domain-neutral repair instruction for one SCBKR dimension."""
    layer = str(layer or "").upper()
    instructions_zh = {
        "S": "只修 S。content 必須寫清楚本規則的使用者或原始需求點名的主體、要處理的具體任務，以及何時觸發適用；不得寫因果流程、禁止事項、引用政策或簽名責任，也不得照抄這段指令。",
        "C": "只修 C。content 必須寫出原始需求的實際因果或判斷順序：有多步驟時用「先、再」，有條件結果時用「若、則」；兩者皆有時才需要同時寫入。把原始需求的具體事實填進去，不得照抄這段指令，也不得替使用者補最終決定。",
        "B": "只修 B。content 必須同時有一個從原始需求推導的具體「不得」行動，以及資料不足、未確認或越界時必須「停止並留在草稿」；把原始需求的具體事實填進去，不得照抄這段指令或新增案例。",
        "K": "只修 K。content 必須原樣使用 request_grounding_terms 中至少一個具體項目，寫明該資料經使用者確認後「可引用」；再寫未確認內容、聊天或模型猜測、未簽名草稿與 VECTOR 候選「不可引用」。不得只寫「原始需求中的資料」，不得拿 JSON 欄位名當依據，也不得新增原始需求沒有的具名來源。",
        "R": "只修 R。content 必須寫明「使用者或原始需求點名的負責人」驗收、承擔並簽名，出錯時修復與回放，且「模型不能簽名、入庫或啟用」；把原始需求的責任人填進去，不得照抄這段指令。",
    }
    instructions_en = {
        "S": "Edit S only. State the user or request-named subject, the concrete task governed by this rule, and the situation that triggers it. Do not write the causal process, prohibitions, citation policy, or signature responsibility, and do not copy this instruction.",
        "C": "Edit C only. State the actual causality or decision order from the request: use first/then for multiple steps and if/then for a conditional consequence. Use both only when the request contains both. Fill in concrete request facts; do not copy this instruction or invent the user's final decision.",
        "B": "Edit B only. The content must contain both one concrete 'must not' action derived from the original request and a 'stop and remain a draft' condition for missing, unconfirmed, or out-of-scope facts. Fill in concrete request facts; do not copy this instruction or add an example.",
        "K": "Edit K only. The content must repeat at least one concrete item from request_grounding_terms and say it 'may be cited' after user confirmation, then state that unconfirmed content, chat or model guesses, unsigned drafts, and VECTOR candidates 'may not be cited'. Do not say only 'facts from the original request', use JSON field names as evidence, or add a named source absent from the request.",
        "R": "Edit R only. The content must state that the user or request-named accountable person reviews, accepts responsibility, and signs; include repair and replay after failure; and state that the model cannot sign, store, or activate. Fill in the request's responsible person and do not copy this instruction.",
    }
    instructions = instructions_en if _is_english(locale) else instructions_zh
    if layer not in instructions:
        raise ValueError("layer must be S/C/B/K/R")
    return instructions[layer]


def build_model_basis_selection_messages(
    user_input: str,
    *,
    locale: str = "zh-TW",
) -> list[dict[str, str]]:
    """Ask a small model to select task-specific K evidence without policy prose."""
    candidate_terms = _grounding_candidates(user_input)
    if _is_english(locale):
        system = (
            "Select evidence or data nouns for one SCBKR K field. "
            "Choose only from candidate_terms. Do not add words, policy, JSON, actions, or an explanation."
        )
        task = "Return only candidate_terms that name checkable data, records, or evidence. Comma-separated, at most 3."
    else:
        system = (
            "你只負責挑出 SCBKR K 欄位的可核對資料名稱。"
            "只能從 candidate_terms 選擇，不得新增詞語、規則、JSON、動作或解釋。"
        )
        task = "只回傳可作為資料、紀錄或證據的 candidate_terms，最多三個，以頓號分隔。"
    payload = {
        "owner_request": user_input,
        "candidate_terms": candidate_terms,
        "task": task,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
    ]


def parse_model_basis_selection_output(
    text: str,
    *,
    user_input: str,
    locale: str = "zh-TW",
) -> list[str]:
    """Keep only request-grounded terms that the model actually selected."""
    normalized = normalize_locale_text(str(text or ""), locale).strip()
    if not normalized:
        raise ModelRulebookAuthoringError("k_basis_selection_empty")
    clause_markers = (
        "不得", "不能", "不可", "禁止", "停止", "生效", "簽名", "簽署",
        "發布", "公開", "引用", "適用", "建立", "若", "如果", "先", "再",
        "must not", "cannot", "do not", "stop", "activate", "sign", "publish",
        "cite", "apply", "create", "first", "then", "if ",
    )

    def normalized_term(value: str) -> str:
        return normalize_locale_text(str(value or ""), locale).strip().lower()

    readable_candidates = [
        candidate
        for candidate in _grounding_candidates(user_input)
        if not any(marker in normalized_term(candidate) for marker in clause_markers)
    ]
    selected: list[str] = []
    for raw_item in re.split(r"[,，、;\n]", normalized):
        item = raw_item.strip(" ：:()（）[]「」『』'\".。")
        if not item:
            continue
        normalized_item = normalized_term(item)
        exact = next(
            (
                candidate
                for candidate in readable_candidates
                if normalized_term(candidate) == normalized_item
            ),
            "",
        )
        if not exact and re.search(r"[\u3400-\u9fff]", item):
            containing = [
                candidate
                for candidate in readable_candidates
                if normalized_item in normalized_term(candidate)
                and len(candidate) <= len(item) + 2
            ]
            exact = min(containing, key=len) if containing else ""
        if exact and exact not in selected:
            selected.append(exact)
    if selected:
        return selected[:3]

    allowed = _semantic_terms(user_input)
    ignored = {
        "becomes", "first", "missing", "require", "reusable", "stop", "verify", "when",
    }
    positions: list[tuple[int, str]] = []
    lowered = normalized.lower()
    for term in allowed:
        if term in ignored:
            continue
        if re.fullmatch(r"[a-z][a-z0-9_-]*", term):
            match = re.search(rf"\b{re.escape(term)}\b", lowered, flags=re.IGNORECASE)
            index = match.start() if match else -1
        else:
            index = lowered.find(term.lower())
        if index >= 0:
            positions.append((index, term))
    selected = list(dict.fromkeys(term for _, term in sorted(positions)))[:3]
    if not selected:
        raise ModelRulebookAuthoringError("k_basis_selection_not_grounded")
    return selected


def compile_model_basis_selection_candidate(
    candidate: dict[str, Any],
    *,
    selected_terms: list[str],
    raw_model_output: str,
    locale: str = "zh-TW",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compile a model-selected K fragment with invariant citation boundaries."""
    repaired = json.loads(json.dumps(candidate, ensure_ascii=False))
    k_payload = repaired.get("K")
    if not isinstance(k_payload, dict) or not selected_terms:
        raise ModelRulebookAuthoringError("k_basis_selection_invalid")
    original = str(k_payload.get("content") or "").strip()
    separator = ", " if _is_english(locale) else "、"
    fragment = separator.join(selected_terms[:3])
    if _is_english(locale):
        content = (
            f"Owner-confirmed {fragment} may be cited; unconfirmed content, chat or model guesses, "
            "unsigned drafts, and VECTOR candidates may not be cited."
        )
        required_clauses = [
            "owner confirmation required before citation",
            "unconfirmed chat, model guesses, unsigned drafts, and VECTOR are non-citable",
        ]
    else:
        content = (
            f"使用者已確認的{fragment}可引用；未確認內容、聊天或模型猜測、"
            "未簽名草稿與 VECTOR 候選不可引用。"
        )
        required_clauses = [
            "引用前必須經使用者確認",
            "未確認聊天、模型猜測、未簽名草稿與 VECTOR 不可引用",
        ]
    k_payload["content"] = content
    k_payload["model_task_fragment"] = fragment
    k_payload["model_basis_selection_raw"] = str(raw_model_output or "")
    k_payload["model_original_content_before_kernel_compile"] = original
    k_payload["kernel_required_clauses"] = required_clauses
    k_payload["kernel_structure_compiled"] = True
    audit = {
        "code": "k_model_fragment_compiled_with_citation_boundary",
        "layer": "K",
        "model_selected_terms": selected_terms[:3],
        "model_raw_output": str(raw_model_output or ""),
        "original": original,
        "compiled": content,
        "source": "model_fragment_plus_kernel_invariant",
    }
    repaired.setdefault("kernel_structure_compiled_dimensions", [])
    if "K" not in repaired["kernel_structure_compiled_dimensions"]:
        repaired["kernel_structure_compiled_dimensions"].append("K")
    repaired.setdefault("kernel_structure_compile_audit", []).append(audit)
    repaired.setdefault(
        "model_semantic_valid_before_kernel_compile",
        bool(candidate.get("model_semantic_valid")),
    )
    return repaired, audit


def compile_kernel_required_clauses(
    candidate: dict[str, Any],
    *,
    user_input: str = "",
    locale: str = "zh-TW",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Append only universal Rule OS clauses after model task meaning exists."""
    repaired = json.loads(json.dumps(candidate, ensure_ascii=False))
    audits: list[dict[str, Any]] = []
    k_payload = repaired.get("K")
    if isinstance(k_payload, dict):
        original_k = str(k_payload.get("content") or "").strip()
        lowered_k = original_k.lower()
        k_has_citable = any(
            token in lowered_k
            for token in (
                "只可引用", "可引用", "只能使用", "正式依據",
                "may cite", "may be cited", "cite only", "formal basis",
            )
        )
        k_has_confirmation = any(
            token in lowered_k
            for token in (
                "使用者已確認", "使用者確認", "已確認", "正式資料",
                "owner-confirmed", "user-confirmed", "confirmed record", "confirmed data",
            )
        )
        k_has_non_citable = any(
            token in lowered_k
            for token in (
                "不可引用", "不得引用", "不能當正式依據", "不是正式依據",
                "recall only", "may not cite", "may not be cited", "must not cite", "must not be cited",
                "cannot cite", "cannot be cited", "not formal basis",
            )
        )
        grounded = (
            not _semantic_terms(user_input)
            or bool(_semantic_terms(user_input) & _semantic_terms(original_k))
        )
        signature_as_basis = bool(re.search(
            r"(?:引用|依據|cite|basis|source).{0,28}(?:簽名|審核|驗收|signature|review)",
            original_k,
            flags=re.IGNORECASE,
        ))
        if (
            original_k
            and grounded
            and k_has_citable
            and not signature_as_basis
            and not _unrequested_non_citable_sources(original_k, user_input)
            and (not k_has_confirmation or not k_has_non_citable)
        ):
            additions_k: list[str] = []
            if not k_has_confirmation:
                additions_k.append(
                    "The cited task material becomes a formal basis only after user confirmation"
                    if _is_english(locale)
                    else "前述任務資料須經使用者確認後才可作正式依據"
                )
            if not k_has_non_citable:
                additions_k.append(
                    "Unconfirmed content, chat or model guesses, unsigned drafts, and VECTOR candidates may not be cited"
                    if _is_english(locale)
                    else "未確認內容、聊天或模型猜測、未簽名草稿與 VECTOR 候選不可引用"
                )
            punctuation = "; " if _is_english(locale) else "；"
            compiled_k = original_k.rstrip("；;。 .") + punctuation + punctuation.join(additions_k) + "."
            k_payload["content"] = compiled_k
            k_payload["model_original_content_before_kernel_compile"] = original_k
            k_payload["kernel_required_clauses"] = additions_k
            k_payload["kernel_structure_compiled"] = True
            audits.append({
                "code": "k_model_fragment_compiled_with_citation_boundary",
                "layer": "K",
                "original": original_k,
                "compiled": compiled_k,
                "kernel_required_clauses": additions_k,
                "source": "model_fragment_plus_kernel_invariant",
            })

    b_payload = repaired.get("B")
    if isinstance(b_payload, dict):
        original_b = str(b_payload.get("content") or "").strip()
        lowered_b = original_b.lower()
        claims_no_boundary = any(
            token in lowered_b
            for token in (
                "沒有禁止", "無禁止", "未提及禁止", "沒有明確禁止",
                "no forbidden", "no specific forbidden", "no prohibition", "no explicit prohibition",
            )
        )
        b_has_prohibition = any(
            token in lowered_b
            for token in (
                "不得", "不能", "不可", "禁止", "不應",
                "must not", "cannot", "do not", "should not", "prohibit",
            )
        )
        b_has_stop = any(
            token in lowered_b
            for token in (
                "停止", "停在", "待確認", "未確認", "資料不足",
                "stop", "halt", "pending confirmation", "unconfirmed",
                "missing data", "records are missing", "draft",
            )
        )
        grounded = (
            not _semantic_terms(user_input)
            or bool(_semantic_terms(user_input) & _semantic_terms(original_b))
        )
        if (
            original_b
            and grounded
            and not claims_no_boundary
            and not _dimension_role_complete("B", original_b)
            and (b_has_prohibition or b_has_stop)
        ):
            if _is_english(locale):
                compiled_b = original_b
                clauses_b: list[str] = []
                if not b_has_prohibition:
                    compiled_b = (
                        "Do not proceed unless this model-authored task condition is satisfied: "
                        f"{original_b}"
                    )
                    clauses_b.append("the task must not proceed before its model-authored condition is satisfied")
                if not b_has_stop:
                    compiled_b = compiled_b.rstrip(" .;") + (
                        "; if required facts are missing, unconfirmed, or out of scope, stop and remain a draft"
                    )
                    clauses_b.append("missing, unconfirmed, or out-of-scope facts stop in draft")
            else:
                compiled_b = original_b
                clauses_b = []
                if not b_has_prohibition:
                    compiled_b = f"在符合下列模型草擬條件前不得繼續：{original_b}"
                    clauses_b.append("未符合模型草擬條件前不得繼續")
                if not b_has_stop:
                    compiled_b = compiled_b.rstrip("。；") + "；必要資料缺少、未確認或越界時必須停止並留在草稿"
                    clauses_b.append("缺少、未確認或越界時停止在草稿")
            b_payload["content"] = compiled_b
            b_payload["model_original_content_before_kernel_compile"] = original_b
            b_payload["kernel_required_clauses"] = clauses_b
            b_payload["kernel_structure_compiled"] = True
            audits.append({
                "code": "b_model_fragment_compiled_with_stop_boundary",
                "layer": "B",
                "original": original_b,
                "compiled": compiled_b,
                "kernel_required_clauses": clauses_b,
                "source": "model_fragment_plus_kernel_invariant",
            })

    r_payload = repaired.get("R")
    if isinstance(r_payload, dict):
        original_r = str(r_payload.get("content") or "").strip()
        if original_r and _responsibility_owner_signs(original_r):
            lowered_r = original_r.lower()
            additions_r: list[str] = []
            has_model_boundary = any(
                token in lowered_r
                for token in ("模型不能", "模型不得", "模型無法", "model cannot", "model must not")
            )
            has_repair_replay = (
                any(token in lowered_r for token in ("修復", "修正", "repair"))
                and any(token in lowered_r for token in ("回放", "重播", "replay"))
            )
            if not has_repair_replay:
                additions_r.append(
                    "After a failure, the user repairs and replays the decision before signing again"
                    if _is_english(locale)
                    else "失敗後由使用者修復並回放判斷，再重新簽名"
                )
            if not has_model_boundary:
                additions_r.append(
                    "The model cannot sign, store, approve, or activate this rule"
                    if _is_english(locale)
                    else "模型不能簽名、入庫、核准或啟用此規則"
                )
            if additions_r:
                punctuation = "; " if _is_english(locale) else "；"
                compiled_r = original_r.rstrip("；;。 .") + punctuation + punctuation.join(additions_r) + "."
                r_payload["content"] = compiled_r
                r_payload["model_original_content_before_kernel_compile"] = original_r
                r_payload["kernel_required_clauses"] = additions_r
                r_payload["kernel_structure_compiled"] = True
                audits.append({
                    "code": "r_model_fragment_compiled_with_authority_boundary",
                    "layer": "R",
                    "original": original_r,
                    "compiled": compiled_r,
                    "kernel_required_clauses": additions_r,
                    "source": "model_fragment_plus_kernel_invariant",
                })

    if audits:
        repaired.setdefault("kernel_structure_compiled_dimensions", [])
        repaired.setdefault("kernel_structure_compile_audit", [])
        for audit in audits:
            layer = audit["layer"]
            if layer not in repaired["kernel_structure_compiled_dimensions"]:
                repaired["kernel_structure_compiled_dimensions"].append(layer)
            repaired["kernel_structure_compile_audit"].append(audit)
        repaired.setdefault(
            "model_semantic_valid_before_kernel_compile",
            bool(candidate.get("model_semantic_valid")),
        )
    return repaired, audits


def merge_model_dimension_patch_candidate(
    candidate: dict[str, Any],
    *,
    layer: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Merge one model-authored repair into a candidate and its support fields."""
    layer = str(layer or "").upper()
    if layer not in DIMENSIONS:
        raise ValueError("layer must be S/C/B/K/R")
    merged = json.loads(json.dumps(candidate, ensure_ascii=False))
    merged[layer] = {
        "content": patch["content"],
        "explanation": patch["explanation"],
        "missing_information": _as_list(patch.get("missing_information")),
        "needs_user_confirmation": _as_list(patch.get("needs_user_confirmation")),
        "model_cannot_decide": _as_list(patch.get("model_cannot_decide")),
        "risk_notes": _as_list(patch.get("risk_notes")),
    }
    support_map = {
        "missing_information": "missing_information",
        "needs_user_confirmation": "user_confirmation_items",
        "model_cannot_decide": "model_cannot_decide",
        "risk_notes": "risk_reminders",
    }
    for patch_key, global_key in support_map.items():
        combined = [
            *[str(item).strip() for item in _as_list(merged.get(global_key)) if str(item).strip()],
            *[str(item).strip() for item in _as_list(patch.get(patch_key)) if str(item).strip()],
        ]
        merged[global_key] = list(dict.fromkeys(combined))[:10]
    return merged


def build_model_capability_assessment(
    report: dict[str, Any],
    *,
    attempts: int,
    targeted_repair_attempted: bool = False,
    locale: str = "zh-TW",
    model_name: str = "",
) -> dict[str, Any]:
    """Describe a task-scoped capability limit without judging model speed.

    A local small model may understand SCBKR and remain useful for later signed
    rule-package execution while still failing to close a complex rulebook in
    this authoring run. Escalation is therefore based only on unresolved SCBKR
    structure, grounding, or evidence roles, never elapsed time.
    """
    codes = semantic_gap_codes(report)
    en = _is_english(locale)
    labels = {
        "dimensions_not_distinct": (
            "Two or more SCBKR dimensions contain the same judgement.",
            "兩個以上的 SCBKR 維度寫成相同判斷，尚未分工。",
        ),
        "request_not_grounded": (
            "The draft does not preserve enough facts from the user's request.",
            "草稿沒有保留足夠的使用者原始需求內容。",
        ),
        "s_role_unresolved": (
            "S does not identify the task subject or trigger from the user's request.",
            "S 沒有寫出使用者需求中的任務主體與觸發情境。",
        ),
        "copied_field_definitions": (
            "The model copied SCBKR field names instead of applying them to this task.",
            "模型只抄了 SCBKR 欄位名稱，尚未套用到本次任務。",
        ),
        "unresolved_placeholders": (
            "One or more dimensions still contain an instruction skeleton or placeholder.",
            "一個以上維度仍保留提示骨架或佔位符，尚未寫成本次任務內容。",
        ),
        "model_explanations_missing": (
            "The model did not write a task-specific explanation for every SCBKR dimension.",
            "模型沒有為每個 SCBKR 維度寫出本次任務專用的解釋。",
        ),
        "c_b_roles_overlapping": (
            "C repeats B prohibitions instead of describing a separate decision path.",
            "C 大量重複 B 的禁止事項，沒有形成獨立判斷路徑。",
        ),
        "unrequested_identity_injection": (
            "The draft inserted the product author as the user's rule subject without permission.",
            "草稿未經要求就把產品作者放成使用者規則主體。",
        ),
        "k_signature_as_basis": (
            "K treats a signature or review as source evidence instead of keeping it in R.",
            "K 把簽名或審核誤當資料依據；這些責任條件應留在 R。",
        ),
        "k_unrequested_source_restriction": (
            "K added a named source restriction that the owner never requested.",
            "K 自行新增使用者未指定的具名文件或來源限制。",
        ),
        "support_fields_missing": (
            "The model omitted the summary, confirmation items, limitations, risks, or next actions.",
            "模型漏寫摘要、確認項目、不可自行判斷事項、風險或下一步。",
        ),
        "c_role_unresolved": (
            "C still lacks a causal path or decision order.",
            "C 因果仍缺少成立原因或判斷先後順序。",
        ),
        "b_role_unresolved": (
            "B still lacks a boundary, prohibition, exception, or stop condition.",
            "B 邊界仍缺少限制、禁止、例外或停止條件。",
        ),
        "k_role_unresolved": (
            "K still lacks confirmed evidence, citable sources, or non-citable sources.",
            "K 依據仍缺少已確認證據、可引用來源或不可引用項目。",
        ),
        "r_role_unresolved": (
            "R still lacks responsibility, review, repair, or owner-signature conditions.",
            "R 責任仍缺少承擔者、驗收、修復或使用者簽名條件。",
        ),
        "model_authority_overreach": (
            "The draft gives the model signature, review, approval, storage, or activation authority.",
            "草稿把簽名、驗收、核准、入庫或啟用權限錯交給模型。",
        ),
    }
    gaps = [labels[code][0 if en else 1] for code in codes]
    stronger_recommended = bool(codes) and (attempts >= 2 or targeted_repair_attempted)
    if en:
        summary = (
            "This model understands the SCBKR draft structure, but this task is not closed yet. "
            "The draft is preserved for review and cannot be signed or stored."
        )
        recommendation = (
            "Add the missing facts, or select a stronger model for one authoring pass. "
            "After the owner signs and compiles the result, a smaller model can reuse the minimal signed rule package."
        )
    else:
        summary = "此模型具備 SCBKR 草擬能力，但本次任務尚未閉合；草稿會保留供檢查，不能簽名或入庫。"
        recommendation = "請補充缺少資料，或改用較強模型完成一次補鏈收束；使用者簽名編譯後，小模型即可重用最小已簽名規則包。"
    return {
        "state": "task_draft_only",
        "model_baseline": "scbkr_draft_capable",
        "current_task_closure": False,
        "model_name": model_name,
        "attempts": attempts,
        "targeted_repair_attempted": targeted_repair_attempted,
        "gap_codes": codes,
        "unresolved_gaps": gaps,
        "summary": summary,
        "recommended_action": recommendation,
        "stronger_model_recommended": stronger_recommended,
        "escalation_basis": "unresolved_scbkr_structure_gaps" if codes else "none",
        "latency_triggered": False,
        "automatic_cloud_escalation": False,
        "owner_decision_required": True,
        "signed_rule_small_model_reuse_supported": True,
    }


def build_semantic_repair_instruction(report: dict[str, Any], *, locale: str = "zh-TW") -> str:
    """Build role-specific retry feedback without supplying domain answers."""
    codes = semantic_gap_codes(report)
    en = _is_english(locale)
    role_hints_en = {
        "dimensions_not_distinct": "Make every dimension a different judgement.",
        "request_not_grounded": "Preserve concrete people, objects, conditions, and facts from the user request.",
        "s_role_unresolved": "S must identify the task, affected actor, and trigger from the user's request.",
        "copied_field_definitions": "Do not repeat field definitions; write task-specific judgements.",
        "unresolved_placeholders": "Replace every instruction skeleton, ellipsis, and slash-choice with task-specific rule text.",
        "model_explanations_missing": "Return every S/C/B/K/R value as an object containing task-specific content and explanation.",
        "c_b_roles_overlapping": "Rewrite C as ordered checks and consequences; move repeated prohibitions to B only.",
        "unrequested_identity_injection": "The product author is not the local user's rule owner. Use 'the user' unless the request names someone else.",
        "k_signature_as_basis": "A signature belongs in R, not K. K must name confirmed records or facts and non-citable guesses.",
        "k_unrequested_source_restriction": "Remove every named document or source restriction absent from the original request. Non-citable material may only be unconfirmed content, chat or model guesses, unsigned drafts, or VECTOR candidates.",
        "support_fields_missing": "Include every required global field with concise task-specific items, including risks and owner confirmations.",
        "c_role_unresolved": (
            "Rewrite C as an actual causal or decision path: use 'first ... then ...' for ordered checks "
            "or 'if ... then ...' for a conditional consequence. Move prohibitions such as 'must not' "
            "or 'cannot' to B instead of using them as C."
        ),
        "b_role_unresolved": "B must contain both a prohibition and a stop condition for missing or unconfirmed data.",
        "k_role_unresolved": "K must say what owner-confirmed material may be cited and what may not be cited.",
        "r_role_unresolved": "R must name the user as accountable signer and explicitly say the model cannot sign.",
        "model_authority_overreach": "No summary, dimension, explanation, or support field may give the model signature, review, approval, storage, or activation authority; those actions remain with the user.",
    }
    role_hints_zh = {
        "dimensions_not_distinct": "每一維都必須是不同判斷，不得重複同一句。",
        "request_not_grounded": "保留使用者需求中的具體人物、事項、條件與事實。",
        "s_role_unresolved": "S 必須寫出使用者需求中的任務、相關主體與觸發情境。",
        "copied_field_definitions": "不得重抄欄位定義，必須寫成本次任務的具體判斷。",
        "unresolved_placeholders": "把所有句型骨架、省略號與斜線選項改成本次任務的完整規則文字。",
        "model_explanations_missing": "S／C／B／K／R 每一維都必須回傳含本次任務具體 content 與 explanation 的物件。",
        "c_b_roles_overlapping": "C 只寫判斷順序與結果；重複的禁止事項全部移到 B。",
        "unrequested_identity_injection": "產品作者不是本地使用者的規則主體；除非原始需求點名，請一律寫「使用者」。",
        "k_signature_as_basis": "簽名屬於 R，不是 K。K 要寫已確認資料或紀錄，以及不可引用的猜測。",
        "k_unrequested_source_restriction": "移除原始需求沒有點名的文件或來源限制；不可引用項目只能是未確認內容、聊天或模型猜測、未簽名草稿與 VECTOR 候選。",
        "support_fields_missing": "必須補齊所有全域欄位，包含摘要、風險、使用者確認項目、模型不可判斷事項與下一步。",
        "c_role_unresolved": (
            "C 必須改寫成真正的因果或判斷路徑：多步驟用「先……再……」，條件結果用「若……則……」。"
            "「不得／禁止／不能」等限制要放到 B，不得拿來代替 C。"
        ),
        "b_role_unresolved": "B 必須同時寫禁止事項，以及資料不足或未確認時的停止條件。",
        "k_role_unresolved": "K 必須寫可引用的使用者已確認資料，以及不可引用的聊天猜測或候選資料。",
        "r_role_unresolved": "R 必須寫由使用者承擔與簽名，並明列模型不能簽名。",
        "model_authority_overreach": "摘要、五維與補充欄都不得宣稱模型可簽名、驗收、核准、入庫或啟用；這些權限只屬於使用者。",
    }
    hints = role_hints_en if en else role_hints_zh
    details = " ".join(hints[code] for code in codes if code in hints)
    if en:
        return (
            "The previous JSON is a usable SCBKR draft attempt but did not close the five semantic roles. "
            f"{details} Rewrite the complete object from the user's actual request, do not invent missing evidence, "
            "include all required global fields, and return JSON only."
        )
    return f"上一版是可保留的 SCBKR 草擬嘗試，但五維尚未閉合。{details} 請依使用者原始需求重寫完整物件並補齊所有全域欄位；缺少證據時要明列缺口，不得編造，只回 JSON。"


def _contains_overreach(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False).lower()
    structured_forbidden = (
        '"signature_status":"owner_signed"',
        '"signature_status": "owner_signed"',
        '"confirmed":true',
        '"confirmed": true',
        '"storage_confirmed":true',
        '"storage_confirmed": true',
        '"physical_write_performed":true',
        '"physical_write_performed": true',
    )
    if any(token in text for token in structured_forbidden):
        return True
    natural_claims = (
        "規則已成立",
        "已完成簽名",
        "已完成入庫",
        "已正式啟用",
        "owner signed",
        "stored successfully",
        "rule activated",
    )
    negations = ("不得", "不能", "不可", "尚未", "並未", "未", "not", "never", "cannot", "must not")
    for claim in natural_claims:
        offset = 0
        while True:
            index = text.find(claim, offset)
            if index < 0:
                break
            prefix = text[max(0, index - 24) : index]
            if not any(token in prefix for token in negations):
                return True
            offset = index + len(claim)
    return False


def _extract_json_object(text: str) -> dict[str, Any]:
    value = (text or "").strip()
    if not value:
        raise ModelRulebookAuthoringError("empty_model_output")
    if "```" in value:
        for part in value.split("```"):
            candidate = part.strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{"):
                value = candidate
                break
    start = value.find("{")
    if start < 0:
        raise ModelRulebookAuthoringError("json_object_not_found")
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(value)):
        ch = value[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(value[start : index + 1])
                    except json.JSONDecodeError as exc:
                        raise ModelRulebookAuthoringError("invalid_json") from exc
                    if not isinstance(parsed, dict):
                        raise ModelRulebookAuthoringError("json_root_must_be_object")
                    return parsed
    raise ModelRulebookAuthoringError("unterminated_json_object")


def model_rulebook_response_format() -> dict[str, Any]:
    # Flat strings keep constrained decoding tractable on CPU-only 1-2B local
    # models. The parser rehydrates this into the editable nested rulebook.
    # Every value is still authored by the connected model.
    required = [
        "S", "S_explanation",
        "C", "C_explanation",
        "B", "B_explanation",
        "K", "K_explanation",
        "R", "R_explanation",
        "rule_summary",
        "missing_information",
        "user_confirmation_items",
        "model_cannot_decide",
        "risk_reminders",
        "next_actions",
    ]
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "scbkr_model_rulebook_authoring",
            "strict": True,
            "schema": {
                "type": "object",
                "required": required,
                "properties": {
                    key: {"type": "string", "minLength": 4}
                    for key in required
                },
                "additionalProperties": False,
            },
        },
    }


def model_dimension_patch_response_format() -> dict[str, Any]:
    """OpenAI-compatible response schema for one model-authored SCBKR edit."""
    required = [
        "content",
        "explanation",
        "missing_information",
        "needs_user_confirmation",
        "model_cannot_decide",
        "risk_notes",
    ]
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "scbkr_model_dimension_patch",
            "strict": True,
            "schema": {
                "type": "object",
                "required": required,
                "properties": {
                    key: {"type": "string", "minLength": 4}
                    for key in required
                },
                "additionalProperties": False,
            },
        },
    }


def model_dimension_explanation_response_format() -> dict[str, Any]:
    """OpenAI-compatible schema for a model-authored human explanation only."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "scbkr_model_dimension_explanation",
            "strict": True,
            "schema": {
                "type": "object",
                "required": ["explanation"],
                "properties": {
                    "explanation": {"type": "string", "minLength": 8},
                },
                "additionalProperties": False,
            },
        },
    }


def build_model_dimension_explanation_messages(
    user_input: str,
    *,
    layer: str,
    current_content: str,
    locale: str = "zh-TW",
) -> list[dict[str, str]]:
    """Ask the model to explain one accepted dimension without rewriting it."""
    layer = str(layer or "").upper()
    roles = {
        "S": ("Subject and Situation", "主體與情境"),
        "C": ("Causality and Decision Order", "因果與判斷順序"),
        "B": ("Boundaries and Stop Conditions", "邊界與停止條件"),
        "K": ("Basis and Citation Authority", "依據與引用權限"),
        "R": ("Responsibility and Human Signature", "責任與人類簽名"),
    }
    if layer not in roles:
        raise ValueError("layer must be S/C/B/K/R")
    if _is_english(locale):
        system = (
            f"Explain only SCBKR dimension {layer}: {roles[layer][0]}. "
            "Do not rewrite, extend, approve, sign, store, or activate the rule content. "
            "Explain in one short plain-language sentence why the supplied task-specific content belongs in this dimension. "
            "Mention at least one concrete task item from current_content. Return JSON with only the key explanation."
        )
    else:
        system = (
            f"你只負責解釋 SCBKR 的 {layer} 欄：{roles[layer][1]}。"
            "不得重寫、擴張、核准、簽名、入庫或啟用規則內容。"
            "請用一個簡短人話句子，說明這段任務專用內容為何屬於本欄，並提到 current_content 至少一個具體任務項目。"
            "只能回傳 explanation 一個鍵的 JSON。使用繁體中文。"
        )
    payload = {
        "original_rule_request": user_input,
        "dimension": layer,
        "dimension_role": roles[layer][0 if _is_english(locale) else 1],
        "current_content": str(current_content or "").strip(),
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
    ]


def parse_model_dimension_explanation_output(
    text: str,
    *,
    layer: str,
    current_content: str,
    user_input: str = "",
    locale: str = "zh-TW",
) -> str:
    """Validate one human explanation while keeping accepted rule content fixed."""
    layer = str(layer or "").upper()
    if layer not in DIMENSIONS:
        raise ModelRulebookAuthoringError("invalid_dimension")
    normalized = normalize_locale_text(text, locale).strip()
    try:
        parsed = _extract_json_object(normalized)
        if _contains_overreach(parsed):
            raise ModelRulebookAuthoringError("model_overreach_signature_or_storage")
        explanation = str(parsed.get("explanation") or "").strip()
    except ModelRulebookAuthoringError as exc:
        if str(exc) != "json_object_not_found":
            raise
        match = re.match(r"^\s*explanation\s*:\s*(.+?)\s*$", normalized, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            raise
        explanation = match.group(1).strip()
        if explanation.startswith('"'):
            explanation = explanation[1:]
        if explanation.endswith('"'):
            explanation = explanation[:-1]
        explanation = explanation.strip()
    if len(explanation) < 8:
        raise ModelRulebookAuthoringError(f"{layer.lower()}_explanation_missing")
    grounding_terms = _semantic_terms(f"{current_content} {user_input}")
    explanation_terms = _semantic_terms(explanation)
    if grounding_terms and not grounding_terms.intersection(explanation_terms):
        raise ModelRulebookAuthoringError(f"{layer.lower()}_explanation_not_grounded")
    return explanation


def merge_model_dimension_explanation_candidate(
    candidate: dict[str, Any],
    *,
    layer: str,
    explanation: str,
) -> dict[str, Any]:
    """Attach a model-authored explanation without changing rule content."""
    layer = str(layer or "").upper()
    if layer not in DIMENSIONS:
        raise ValueError("layer must be S/C/B/K/R")
    merged = json.loads(json.dumps(candidate, ensure_ascii=False))
    payload = merged.get(layer)
    if not isinstance(payload, dict) or not str(payload.get("content") or "").strip():
        raise ModelRulebookAuthoringError(f"{layer}_missing_content")
    payload["explanation"] = str(explanation or "").strip()
    payload["model_explanation_repaired_by_model"] = True
    return merged


def build_model_dimension_patch_messages(
    user_input: str,
    *,
    layer: str,
    instruction: str,
    current_dimension: dict[str, Any] | None = None,
    locale: str = "zh-TW",
    compact: bool = False,
) -> list[dict[str, str]]:
    """Build a minimal, task-scoped model request for one editable dimension."""
    layer = str(layer or "").upper()
    if layer not in DIMENSIONS:
        raise ValueError("layer must be S/C/B/K/R")
    roles = {
        "S": "Subject and Situation: who, what, and when this rule applies",
        "C": "Causality and Decision Order: why it applies and what is checked first, next, and last",
        "B": "Boundaries, Prohibitions, Exceptions, and Stop Conditions",
        "K": "Basis and Citable Sources, including what cannot be cited",
        "R": "Responsibility, Acceptance, Repair/Replay, and Owner Signature Conditions",
    }
    roles_zh = {
        "S": "主體與情境：誰、什麼事、何時適用",
        "C": "因果與判斷順序：為什麼成立、先判什麼再判什麼",
        "B": "邊界、禁止、例外與停止條件",
        "K": "依據與可引用來源，並寫清楚不可引用項目",
        "R": "責任、驗收、修復回放與使用者簽名條件",
    }
    if compact:
        output_contract = {
            "content": "one complete task-specific rule statement for this dimension",
            "explanation": "why this statement belongs in this dimension",
        }
        output_rule_en = (
            "Return exactly one flat object with only the keys content and explanation. "
            "Do not rename content to rule_content. Both values must be short natural-language strings."
        )
        output_rule_zh = (
            "只能回傳一個扁平物件，而且只能有 content 與 explanation 兩個鍵；"
            "不得把 content 改名為 rule_content。兩個值都必須是人話短字串。"
        )
    else:
        output_contract = {
            "content": "one complete task-specific rule statement for this dimension",
            "explanation": "why this statement belongs in this dimension",
            "missing_information": "facts still missing, or none",
            "needs_user_confirmation": "what the user must confirm",
            "model_cannot_decide": "the final judgement reserved for the user",
            "risk_notes": "one concrete risk, or none",
        }
        output_rule_en = (
            "Return exactly one flat object with the keys content, explanation, missing_information, "
            "needs_user_confirmation, model_cannot_decide, and risk_notes. Do not rename content to rule_content. "
            "Every value must be a short natural-language string; use semicolons for at most two items."
        )
        output_rule_zh = (
            "只能回傳一個扁平物件，鍵名必須是 content、explanation、missing_information、"
            "needs_user_confirmation、model_cannot_decide、risk_notes，不得把 content 改名為 rule_content。"
            "每個值都用人話短字串，多項用分號隔開。"
        )
    current = current_dimension or {}
    compact_current = {
        key: current.get(key)
        for key in (
            "task_subject",
            "core_logic",
            "forbidden",
            "stop_conditions",
            "references",
            "citable_sources",
            "non_citable_sources",
            "real_world_responsibility",
            "acceptance_criteria",
            "model_draft_content",
            "model_explanation",
            "missing_information",
            "needs_user_confirmation",
        )
        if current.get(key) not in (None, "", [], {})
    }
    if _is_english(locale):
        system = (
            f"You are editing only SCBKR dimension {layer}: {roles[layer]}. "
            "Apply the owner's instruction to the actual rule request and current dimension. Return JSON only. "
            "Write concrete rule content, not a definition of the field. Do not edit another dimension. "
            "The content must repeat at least one concrete item from request_grounding_terms; "
            "generic phrases such as 'facts from the original request' are not grounded. "
            "You may draft and explain, but you cannot sign, confirm, store, activate, publish, send, pay, delete, or execute tools. "
            "Chat history and VECTOR are not formal authority. "
            f"{output_rule_en}"
        )
    else:
        system = (
            f"你是 SCBKR 確認單的單欄草擬員。本次只能修改 {layer}：{roles_zh[layer]}。"
            "請把使用者修改指令真正套用到原始規則與目前欄位，僅回傳 JSON。"
            "必須寫本次任務的具體規則內容，不得只解釋欄位定義，也不得偷改其他維度。"
            "content 至少必須原樣使用 request_grounding_terms 中一個具體項目；"
            "只寫「原始需求中的資料」不算有對齊。"
            "你只能草擬與解釋，不能簽名、確認、入庫、啟用、發布、寄送、付款、刪除或執行工具。"
            "聊天歷史與 VECTOR 不是正式依據。"
            f"{output_rule_zh}使用繁體中文。"
        )
    payload = {
        "original_rule_request": user_input,
        "request_grounding_terms": _grounding_candidates(user_input)[:16],
        "dimension": layer,
        "dimension_role": roles[layer] if _is_english(locale) else roles_zh[layer],
        "owner_edit_instruction": instruction,
        "current_dimension": compact_current,
        "output_contract": output_contract,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
    ]


def parse_model_dimension_patch_output(
    text: str,
    *,
    layer: str,
    instruction: str = "",
    user_input: str = "",
    locale: str = "zh-TW",
    require_complete_role: bool = False,
) -> dict[str, Any]:
    """Parse one model-authored dimension and reject role-confused edits."""
    layer = str(layer or "").upper()
    if layer not in DIMENSIONS:
        raise ModelRulebookAuthoringError("invalid_dimension")
    parsed = _extract_json_object(text)
    if _contains_overreach(parsed):
        raise ModelRulebookAuthoringError("model_overreach_signature_or_storage")
    authority_text = json.dumps(parsed, ensure_ascii=False).lower()
    direct_overreach = (
        "不需要使用者確認", "不需要用戶確認", "無需使用者確認",
        "no user confirmation", "未簽名則視為同意", "未簽名視為同意",
    )
    authority_claims = (
        "模型可以決定", "模型可自行決定", "模型有權決定",
        "model can decide", "model may decide",
    )
    has_authority_claim = False
    for claim in authority_claims:
        offset = 0
        while True:
            index = authority_text.find(claim, offset)
            if index < 0:
                break
            prefix = authority_text[max(0, index - 20):index]
            if not any(token in prefix for token in ("不得說", "不能說", "不可說", "不得", "不能", "不可", "never say", "must not say", "cannot say")):
                has_authority_claim = True
                break
            offset = index + len(claim)
        if has_authority_claim:
            break
    if any(token in authority_text for token in direct_overreach) or has_authority_claim:
        raise ModelRulebookAuthoringError("model_overreach_owner_authority")
    value = parsed.get(layer) if isinstance(parsed.get(layer), dict) else parsed
    normalized = _canonicalize_compact_dimension(value, layer, locale)
    payload = _dim_payload({layer: normalized}, layer)
    for key in ("missing_information", "needs_user_confirmation", "model_cannot_decide", "risk_notes"):
        payload[key] = [item for item in payload[key] if _has_meaningful_items([item])]
    content = payload["content"].lower()
    promoted_from_field = ""
    if layer in ROLE_SIGNALS and not any(signal in content for signal in ROLE_SIGNALS[layer]):
        candidates: list[tuple[str, str]] = [("explanation", payload["explanation"])]
        for support_key in ("missing_information", "needs_user_confirmation", "model_cannot_decide", "risk_notes"):
            candidates.extend((support_key, item) for item in payload[support_key])
        for source_key, source_text in candidates:
            if any(signal in source_text.lower() for signal in ROLE_SIGNALS[layer]):
                original_content = payload["content"]
                payload["content"] = source_text
                if source_key == "explanation":
                    payload["explanation"] = original_content
                else:
                    payload[source_key] = [item for item in payload[source_key] if item != source_text]
                content = payload["content"].lower()
                promoted_from_field = source_key
                break
        if not promoted_from_field:
            raise ModelRulebookAuthoringError(f"{layer.lower()}_role_unresolved")
    instruction_terms = _semantic_terms(instruction)
    user_terms = _semantic_terms(user_input)
    grounding_terms = user_terms or instruction_terms
    output_terms = _semantic_terms(payload["content"])
    if grounding_terms and not grounding_terms.intersection(output_terms):
        raise ModelRulebookAuthoringError("patch_not_grounded_in_owner_instruction")
    if require_complete_role and not _dimension_role_complete(layer, payload["content"]):
        raise ModelRulebookAuthoringError(f"{layer.lower()}_role_incomplete")
    return {
        **payload,
        "model_schema_valid": True,
        "model_semantic_valid": True,
        "model_schema_repaired": bool(normalized.get("schema_adapter_generated")),
        "model_content_promoted_from_explanation": promoted_from_field == "explanation",
        "model_content_promoted_from_field": promoted_from_field,
        "matched_instruction_terms": sorted(grounding_terms.intersection(output_terms))[:12],
    }


def apply_model_dimension_patch(
    current_dimension: dict[str, Any] | None,
    *,
    layer: str,
    patch: dict[str, Any],
    model_provider: str = "",
    model_name: str = "",
) -> dict[str, Any]:
    """Map model-authored human content into fields used by local compilation."""
    layer = str(layer or "").upper()
    if layer not in DIMENSIONS:
        raise ValueError("layer must be S/C/B/K/R")
    after = dict(current_dimension or {})
    content = str(patch.get("content") or "").strip()
    explanation = str(patch.get("explanation") or "").strip()
    missing = _as_list(patch.get("missing_information"))
    confirmations = _as_list(patch.get("needs_user_confirmation"))
    cannot_decide = _as_list(patch.get("model_cannot_decide"))
    risks = _as_list(patch.get("risk_notes"))
    after.update({
        "model_draft_content": content,
        "model_explanation": explanation,
        "model_schema_adapter_generated": False,
        "model_explanation_derived_from_fields": False,
        "missing_information": missing,
        "needs_user_confirmation": confirmations,
        "model_cannot_decide": cannot_decide,
        "risk_notes": risks,
        "pending_questions": confirmations + missing,
        "user_confirm_required": True,
        "model_patch": {
            "model_used": True,
            "model_provider": model_provider,
            "model_name": model_name,
            "model_schema_valid": True,
            "model_semantic_valid": True,
        },
        "rule_os_dimension_contract": {
            "requires_user_confirmation": True,
            "usage_conditions": [explanation],
            "gap_notes": missing or ["使用者仍需確認此欄位。"],
        },
    })
    if layer == "S":
        after.update({"task_subject": content[:160], "rule_subject": content[:160], "applies_when": [content]})
    elif layer == "C":
        after.update({"core_logic": content, "causal_chain": [content, explanation], "why_rule_needed": explanation})
        after["flow_steps"] = [content, "使用者確認修改", "重新通過 Kernel Validator 後簽名"]
    elif layer == "B":
        invariants = [
            item for item in _as_list(after.get("forbidden"))
            if "模型不得" in item or "chat" in item.lower() or "vector" in item.lower() or "聊天上下文" in item
        ]
        after["forbidden"] = [content, *invariants]
        after["stop_conditions"] = [content, *confirmations, *missing]
    elif layer == "K":
        after["references"] = ["使用者原始規則需求", "SCBKR Kernel Pack", content]
        after["source_credibility"] = content
        after["evidence_policy"] = "signed_four_store_required_for_formal_citation"
    else:
        after["real_world_responsibility"] = content
        after["acceptance_criteria"] = [content, *confirmations]
        after["owner_signature_required"] = True
        after["model_signature_allowed"] = False
        after["required_signer"] = "user"
    return after


def build_model_rulebook_messages(
    user_input: str,
    *,
    kernel_pack: dict[str, Any],
    plan_level: str = "FREE",
    locale: str = "zh-TW",
) -> list[dict[str, str]]:
    language_rule = "Use English." if str(locale).lower().startswith("en") else "使用繁體中文。"
    identity_guard = (
        "Never mention the product author, kernel author, kernel name, or SCBKR itself inside rule fields unless the request explicitly names them."
        if _is_english(locale)
        else "除非使用者原始需求明確點名，規則欄位內不得寫入產品作者、Kernel 作者、Kernel 名稱或 SCBKR 名稱。"
    )
    uncertainty_guard = (
        "If the request does not specify the final action or threshold, do not invent it: list it as missing information and make B stop pending user confirmation."
        if _is_english(locale)
        else "若原始需求沒有說明最終動作或判斷門檻，不得自行補結論；必須列為缺少資訊，並在 B 寫成等待使用者確認的停止條件。"
    )
    role_contract = (
        "SCBKR is a five-dimension responsibility chain, not five abbreviations or a prose template. "
        "S means Subject and Situation: identify who, what, and when the rule applies. "
        "C means Causality and Decision Order: explain why and list the ordered checks or consequences. "
        "B means Boundaries, Prohibitions, and Stops: state limits, exceptions, forbidden actions, and stop conditions. "
        "K means Key/Basis and Citable Sources: state evidence, source authority, citable material, and non-citable material. "
        "R means Responsibility, Review, and Signature: state who is accountable, acceptance criteria, repair/replay, and owner signature conditions. "
        "Never swap dimensions, especially B and K. Never copy generic field definitions as the answer; apply every dimension to the user's actual request."
        if _is_english(locale)
        else "SCBKR 是五維責任鏈，不是五個縮寫或說明文模板。S＝主體與情境，必須寫誰、什麼事、何時適用；C＝因果與判斷順序，必須寫為什麼成立、先判什麼再判什麼、條件造成何種結果；B＝邊界、禁止與停止，必須寫限制、例外、禁止事項與停止條件；K＝依據與可引用來源，必須寫證據、來源權威、可引用與不可引用資料；R＝責任、驗收與簽名，必須寫誰承擔、怎樣驗收、如何修復回放及誰能簽名。五維不得互換，尤其 B 與 K 不得互換；不得只抄欄位定義，必須逐維套用到使用者的實際需求。"
    )
    compact_contract = (
        "Return exactly one flat JSON object with these string fields: S, S_explanation, C, C_explanation, "
        "B, B_explanation, K, K_explanation, R, R_explanation, rule_summary, missing_information, "
        "user_confirmation_items, model_cannot_decide, risk_reminders, next_actions. Separate multiple items with semicolons. "
        "Replace every instruction with task-specific text; "
        "never output placeholders. Use these sentence grammars: S identifies the actor, task, and trigger; "
        "C states the actual causality or decision order: use 'first/then' for multiple steps, "
        "'if/then' for a conditional consequence, and both only when both exist; C contains a decision path, not prohibitions; "
        "B writes one specific forbidden action from the request plus a stop condition. "
        "K names which owner-confirmed records from the request may be cited, and says unconfirmed content, "
        "chat or model guesses, unsigned drafts, and VECTOR candidates may not be cited. "
        "K must never add or exclude a named document or source type absent from the request; its non-citable clause is limited to "
        "unconfirmed content, chat or model guesses, unsigned drafts, and VECTOR candidates. "
        "R names who is accountable, who reviews and signs, how failure is repaired, and literally states that the model cannot sign. "
        "First-person words in rule_request such as 'I', 'me', and 'my' always refer to the human user, never the model; "
        "rewrite 'I sign' as 'the user signs'. "
        "Every support field must be non-empty and task-specific: missing_information names a fact to verify; "
        "user_confirmation_items names an owner decision; model_cannot_decide names an authority limit; "
        "risk_reminders names a concrete risk; next_actions names owner review and signature. The product author is not the "
        "local user's rule subject: use 'the user' unless the request explicitly names another person. Never use a signature as K evidence."
        if _is_english(locale)
        else "請只回傳一個扁平 JSON 物件，所有值都是短字串。欄位必須包含 S、S_explanation、C、C_explanation、"
        "B、B_explanation、K、K_explanation、R、R_explanation、rule_summary、missing_information、"
        "user_confirmation_items、model_cannot_decide、risk_reminders、next_actions；多個項目用分號隔開。"
        "所有內容都要換成本次任務的具體文字，不得輸出省略號或佔位符。"
        "句型硬規則：S 要寫主體、任務與觸發情境；C 必須寫實際因果或判斷路徑：多步驟用「先……再……」，"
        "條件結果用「若……則……」，兩者皆有時才同時使用；不得把禁止事項當成 C；"
        "B 必須使用「不得／不能」並寫停止條件；K 必須使用「只可引用使用者已確認……；不可引用……」；"
        "K 不得新增或排除原始需求沒有點名的具名文件或來源；不可引用項目只能是未確認內容、聊天或模型猜測、未簽名草稿與 VECTOR 候選。"
        "R 必須寫由誰承擔、由誰驗收簽名、出錯如何修復，並逐字寫明「模型不能簽名」。"
        "原始規則需求中的「我／我的」永遠指人類使用者，不是模型；「由我簽名」必須改寫成「由使用者簽名」。"
        "五個補充欄都不可留空且要對應本次任務：missing_information 寫待核對事實；user_confirmation_items 寫使用者要確認的決定；"
        "model_cannot_decide 寫模型權限界線；risk_reminders 寫具體風險；next_actions 寫使用者逐欄確認與簽名。"
        "產品作者不是本地使用者的規則主體；除非原始需求明確點名其他人，"
        "一律使用「使用者」，也不得把簽名當成 K 的資料依據。"
    )
    system = (
        "You are the Model-assisted SCBKR Rulebook Authoring engine. "
        "Read the SCBKR structure and turn the user's natural-language rule request into a draft rulebook. "
        "Return JSON only. You must write the content and explanation for every S/C/B/K/R dimension. "
        "You cannot sign, store, activate, publish, send, pay, delete, or claim the rule is established. "
        "Chat context and VECTOR are not formal basis. VECTOR is recall only. "
        f"Plan depth: {plan_level}. {language_rule} "
        f"{role_contract} "
        f"{compact_contract} "
        f"{identity_guard} "
        f"{uncertainty_guard} "
        "Keep the response compact so a small local model can finish: every field is one short sentence, "
        "use semicolons for at most two items, do not use markdown, and finish within about 600 output tokens."
    )
    user = {
        "rule_request": user_input,
        "request_grounding_terms": _grounding_candidates(user_input)[:16],
        "plan": plan_level,
        "authority": "model_drafts_and_explains; user_reviews_edits_signs_and_stores",
        "formal_sources": "signed active LOGIC/CORPUS/MEMORY only; VECTOR and chat are never formal basis",
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False, sort_keys=True)},
    ]


def parse_model_rulebook_candidate(
    text: str,
    *,
    user_input: str = "",
    locale: str = "zh-TW",
) -> dict[str, Any]:
    """Parse a model-authored candidate even when semantic closure is missing."""
    parsed = _extract_json_object(normalize_locale_text(text, locale))
    if _contains_overreach(parsed):
        raise ModelRulebookAuthoringError("model_overreach_signature_or_storage")
    raw_candidate = dict(parsed)
    try:
        parsed, repaired = _canonicalize_compact_authoring(parsed, locale)
    except ModelRulebookAuthoringError as exc:
        raise ModelRulebookAuthoringError(
            exc.code,
            candidate=raw_candidate,
        ) from exc
    for dim in DIMENSIONS:
        try:
            _dim_payload(parsed, dim)
        except ModelRulebookAuthoringError as exc:
            raise ModelRulebookAuthoringError(
                exc.code,
                candidate=raw_candidate,
            ) from exc
    for key in ("rule_summary", "missing_information", "user_confirmation_items", "model_cannot_decide", "risk_reminders", "next_actions"):
        if key == "rule_summary":
            if not str(parsed.get(key) or "").strip():
                raise ModelRulebookAuthoringError("missing_rule_summary")
        else:
            parsed[key] = _as_list(parsed.get(key))
    parsed["model_schema_repaired"] = repaired
    semantic_report = validate_model_rulebook_semantics(parsed, user_input=user_input)
    parsed["model_semantic_valid"] = semantic_report["passed"] is True
    parsed["model_semantic_report"] = semantic_report
    return parsed


def parse_model_rulebook_output(
    text: str,
    *,
    user_input: str = "",
    locale: str = "zh-TW",
) -> dict[str, Any]:
    """Parse a candidate and require strict five-role semantic closure."""
    parsed = parse_model_rulebook_candidate(text, user_input=user_input, locale=locale)
    semantic_report = parsed["model_semantic_report"]
    if not semantic_report["passed"]:
        raise ModelRulebookAuthoringError(
            "scbkr_semantic_roles_invalid",
            candidate=parsed,
            semantic_report=semantic_report,
        )
    return parsed


def enforce_kernel_authority_boundary(
    authoring: dict[str, Any],
    *,
    locale: str = "zh-TW",
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Remove model self-sign authority while preserving model-authored rules.

    This is a Rule OS invariant, not an authoring fallback. The original model
    text remains in the attempt audit and every deterministic repair is marked.
    """
    repaired = json.loads(json.dumps(authoring, ensure_ascii=False))
    repairs: list[dict[str, str]] = []
    boundary = (
        "The model cannot sign, store, approve, or activate this rule; the user must review and sign it"
        if _is_english(locale)
        else "模型不能簽名、入庫、核准或啟用此規則；必須由使用者驗收並簽名"
    )
    summary_boundary = (
        "The rule can be established only after the user reviews and signs it"
        if _is_english(locale)
        else "本規則必須由使用者驗收並簽名後才可成立"
    )

    def sanitize(path: str, value: Any) -> Any:
        items = _as_list(value)
        if not any(_has_model_authority_claim(item) for item in items):
            return value
        kept: list[str] = []
        for item in items:
            segments = [
                segment.strip()
                for segment in re.split(r"[；;。]+", item)
                if segment.strip()
            ]
            kept.extend(segment for segment in segments if not _has_model_authority_claim(segment))
        required = summary_boundary if path == "rule_summary" else boundary
        if required not in kept:
            kept.append(required)
        sanitized_items = list(dict.fromkeys(kept))
        sanitized: Any = sanitized_items if isinstance(value, list) else "；".join(sanitized_items) + "。"
        repairs.append({
            "code": "model_authority_claim_removed",
            "path": path,
            "original": json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else str(value),
            "repaired": json.dumps(sanitized, ensure_ascii=False) if isinstance(sanitized, (list, dict)) else str(sanitized),
            "source": "kernel_authority_guard",
        })
        return sanitized

    for key in (
        "rule_summary",
        "missing_information",
        "user_confirmation_items",
        "model_cannot_decide",
        "risk_reminders",
        "next_actions",
    ):
        if key in repaired:
            repaired[key] = sanitize(key, repaired.get(key))
    for dim in DIMENSIONS:
        payload = repaired.get(dim)
        if not isinstance(payload, dict):
            continue
        for key in (
            "content",
            "explanation",
            "missing_information",
            "needs_user_confirmation",
            "model_cannot_decide",
            "risk_notes",
        ):
            if key in payload:
                payload[key] = sanitize(f"{dim}.{key}", payload.get(key))
        if any(item.get("path", "").startswith(f"{dim}.") for item in repairs):
            payload["kernel_authority_guard_applied"] = True
    if not repairs:
        return repaired, []
    repaired["kernel_authority_repairs"] = repairs
    repaired["model_semantic_valid_before_kernel_authority_guard"] = bool(authoring.get("model_semantic_valid"))
    return repaired, repairs


def build_context_audit(
    *,
    messages: list[dict[str, str]],
    model_output: str = "",
    kernel_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    messages_json = json.dumps(messages, ensure_ascii=False, sort_keys=True)
    kernel_json = json.dumps(kernel_pack or {}, ensure_ascii=False, sort_keys=True)
    return {
        "chat_context_used": False,
        "vector_formal_basis": False,
        "model_messages_chars": len(messages_json),
        "model_messages_est_tokens": _estimate_tokens(messages_json),
        "kernel_pack_chars": len(kernel_json),
        "kernel_pack_est_tokens": _estimate_tokens(kernel_json),
        "model_output_chars": len(model_output or ""),
        "model_output_est_tokens": _estimate_tokens(model_output or ""),
        "policy": "model receives SCBKR kernel structure and the current user request only; chat history is not formal basis; VECTOR is recall only",
    }


def authoring_to_scbkr_draft(
    *,
    user_input: str,
    authoring: dict[str, Any],
    kernel_pack: dict[str, Any],
    plan_level: str = "FREE",
    locale: str = "zh-TW",
    model_provider: str = "",
    model_name: str = "",
    response_source: str = "model_assisted_rulebook",
    context_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dims = {dim: _dim_payload(authoring, dim) for dim in DIMENSIONS}
    semantic_valid = bool(authoring.get("model_semantic_valid"))
    kernel_compiled_dimensions = _as_list(authoring.get("kernel_structure_compiled_dimensions"))
    kernel_compile_audit = authoring.get("kernel_structure_compile_audit") or []
    global_missing = _as_list(authoring.get("missing_information"))
    global_confirm = _as_list(authoring.get("user_confirmation_items"))
    global_cannot = _as_list(authoring.get("model_cannot_decide"))
    global_risks = _as_list(authoring.get("risk_reminders"))
    next_actions = _as_list(authoring.get("next_actions")) or ["owner_review_and_signature"]
    subject = dims["S"]["content"][:120]
    draft = {
        "meta": {
            "compiler": "model_rulebook_author",
            "generated_under_kernel": KERNEL_NAME,
            "model_role": "draft_only",
            "author_kernel_source": True,
            "user_rule_owner": "local_user",
            "requires_user_signature": True,
            "user_data_local_only": True,
            "model_cannot_sign": True,
            "model_cannot_store": True,
            "model_cannot_activate": True,
            "plan_level": plan_level,
            "locale": locale,
            "model_provider": model_provider,
            "model_name": model_name,
        },
        "confirmation_status": "draft",
        "draft_source": response_source,
        "model_authored": True,
        "model_participated": True,
        "model_used": True,
        "model_provider": model_provider,
        "model_name": model_name,
        "model_schema_valid": True,
        "model_schema_repaired": bool(authoring.get("model_schema_repaired")),
        "model_semantic_valid": semantic_valid,
        "model_semantic_report": authoring.get("model_semantic_report") or {},
        "kernel_structure_compiled": bool(kernel_compiled_dimensions),
        "kernel_structure_compiled_dimensions": kernel_compiled_dimensions,
        "model_semantic_valid_before_kernel_compile": bool(
            authoring.get("model_semantic_valid_before_kernel_compile")
        ),
        "validator_passed": False,
        "fallback_used": False,
        "fallback_reason": "",
        "requires_user_signature": True,
        "model_signature_allowed": False,
        "signing_allowed": semantic_valid,
        "next_required_action": "owner_review_and_signature" if semantic_valid else "owner_clarify_or_select_stronger_model",
        "rule_assist_plan": plan_level,
        "rule_summary": str(authoring.get("rule_summary") or subject),
        "missing_information": global_missing,
        "risk_reminders": global_risks,
        "user_confirmation_items": global_confirm,
        "model_cannot_decide": global_cannot,
        "next_actions": next_actions,
        "context_audit": context_audit or {},
        "compiler_report": {
            "status": "model_assisted_rulebook",
            "attempts": 1,
            "repairs": 0,
            "errors": [],
            "model_used": True,
            "model_schema_valid": True,
            "model_schema_repaired": bool(authoring.get("model_schema_repaired")),
            "model_semantic_valid": semantic_valid,
            "model_semantic_report": authoring.get("model_semantic_report") or {},
            "kernel_structure_compiled": bool(kernel_compiled_dimensions),
            "kernel_structure_compiled_dimensions": kernel_compiled_dimensions,
            "kernel_structure_compile_audit": kernel_compile_audit,
            "model_semantic_valid_before_kernel_compile": bool(
                authoring.get("model_semantic_valid_before_kernel_compile")
            ),
            "fallback_used": False,
            "next_required_action": "owner_review_and_signature" if semantic_valid else "owner_clarify_or_select_stronger_model",
        },
        "S": {
            "task_name": f"{subject[:48]}規則書草稿",
            "task_subject": subject,
            "rule_subject": subject,
            "user_instruction": user_input,
            "input_content": user_input,
            "output_format": "可編輯、可簽名、可入庫的本地 SCBKR 規則書草稿",
            "interface_type": "local_first_ai_chat_and_workbench",
            "platform_type": "SCBKR Desktop local rule OS",
            "applies_when": [dims["S"]["content"]],
            "does_not_apply_when": dims["B"]["model_cannot_decide"] or ["情境、角色、資料來源或風險條件不同時不得直接套用。"],
            "expected_output": ["產生可編輯 S/C/B/K/R 規則書草稿。"],
            "model_explanation": dims["S"]["explanation"],
            "model_draft_content": dims["S"]["content"],
            "model_schema_adapter_generated": dims["S"]["schema_adapter_generated"],
            "model_explanation_derived_from_fields": dims["S"]["model_explanation_derived_from_fields"],
            "model_explanation_repaired_by_model": dims["S"]["model_explanation_repaired_by_model"],
            "missing_information": dims["S"]["missing_information"],
            "needs_user_confirmation": dims["S"]["needs_user_confirmation"],
            "model_cannot_decide": dims["S"]["model_cannot_decide"],
            "risk_notes": dims["S"]["risk_notes"],
            "pending_questions": dims["S"]["needs_user_confirmation"] + dims["S"]["missing_information"],
            "rule_os_dimension_contract": {
                "requires_user_confirmation": True,
                "usage_conditions": [dims["S"]["explanation"]],
                "gap_notes": dims["S"]["missing_information"] or ["需使用者確認主體與適用情境。"],
            },
        },
        "C": {
            "core_logic": dims["C"]["content"],
            "user_core_judgement": user_input,
            "flow_steps": [dims["C"]["content"], "使用者逐欄修改與確認", "使用者簽名", "二次確認入庫", "後續以 current_rule_package 引用"],
            "execution_order": ["draft", "owner_edit", "kernel_validator", "owner_signature", "storage_confirm", "active_rule_package"],
            "data_flow": "模型只讀本次使用者規則需求與 SCBKR 結構；聊天上下文不得成為正式依據。",
            "event_flow": "建立草稿 -> Kernel Validator -> 使用者簽名 -> 入庫 -> current_rule_package -> post-check。",
            "causal_chain": [dims["C"]["content"], dims["C"]["explanation"]],
            "ignored_consequence": dims["C"]["risk_notes"] or ["若不先建立規則，後續回答會漂回一般聊天上下文。"],
            "why_rule_needed": dims["C"]["explanation"],
            "dependencies": ["本地 Runtime", "模型規則書草擬", "Kernel Validator", "使用者簽名", "四庫入庫"],
            "failure_impact": "缺資料、缺簽名、模型越權或依據不足時不得成為正式規則。",
            "test_conditions": ["模型輸出 schema valid", "Kernel Validator passed", "chat_context_used=false", "VECTOR recall only"],
            "model_explanation": dims["C"]["explanation"],
            "model_draft_content": dims["C"]["content"],
            "model_schema_adapter_generated": dims["C"]["schema_adapter_generated"],
            "model_explanation_derived_from_fields": dims["C"]["model_explanation_derived_from_fields"],
            "model_explanation_repaired_by_model": dims["C"]["model_explanation_repaired_by_model"],
            "missing_information": dims["C"]["missing_information"],
            "needs_user_confirmation": dims["C"]["needs_user_confirmation"],
            "model_cannot_decide": dims["C"]["model_cannot_decide"],
            "risk_notes": dims["C"]["risk_notes"],
            "pending_questions": dims["C"]["needs_user_confirmation"] + dims["C"]["missing_information"],
            "rule_os_dimension_contract": {
                "requires_user_confirmation": True,
                "usage_conditions": [dims["C"]["explanation"]],
                "gap_notes": dims["C"]["missing_information"] or ["需確認流程、原因與判斷順序。"],
            },
        },
        "B": {
            "data_read_scope": ["本次規則需求", "SCBKR 結構", "已簽名且已驗收的本地四庫資料"],
            "data_write_scope": ["簽名前不得寫入正式庫", "二次確認前不得入庫"],
            "local_scope": ["SCBKR Desktop local Runtime"],
            "external_scope": ["外部模型只能接收本次最小 authoring context"],
            "permission_switches": ["model_generate", "external_api_call_requires_permission", "storage_write_requires_user_second_confirm"],
            "forbidden": [dims["B"]["content"], "模型不得簽名、入庫、啟用、發布、寄信、付款或刪除。", "不得把聊天上下文或 VECTOR 當正式依據。"],
            "stop_conditions": dims["B"]["needs_user_confirmation"] + dims["B"]["missing_information"] + ["缺使用者簽名時停止在 draft。"],
            "error_handling": "模型輸出壞掉或模型未連上時，不產生 fallback 草稿；只回報模型不可用或 schema invalid。",
            "storage_conditions": "owner_signed + review_passed + second_storage_confirm 才能入四庫。",
            "model_must_not": ["sign", "store", "activate", "publish", "send", "pay", "delete", "execute_external_action"],
            "requires_user_confirmation_when": global_confirm or dims["B"]["needs_user_confirmation"] or ["正式引用", "入庫", "高風險行動"],
            "model_explanation": dims["B"]["explanation"],
            "model_draft_content": dims["B"]["content"],
            "model_schema_adapter_generated": dims["B"]["schema_adapter_generated"],
            "model_explanation_derived_from_fields": dims["B"]["model_explanation_derived_from_fields"],
            "model_explanation_repaired_by_model": dims["B"]["model_explanation_repaired_by_model"],
            "model_task_fragment": dims["B"]["model_task_fragment"],
            "model_original_content_before_kernel_compile": dims["B"]["model_original_content_before_kernel_compile"],
            "kernel_required_clauses": dims["B"]["kernel_required_clauses"],
            "kernel_structure_compiled": dims["B"]["kernel_structure_compiled"],
            "missing_information": dims["B"]["missing_information"],
            "needs_user_confirmation": dims["B"]["needs_user_confirmation"],
            "model_cannot_decide": dims["B"]["model_cannot_decide"],
            "risk_notes": dims["B"]["risk_notes"],
            "pending_questions": dims["B"]["needs_user_confirmation"] + dims["B"]["missing_information"],
            "rule_os_dimension_contract": {
                "requires_user_confirmation": True,
                "usage_conditions": [dims["B"]["explanation"]],
                "gap_notes": dims["B"]["missing_information"] or ["需確認邊界、禁止事項與停止條件。"],
            },
        },
        "K": {
            "references": ["使用者原始規則需求", "SCBKR Kernel Pack", dims["K"]["content"]],
            "technical_docs": ["kernel_pack/scbkr_kernel_pack.json", "schemas/scbkr.schema.json"],
            "style_settings": "使用者語言優先；規則本體保存穩定欄位。",
            "framework_choice": "SCBKR five-dimensional rulebook authoring",
            "model_basis": "模型只可依本次規則需求與 SCBKR 結構草擬；不得使用聊天上下文當正式 K。",
            "citable_sources": ["LOGIC signed/reviewed/active", "CORPUS signed/reviewed/active", "MEMORY signed/reviewed/active"],
            "non_citable_sources": ["VECTOR recall only; not formal basis", "unsigned chat context", "model guesses", "unreviewed drafts"],
            "four_store_policy": {
                "LOGIC": "formal rule basis",
                "CORPUS": "formal data basis",
                "MEMORY": "formal preference basis",
                "VECTOR": "recall only; not formal K basis",
            },
            "when_basis_missing": "輸出 DRAFT / OWNER_REVIEW / NEED_DEFINITION，不得假裝正式依據存在。",
            "source_credibility": "VECTOR recall only; signed LOGIC/CORPUS/MEMORY are formal basis after review.",
            "model_explanation": dims["K"]["explanation"],
            "model_draft_content": dims["K"]["content"],
            "model_schema_adapter_generated": dims["K"]["schema_adapter_generated"],
            "model_explanation_derived_from_fields": dims["K"]["model_explanation_derived_from_fields"],
            "model_explanation_repaired_by_model": dims["K"]["model_explanation_repaired_by_model"],
            "model_task_fragment": dims["K"]["model_task_fragment"],
            "model_original_content_before_kernel_compile": dims["K"]["model_original_content_before_kernel_compile"],
            "kernel_required_clauses": dims["K"]["kernel_required_clauses"],
            "kernel_structure_compiled": dims["K"]["kernel_structure_compiled"],
            "missing_information": dims["K"]["missing_information"],
            "needs_user_confirmation": dims["K"]["needs_user_confirmation"],
            "model_cannot_decide": dims["K"]["model_cannot_decide"],
            "risk_notes": dims["K"]["risk_notes"],
            "pending_questions": dims["K"]["needs_user_confirmation"] + dims["K"]["missing_information"],
            "rule_os_dimension_contract": {
                "requires_user_confirmation": True,
                "usage_conditions": [dims["K"]["explanation"]],
                "gap_notes": dims["K"]["missing_information"] or ["需確認依據與不可引用項目。"],
            },
        },
        "R": {
            "expected_outputs": ["可編輯 S/C/B/K/R 規則書草稿", "模型解釋", "缺資料", "風險", "確認項目"],
            "acceptance_criteria": ["使用者可理解並修改每一層。", "Kernel Validator 通過。", "使用者簽名後才成立。"],
            "ledger_requirements": ["record_model_authoring", "record_validator", "record_signature", "record_storage", "record_rule_package", "record_token_context_audit"],
            "storage_options": ["logic", "corpus", "memory", "vector"],
            "signature_status": "waiting_owner_signature",
            "review_status": "not_reviewed",
            "user_signature_required": True,
            "model_cannot_sign": True,
            "formation_conditions": ["S/C/B/K/R 五維完整。", "使用者逐欄確認。", "使用者簽名後才成立。"],
            "failure_conditions": ["失效：使用者未簽名。", "失效：模型宣稱簽名/入庫/啟用。", "失效：VECTOR 或聊天上下文被當正式依據。"],
            "replay_requirements": ["replay model messages", "replay model schema validation", "replay Kernel Validator", "replay owner signature", "replay storage result"],
            "repair_path": ["修復：回到失敗維度補資料。", "重新呼叫模型草擬或人工修改。", "重新 Kernel Validator。", "使用者重新簽名。"],
            "real_world_responsibility": "使用者採用本規則後，現實行動與結果由使用者自行承擔。",
            "kernel_attribution": f"本草稿由模型依據「{KERNEL_NAME}」草擬；Kernel 提供結構，不代表規則已成立。",
            "model_explanation": dims["R"]["explanation"],
            "model_draft_content": dims["R"]["content"],
            "model_schema_adapter_generated": dims["R"]["schema_adapter_generated"],
            "model_explanation_derived_from_fields": dims["R"]["model_explanation_derived_from_fields"],
            "model_explanation_repaired_by_model": dims["R"]["model_explanation_repaired_by_model"],
            "model_task_fragment": dims["R"]["model_task_fragment"],
            "model_original_content_before_kernel_compile": dims["R"]["model_original_content_before_kernel_compile"],
            "kernel_required_clauses": dims["R"]["kernel_required_clauses"],
            "kernel_structure_compiled": dims["R"]["kernel_structure_compiled"],
            "missing_information": dims["R"]["missing_information"],
            "needs_user_confirmation": dims["R"]["needs_user_confirmation"],
            "model_cannot_decide": dims["R"]["model_cannot_decide"],
            "risk_notes": dims["R"]["risk_notes"],
            "pending_questions": dims["R"]["needs_user_confirmation"] + dims["R"]["missing_information"],
            "rule_os_dimension_contract": {
                "requires_user_confirmation": True,
                "usage_conditions": [dims["R"]["explanation"]],
                "gap_notes": dims["R"]["missing_information"] or ["需確認責任、驗收與簽名條件。"],
            },
        },
    }
    return draft


def build_authoring_failure(
    *,
    reason: str,
    model_provider: str = "",
    model_name: str = "",
    message: str | None = None,
    context_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    unavailable_reasons = {
        "model_not_connected",
        "model_call_failed",
        "external_api_permission_required",
        "model_generate_permission_required",
    }
    timed_out = reason == "model_timeout"
    return {
        "draft_source": "model_timeout" if timed_out else ("model_unavailable" if reason in unavailable_reasons else "model_rulebook_schema_invalid"),
        "model_used": timed_out or reason not in unavailable_reasons,
        "model_provider": model_provider,
        "model_name": model_name,
        "model_schema_valid": False,
        "validator_passed": False,
        "fallback_used": False,
        "fallback_reason": "",
        "failure_reason": reason,
        "failure_message": message or reason,
        "requires_user_signature": True,
        "model_signature_allowed": False,
        "next_required_action": "retry_model_rulebook_authoring" if timed_out else ("model_connection_required" if reason in unavailable_reasons else "retry_model_rulebook_authoring"),
        "context_audit": context_audit or {},
    }
