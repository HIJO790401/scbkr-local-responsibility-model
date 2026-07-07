from pathlib import Path

APP = Path("apps/web/src/V2App.tsx").read_text(encoding="utf-8")
API_BASE = Path("apps/web/src/apiBase.ts").read_text(encoding="utf-8")


def test_test_backend_fetches_user_entered_backend_origin_directly():
    assert "const [backend, setBackend]" in APP
    assert "Backend API URL" in APP
    assert "saveConnection" in APP
    assert 'api("/api/backend/test"' not in APP


def test_successful_backend_test_persists_active_backend_url():
    assert "setBackend(backend.replace" in APP
    assert "localStorage.setItem(BACKEND_KEY" in APP
    assert "scbkr.activeBackendUrl" in APP


def test_api_helper_routes_through_active_backend_url_and_preserves_masked_key_ui():
    assert "resolveApiBaseUrl" in APP
    assert "fetch(`${backend}${path}`" in APP
    assert "X-SCBKR-Companion-Token" in APP
    assert 'export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8787"' in API_BASE
    assert "if (isTauriDesktopHostname(hostname)) return DEFAULT_API_BASE_URL" in API_BASE
    assert "if (!loopback) return origin" in API_BASE
    assert "API Key" in APP
    assert 'type="password"' in APP
