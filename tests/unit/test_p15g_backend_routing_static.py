from pathlib import Path

APP = Path("apps/web/src/App.tsx").read_text(encoding="utf-8")


def test_test_backend_fetches_user_entered_backend_origin_directly():
    assert "const [backendUrl, setBackendUrl]" in APP
    assert "const [activeBackendUrl, setActiveBackendUrl]" in APP
    assert "fetch(`${candidate}/health`)" in APP
    assert 'api("/api/backend/test"' not in APP


def test_successful_backend_test_persists_active_backend_url():
    assert "setActiveBackendUrl(candidate)" in APP
    assert "localStorage.setItem(ACTIVE_BACKEND_STORAGE_KEY, candidate)" in APP
    assert "scbkr.activeBackendUrl" in APP


def test_api_helper_routes_through_active_backend_url_and_preserves_masked_key_ui():
    assert "const [selectedBackendUrl, setSelectedBackendUrl]" in APP
    assert "function storedBackendUrl()" in APP
    assert "function apiUrl(path: string, baseUrl = storedBackendUrl())" in APP
    assert "fetch(apiUrl(path, backendUrl)" in APP
    assert "API Key（目前：{model?.api_key || \"空\"}）" in APP
    assert 'type="password"' in APP
