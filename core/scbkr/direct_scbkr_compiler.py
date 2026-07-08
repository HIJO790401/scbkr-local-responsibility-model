"""Direct SCBKR compiler.

This compiler treats the user judgement itself as the source of the five
dimensions. It is generic and intentionally avoids scenario-specific branches.
"""

from __future__ import annotations

from typing import Any

from core.kernel.scbkr_kernel_compiler import KERNEL_NAME


def _clean_input(user_input: str) -> str:
    return " ".join(str(user_input or "").strip().split())


def _subject_phrase(user_input: str) -> str:
    text = _clean_input(user_input)
    for marker in ("幫我建立一個", "幫我建立", "幫我生成", "把這個", "把它", "write this", "turn this"):
        text = text.replace(marker, "")
    if "：" in text and "規則" in text.split("：", 1)[0]:
        text = text.split("：", 1)[0]
    if ":" in text and "rule" in text.split(":", 1)[0].lower():
        text = text.split(":", 1)[0]
    text = text.replace("規則表單", "規則").strip(" 。.")
    return text[:120] or "使用者本地判斷規則"


def compile_direct_scbkr_draft(
    user_input: str,
    kernel_pack: dict[str, Any],
    *,
    plan_level: str = "FREE",
    locale: str = "zh-TW",
) -> dict[str, Any]:
    subject = _subject_phrase(user_input)
    return {
        "meta": {
            "compiler": "direct_scbkr_compiler",
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
        },
        "confirmation_status": "draft",
        "draft_source": "direct_scbkr_kernel_compiler",
        "fallback_used": False,
        "model_authored": False,
        "draft_model_call_skipped_reason": "direct_scbkr_kernel_compiler",
        "rule_assist_plan": plan_level,
        "model_participated": False,
        "compiler_report": {
            "status": "direct_kernel_compiled",
            "attempts": 1,
            "repairs": 0,
            "errors": [],
            "model_used": False,
        },
        "S": {
            "task_name": f"{subject[:48]}規則草稿",
            "task_subject": subject,
            "rule_subject": subject,
            "user_instruction": user_input,
            "input_content": user_input,
            "output_format": "可編輯、可簽名、可入庫的本地 SCBKR 規則草稿",
            "interface_type": "local_first_ai_chat_and_workbench",
            "platform_type": "SCBKR local rule OS",
            "applies_when": [f"使用者遇到與此判斷相同或相近的情境：{subject}"],
            "does_not_apply_when": ["情境、角色、資料來源或風險條件與本規則不同。"],
            "expected_output": ["輸出可編輯、可簽名、可入庫的本地 SCBKR 規則草稿。"],
            "rule_os_dimension_contract": {"requires_user_confirmation": True, "usage_conditions": ["簽名前必須確認主體與適用情境。"], "gap_notes": []},
        },
        "C": {
            "core_logic": "使用者判斷先經本地 Kernel 轉成 S/C/B/K/R，再由使用者簽名後成為正式本地規則。",
            "user_core_judgement": user_input,
            "flow_steps": ["偵測規則意圖", "草擬五維確認單", "使用者編輯", "使用者簽名", "驗收", "入庫", "下次以最小規則包回答"],
            "execution_order": ["draft", "owner_edit", "owner_signature", "review", "storage_confirm", "active_rule_package"],
            "data_flow": "使用者原句只進本地草稿；正式引用只取 signed/reviewed/active LOGIC/CORPUS/MEMORY，VECTOR 僅召回。",
            "event_flow": "每一步寫入 replay ledger，模型不能跳過使用者簽名與二次入庫確認。",
            "causal_chain": [
                "使用者提出可重複使用的判斷。",
                "此判斷若直接交給模型自由回答，會造成標準漂移。",
                "因此先轉成 S/C/B/K/R，待使用者簽名後才成為本地正式依據。",
            ],
            "ignored_consequence": ["若忽略此規則，模型可能用聊天上下文或一般常識替代使用者標準。"],
            "why_rule_needed": "把使用者判斷變成可回放、可驗收、可引用的本地規則。",
            "dependencies": ["本地 Kernel Pack", "使用者簽名", "四庫狀態", "post-check"],
            "failure_impact": "若跳過此因果鏈，模型會回到一般聊天或把未簽名內容當依據。",
            "test_conditions": ["未簽名前不得入庫", "Active 前不得正式引用", "回答時 chat_context_used 必須為 false"],
            "rule_os_dimension_contract": {"requires_user_confirmation": True, "usage_conditions": ["因果鏈需能回放。"], "gap_notes": []},
        },
        "B": {
            "data_read_scope": ["只讀取與本次需求相關的 signed/reviewed/active 四庫資料與必要召回候選。"],
            "data_write_scope": ["簽名與二次確認前不得寫入正式庫。"],
            "local_scope": ["本地優先；使用者資料不作外部訓練或未授權同步。"],
            "external_scope": ["外部模型或工具只能接收最小規則包，不得接收完整記憶庫。"],
            "permission_switches": ["model_generate", "storage_write", "external_api_call_requires_permission"],
            "forbidden": [
                "模型不得替使用者簽名、入庫、啟用或終裁。",
                "不得把聊天上下文當正式 K 依據。",
                "不得宣稱已發布、已寄出、已付款、已簽名、已入庫或已執行外部動作。",
            ],
            "stop_conditions": [
                "缺少使用者簽名時停止在草稿。",
                "缺少正式 LOGIC/CORPUS/MEMORY 依據時標示 NEED_DEFINITION 或 OWNER_REVIEW。",
                "涉及發布、寄送、付款、刪除、外部工具或高風險決策時必須要求使用者確認。",
            ],
            "error_handling": "若缺資料、缺簽名、缺驗收或 post-check 失敗，降級成本地安全草稿。",
            "storage_conditions": "owner_signed + review_passed + second_storage_confirm 才能寫入 LOGIC/CORPUS/MEMORY/VECTOR。",
            "model_must_not": ["sign", "store", "activate", "publish", "send", "pay", "delete", "execute_external_action"],
            "requires_user_confirmation_when": ["正式引用", "入庫", "啟用", "對外執行", "高風險動作"],
            "rule_os_dimension_contract": {"requires_user_confirmation": True, "usage_conditions": ["邊界不足時不得簽名。"], "gap_notes": []},
        },
        "K": {
            "references": ["使用者原始判斷", "本地 SCBKR Kernel Pack", "已簽名且已驗收的本地四庫"],
            "technical_docs": ["SCBKR Kernel Pack", "Rule OS four-store policy", "Token / Cost Audit"],
            "style_settings": "使用者語言優先；繁中輸入以繁中回覆，英文輸入以英文回覆。",
            "framework_choice": "SCBKR five-dimensional confirmation sheet with local-first rule package retrieval.",
            "model_basis": "模型只能依最小 current_rule_package 草擬，不得把聊天上下文當正式依據。",
            "citable_sources": ["LOGIC: signed/reviewed/active rules", "CORPUS: signed/reviewed/active data", "MEMORY: signed/reviewed/active long-term preferences"],
            "non_citable_sources": ["VECTOR candidates", "unsigned chat context", "model guesses", "unreviewed drafts"],
            "four_store_policy": {
                "LOGIC": "formal rule basis",
                "CORPUS": "formal data basis",
                "MEMORY": "formal preference basis",
                "VECTOR": "recall only; not formal K basis",
            },
            "when_basis_missing": "輸出 DRAFT / OWNER_REVIEW / NEED_DEFINITION，不得假裝正式依據存在。",
            "source_credibility": "VECTOR 只召回；聊天上下文不是正式 K 依據。",
            "rule_os_dimension_contract": {"requires_user_confirmation": True, "usage_conditions": ["K 必須區分正式依據與候選召回。"], "gap_notes": []},
        },
        "R": {
            "expected_outputs": ["可編輯 S/C/B/K/R 草稿", "使用者簽名紀錄", "驗收結果", "入庫紀錄", "下次回答的 current_rule_package"],
            "acceptance_criteria": ["使用者可逐欄檢查 S/C/B/K/R。", "使用者簽名後才可入庫與引用。"],
            "ledger_requirements": ["record_route", "record_signature", "record_review", "record_storage", "record_rule_package", "record_post_check"],
            "storage_options": ["LOGIC", "CORPUS", "MEMORY", "VECTOR"],
            "signature_status": "waiting_owner_signature",
            "review_status": "not_reviewed",
            "user_signature_required": True,
            "model_cannot_sign": True,
            "formation_conditions": [
                "S/C/B/K/R 五維都有具體內容。",
                "使用者逐欄確認。",
                "使用者簽名後才成立。",
            ],
            "failure_conditions": [
                "失效：使用者未簽名。",
                "失效：模型越位宣稱已簽名、已入庫或已啟用。",
                "失效：VECTOR 或聊天上下文被當正式依據。",
            ],
            "replay_requirements": ["記錄 user_input、kernel_pack、validator 結果、使用者簽名、入庫結果與引用規則包。"],
            "repair_path": ["修復：回到失敗維度補資料", "重新驗證", "使用者重新簽名", "保留版本回放"],
            "real_world_responsibility": "使用者採用本規則後，現實行動與結果由使用者自行承擔。",
            "kernel_attribution": f"本草稿由本地模型依據「{KERNEL_NAME}」生成；Kernel 提供結構，不代表規則已成立。",
            "rule_os_dimension_contract": {"requires_user_confirmation": True, "usage_conditions": ["只有使用者可簽收責任。"], "gap_notes": []},
        },
    }
