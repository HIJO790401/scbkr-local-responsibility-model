from fastapi.testclient import TestClient

import apps.api.main as main
from core.model_gateway.settings import DEFAULT_MODEL_SETTINGS
from core.permissions.permission_flags import DEFAULT_PERMISSION_SETTINGS


def reset_runtime(mode="external", provider="openai_compatible", base_url="https://example.test/v1"):
    main.MODEL_SETTINGS.clear()
    main.MODEL_SETTINGS.update(
        {
            **DEFAULT_MODEL_SETTINGS,
            "provider": provider,
            "mode": mode,
            "base_url": base_url,
            "model_name": "test-model",
            "enabled": True,
            "last_test_status": "success",
        }
    )
    main.PERMISSIONS.clear()
    main.PERMISSIONS.update({**DEFAULT_PERMISSION_SETTINGS, "model_generate": True, "dangerous_operation_confirmed": True})


def install_fake_model(monkeypatch, calls):
    def fake(settings, messages):
        calls.append({"settings": dict(settings), "messages": messages})
        return {"choices": [{"message": {"content": "remote ok"}}]}

    monkeypatch.setattr(main, "_post_openai_compatible", fake)


def test_remote_chat_calls_model_when_external_api_allowed(monkeypatch):
    reset_runtime()
    main.PERMISSIONS["external_api"] = True
    calls = []
    install_fake_model(monkeypatch, calls)

    response = TestClient(main.app).post("/api/chat/general", json={"message": "hello remote"})

    assert response.status_code == 200
    assert "remote ok" in response.json()["reply"]
    assert "SCBKR Responsibility Chain Language Model | EMPTY" in response.json()["reply"]
    assert response.json()["rule_state"]["awareness_state"] == "EMPTY"
    assert calls[0]["messages"][-1]["content"] == "hello remote"


def test_remote_chat_blocks_model_and_text_when_external_api_disabled(monkeypatch):
    reset_runtime()
    main.PERMISSIONS["external_api"] = False
    calls = []
    install_fake_model(monkeypatch, calls)

    response = TestClient(main.app).post("/api/chat/general", json={"message": "do not leak me"})

    assert response.status_code == 403
    assert main.EXTERNAL_API_LOOPBACK_ERROR in response.json()["detail"]
    assert calls == []


def test_loopback_local_model_is_not_blocked_by_external_api_false(monkeypatch):
    reset_runtime(mode="local", provider="lm_studio", base_url="http://127.0.0.1:1234/v1")
    main.PERMISSIONS["external_api"] = False
    calls = []
    install_fake_model(monkeypatch, calls)

    response = TestClient(main.app).post("/api/chat/general", json={"message": "local ok"})

    assert response.status_code == 200
    assert "remote ok" in response.json()["reply"]
    assert "SCBKR Responsibility Chain Language Model | EMPTY" in response.json()["reply"]
    assert response.json()["rule_state"]["awareness_state"] == "EMPTY"
    assert calls[0]["messages"][-1]["content"] == "local ok"


def test_remote_chat_rechecks_permission_after_success_then_disabled(monkeypatch):
    reset_runtime()
    main.PERMISSIONS["external_api"] = True
    calls = []
    install_fake_model(monkeypatch, calls)
    client = TestClient(main.app)

    assert client.post("/api/chat/general", json={"message": "first"}).status_code == 200
    main.PERMISSIONS["external_api"] = False
    response = client.post("/api/chat/general", json={"message": "second secret"})

    assert response.status_code == 403
    assert len(calls) == 1
    assert all("second secret" not in str(call) for call in calls)


def test_only_loopback_urls_skip_external_api_permission():
    for base_url in ("http://127.0.0.1:1234/v1", "http://localhost:1234/v1", "http://[::1]:1234/v1", "https://127.0.0.1/v1", "https://localhost/v1", "https://[::1]/v1"):
        reset_runtime(mode="local", provider="openai_compatible", base_url=base_url)
        assert main._model_call_requires_external_api_permission(main.MODEL_SETTINGS) is False
        assert main._model_draft_requires_external_api_permission(main.MODEL_SETTINGS) is False


def test_lm_studio_lan_local_mode_requires_external_api_and_does_not_call(monkeypatch):
    reset_runtime(mode="local", provider="lm_studio", base_url="http://192.168.1.10:1234/v1")
    main.PERMISSIONS["external_api"] = False
    calls = []
    install_fake_model(monkeypatch, calls)

    response = TestClient(main.app).post("/api/chat/general", json={"message": "lan secret"})

    assert response.status_code == 403
    assert main.EXTERNAL_API_LOOPBACK_ERROR in response.json()["detail"]
    assert calls == []


def test_ollama_lan_local_mode_requires_external_api_and_does_not_call(monkeypatch):
    reset_runtime(mode="local", provider="ollama", base_url="http://192.168.1.10:11434/v1")
    main.PERMISSIONS["external_api"] = False
    calls = []
    install_fake_model(monkeypatch, calls)

    response = TestClient(main.app).post("/api/chat/general", json={"message": "ollama lan secret"})

    assert response.status_code == 403
    assert calls == []


def test_openai_compatible_non_loopback_requires_external_api_and_external_true_allows(monkeypatch):
    reset_runtime(mode="local", provider="openai_compatible", base_url="https://api.example.com/v1")
    main.PERMISSIONS["external_api"] = False
    calls = []
    install_fake_model(monkeypatch, calls)

    response = TestClient(main.app).post("/api/chat/general", json={"message": "api secret"})
    assert response.status_code == 403
    assert calls == []

    main.PERMISSIONS["external_api"] = True
    response = TestClient(main.app).post("/api/chat/general", json={"message": "api allowed"})
    assert response.status_code == 200
    assert calls[0]["messages"][-1]["content"] == "api allowed"


def test_model_test_non_loopback_requires_external_api_and_does_not_call(monkeypatch):
    reset_runtime(mode="local", provider="lm_studio", base_url="http://192.168.1.10:1234/v1")
    main.PERMISSIONS["external_api"] = False
    calls = []
    install_fake_model(monkeypatch, calls)

    response = TestClient(main.app).post("/api/model/test")

    assert response.status_code == 200
    assert response.json()["last_test_status"] == "failed"
    assert main.EXTERNAL_API_LOOPBACK_ERROR in response.json()["last_test_message"]
    assert calls == []
