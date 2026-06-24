"""SCBKR draft grammar, understanding compiler, and evidence relation gate."""
from __future__ import annotations
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


def build_scbkr_grammar_pack() -> str:
    return SCBKR_GRAMMAR_PACK_ZH


def build_task_understanding_messages(raw_input: str, task_type: str, evidence_context: dict[str, Any] | None = None) -> list[dict[str, str]]:
    adopted = (evidence_context or {}).get("adopted_hits", [])
    return [
        {"role": "system", "content": SCBKR_GRAMMAR_PACK_ZH + "\nReturn JSON only."},
        {"role": "user", "content": str({"raw_input": raw_input, "task_type": task_type, "adopted_evidence": adopted})},
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
    for key in ("滷肉飯", "商業", "文案", "餐飲", "ui", "介面", "工作台", "人類", "描述", "確定性", "邏輯"):
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
    elif ("商業" in q and "商業" in c) or ("餐飲" in q and "餐飲" in c):
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
    model_ok = isinstance(understanding, dict) and bool(str(understanding.get("task_subject") or understanding.get("core_claim") or "").strip()) and not any(understanding.get(k) is True for k in ("confirmed", "review_passed", "storage_confirmed", "physical_write_performed")) and understanding.get("model_role", "describe_compile_only") == "describe_compile_only"
    draft = create_scbkr_draft(raw_input, task_type)
    if model_ok:
        draft["S"]["task_subject"] = understanding.get("task_subject") or draft["S"]["task_subject"]
        draft["C"]["core_logic"] = understanding.get("causal_chain") or [understanding.get("core_claim")]
        draft["B"]["stop_conditions"] = list(draft["B"].get("stop_conditions", [])) + list(understanding.get("boundary_rules") or []) + list(understanding.get("forbidden_dilutions") or [])
        draft["R"]["acceptance_criteria"] = list(draft["R"].get("acceptance_criteria", [])) + list(understanding.get("acceptance_criteria") or [])
    adopted = (evidence_context or {}).get("adopted_hits", []) or []
    if adopted:
        draft["K"]["references"] = ["使用者原始指令", "SCBKR 基礎責任鏈語法"] + [h.get("rule") or h.get("summary") or h.get("case_id") for h in adopted]
    else:
        draft["K"]["references"] = ["使用者原始指令", "SCBKR 基礎責任鏈語法"]
        draft["K"]["source_credibility"] = ["本次未採用四庫資料", "不得聲稱引用既有資料", "本次未命中相關已確認資料。"]
    _human_logic_overrides(raw_input, draft)
    _apply_signature_gate(draft)
    draft.update({"draft_source": "model_assisted_structured" if model_ok else "scbkr_base_logic", "model_participated": model_ok, "model_authored": model_ok, "model_role": "describe_compile_only", "model_signature_allowed": False, "owner_signature_required": True, "signature_status": "waiting_owner_signature", "fallback_used": False, "data_center_context": evidence_context or {}, "referenced_sources": adopted})
    return draft
