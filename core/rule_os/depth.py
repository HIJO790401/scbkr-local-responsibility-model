"""Plan-depth reinforcement for generated SCBKR five-dimensional drafts."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

PLAN_LEVELS = {"FREE", "NT690", "NT3300"}


def _normalize_plan(plan_level: str | None) -> str:
    value = str(plan_level or "FREE").upper()
    return value if value in PLAN_LEVELS else "FREE"


def _ensure_list(container: dict[str, Any], key: str) -> list[Any]:
    value = container.get(key)
    if isinstance(value, list):
        return value
    if value in (None, "", {}):
        container[key] = []
    else:
        container[key] = [value]
    return container[key]


def _append_unique(target: list[Any], values: list[Any]) -> list[Any]:
    seen = {str(item) for item in target}
    for value in values:
        if value in (None, "", []):
            continue
        text = str(value).strip()
        if text and text not in seen:
            target.append(text)
            seen.add(text)
    return target


def _is_beauty_copy_rule(raw_input: str) -> bool:
    text = (raw_input or "").lower()
    return any(token in text for token in ("美容院", "美容", "臉部", "脸部", "保養", "保养", "美睫", "美甲")) and any(
        token in text for token in ("文案", "貼文", "贴文", "商業", "廣告", "copy")
    )


def _task_label(raw_input: str) -> str:
    if "商業文案" in raw_input and ("規則表單" in raw_input or "表單" in raw_input):
        return "商業文案規則表單"
    match = re.search(r"(?:建立|生成|制定|新增|寫)(?:一個|一份|這個)?(.{2,36}?規則)", raw_input or "")
    if match:
        return match.group(1).strip(" ：:，,。.")
    if _is_beauty_copy_rule(raw_input):
        return "美容院商業文案規則"
    if "商業文案" in raw_input or "文案" in raw_input:
        return "商業文案規則"
    if "規則" in raw_input:
        return str(raw_input).strip(" 。")[:36] or "使用者自訂規則"
    return "使用者自訂規則"


def _base_rule_fields(raw_input: str) -> dict[str, list[str]]:
    label = _task_label(raw_input)
    forbidden = [
        "不得把未簽名草稿當正式規則。",
        "不得由模型簽名、驗收、入庫、發布或執行工具。",
        "不得引用未確認資料作為正式依據。",
    ]
    stop = [
        "主體、邊界、依據或責任任一缺失時，只能停在草稿。",
        "需要發布、寄信、上架、付款、刪除或外部工具時，必須先取得使用者確認。",
    ]
    basis = ["使用者原始指令", "SCBKR 五維規則語法", "已簽名且已驗收的本地四庫資料"]
    acceptance = [
        "使用者能逐欄檢查主體、因果、邊界、依據、責任。",
        "使用者簽名後才可入庫並啟用。",
        "後續模型回答只能使用本次規則包，不得靠聊天上下文自行猜測。",
    ]
    if _is_beauty_copy_rule(raw_input):
        forbidden.extend(
            [
                "不得誇大療效、保證變美、保證治療或暗示醫療效果。",
                "不得編造價格、優惠、療程時間、客戶見證、醫師背書或法規資料。",
                "不得自動發布、寄送或上架美容院文案。",
            ]
        )
        stop.extend(
            [
                "缺少服務項目、目標客群、通路、品牌語氣或禁用語時，只能生成待確認草稿。",
                "涉及價格、療效、醫療宣稱、優惠期限或客戶案例時，必須要求使用者提供正式資料。",
            ]
        )
        basis.extend(["使用者確認的美容院服務資料", "使用者確認的價格表或活動資料"])
        acceptance.extend(
            [
                "文案必須標示為草稿，除非使用者完成驗收。",
                "文案不得含未提供的價格、療效保證或自動發布承諾。",
            ]
        )
    return {"label": [label], "forbidden": forbidden, "stop": stop, "basis": basis, "acceptance": acceptance}


def _dimension_contract(name: str, raw_input: str) -> dict[str, Any]:
    fields = _base_rule_fields(raw_input)
    dimension_names = {"S": "主體", "C": "因果", "B": "邊界", "K": "依據", "R": "責任"}
    return {
        "dimension_code": name,
        "dimension_name": dimension_names[name],
        "concrete_content_required": True,
        "gap_notes": [],
        "forbidden_items": fields["forbidden"] if name in {"B", "R"} else [],
        "usage_conditions": fields["stop"] if name in {"B", "K", "R"} else ["必須符合使用者原始規則需求。"],
        "requires_user_confirmation": True,
    }


def _apply_common_five_dimensional_form(raw_input: str, draft: dict[str, Any]) -> None:
    fields = _base_rule_fields(raw_input)
    label = fields["label"][0]
    for layer in ("S", "C", "B", "K", "R"):
        draft.setdefault(layer, {})
        draft[layer].setdefault("rule_os_dimension_contract", _dimension_contract(layer, raw_input))
    draft["S"]["task_name"] = draft["S"].get("task_name") or f"{label}草稿"
    draft["S"]["task_subject"] = label if label != "使用者自訂規則" else draft["S"].get("task_subject") or label
    _append_unique(_ensure_list(draft["C"], "core_logic"), [
        "使用者人話需求先轉成 S/C/B/K/R 五維規則草稿。",
        "五維完整性檢查後，再依方案深度補強。",
        "使用者簽名後才可入庫，並編譯為本地可執行規則。",
    ])
    _append_unique(_ensure_list(draft["B"], "stop_conditions"), fields["stop"] + fields["forbidden"])
    _append_unique(_ensure_list(draft["K"], "references"), fields["basis"])
    _append_unique(_ensure_list(draft["K"], "source_credibility"), [
        "檢索庫只能召回候選，不可直接作正式依據。",
        "正式引用必須回到規則庫、資料庫或記憶庫確認簽名與驗收狀態。",
    ])
    _append_unique(_ensure_list(draft["R"], "acceptance_criteria"), fields["acceptance"])
    draft["R"]["model_signature_allowed"] = False
    draft["R"]["owner_signature_required"] = True
    draft["R"]["required_signer"] = "user"


def _apply_nt690(raw_input: str, draft: dict[str, Any]) -> None:
    fields = _base_rule_fields(raw_input)
    missing = [
        "需確認任務類型、目標受眾、輸出格式與不可越界事項。",
        "需確認哪些資料可正式引用，哪些只能當候選。",
    ]
    if _is_beauty_copy_rule(raw_input):
        missing.extend(["需補美容院服務項目、價格來源、活動期限、品牌語氣、禁用醫療宣稱。"])
    _append_unique(_ensure_list(draft["B"], "stop_conditions"), fields["stop"])
    draft["responsibility_chain_assist"] = {
        "plan_level": "NT690",
        "missing_fields": missing,
        "clarifying_questions": [
            "這條規則要套用在哪些任務類型？",
            "哪些資料沒有正式確認時必須停下來問你？",
            "哪些動作需要你再次簽名？",
        ],
        "incomplete_boundaries": fields["stop"],
        "insufficient_basis": ["沒有已簽名資料時，不得說成正式依據。"],
        "draft_only_conditions": ["資訊不足、資料未確認、未完成簽名時只能產生草稿。"],
        "non_citable_content": ["檢索庫候選", "一般聊天上下文", "模型自行推測內容"],
        "actions_requiring_confirmation": ["發布", "寄信", "上架", "付款", "刪除", "入庫", "外部工具執行"],
        "shenyao_basic_assist_signature": "structure_assist_only_not_forced_signature",
    }
    draft["R"]["basic_formation_conditions"] = [
        "使用者明確要建立規則。",
        "五維欄位都有可讀內容。",
        "使用者完成簽名。",
    ]
    draft["R"]["basic_failure_reminders"] = fields["stop"]
    draft["R"]["basic_risk_reminders"] = fields["forbidden"]


def _apply_nt3300(raw_input: str, draft: dict[str, Any]) -> None:
    fields = _base_rule_fields(raw_input)
    formation = [
        "S/C/B/K/R 五維已由使用者逐欄確認。",
        "規則庫保存可執行判斷邏輯。",
        "資料庫只保存使用者確認過的正式資料。",
        "記憶庫只在命中任務時引用偏好，不污染聊天上下文。",
        "檢索庫只召回相似候選，不直接當正式依據。",
        "使用者簽名與沈耀強制簽名條件都成立後，才能成為規則書閉環。",
    ]
    failure = [
        "任一五維欄位缺失或使用者未簽名。",
        "模型把草稿說成正式結果。",
        "模型引用未確認資料或檢索庫候選作正式依據。",
        "模型越權發布、寄送、上架、付款、刪除或入庫。",
    ]
    if _is_beauty_copy_rule(raw_input):
        formation.extend(["美容院服務、受眾、通路、品牌語氣與禁止宣稱已確認。"])
        failure.extend(["出現誇大療效、編造價格、未提供客戶見證或自動發布承諾。"])
    repair = [
        "回到缺失維度補資料。",
        "重新產生五維草稿。",
        "交使用者逐欄確認。",
        "重新簽名、驗收、入庫並寫入回放。",
    ]
    draft["B"]["formation_conditions"] = _append_unique(_ensure_list(draft["B"], "formation_conditions"), formation)
    draft["B"]["failure_conditions"] = _append_unique(_ensure_list(draft["B"], "failure_conditions"), failure)
    draft["R"]["formation_conditions"] = _append_unique(_ensure_list(draft["R"], "formation_conditions"), formation)
    draft["R"]["failure_conditions"] = _append_unique(_ensure_list(draft["R"], "failure_conditions"), failure)
    draft["R"]["risk_levels"] = {
        "low": "只產生草稿，不引用正式資料，不執行工具。",
        "medium": "引用已簽名規則或正式資料，但仍等待使用者驗收。",
        "high": "涉及發布、寄送、上架、付款、刪除、入庫或外部工具。",
    }
    draft["R"]["repair_path"] = _append_unique(_ensure_list(draft["R"], "repair_path"), repair)
    draft["R"]["replay_requirements"] = _append_unique(_ensure_list(draft["R"], "replay_requirements"), [
        "記錄分類結果。",
        "記錄命中的四庫資料。",
        "記錄本次規則包。",
        "記錄回答後檢查結果。",
    ])
    draft["R"]["version_conditions"] = ["新版規則需保留 parent/version/superseded 關係，不得直接覆寫舊版。"]
    draft["R"]["dual_signature_conditions"] = ["沈耀強制簽名", "使用者簽名", "兩者缺一只能停在草稿或 OWNER_REVIEW。"]
    draft["R"]["long_term_workflow_conditions"] = ["只有規則狀態 active、簽名 owner_signed、驗收 review_passed 時才可進長期流程。"]
    draft["R"]["formal_citation_allowed"] = "only_when_signed_reviewed_active_logic_or_corpus_or_memory"
    draft["R"]["long_term_workflow_allowed"] = "owner_signed_and_review_passed_only"
    draft["R"]["shenyao_forced_signature_required"] = True
    draft["rulebook_closure"] = {
        "plan_level": "NT3300",
        "formation_conditions": formation,
        "failure_conditions": failure,
        "risk_levels": draft["R"]["risk_levels"],
        "repair_path": repair,
        "replay_required": True,
        "dual_signature_required": True,
        "formal_citation_allowed": draft["R"]["formal_citation_allowed"],
    }


def apply_plan_depth_to_draft(raw_input: str, draft: dict[str, Any], plan_level: str | None) -> dict[str, Any]:
    """Return a SCBKR draft reinforced by the selected product depth.

    This function is deterministic and never signs, stores, activates, or closes
    a rule. It only makes the generated draft inspectable.
    """
    result = deepcopy(draft or {})
    plan = _normalize_plan(plan_level)
    _apply_common_five_dimensional_form(raw_input, result)
    result["rule_os"] = {
        "contract": "local_rule_operating_system",
        "input_to_rule_flow": "user_text_to_five_dimension_rule_draft",
        "model_role": "five_dimension_rule_drafter",
        "plan_level": plan,
        "can_model_sign": False,
        "can_model_store": False,
        "can_model_activate": False,
        "requires_user_signature": True,
    }
    result["plan_depth"] = {
        "plan_level": plan,
        "free": {
            "enabled": True,
            "result_name": "我的自訂規則",
            "signature_mode": "user_self_signed",
            "can_generate_basic_five_dimension_draft": True,
        },
        "nt690": {"enabled": plan in {"NT690", "NT3300"}, "adds": "responsibility_chain_structure_assist"},
        "nt3300": {"enabled": plan == "NT3300", "adds": "rulebook_closure_audit"},
    }
    if plan in {"NT690", "NT3300"}:
        _apply_nt690(raw_input, result)
    if plan == "NT3300":
        _apply_nt3300(raw_input, result)
    result["confirmation_status"] = result.get("confirmation_status") or "draft"
    result["signature_status"] = "waiting_owner_signature"
    result["model_signature_allowed"] = False
    result["owner_signature_required"] = True
    return result
