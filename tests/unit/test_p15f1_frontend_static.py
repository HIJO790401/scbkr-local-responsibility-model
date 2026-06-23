from pathlib import Path

APP = Path("apps/web/src/App.tsx").read_text()
CSS = Path("apps/web/src/App.css").read_text()


def test_desktop_split_chat_left_workbench_right_static_contract():
    assert "split-layout" in APP
    assert "chat-main" in APP
    assert "workbench-panel" in APP
    assert "grid-template-columns: minmax(0, 1fr) minmax(360px, 42vw)" in CSS
    assert "不得" not in APP.split('aria-label="一般聊天主視窗"')[1].split("</section>")[0]


def test_mobile_drawer_and_no_workbench_under_chat_contract():
    assert "menu-button" in APP
    assert "mobile-drawer" in APP
    assert "工作台 / 工單" in APP
    assert "Data Center / 資料中心" in APP
    assert "Model Settings / 模型設定" in APP
    assert "Audit / 審計資料" in APP
    assert "position: fixed; inset: 0 0 0 auto" in CSS


def test_workbench_summary_patch_date_waiting_review_contract():
    assert "查看原始 patch" in APP
    assert "事件日期：{eventDate || \"未設定\"}" in APP
    assert "task.status !== \"waiting_review\"" in APP
    assert "Raw Details" in APP
