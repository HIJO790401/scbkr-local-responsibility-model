"""SCBKR draft grammar, understanding compiler, and evidence relation gate."""
from __future__ import annotations
import json
from copy import deepcopy
from typing import Any

from core.scbkr.generator import create_scbkr_draft

DRAFT_SOURCES = {"model_assisted_structured", "scbkr_base_logic", "draft_failed"}
SCBKR_GRAMMAR_PACK_ZH = """你正在生成 SCBKR confirmation draft 的 Task Understanding，不是完整 SCBKR JSON。
這不是普通企劃表、不是一般 Markdown、不是正式結果、不是任務分配表、不是外部中立評論。
模型只能描述、理解、拆解、產生草案建議、建議欄位、建議引用關係。
模型不能確認責任鏈、驗收、入庫、簽名、修改或刪除 Data Center、把候選資料當已引用、用通用中立語稀釋使用者主體判斷。
輸出 JSON 欄位：task_domain, task_subject, user_original_judgement, user_goal, output_format, core_claim, causal_chain, boundary_rules, forbidden_dilutions, basis_sources, evidence_relation_notes, acceptance_criteria, storage_candidates, owner_signature_required=true, model_role=describe_compile_only。
不得輸出 confirmed=true、review_passed=true、storage_confirmed=true、physical_write_performed=true、signature_status=confirmed、signer=model/assistant/system。
S 定義任務主體；C 定義責任鏈因果；B 定義邊界行為；K 區分已採用引用/類似語法/類似邏輯/候選但未採用/無相關引用；R 必須包含使用者簽名後才成立。"""

GENERIC_STOPWORDS = {"文案", "規則", "確認單", "任務", "計畫", "生成", "草案", "scbkr", "責任鏈", "使用者", "輸出", "內容", "流程", "判斷"}
ADOPTABLE_RELATIONS = {"direct_match", "same_domain", "similar_logic", "style_reference"}



