import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def fresh_main(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    return importlib.reload(main)


def test_get_model_settings_masks_api_key(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    main.MODEL_SETTINGS.update({"api_key": "sk-secret-value", "model_name": "m"})
    data = main.get_model_settings()
    assert data["api_key"] != "sk-secret-value"
    assert "sk-secret-value" not in str(data)
    assert "****" in data["api_key"]


def test_post_model_settings_supports_all_p14d_providers(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(main.app)

    sandbox = client.post("/api/settings/model", json={"mode": "sandbox"}).json()
    assert sandbox["mode"] == "sandbox"
    assert sandbox["provider"] == "sandbox_mock_model"
    assert sandbox["api_key"] == ""

    lm = client.post("/api/settings/model", json={"provider": "lm_studio", "model_name": "qwen"}).json()
    assert lm["mode"] == "local"
    assert lm["base_url"] == "http://127.0.0.1:1234/v1"
    assert lm["api_key"] == "lo****al"

    ollama = client.post("/api/settings/model", json={"provider": "ollama", "model_name": "llama3.1"}).json()
    assert ollama["mode"] == "local"
    assert ollama["base_url"] == "http://127.0.0.1:11434/v1"
    assert ollama["api_key"] == "lo****al"

    api = client.post("/api/settings/model", json={"provider": "openai_compatible", "base_url": "https://example.test/v1", "api_key": "sk-live-secret", "model_name": "gpt-4.1-mini"}).json()
    assert api["mode"] == "external"
    assert api["provider"] == "openai_compatible"
    assert api["api_key"] != "sk-live-secret"


def test_sandbox_model_test_does_not_call_external_model(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    called = {"external": False}
    def fail_if_called(*args, **kwargs):
        called["external"] = True
        raise AssertionError("sandbox test must not call external model")
    monkeypatch.setattr(main, "_post_openai_compatible", fail_if_called)
    client = TestClient(main.app)
    client.post("/api/settings/model", json={"mode": "sandbox"})

    data = client.post("/api/model/test").json()

    assert data["last_test_status"] == "success"
    assert data["external_call_performed"] is False
    assert data["test_result_kind"] == "no_external_call_for_sandbox"
    assert called["external"] is False


def test_model_settings_page_contract_exists():
    source = Path("apps/web/src/App.tsx").read_text(encoding="utf-8")
    for phrase in (
        "模型設定 / Model Settings",
        "模式 / Mode",
        "Base URL",
        "API Key",
        "Model Name",
        "儲存設定",
        "測試連線",
        "切回沙盒模式",
        "前往模型設定",
        "目前模型尚未連線，請先到「模型設定」完成測試連線，或切回沙盒模式。",
        "http://127.0.0.1:1234/v1",
        "http://127.0.0.1:11434/v1",
    ):
        assert phrase in source


def test_openai_compatible_omitted_api_key_preserves_saved_key(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(main.app)
    client.post("/api/settings/model", json={"provider": "openai_compatible", "base_url": "https://example.test/v1", "api_key": "sk-original", "model_name": "gpt-4.1-mini"})

    data = client.post("/api/settings/model", json={"provider": "openai_compatible", "base_url": "https://example.test/v1", "model_name": "gpt-4.1"}).json()

    assert main.MODEL_SETTINGS["api_key"] == "sk-original"
    assert data["api_key"] != "sk-original"


def test_openai_compatible_blank_api_key_without_clear_preserves_saved_key(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(main.app)
    client.post("/api/settings/model", json={"provider": "openai_compatible", "base_url": "https://example.test/v1", "api_key": "sk-original", "model_name": "gpt-4.1-mini"})

    client.post("/api/settings/model", json={"provider": "openai_compatible", "base_url": "https://example.test/v1", "api_key": "", "model_name": "gpt-4.1"})

    assert main.MODEL_SETTINGS["api_key"] == "sk-original"


def test_openai_compatible_model_test_blank_api_key_preserves_saved_key(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(main.app)
    client.post("/api/settings/permissions", json={"external_api": True})
    client.post("/api/settings/model", json={"provider": "openai_compatible", "base_url": "https://example.test/v1", "api_key": "sk-original", "model_name": "gpt-4.1-mini"})
    monkeypatch.setattr(main, "_post_openai_compatible", lambda settings, messages: {"choices": [{"message": {"content": "ok"}}]})

    data = client.post("/api/model/test", json={"provider": "openai_compatible", "base_url": "https://example.test/v1", "api_key": "", "model_name": "gpt-4.1"}).json()

    assert main.MODEL_SETTINGS["api_key"] == "sk-original"
    assert "last_test_status" in data


def test_openai_compatible_new_api_key_updates_saved_key(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(main.app)
    client.post("/api/settings/model", json={"provider": "openai_compatible", "base_url": "https://example.test/v1", "api_key": "sk-original", "model_name": "gpt-4.1-mini"})

    client.post("/api/settings/model", json={"provider": "openai_compatible", "base_url": "https://example.test/v1", "api_key": "sk-new", "model_name": "gpt-4.1"})

    assert main.MODEL_SETTINGS["api_key"] == "sk-new"


def test_openai_compatible_explicit_clear_api_key_clears_saved_key(tmp_path, monkeypatch):
    main = fresh_main(tmp_path, monkeypatch)
    client = TestClient(main.app)
    client.post("/api/settings/model", json={"provider": "openai_compatible", "base_url": "https://example.test/v1", "api_key": "sk-original", "model_name": "gpt-4.1-mini"})

    data = client.post("/api/settings/model", json={"provider": "openai_compatible", "base_url": "https://example.test/v1", "api_key": "", "clear_api_key": True, "model_name": "gpt-4.1"}).json()

    assert main.MODEL_SETTINGS["api_key"] == ""
    assert data["api_key"] == ""


def test_model_settings_page_documents_blank_key_preservation_and_explicit_clear():
    source = Path("apps/web/src/App.tsx").read_text(encoding="utf-8")
    assert 'if (!form.api_key && form.provider === "openai_compatible") delete payload.api_key;' in source
    assert 'clear_api_key: true' in source
    assert "清除 API Key" in source
    assert "Leave blank to keep the saved API key." in source
    assert "Use “Clear API Key” to remove it." in source
