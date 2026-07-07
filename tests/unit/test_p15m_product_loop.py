from fastapi.testclient import TestClient
from pathlib import Path

from apps.api import main
from apps.api.main import app

APP = Path("apps/web/src/App.tsx").read_text(encoding="utf-8")
CSS = Path("apps/web/src/App.css").read_text(encoding="utf-8")


def test_scbkr_workbench_capability_lock_does_not_call_model(monkeypatch):
    called = {"value": False}

    def fail_if_called(*args, **kwargs):
        called["value"] = True
        raise AssertionError("model gateway must not be called")

    monkeypatch.setattr(main, "_post_openai_compatible", fail_if_called)
    response = TestClient(app).post("/api/chat/general", json={"message": "你能編輯 SCKR 工作台嗎"})
    assert response.status_code == 200
    data = response.json()
    assert called["value"] is False
    assert data["reply_source"] == "scbkr_workbench_capability_lock"
    reply = data["reply"]
    assert "修改草案" in reply
    assert "套用修改" in reply
    assert "重新確認責任鏈" in reply or "confirmed=false" in reply
    assert "向量庫、語料庫、程式邏輯庫、記憶庫" in reply
    assert "二次確認" in reply
    assert "引用已確認資料" in reply
    assert "SAP" not in reply
    assert "IT 管理員" not in reply
    assert "官方支持" not in reply
    assert "官方文件" not in reply


def test_scbkr_product_definition_lock(monkeypatch):
    monkeypatch.setattr(main, "_post_openai_compatible", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no model")))
    response = TestClient(app).post("/api/chat/general", json={"message": "什麼是 SCBKR"})
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "一般 AI 聊天與本地責任鏈系統" in reply
    assert "許文耀／沈耀888pi" in reply
    assert "先正常聊天" in reply
    assert "第0原理建議閘" in reply
    assert "中科大" not in reply
    assert "中國科學技術大學" not in reply


def test_p15m_frontend_static_contracts():
    assert 'const [taskText, setTaskText] = useState("")' in APP
    assert "onKeyDown" in APP and "e.key === \"Enter\"" in APP and "!e.shiftKey" in APP and "setChatInput(\"\")" in APP
    assert "isWorkbenchCommand" in APP and "/api/tasks/create" in APP and "create_scbkr_draft: true" in APP
    assert "已建立工作台任務確認單" in APP and "setPage(\"workbench\")" in APP
    assert "storage-request" in APP and "storage-confirm" in APP and "使用者二次確認寫入" in APP
    assert "尚未實體寫入" in APP and "入庫完成" in APP
    assert "written_targets" in APP and "hash / content_hash" in APP and "path / relative_path" in APP and "stored_at" in APP
    assert "recommended" in APP and "storage-card" in CSS and ".storage-badge.green" in CSS and ".storage-badge.red" in CSS
    assert "dataCenterView" in APP and "selectedDataItem" in APP and "dataCenterSections" in APP
    assert "目前尚無資料" in APP and "審計資料明細" in APP
    assert "引用證據" in APP and "本次未命中已確認資料" in APP and "source_store" in APP
    assert "請模型產生更新草案" in APP and "修改前" in APP and "修改後" in APP and "差異" in APP
