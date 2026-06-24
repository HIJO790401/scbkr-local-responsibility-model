from pathlib import Path

APP = Path("apps/web/src/App.tsx").read_text(encoding="utf-8")
CSS = Path("apps/web/src/App.css").read_text(encoding="utf-8")


def test_desktop_has_left_nav_chat_center_and_workbench_right():
    assert "side-nav" in APP
    for label in ["聊天", "工作台", "資料中心", "模型設定", "審計資料"]:
        assert label in APP
    assert "split-layout" in APP and "chat-main" in APP and "workbench-panel" in APP
    assert "grid-template-columns: minmax(0, 1fr) minmax(360px, 42vw)" in CSS


def test_chat_surface_excludes_scbkr_form_and_raw_json():
    chat_source = APP.split('aria-label="一般聊天主視窗"')[1].split('const workbench =')[0]
    assert "SCBKR 五張摘要卡" not in chat_source
    assert "JsonBlock" not in chat_source
    assert "Raw" not in chat_source
    assert "將此對話轉為工作台任務" in chat_source


def test_workbench_has_five_summary_cards_and_llm_edit_area():
    for title in ["S｜任務主體", "C｜流程因果", "B｜邊界行為", "K｜依據風格", "R｜回放驗收"]:
        assert title in APP
    for phrase in ["請模型修改工作台", "選擇修改層", "產生修改草案", "套用修改", "取消"]:
        assert phrase in APP


def test_patch_draft_is_not_auto_applied_and_apply_invalidates_downstream():
    assert "setPendingPatch(r.patch)" in APP
    assert "套用修改" in APP
    assert 'confirmed: false' in APP
    assert 'generation_result: undefined' in APP
    assert 'review_result: undefined' in APP
    assert 'storage_plan: undefined' in APP


def test_completed_or_physical_write_tasks_are_locked():
    assert "physical_write_performed" in APP
    assert 'task?.status === "completed"' in APP
    assert "不能直接修改原任務；請建立新版本或新任務" in APP


def test_mobile_drawer_and_workbench_not_under_chat():
    assert "mobile-drawer" in APP
    assert "menu-button" in APP
    assert "position: fixed; inset: 0 0 0 auto" in CSS
    for label in ["聊天", "工作台", "資料中心", "模型設定", "審計資料"]:
        assert label in APP


def test_data_center_and_storage_labels_are_traditional_chinese():
    for label in ["任務紀錄", "確認單", "生成結果", "驗收紀錄", "入庫資料", "向量庫", "語料庫", "程式邏輯庫", "記憶庫", "回放帳本"]:
        assert label in APP
    for label in ["後端 API URL", "測試後端 API", "儲存設定", "測試模型連線", "清除 API Key", "切回 Sandbox"]:
        assert label in APP


def test_patch1_model_generate_permission_entry_uses_existing_api():
    assert "開啟模型生成權限" in APP
    assert "enableModelGenerate" in APP
    assert 'api("/api/settings/permissions"' in APP
    assert "JSON.stringify({ model_generate: true })" in APP
    assert "模型生成權限已開啟" in APP
    assert "模型生成權限開啟失敗，請確認後端 API 是否連線。" in APP
    assert "fetch(\"/api/settings/permissions" not in APP


def test_patch1_waiting_review_actions_include_fail_and_return_to_revision():
    assert 'can = { confirm: task?.status === "waiting_user_confirm"' in APP
    assert 'review: task?.status === "waiting_review"' in APP
    assert '<button onClick={() => review("pass")}>通過驗收</button>' in APP
    assert '<button onClick={() => review("fail")}>驗收失敗</button>' in APP
    assert '<button onClick={returnToRevision}>退回修改</button>' in APP
    assert 'const review = (decision: "pass" | "fail")' in APP
    assert 'review_decision: decision' in APP
    assert 'status: "waiting_user_confirm"' in APP
    assert 'review_passed: false' in APP


def test_patch1_raw_permission_key_is_not_primary_visible_label():
    visible_source = APP.split("return <main", 1)[1]
    assert ">model_generate<" not in visible_source
    assert "model_generate：" not in visible_source
