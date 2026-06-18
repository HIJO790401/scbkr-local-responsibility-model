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


def build_s_dimension(raw_input, task_type):
    """Build the S dimension draft for interface and subject framing."""
    hint = _task_hint(task_type)
    return {
        "task_name": f"{hint['subject']}草案",
        "user_instruction": raw_input.strip(),
        "task_subject": hint["subject"],
        "input_content": raw_input.strip(),
        "output_format": hint["output_format"],
        "interface_type": "本地責任鏈工作台",
        "platform_type": "local",
        "confirmation_status": "draft",
        "pending_questions": ["請確認任務主體、輸出形式與操作平台是否正確。"],
    }


def build_c_dimension(raw_input, task_type):
    """Build the C dimension draft for causal flow framing."""
    hint = _task_hint(task_type)
    return {
        "flow_steps": ["建立 SCBKR 五維草案", "等待使用者確認", "確認後才可進入後續生成階段"],
        "execution_order": ["先確認 S/C/B/K/R", "再進入後續階段", "P4 不執行生成"],
        "data_flow": ["raw_input 只用於本地草案欄位", "P4 不讀取 data 目錄", "P4 不寫入任何資料儲存"],
        "event_flow": ["草案建立", "等待使用者確認"],
        "core_logic": [hint["core_logic"], "P4 僅建立責任鏈確認單草案。"],
        "dependencies": ["P1 SCBKR 欄位結構", "P1 task_type enum"],
        "failure_impact": ["輸入不完整時停止並回報 ValueError", "未確認前不得進入 generate"],
        "test_conditions": ["五維欄位完整", "輸入驗證有效", "不呼叫外部服務"],
        "pending_questions": ["請確認流程順序、依賴與測試條件是否足夠。"],
    }


def build_b_dimension(raw_input, task_type):
    """Build the B dimension draft for boundary and behavior framing."""
    return {
        "data_read_scope": ["僅使用呼叫方傳入 raw_input / task_type / source metadata"],
        "data_write_scope": ["P4 不寫檔", "P4 不寫 ledger", "P4 不寫 DB", "P4 不寫四庫"],
        "local_scope": ["純 Python dict 草案生成", "純函式修改草案"],
        "external_scope": ["不呼叫 API", "不呼叫模型", "不進行外部搜尋", "不進行真 RAG 檢索"],
        "permission_switches": {
            "can_generate": False,
            "can_write_ledger": False,
            "can_write_storage": False,
        },
        "stop_conditions": ["raw_input 空白", "task_type 無效", "source_mode 無效", "similarity_route 無效"],
        "error_handling": ["輸入驗證失敗時 raise ValueError", "不得自動修正為 confirmed"],
        "sensitive_operation_confirm": False,
        "storage_conditions": ["review_passed = false 時不得標準入庫", "storage_confirmed = false 時不得寫入四庫"],
        "pending_questions": ["請確認資料讀寫範圍與禁止行為是否完整。"],
    }


def build_k_dimension(raw_input, task_type):
    """Build the K dimension draft for basis and style framing."""
    hint = _task_hint(task_type)
    return {
        "references": ["SCBKR v1.2-FINAL 內嵌規格", "P1 Task / SCBKR schema", "P1 dimensions constants"],
        "technical_docs": ["schemas/scbkr.schema.json", "schemas/task.schema.json"],
        "corpus_sources": [],
        "style_settings": {"language": "繁體中文", "tone": "理性、清楚、可驗收"},
        "framework_choice": "純 Python 函式",
        "model_basis": ["P4 不接入模型；模型依據需待 P5 以後確認"],
        "history_cases": [],
        "source_credibility": [hint["subject"], "similarity_route 只作欄位標註，不代表真檢索結果"],
        "pending_questions": ["請確認依據、風格與來源可信度要求。"],
    }


def build_r_dimension(raw_input, task_type):
    """Build the R dimension draft for replay and signature framing."""
    return {
        "expected_outputs": ["SCBKR 五維確認單草案 dict"],
        "acceptance_criteria": ["S/C/B/K/R 欄位完整", "confirmation_status = draft", "使用者確認前不得 generate"],
        "ledger_requirements": ["P4 不寫 ledger", "後續若接入 ledger 必須 append-only"],
        "storage_options": ["P4 不寫四庫", "確認入庫需等待後續階段"],
        "signature_status": "draft",
        "review_status": "not_started",
        "replay_requirements": ["保留 source_mode", "保留 similarity_route", "保留 source_case_ids"],
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
