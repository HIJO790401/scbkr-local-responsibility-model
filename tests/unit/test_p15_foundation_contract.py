from pathlib import Path

from core.workflow.generation_flow import build_generation_messages, build_scbkr_draft_generation_messages
from core.scbkr.generator import create_scbkr_draft
from core.scbkr.confirmation import confirm_all_dimensions

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "apps/web/src/V2App.tsx").read_text(encoding="utf-8")
CSS = (ROOT / "apps/web/src/App.css").read_text(encoding="utf-8")


def test_p15_navigation_and_chat_first_contract():
    for label in ["SCBKR 聊天", "Workbench / SCBKR 工作台", "規則中心", "四庫資料中心", "工具與搜尋", "模型設定"]:
        assert label in APP
    for label in ["一般聊天", "上網查證", "查四庫", "建規則", "第0原理建議閘", "草擬確認單", "補角色與邊界", "保持一般聊天"]:
        assert label in APP
    assert 'setView("workbench")' in APP
    assert "未簽名 SCBKR 確認單已建立，已進入工作台" in APP
    assert "FREE 草稿層確認單已建立，已進入工作台" in APP
    assert "defer_model_draft" in APP


def test_p15_workbench_has_readable_scbkr_dimensions_and_patch_flow():
    assert "task raw JSON" not in APP
    assert "RESPONSIBILITY MATRIX" in APP
    assert "pendingPatch" in APP
    assert "模型提出欄位修改草案" in APP
    assert "套用欄位修改" in APP
    for label in ["這件事是什麼", "流程與原因", "界線與禁止事項", "依據與引用", "責任與驗收"]:
        assert label in APP
    for field in ["formation_conditions", "failure_conditions", "repair_path", "store_role", "store_purpose", "citation_policy"]:
        assert field in APP


def test_p15_generation_review_storage_and_output_contract():
    assert "/generate" in APP
    assert "開始生成" in APP
    assert "通過驗收" in APP
    assert "驗收失敗" in APP
    assert "二次確認入庫" in APP
    assert "模型閱讀草稿" in APP
    assert "搜尋並閱讀" in APP
    assert "四庫資料中心" in APP
    assert "LM Studio" in APP
    assert "開啟模型生成權限" in APP


def test_p15_prompt_contracts():
    draft_messages = build_scbkr_draft_generation_messages("做一個打地鼠遊戲", "game_design")
    draft_prompt = draft_messages[0]["content"]
    assert "SCBKR 草案生成階段" in draft_prompt
    assert "Do not execute the task" in draft_prompt
    assert "Do not set confirmed to true" in draft_prompt

    task = {"confirmed": True, "status": "confirmed", "review_passed": False, "storage_confirmed": False, "raw_input": "做一個打地鼠遊戲", "task_name": "打地鼠", "task_type": "game_design"}
    scbkr = create_scbkr_draft("做一個打地鼠遊戲", "game_design")
    confirm_all_dimensions(scbkr, confirmed_by="user", signature="user")
    execution_prompt = build_generation_messages(task, scbkr)[0]["content"]
    assert "Do not recreate the confirmation sheet" in execution_prompt
    assert "S/C/B/K/R 已由使用者確認" in execution_prompt


def test_p15_css_overflow_guards():
    assert "overflow-x: hidden" in CSS
    assert ".desktop-stage" in CSS and "overflow: auto" in CSS
    assert ".dashboard-grid" in CSS
    assert ".flow-steps > button" in CSS
    assert "white-space: pre-wrap" in CSS
