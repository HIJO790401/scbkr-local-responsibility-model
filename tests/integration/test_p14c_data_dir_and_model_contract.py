import importlib
import sqlite3


def test_scbkr_data_dir_override_writes_sqlite_and_jsonl_to_temp_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "preview-data"
    monkeypatch.setenv("SCBKR_DATA_DIR", str(data_dir))
    import apps.api.main as main
    main = importlib.reload(main)
    task = main.create_task({"raw_input": "desktop preview data dir", "task_type": "workflow"})

    assert (data_dir / "scbkr.sqlite3").exists()
    assert (data_dir / "ledger" / "audit-log.jsonl").exists()
    with sqlite3.connect(data_dir / "scbkr.sqlite3") as conn:
        assert conn.execute("select count(*) from tasks where task_id = ?", (task["task_id"],)).fetchone()[0] == 1


def test_lm_studio_contract_calls_base_url_only_on_model_test(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    main = importlib.reload(main)
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def read(self):
            return b'{"choices":[{"message":{"content":"local ok"}}]}'

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return FakeResponse()

    monkeypatch.setattr(main, "urlopen", fake_urlopen)
    main.set_model_settings({"mode":"local", "provider":"lm_studio", "base_url":"http://127.0.0.1:1234/v1", "api_key":"lm-studio", "model_name":"qwen2.5-vl-7b-instruct"})

    status = main.desktop_status()
    assert status["local_model_base_url"] == "http://127.0.0.1:1234/v1"
    assert calls == []

    result = main.test_model()
    assert result["last_test_status"] == "success"
    assert result["test_result_kind"] == "local_model_success"
    assert calls == ["http://127.0.0.1:1234/v1/chat/completions"]


def test_sandbox_and_ungated_generate_do_not_call_local_base_url(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    main = importlib.reload(main)
    called = {"value": False}
    def fail_urlopen(*args, **kwargs):
        called["value"] = True
        raise AssertionError("local base_url must not be called")
    monkeypatch.setattr(main, "urlopen", fail_urlopen)

    main.set_model_settings({"mode":"sandbox"})
    main.test_model()
    assert called["value"] is False

    main.set_model_settings({"mode":"local", "provider":"lm_studio", "base_url":"http://127.0.0.1:1234/v1", "api_key":"lm-studio", "model_name":"qwen2.5-vl-7b-instruct", "enabled":True, "last_test_status":"success"})
    task = main.create_task({"raw_input": "ungated local model", "task_type": "workflow"})
    try:
        main.generate(task["task_id"])
    except Exception:
        pass
    assert called["value"] is False


def test_enable_model_generate_permission_api_only_updates_model_generate(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    main = importlib.reload(main)

    permissions = main.set_permissions({"model_generate": True})

    assert permissions["model_generate"] is True
    assert permissions["external_api"] is False
    assert permissions["web_search"] is False
    assert permissions["local_file_access"] is False
    assert permissions["storage_write"] is False
    assert permissions["memory_write"] is False


def test_web_ui_contains_permission_refresh_and_sandbox_generate_guard():
    source = open("apps/web/src/V2App.tsx", encoding="utf-8").read()

    assert "/api/settings/permissions" in source
    assert "setPermissions" in source
    assert "permissions.model_generate" in source
    assert "開啟模型生成權限" in source
    assert '/generate' in source
