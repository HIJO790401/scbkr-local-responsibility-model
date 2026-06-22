from pathlib import Path


def test_web_desktop_preview_defaults_to_127_loopback_api_base_url():
    text = Path("apps/web/src/App.tsx").read_text(encoding="utf-8")
    assert 'const DEFAULT_API_BASE_URL = "http://127.0.0.1:8787"' in text
    assert '"http://localhost:8787"' not in text
    assert "API_BASE_URL" in text
    assert "normalizeApiBaseUrl" in text
    assert "apiUrl(path)" in text
    assert "fetch(`${API_URL}${path}`" not in text


def test_web_desktop_readiness_displays_p14c_preview_terms():
    text = Path("apps/web/src/App.tsx").read_text(encoding="utf-8")
    assert "P14-C Windows Desktop Preview" in text
    assert "P14-B Desktop Skeleton" not in text
    assert "api_server_reachable" in text
    assert "api_sidecar" in text
