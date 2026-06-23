"""Pure SCBKR P4 draft generator.

The functions in this module only build local dictionary drafts. They do not
write files, write ledger events, read data stores, call APIs, call models, or
perform retrieval.
"""

from copy import deepcopy

from core.scbkr.dimensions import SCBKR_REQUIRED_FIELDS
from core.scbkr.templates import DEFAULT_SCBKR_TEMPLATE, TASK_TYPE_HINTS

VALID_TASK_TYPES = tuple(TASK_TYPE_HINTS.keys())
VALID_SOURCE_MODES = ("new", "retrieved", "hybrid", "manual")
VALID_SIMILARITY_ROUTES = ("A", "B", "C", "none")
SIMILARITY_ROUTE_LABELS = {
    "A": "高度相似案例草案",
    "B": "部分相似案例草案",
    "C": "低相似參考草案",
    "none": "全新草案",
}


def validate_generator_inputs(raw_input, task_type, source_mode, similarity_route):
    """Validate generator inputs without side effects."""
    if not isinstance(raw_input, str) or not raw_input.strip():
        raise ValueError("raw_input must be a non-empty string")
    if task_type not in VALID_TASK_TYPES:
        raise ValueError(f"task_type must be one of: {', '.join(VALID_TASK_TYPES)}")
    if source_mode not in VALID_SOURCE_MODES:
        raise ValueError(f"source_mode must be one of: {', '.join(VALID_SOURCE_MODES)}")
    if similarity_route not in VALID_SIMILARITY_ROUTES:
        raise ValueError(
            f"similarity_route must be one of: {', '.join(VALID_SIMILARITY_ROUTES)}"
        )
    return True


def _task_hint(task_type):
    return TASK_TYPE_HINTS[task_type]


def _semantic_profile(raw_input, task_type):
    text = raw_input.strip()
    lower = text.lower()
    is_copy = any(token in text for token in ("文案", "宣傳", "開幕", "商業"))
    is_rule = any(token in text for token in ("規則", "判準", "原則", "不得", "不該", "必須", "驗收"))
    if is_copy:
        subject = text.replace("我要寫一個", "").replace("請寫", "").strip("。 ") or "商業文案"
        return {"subject": subject, "output": "標題、短文案、行動呼籲 CTA", "logic": "先辨識產品/活動主軸，再整理受眾、賣點、語氣與可驗收的文案交付。", "kind": "商業文案"}
    if is_rule:
        subject = text.replace("請把這個", "").replace("整理成可重用規則", "可重用規則").strip("。 ") or "可重用規則"
        return {"subject": subject, "output": "可重用規則草案、禁止條件、驗收條件", "logic": "先抽取使用者判斷，再轉為可確認、可回放、可入庫的規則候選。", "kind": "規則整理"}
    hint = _task_hint(task_type)
    return {"subject": text[:32] or hint["subject"], "output": hint["output_format"], "logic": hint["core_logic"], "kind": hint["subject"]}


def build_s_dimension(raw_input, task_type):
    """Build the S dimension draft from user semantics."""
    profile = _semantic_profile(raw_input, task_type)
    return {
        "task_name": f"{profile['subject']}確認草案",
        "user_instruction": raw_input.strip(),
        "task_subject": profile["subject"],
        "input_content": raw_input.strip(),
        "output_format": profile["output"],
        "interface_type": "SCBKR 工作台",
        "platform_type": "local-sidecar-api",
        "confirmation_status": "draft",
        "pending_questions": ["請確認任務主體、輸出形式與操作平台是否正確。"],
    }


def build_c_dimension(raw_input, task_type):
    """Build the C dimension draft for causal flow framing."""
    profile = _semantic_profile(raw_input, task_type)
    return {
        "flow_steps": ["依使用者原句建立任務理解", "整理 S/C/B/K/R 草案", "等待使用者確認後才生成正式結果"],
        "execution_order": ["先確認任務與邊界", "再生成正式輸出", "最後由使用者驗收與決定是否入庫"],
        "data_flow": ["使用者原句只作為草案依據", "模型草案需通過欄位驗證", "入庫需通過驗收與二次確認"],
        "event_flow": ["建立確認單", "使用者確認責任鏈", "生成正式結果", "使用者驗收", "使用者二次確認入庫"],
        "core_logic": [profile["logic"]],
        "dependencies": ["使用者原始輸入", "目前模型設定", "使用者確認狀態"],
        "failure_impact": ["草案不完整時不得確認", "未確認責任鏈時不得生成", "未驗收時不得入庫"],
        "test_conditions": ["五維欄位完整", "confirmed=false 直到使用者按確認", "生成結果不得回到確認單草案"],
        "pending_questions": ["請確認流程順序、依賴與測試條件是否足夠。"],
    }


