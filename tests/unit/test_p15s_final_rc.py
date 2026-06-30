import importlib
import os
from pathlib import Path

import pytest
import asyncio

from apps.api.sidecar import configure_sidecar_environment


def test_sidecar_default_host_port_and_rejects_lan_without_flag(monkeypatch):
    for key in ("SCBKR_API_HOST", "SCBKR_API_PORT", "SCBKR_LAN_COMPANION_ENABLED", "SCBKR_COMPANION_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    env = configure_sidecar_environment()
    assert env["SCBKR_API_HOST"] == "127.0.0.1"
    assert env["SCBKR_API_PORT"] == "8787"
    monkeypatch.setenv("SCBKR_API_HOST", "0.0.0.0")
    monkeypatch.setenv("SCBKR_LAN_COMPANION_ENABLED", "0")
    env = configure_sidecar_environment()
    assert env["SCBKR_LAN_COMPANION_ENABLED"] != "1"


def test_sidecar_lan_mode_requires_token(monkeypatch):
    monkeypatch.setenv("SCBKR_API_HOST", "0.0.0.0")
    monkeypatch.setenv("SCBKR_API_PORT", "8787")
    monkeypatch.setenv("SCBKR_LAN_COMPANION_ENABLED", "1")
    monkeypatch.delenv("SCBKR_COMPANION_TOKEN", raising=False)
    env = configure_sidecar_environment()
    assert env["SCBKR_API_HOST"] == "0.0.0.0"
    assert env["SCBKR_LAN_COMPANION_ENABLED"] == "1"
    assert env["SCBKR_COMPANION_TOKEN"] == ""
    monkeypatch.setenv("SCBKR_COMPANION_TOKEN", "secret")
    assert configure_sidecar_environment()["SCBKR_COMPANION_TOKEN"] == "secret"


def test_lan_public_asset_paths_and_api_protection_contract():
    from apps.api import main

    assert main._is_public_companion_asset_path("/") is True
    assert main._is_public_companion_asset_path("/index.html") is True
    assert main._is_public_companion_asset_path("/assets/index.js") is True
    assert main._is_public_companion_asset_path("/assets/index.css") is True
    assert main._is_public_companion_asset_path("/health") is True
    assert main._is_public_companion_asset_path("/api/settings/model") is False
    assert main._is_public_companion_asset_path("/api/tasks/create") is False


def test_lan_non_loopback_token_assets_and_health_minimal(monkeypatch):
    monkeypatch.setenv("SCBKR_LAN_COMPANION_ENABLED", "1")
    monkeypatch.setenv("SCBKR_COMPANION_TOKEN", "secret")
    from apps.api import main

    class DummyUrl:
        def __init__(self, path):
            self.path = path

    class DummyRequest:
        client = type("Client", (), {"host": "192.168.1.50"})()
        query_params = {}
        def __init__(self, path, token=""):
            self.url = DummyUrl(path)
            self.headers = {"X-SCBKR-Companion-Token": token} if token else {}

    async def ok_response(_request):
        return "ok"

    asset = asyncio.run(main.require_companion_token_for_lan_requests(DummyRequest("/assets/index.js"), ok_response))
    assert asset == "ok"
    denied = asyncio.run(main.require_companion_token_for_lan_requests(DummyRequest("/api/settings/model"), ok_response))
    assert denied.status_code == 401
    allowed = asyncio.run(main.require_companion_token_for_lan_requests(DummyRequest("/api/settings/model", "secret"), ok_response))
    assert allowed == "ok"
    health = main.health()
    assert health["ok"] is True and health["lan_companion_enabled"] is True
    assert "secret" not in str(health)


def test_frontend_api_base_runtime_matrix_and_companion_token_contract():
    app = Path("apps/web/src/App.tsx").read_text(encoding="utf-8")
    api_base_path = Path("apps/web/src/apiBase.ts")
    assert api_base_path.exists()
    api_base = api_base_path.read_text(encoding="utf-8")

    assert 'export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8787"' in api_base
    assert "export function resolveApiBaseUrl" in api_base
    assert "export function isLoopbackHostname" in api_base
    assert "export function hasCompanionToken" in api_base
    assert "export function isTauriDesktopHostname" in api_base
    assert "tauri.localhost" in api_base
    assert api_base.index("if (isTauriDesktopHostname(hostname)) return DEFAULT_API_BASE_URL") < api_base.index("if (!loopback) return origin")
    assert 'from "./apiBase"' in app and "resolveApiBaseUrl" in app
    assert "X-SCBKR-Companion-Token" in app
    assert "companion_token" in app
    assert "activeBackendUrl" in app
    assert "VITE_SCBKR_API_URL" in app
    assert 'window.location.port === "8787"' not in app
    assert '/^https?:$/.test(window.location.protocol)) return window.location.origin;' not in app
    assert 'return window.location.origin' not in app[app.index("function defaultApiBaseUrl"):app.index("const API_BASE_URL")]

    matrix_contracts = [
        ("envApiUrl highest priority", "if (envApiUrl) return envApiUrl"),
        ("non-http fallback", 'input.protocol !== "http:" && input.protocol !== "https:"'),
        ("tauri desktop sidecar fallback", "if (isTauriDesktopHostname(hostname)) return DEFAULT_API_BASE_URL"),
        ("non-loopback page origin", "if (!loopback) return origin"),
        ("loopback 8787 page origin", 'if (input.port === "8787") return origin'),
        ("loopback companion token page origin", "if (hasCompanionToken(input.search)) return origin"),
        ("loopback dev/custom fallback", "return DEFAULT_API_BASE_URL"),
        ("localhost loopback", 'normalized === "localhost"'),
        ("127.0.0.1 loopback", 'normalized === "127.0.0.1"'),
        ("::1 loopback", 'normalized === "::1"'),
    ]
    for label, needle in matrix_contracts:
        assert needle in api_base, label

    matrix_cases = [
        {"case": "CASE 01", "envApiUrl": "http://custom:9999", "current": "http://localhost:5500", "expected": "http://custom:9999"},
        {"case": "CASE 02", "protocol": "file:", "expected": "http://127.0.0.1:8787"},
        {"case": "CASE 03", "current": "http://127.0.0.1:8787", "expected": "http://127.0.0.1:8787"},
        {"case": "CASE 04", "current": "http://localhost:8787", "expected": "http://localhost:8787"},
        {"case": "CASE 05", "current": "http://192.168.1.5:8787", "expected": "http://192.168.1.5:8787"},
        {"case": "CASE 06", "current": "http://192.168.1.5:8788", "expected": "http://192.168.1.5:8788"},
        {"case": "CASE 07", "current": "http://localhost:5500", "expected": "http://127.0.0.1:8787"},
        {"case": "CASE 08", "current": "http://127.0.0.1:5173", "expected": "http://127.0.0.1:8787"},
        {"case": "CASE 09", "current": "http://127.0.0.1:8788/?companion_token=abc", "expected": "http://127.0.0.1:8788"},
        {"case": "CASE 10", "current": "http://localhost:8788", "expected": "http://127.0.0.1:8787"},
        {"case": "CASE 11", "current": "http://tauri.localhost", "expected": "http://127.0.0.1:8787"},
        {"case": "CASE 12", "current": "https://tauri.localhost", "expected": "http://127.0.0.1:8787"},
    ]
    script = Path("scripts/check_api_base_matrix.mjs").read_text(encoding="utf-8")
    for row in matrix_cases:
        assert row["case"] in script
        assert row["expected"] in script
    assert "tauri.localhost" in script
    assert script.index("CASE 11") < script.index("CASE 12")


def test_readme_final_rc_contract_and_images_exist():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "Desktop Mode" in readme and "LAN Companion Mode" in readme
    assert "手機不是直接連本地 LLM" in readme
    assert "手機 → SCBKR 後端 → 本地 LLM" in readme
    assert "手機直接連本地 LLM" not in readme.replace("手機不是直接連本地 LLM", "")
    assert "LAN Companion Mode is never enabled by default" in readme
    assert "one-time six-digit code" in readme
    assert "127.0.0.1:8000" not in readme and ":8000/health" not in readme
    assert "README_EN.md" not in readme
    assert "2.0 已包含 Rule Registry" in readme
    assert "嚴格 JSON 編譯器" in readme
    for image in [
        "docs/images/scbkr-hero.png",
        "docs/images/responsibility-loop.png",
        "docs/images/responsibility-loop-en.png",
        "docs/images/workbench-owner-signature.png",
        "docs/images/workbench-owner-signature-en.png",
        "docs/images/four-store-evidence.png",
        "docs/images/four-store-evidence-en.png",
        "docs/images/architecture.png",
        "docs/images/local-model-architecture-en.png",
        "docs/images/mobile-companion-en.png",
        "docs/images/roadmap-2.0-en.png",
    ]:
        assert Path(image).exists(), image


def test_release_metadata_contracts():
    assert '"version": "2.0.0"' in Path("package.json").read_text(encoding="utf-8")
    assert '"version": "2.0.0"' in Path("apps/desktop/package.json").read_text(encoding="utf-8")
    assert '"version": "2.0.0"' in Path("apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    assert 'version = "2.0.0"' in Path("apps/desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8")
    build = Path("scripts/build_desktop_release_windows.ps1").read_text(encoding="utf-8")
    assert 'lan_companion_supported = $true' in build
    assert 'lan_companion_default_enabled = $false' in build
    assert 'four_store_targets = @("vector", "corpus", "logic", "memory")' in build
    assert 'exports_storage_target = $false' in build


def test_web_dist_detection_contract():
    main_py = Path("apps/api/main.py").read_text(encoding="utf-8")
    assert "SCBKR_WEB_DIST_DIR" in main_py
    assert "_MEIPASS" in main_py
    assert "web-dist" in main_py
    assert "apps" in main_py and "web" in main_py and "dist" in main_py
