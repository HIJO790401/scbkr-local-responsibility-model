import json
from urllib.request import Request

import pytest

from core.launch.readiness import launch_readiness, public_launch_settings, save_launch_settings
from core.rule_state.runtime import RuleStateRuntime
from core.runtime_settings import save_runtime_section
from core.tools import web_runtime
from core.tools.web_runtime import WebRuntime, _PublicOnlyRedirectHandler, _assert_public_http_url


def test_rule_state_requires_entitlement_and_supports_signed_preview(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SCBKR_PERSIST_RUNTIME_SETTINGS", "1")
    runtime = RuleStateRuntime()

    assert runtime.status()["state"] == "independent"
    with pytest.raises(PermissionError):
        runtime.select({"runtime_id": "shenyao-rule-state", "version": "1.2.0", "mode": "black_shield_strict"})

    with pytest.raises(PermissionError):
        runtime.select({"runtime_id": "shenyao-rule-state", "version": "1.2.0", "mode": "black_shield_strict", "entitlement_status": "active"})

    monkeypatch.setenv("SCBKR_OWNER_PREVIEW_TOKEN", "owner")
    selected = runtime.select({"runtime_id": "shenyao-rule-state", "version": "1.2.0", "mode": "black_shield_strict", "developer_preview": True, "preview_token": "owner"})
    assert selected["state"] == "shenyao_active"
    assert selected["entitlement_status"] == "developer_preview"

    report = runtime.validate_overlay("當使用者發布內容時，只能引用有來源與版本的資料，最後由使用者負責驗收。")
    assert report["checks"] == {"S": True, "C": True, "B": True, "K": True, "R": True}
    assert report["shenyao_verified"] is True
    monkeypatch.delenv("SCBKR_OWNER_PREVIEW_TOKEN")
    assert runtime.status()["state"] == "independent"
    assert runtime.deactivate()["state"] == "independent"


def test_rule_state_uses_server_entitlement_record(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SCBKR_PERSIST_RUNTIME_SETTINGS", "1")
    save_runtime_section("rule_state_entitlement", {"status": "active", "runtime_id": "shenyao-rule-state", "subscriber_id": "sub_123", "allowed_versions": ["1.2.0"]})

    selected = RuleStateRuntime().select({"runtime_id": "shenyao-rule-state", "version": "1.2.0", "mode": "responsibility_audit"})
    assert selected["entitlement_status"] == "active"
    assert selected["subscriber_id"] == "sub_123"

    save_runtime_section("rule_state_entitlement", {"status": "active", "runtime_id": "shenyao-rule-state", "allowed_versions": ["1.2.0"], "expires_at": "2000-01-01T00:00:00Z"})
    assert RuleStateRuntime().status()["state"] == "independent"
    with pytest.raises(PermissionError):
        RuleStateRuntime().select({"runtime_id": "shenyao-rule-state", "version": "1.2.0", "mode": "responsibility_audit"})


def test_launch_readiness_tracks_owner_accounts_and_masks_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SCBKR_PERSIST_RUNTIME_SETTINGS", "1")
    monkeypatch.setenv("SCBKR_BRAVE_API_KEY", "secret")
    settings = save_launch_settings({"public_domain": "https://scbkr.example", "search_provider": "brave", "brave_api_key": "must-not-persist"})

    public = public_launch_settings(settings)
    assert "brave_api_key" not in public
    assert public["brave_api_key_configured"] is True
    assert "must-not-persist" not in (tmp_path / "runtime-settings.json").read_text(encoding="utf-8")
    readiness = launch_readiness(settings)
    assert readiness["ready_count"] == 2
    assert "billing" in readiness["blocked_by"]


def test_page_reader_blocks_local_and_private_networks(monkeypatch):
    monkeypatch.setattr(web_runtime.socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 80))])
    with pytest.raises(ValueError, match="blocked"):
        _assert_public_http_url("http://example.test/internal")


def test_redirect_handler_rechecks_redirect_destination(monkeypatch):
    monkeypatch.setattr(web_runtime.socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 80))])
    with pytest.raises(ValueError, match="blocked"):
        _PublicOnlyRedirectHandler().redirect_request(Request("https://example.com"), None, 302, "Found", {}, "http://localhost/admin")


def test_searxng_adapter_returns_normalized_results(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, limit): return json.dumps({"results": [{"title": "Official", "url": "https://example.com", "content": "Result"}]}).encode()

    monkeypatch.setattr(web_runtime, "_assert_public_http_url", lambda url: url)
    monkeypatch.setattr(web_runtime, "_open", lambda request, timeout: Response())
    result = WebRuntime({"search_provider": "searxng", "searxng_url": "https://search.example", "search_timeout": 5}).search("SCBKR")
    assert result["external_call_performed"] is True
    assert result["results"] == [{"title": "Official", "url": "https://example.com", "snippet": "Result", "source": "searxng"}]