def build_b_dimension(raw_input, task_type):
    """Build the B dimension draft for boundary and behavior framing."""
    return {
        "data_read_scope": ["僅讀取本次使用者輸入與使用者允許的 Data Center 內容"],
        "data_write_scope": ["普通聊天不寫入", "驗收前不寫入", "入庫必須使用者二次確認"],
        "local_scope": ["透過桌面 sidecar / 本地 API 執行", "手機僅作操作入口"],
        "external_scope": ["本地 loopback 模型不視為外部 API", "遠端 API 必須取得 external_api 權限"],
        "permission_switches": {"model_generate": "required_for_generation", "external_api": "remote_only", "storage_confirm": "user_second_confirm"},
        "stop_conditions": ["使用者尚未確認責任鏈", "模型輸出確認單而非正式結果", "模型自行宣稱驗收或入庫"],
        "error_handling": ["低階錯誤需轉為人話", "模型草案失敗才使用語意 fallback", "不得自動改成 confirmed"],
        "sensitive_operation_confirm": True,
        "storage_conditions": ["review_passed=true 後才能建議入庫", "storage_confirmed=false 時不得實體寫入"],
        "pending_questions": ["請確認資料讀寫範圍與禁止行為是否完整。"],
    }


def build_k_dimension(raw_input, task_type):
    """Build the K dimension draft for basis and style framing."""
    profile = _semantic_profile(raw_input, task_type)
    return {
        "references": ["使用者原始輸入", "已確認的 SCBKR 責任鏈"],
        "technical_docs": ["schemas/scbkr.schema.json", "schemas/task.schema.json"],
        "corpus_sources": [],
        "style_settings": {"language": "繁體中文", "tone": "清楚、可驗收", "task_kind": profile["kind"]},
        "framework_choice": "SCBKR 分步確認流程",
        "model_basis": ["依使用者原句產生草案；有效模型草案不得被 fallback 覆蓋"],
        "history_cases": [],
        "source_credibility": ["使用者輸入為主要任務依據", "Data Center 內容僅在使用者允許時作輔助"],
        "pending_questions": ["請確認依據、風格與來源可信度要求。"],
    }


def build_r_dimension(raw_input, task_type):
    """Build the R dimension draft for review and storage framing."""
    profile = _semantic_profile(raw_input, task_type)
    return {
        "expected_outputs": [profile["output"]],
        "acceptance_criteria": ["符合使用者原始任務", "不輸出 SCBKR 草案或 JSON", "可由使用者明確驗收"],
        "ledger_requirements": ["任務、確認、生成、驗收、入庫事件需可審計"],
        "storage_options": ["vector", "corpus", "logic", "memory"],
        "signature_status": "draft",
        "review_status": "not_started",
        "replay_requirements": ["保留使用者原句", "保留確認快照", "保留生成與驗收結果"],
        "memory_rule_generated": False,
        "pending_questions": ["請確認驗收、回放與入庫選項是否符合任務需求。"],
    }


def _ensure_dimension_fields(draft):
    for dimension, required_fields in SCBKR_REQUIRED_FIELDS.items():
        missing_fields = [field for field in required_fields if field not in draft[dimension]]
        if missing_fields:
            raise ValueError(f"{dimension} missing required fields: {', '.join(missing_fields)}")


def create_scbkr_draft(
    raw_input,
    task_type="general",
    source_mode="new",
    similarity_route="none",
    source_case_ids=None,
):
    """Create a SCBKR five-dimension draft waiting for user confirmation."""
    validate_generator_inputs(raw_input, task_type, source_mode, similarity_route)

    source_case_ids = [] if source_case_ids is None else list(source_case_ids)
    draft = deepcopy(DEFAULT_SCBKR_TEMPLATE)
    draft["S"] = build_s_dimension(raw_input, task_type)
    draft["C"] = build_c_dimension(raw_input, task_type)
    draft["B"] = build_b_dimension(raw_input, task_type)
    draft["K"] = build_k_dimension(raw_input, task_type)
    draft["R"] = build_r_dimension(raw_input, task_type)
    if source_mode != "new":
        draft["B"]["external_scope"] = ["不呼叫 API", "不呼叫模型", "不進行外部搜尋", "不進行真 RAG 檢索"]
    draft["source_mode"] = source_mode
    draft["similarity_route"] = similarity_route
    draft["source_case_ids"] = source_case_ids
    draft["confirmation_status"] = "draft"
    draft["pending_questions"] = [
        "請確認此 SCBKR 草案是否可作為後續任務責任鏈。",
        f"目前相似路徑標註：{SIMILARITY_ROUTE_LABELS[similarity_route]}。",
    ]
    _ensure_dimension_fields(draft)
    return draft
