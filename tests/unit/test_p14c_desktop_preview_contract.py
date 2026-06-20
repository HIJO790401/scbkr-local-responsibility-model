import importlib
from pathlib import Path


def test_p14c_build_scripts_and_workflow_exist():
    api_script = Path("scripts/build_api_sidecar_windows.ps1")
    desktop_script = Path("scripts/build_desktop_preview_windows.ps1")
    workflow = Path(".github/workflows/windows-desktop-preview.yml")
    assert api_script.exists()
    assert desktop_script.exists()
    assert workflow.exists()
    text = workflow.read_text(encoding="utf-8")
    for phrase in ("Setup Python 3.12", "Setup Node LTS", "Setup Rust stable", "Run Python tests", "Build web UI", "Build API sidecar", "Upload Windows desktop preview artifact", "scbkr-windows-desktop-preview"):
        assert phrase in text


def test_p14c_desktop_package_scripts_exist():
    package = Path("apps/desktop/package.json").read_text(encoding="utf-8")
    assert "tauri:build:preview" in package
    assert "check:skeleton" in package


def test_sidecar_environment_uses_loopback_and_data_dir_override(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path / "desktop-data"))
    monkeypatch.delenv("SCBKR_API_HOST", raising=False)
    monkeypatch.delenv("SCBKR_API_PORT", raising=False)
    import apps.api.sidecar as sidecar
    sidecar = importlib.reload(sidecar)

    env = sidecar.configure_sidecar_environment()

    assert env["SCBKR_DATA_DIR"] == str(tmp_path / "desktop-data")
    assert env["SCBKR_API_HOST"] == "127.0.0.1"
    assert env["SCBKR_API_PORT"] == "8787"


def test_desktop_status_p14c_preview_no_side_effects(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    main = importlib.reload(main)
    called = {"model": False}
    def fail_if_called(*args, **kwargs):
        called["model"] = True
        raise AssertionError("desktop status must not call model")
    monkeypatch.setattr(main, "_post_openai_compatible", fail_if_called)

    status = main.desktop_status()

    assert status["desktop_stage"].startswith("P14-C")
    assert status["preview"] is True
    assert status["production_packaging"] is False
    assert status["sidecar_host"] == "127.0.0.1"
    assert status["sidecar_port"] == 8787
    assert called["model"] is False


def test_desktop_runtime_doc_p14c_terms():
    text = Path("docs/desktop_runtime.md").read_text(encoding="utf-8")
    for phrase in ("P14-C Windows Preview Package", "Sidecar runtime", "%APPDATA%/SCBKR/data", "scbkr-windows-desktop-preview", "no code signing", "no auto-update"):
        assert phrase in text
