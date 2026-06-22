from pathlib import Path

from core.workflow.generation_flow import build_generation_messages, build_scbkr_draft_generation_messages
from core.scbkr.generator import create_scbkr_draft
from core.scbkr.confirmation import confirm_all_dimensions

ROOT = Path(__file__).resolve().parents[2]
APP = (ROOT / "apps/web/src/App.tsx").read_text(encoding="utf-8")
CSS = (ROOT / "apps/web/src/App.css").read_text(encoding="utf-8")


def test_p15_navigation_and_chat_to_workbench_contract():
    for label in ["Chat / 任務入口", "Workbench / SCBKR 工作台", "Model Settings / 模型設定", "Data Center / 資料中心", "Audit / 審計資料"]:
        assert label in APP
    assert "任務輸入框" in APP
    assert "建立 SCBKR 任務 / 建立確認單" in APP
    assert "setPage(\"workbench\")" in APP
    assert "已將聊天內容轉為 SCBKR 任務草案" in APP


def test_p15_workbench_not_raw_json_first_and_has_editable_dimensions():
    assert "task raw JSON" not in APP
    assert "Raw Audit Details（預設關閉）" in APP
    assert "<details><summary>點擊展開 JSON</summary>" in APP
    assert "SCBKR 五維確認單｜可編輯" in APP
    assert "onChange={(e: any) => updateField(dim, field.key, e.target.value)}" in APP
    for label in ["任務名稱", "使用者指令", "任務主體", "輸入內容", "輸出形式", "操作介面", "平台類型"]:
        assert label in APP
    for label in ["流程拆解", "執行順序", "資料流", "事件流", "核心邏輯", "依賴關係", "失敗影響", "測試條件"]:
        assert label in APP
    for label in ["資料讀取範圍", "資料寫入範圍", "權限開關", "停止條件", "錯誤處理", "入庫條件"]:
        assert label in APP
    for label in ["參考資料", "技術文件", "語料來源", "風格設定", "模型依據", "歷史案例", "待確認項目"]:
        assert label in APP
    for label in ["預期輸出", "驗收條件", "回放要求", "入庫選項", "簽名狀態"]:
        assert label in APP


def test_p15_generation_review_storage_and_output_contract():
    assert "confirmed=false：請先確認責任鏈，模型不可執行。" in APP
    assert "disabled={!task?.confirmed}" in APP
    assert "result?.content ?? result?.generated_text" in APP
    assert "模型回覆 / 生成結果" in APP
    assert "通過驗收" in APP
    assert "驗收失敗 / 建立記憶規則" in APP
    assert "二次確認入庫" in APP
    assert "我的資料中心" in APP
    assert "LM Studio" in APP


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
    assert "max-width: 1180px" in CSS
    assert "white-space: pre-wrap" in CSS
    assert ".raw-json" in CSS
