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
    assert 'review: task?.status === "waiting_review" && Boolean(task?.generation_result)' in APP
    assert 'review: task?.status === "waiting_review" || Boolean(task?.generation_result)' not in APP
    assert 'revise: ["waiting_review", "review_failed", "rollback_requested"].includes(task?.status ?? "") && !locked' in APP
    assert '<button onClick={() => review("pass")}>通過驗收</button>' in APP
    assert '<button onClick={() => review("fail")}>驗收失敗</button>' in APP
    assert '<button onClick={returnToRevision}>退回修改</button>' in APP
    assert 'const review = (decision: "pass" | "fail")' in APP
    assert 'review_decision: decision' in APP
    assert 'status: "waiting_user_confirm"' in APP
    assert 'review_passed: false' in APP


def test_patch2_return_to_revision_invalidates_downstream_state():
    assert "const invalidateDownstreamForRevision = (current: TaskSummary): TaskSummary" in APP
    assert "const localRevision = invalidateDownstreamForRevision(task)" in APP
    assert "setTask(localRevision)" in APP
    for assignment in [
        'confirmed: false',
        'status: "waiting_user_confirm"',
        'review_passed: false',
        'storage_confirmed: false',
    ]:
        assert assignment in APP
    for field in [
        "generation_result",
        "review_result",
        "storage_suggestion",
        "storage_request",
        "storage_plan",
        "storage_result",
        "memory_rule_draft",
    ]:
        assert f"delete next.{field};" in APP
    assert "setStorageSuggestion(null)" in APP
    assert "setSelectedTargets([])" in APP
    assert "setPendingPatch(null)" in APP
    assert "舊生成、驗收與入庫資料已作廢" in APP


def test_patch2_review_actions_require_waiting_review_and_generation_result():
    assert 'review: task?.status === "waiting_review" && Boolean(task?.generation_result)' in APP
    assert 'review: task?.status === "waiting_review" || Boolean(task?.generation_result)' not in APP
    action_source = APP.split('<section className="step-card action-card">', 1)[1].split('{can.suggest &&', 1)[0]
    assert "can.review &&" in action_source
    assert "通過驗收" in action_source
    assert "驗收失敗" in action_source


def test_patch1_raw_permission_key_is_not_primary_visible_label():
    visible_source = APP.split("return <main", 1)[1]
    assert ">model_generate<" not in visible_source
    assert "model_generate：" not in visible_source


def test_patch3_return_to_revision_persists_scbkr_revision():
    assert "const returnToRevision = async ()" in APP
    assert 'api<TaskSummary>(`/api/tasks/${task.task_id}/scbkr`, {' in APP
    assert 'method: "PATCH"' in APP
    assert 'scbkr: task.scbkr' in APP
    assert 'layer: "return_to_revision"' in APP
    assert 'const persisted = await run("退回修改"' in APP
    assert "setTask(invalidateDownstreamForRevision(persisted))" in APP
    assert APP.count("invalidateDownstreamForRevision(") >= 2
    assert "setStorageSuggestion(null)" in APP
    assert "setSelectedTargets([])" in APP
    assert "setPendingPatch(null)" in APP


def test_patch3_review_failed_can_revise_without_review_buttons():
    assert 'review: task?.status === "waiting_review" && Boolean(task?.generation_result)' in APP
    assert 'revise: ["waiting_review", "review_failed", "rollback_requested"].includes(task?.status ?? "") && !locked' in APP
    action_source = APP.split('<section className="step-card action-card">', 1)[1].split('{can.suggest &&', 1)[0]
    review_group = action_source.split('{can.review &&', 1)[1].split('}{can.revise &&', 1)[0]
    revise_group = action_source.split('{can.revise &&', 1)[1]
    assert "通過驗收" in review_group
    assert "驗收失敗" in review_group
    assert "退回修改" not in review_group
    assert "退回修改" in revise_group
    assert 'can.review &&' in action_source
    assert 'can.revise &&' in action_source
