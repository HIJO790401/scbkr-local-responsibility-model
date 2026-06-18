"""Pure SCBKR P4 draft templates.

This module contains data only. It performs no IO, retrieval, generation,
ledger writing, database access, API calls, or model calls.
"""

DEFAULT_SCBKR_TEMPLATE = {
    "S": {
        "task_name": "待命名任務",
        "user_instruction": "",
        "task_subject": "待確認任務主體",
        "input_content": "",
        "output_format": "待使用者確認輸出形式",
        "interface_type": "本地責任鏈工作台",
        "platform_type": "local",
        "confirmation_status": "draft",
        "pending_questions": [],
    },
    "C": {
        "flow_steps": [],
        "execution_order": [],
        "data_flow": [],
        "event_flow": [],
        "core_logic": [],
        "dependencies": [],
        "failure_impact": [],
        "test_conditions": [],
        "pending_questions": [],
    },
    "B": {
        "data_read_scope": [],
        "data_write_scope": [],
        "local_scope": [],
        "external_scope": [],
        "permission_switches": {},
        "stop_conditions": [],
        "error_handling": [],
        "sensitive_operation_confirm": False,
        "storage_conditions": [],
        "pending_questions": [],
    },
    "K": {
        "references": [],
        "technical_docs": [],
        "corpus_sources": [],
        "style_settings": {},
        "framework_choice": "待確認",
        "model_basis": [],
        "history_cases": [],
        "source_credibility": [],
        "pending_questions": [],
    },
    "R": {
        "expected_outputs": [],
        "acceptance_criteria": [],
        "ledger_requirements": [],
        "storage_options": [],
        "signature_status": "draft",
        "review_status": "not_started",
        "replay_requirements": [],
        "memory_rule_generated": False,
        "pending_questions": [],
    },
}

TASK_TYPE_HINTS = {
    "general": {
        "subject": "一般任務",
        "output_format": "結構化回覆草案",
        "core_logic": "先釐清需求，再整理可驗收的執行步驟。",
    },
    "coding": {
        "subject": "程式開發任務",
        "output_format": "程式變更計畫與驗收條件草案",
        "core_logic": "先界定檔案範圍、測試方式與禁止越界項目。",
    },
    "info_search": {
        "subject": "資訊查詢任務",
        "output_format": "來源導向的摘要草案",
        "core_logic": "先確認問題、來源需求與不可使用未驗證資訊的邊界。",
    },
    "fraud_audit": {
        "subject": "詐騙稽核任務",
        "output_format": "風險訊號與查核步驟草案",
        "core_logic": "先辨識疑點、證據需求與不可直接定罪的限制。",
    },
    "document_audit": {
        "subject": "文件稽核任務",
        "output_format": "文件問題清單與修正建議草案",
        "core_logic": "先確認文件目的、受眾、稽核標準與修正邊界。",
    },
    "app_design": {
        "subject": "應用設計任務",
        "output_format": "產品流程與介面規格草案",
        "core_logic": "先整理使用者路徑、核心功能、限制與驗收方式。",
    },
    "game_design": {
        "subject": "遊戲設計任務",
        "output_format": "玩法、系統與內容規格草案",
        "core_logic": "先釐清核心循環、規則、資源與體驗目標。",
    },
    "animation": {
        "subject": "動畫任務",
        "output_format": "分鏡、節奏與輸出規格草案",
        "core_logic": "先確認畫面、動作、時間軸、風格與交付格式。",
    },
    "music": {
        "subject": "音樂任務",
        "output_format": "曲風、段落與製作規格草案",
        "core_logic": "先確認用途、風格、段落、限制與授權邊界。",
    },
    "privacy": {
        "subject": "隱私任務",
        "output_format": "資料風險與保護措施草案",
        "core_logic": "先確認資料類型、讀寫邊界、敏感操作與最小化原則。",
    },
    "workflow": {
        "subject": "工作流程任務",
        "output_format": "流程節點、責任與驗收條件草案",
        "core_logic": "先拆解節點、前後依賴、停止條件與責任邊界。",
    },
    "private_memory": {
        "subject": "私人記憶任務",
        "output_format": "記憶規則候選草案",
        "core_logic": "先確認是否可記憶、記憶範圍、敏感性與使用者確認。",
    },
}
