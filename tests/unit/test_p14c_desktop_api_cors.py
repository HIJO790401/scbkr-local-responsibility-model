from fastapi.testclient import TestClient

from apps.api.main import LOCAL_DESKTOP_CORS_ORIGINS, app, desktop_status


PREFLIGHT_HEADERS = {
    "Origin": "tauri://localhost",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type",
}


def test_fastapi_app_allows_local_desktop_preflight_routes():
    client = TestClient(app)
    for path in ("/health", "/api/tasks/create", "/api/settings/model", "/api/model/test"):
        response = client.request("OPTIONS", path, headers=PREFLIGHT_HEADERS)
        assert response.status_code != 400
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "tauri://localhost"
        assert "POST" in response.headers["access-control-allow-methods"]
        assert "OPTIONS" in response.headers["access-control-allow-methods"]


def test_cors_allows_only_local_desktop_preview_origins():
    expected = {
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8787",
        "http://localhost:8787",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "null",
    }
    assert expected.issubset(set(LOCAL_DESKTOP_CORS_ORIGINS))
    assert "*" not in LOCAL_DESKTOP_CORS_ORIGINS
    assert "https://example.com" not in LOCAL_DESKTOP_CORS_ORIGINS


def test_remote_origin_preflight_not_allowed_to_control_sidecar():
    client = TestClient(app)
    response = client.request(
        "OPTIONS",
        "/api/tasks/create",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_desktop_status_reports_p14c_preview_reachable_sidecar():
    status = desktop_status()
    assert status["desktop_stage"].startswith("P14-C")
    assert status["api_server_reachable"] is True
    assert status["sidecar_running"] is True
    assert status["api_url"] == "http://127.0.0.1:8787"
    assert status["sidecar_host"] == "127.0.0.1"
    assert status["sidecar_port"] == 8787
    assert status["sandbox_available"] is True
    assert status["production_packaging"] is False