def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except TypeError:
            return str(value).strip()
    return str(value).strip()


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple, set)):
        raw_items = []
        for item in value:
            if isinstance(item, (list, tuple, set)):
                raw_items.extend(item)
            else:
                raw_items.append(item)
    elif isinstance(value, dict):
        raw_items = [json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))]
    else:
        raw_items = [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = normalize_text(item)
        if not text or text.lower() in {"none", "null"}:
            continue
        if text not in seen:
            normalized.append(text)
            seen.add(text)
    return normalized


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = normalize_text(value)
        if text and text.lower() not in {"none", "null"}:
            return text
    return ""


def normalize_task_understanding(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "task_domain": normalize_text(candidate.get("task_domain")),
        "task_subject": first_non_empty(candidate.get("task_subject"), candidate.get("core_claim"), candidate.get("user_goal")),
        "user_original_judgement": normalize_text(candidate.get("user_original_judgement")),
        "user_goal": normalize_text(candidate.get("user_goal")),
        "output_format": normalize_list(candidate.get("output_format")),
        "core_claim": normalize_text(candidate.get("core_claim")),
        "causal_chain": normalize_list(candidate.get("causal_chain")),
        "boundary_rules": normalize_list(candidate.get("boundary_rules")),
        "forbidden_dilutions": normalize_list(candidate.get("forbidden_dilutions")),
        "basis_sources": normalize_list(candidate.get("basis_sources")),
        "evidence_relation_notes": normalize_list(candidate.get("evidence_relation_notes")),
        "acceptance_criteria": normalize_list(candidate.get("acceptance_criteria")),
        "storage_candidates": normalize_list(candidate.get("storage_candidates")),
        "owner_signature_required": True,
        "model_role": "describe_compile_only",
    }
    return normalized

def build_scbkr_grammar_pack() -> str:
    return SCBKR_GRAMMAR_PACK_ZH


def build_task_understanding_messages(raw_input: str, task_type: str, evidence_context: dict[str, Any] | None = None) -> list[dict[str, str]]:
    from core.scbkr.compiler import TASK_UNDERSTANDING_CONTRACT_VERSION, task_understanding_json_schema

    context = evidence_context or {}
    packet = context.get("evidence_packet") or {
        "contract_version": "scbkr.evidence.v2",
        "citations": [],
        "candidates": [],
        "vector_is_discovery_only": True,
    }
    return [
        {
            "role": "system",
            "content": (
                SCBKR_GRAMMAR_PACK_ZH
                + "\nReturn exactly one JSON object. Do not add keys. Contract: "
                + TASK_UNDERSTANDING_CONTRACT_VERSION
                + "\nJSON Schema: "
                + json.dumps(task_understanding_json_schema(), ensure_ascii=False, separators=(",", ":"))
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "raw_input": raw_input,
                    "task_type": task_type,
                    "evidence_packet": packet,
                    "citation_rule": "Only evidence_packet.citations may be used as formal basis. candidates are discovery-only.",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        },
    ]


def has_task_subject(raw_input: str) -> bool:
    text = (raw_input or "").strip()
    if len(text) < 4:
        return False
    if any(ch.isascii() and ch.isalpha() for ch in text):
        return True
    return any(t in text for t in ("我要", "請", "生成", "建立", "整理", "把", "對", "文案", "判準", "規則", "確認單"))


def _tokens(text: str) -> set[str]:
    raw = (text or "").lower()
    found = {t for t in raw.replace("/", " ").replace("_", " ").replace("-", " ").split() if len(t) >= 2}
    for key in ("滷肉飯", "商業", "文案", "餐飲", "ui", "介面", "工作台", "人類", "描述", "確定性", "邏輯", "二手手機", "交易", "防詐", "風險", "買賣"):
        if key in raw:
            found.add(key)
    return found - GENERIC_STOPWORDS


def classify_evidence_relation(raw_input: str, candidate_text: str, *, score: Any = None, source_store: str = "") -> dict[str, Any]:
    q = _tokens(raw_input); c = _tokens(candidate_text)
    overlap = q & c
    relation = "irrelevant"; adopted = False; scope = "none"; reason = "generic token overlap is ignored; no task-specific relation"
    raw = (raw_input or "").lower(); text = (candidate_text or "").lower()
    if any(t in text for t in ("衝突", "否認", "相反", "conflict")) and overlap:
        relation, reason = "conflict", "candidate conflicts with task-specific terms"
    elif len(overlap) >= 2 or any(token in overlap for token in ("滷肉飯", "工作台", "人類", "確定性")):
        relation, adopted, scope, reason = "direct_match", True, "basis", f"task-specific overlap: {', '.join(sorted(overlap))}"
    elif ("商業" in q and "商業" in c) or ("餐飲" in q and "餐飲" in c) or ({"交易", "二手手機", "防詐", "風險"} & q and {"交易", "二手手機", "防詐", "風險"} & c):
        relation, adopted, scope, reason = "same_domain", True, "basis", "same domain"
    elif "文案" in (raw + text) and not overlap:
        relation, scope, reason = "candidate_only", "none", "only generic copywriting token matched"
    elif ("scbkr" in text or "責任鏈" in text) and not overlap:
        relation, scope, reason = "similar_grammar", "grammar", "SCBKR grammar only; not a formal basis"
    try:
        if float(score) >= 0.7 and relation not in {"irrelevant", "candidate_only", "similar_grammar"}:
            adopted = True
    except Exception:
        pass
    return {"relation": relation, "adopted": adopted, "adoption_scope": scope, "relation_reason": reason}


def _apply_signature_gate(draft: dict[str, Any]) -> None:
    draft.update({"model_role": "describe_compile_only", "model_signature_allowed": False, "owner_signature_required": True, "signature_status": "waiting_owner_signature"})
    draft.setdefault("R", {})
    draft["R"].update({"signature_status": "waiting_owner_signature", "required_signer": "user", "model_signature_allowed": False, "closure_condition": "owner_signature_required", "owner_signature_required": True})


def _human_logic_overrides(raw_input: str, draft: dict[str, Any]) -> None:
    if "人類" in raw_input and "描述" in raw_input and "確定性" in raw_input:
        draft["S"].update({"task_name": "人類描述性邏輯判準確認單", "task_subject": "將「人類只有描述，沒有確定性邏輯」整理成 SCBKR 責任確認單。", "output_format": "判準規則草案、責任鏈確認單、驗收條件、入庫建議"})
        draft["C"].update({"core_logic": ["只有描述 → 無確定性邏輯 → 無法形成可驗收規則 → 無法確認責任 → 無法回放錯誤 → 不成立為責任鏈邏輯"], "flow_steps": ["抽取使用者主體判準", "編譯為 S/C/B/K/R 草案", "等待使用者簽名確認後才成立"]})
        draft["B"]["stop_conditions"] = list(draft["B"].get("stop_conditions", [])) + ["不得把使用者主體判斷稀釋成外部中立描述。", "不得用「不一定、未必、每個人不同」覆蓋本任務判準前提。", "若外部否認本判準，必須提出完整定義、條件、因果、責任、驗收與回放；交不出則標記 VOID。"]
        draft["R"]["acceptance_criteria"] = list(draft["R"].get("acceptance_criteria", [])) + ["使用者是否確認此判準作為主體判斷。", "使用者是否確認模型只能描述與編譯。", "使用者是否確認無完整反判準者標記 VOID。", "使用者簽名後才成立。"]


def build_scbkr_from_understanding(raw_input: str, task_type: str, understanding: dict[str, Any] | None, evidence_context: dict[str, Any] | None = None) -> dict[str, Any]:
    if not has_task_subject(raw_input):
        return {"draft_source": "draft_failed", "confirmation_status": "draft_failed", "model_participated": False, "model_role": "describe_compile_only", "model_signature_allowed": False, "owner_signature_required": True, "signature_status": "waiting_owner_signature", "failure_reason": "missing_task_subject"}
    understanding = normalize_task_understanding(understanding) if isinstance(understanding, dict) else None
    model_ok = isinstance(understanding, dict) and bool(first_non_empty(understanding.get("task_subject"), understanding.get("core_claim"), understanding.get("user_goal"))) and understanding.get("model_role") == "describe_compile_only"
    draft = create_scbkr_draft(raw_input, task_type)
    if model_ok:
        boundary_rules = normalize_list(understanding.get("boundary_rules"))
        forbidden_dilutions = normalize_list(understanding.get("forbidden_dilutions"))
        acceptance_criteria = normalize_list(understanding.get("acceptance_criteria"))
        causal_chain = normalize_list(understanding.get("causal_chain"))
        core_claim = normalize_text(understanding.get("core_claim"))
        draft["S"]["task_subject"] = understanding.get("task_subject") or draft["S"]["task_subject"]
        output_format = normalize_list(understanding.get("output_format"))
        if output_format:
            draft["S"]["output_format"] = output_format
        logic_items = causal_chain
        if not logic_items and core_claim:
            logic_items = [core_claim]
        if logic_items:
            draft["C"]["core_logic"] = logic_items
        draft["B"]["stop_conditions"] = list(draft["B"].get("stop_conditions", [])) + boundary_rules + forbidden_dilutions
        draft["R"]["acceptance_criteria"] = list(draft["R"].get("acceptance_criteria", [])) + acceptance_criteria
    adopted = (evidence_context or {}).get("adopted_hits", []) or []
    if adopted:
        draft["K"]["references"] = ["使用者原始指令", "SCBKR 基礎責任鏈語法"] + [h.get("excerpt") or h.get("rule") or h.get("summary") or h.get("citation_id") or h.get("case_id") for h in adopted]
    else:
        draft["K"]["references"] = ["使用者原始指令", "SCBKR 基礎責任鏈語法"]
        draft["K"]["source_credibility"] = ["本次未採用四庫資料", "不得聲稱引用既有資料", "本次未命中相關已確認資料。"]
    _human_logic_overrides(raw_input, draft)
    _apply_signature_gate(draft)
    draft.update({"draft_source": "model_assisted_structured" if model_ok else "scbkr_base_logic", "model_participated": model_ok, "model_authored": model_ok, "model_role": "describe_compile_only", "model_signature_allowed": False, "owner_signature_required": True, "signature_status": "waiting_owner_signature", "fallback_used": False, "data_center_context": evidence_context or {}, "referenced_sources": adopted})
    return draft
