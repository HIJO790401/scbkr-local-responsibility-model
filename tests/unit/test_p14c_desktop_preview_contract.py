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


def test_tauri_sidecar_external_bin_and_windows_staging_contract():
    import json
    config = json.loads(Path("apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    assert config["bundle"]["externalBin"] == ["sidecar/scbkr-api"]

    api_script = Path("scripts/build_api_sidecar_windows.ps1").read_text(encoding="utf-8")
    desktop_script = Path("scripts/build_desktop_preview_windows.ps1").read_text(encoding="utf-8")
    expected = "apps\\desktop\\src-tauri\\sidecar"
    expected_name = "scbkr-api-x86_64-pc-windows-msvc.exe"
    assert expected in api_script
    assert "scbkr-api-$TargetTriple.exe" in api_script
    assert "x86_64-pc-windows-msvc" in api_script
    assert expected_name in desktop_script
    assert "Tauri sidecar staging file missing before build" in desktop_script


def test_pyinstaller_sidecar_uses_explicit_app_import_and_hidden_imports():
    sidecar_text = Path("apps/api/sidecar.py").read_text(encoding="utf-8")
    assert "from apps.api.main import app" in sidecar_text
    assert 'uvicorn.run(app, host=host, port=port, log_level="info")' in sidecar_text
    assert 'uvicorn.run("apps.api.main:app"' not in sidecar_text

    spec_text = Path("scripts/scbkr_api_sidecar.spec").read_text(encoding="utf-8")
    for module in (
        "apps.api.main",
        "apps.api.sidecar",
        "core",
        "core.generation",
        "core.model_gateway",
        "core.permissions",
        "core.ledger",
        "core.review_rules",
        "core.scbkr",
        "core.storage",
        "core.workflow",
        "core.retrieval",
    ):
        assert f'"{module}"' in spec_text
    assert "collect_submodules" in spec_text


def test_desktop_preview_script_copies_tauri_outputs_and_fails_if_missing():
    text = Path("scripts/build_desktop_preview_windows.ps1").read_text(encoding="utf-8")
    assert "bundle\\nsis" in text
    assert "target\\release" in text
    assert "Tauri build completed but no desktop executable or NSIS installer" in text
    assert "Copy-Item -Force $Output.FullName $DesktopDir" in text
    assert "README_PREVIEW.md" in text
    assert "VERSION" in text


def test_windows_preview_workflow_uploads_complete_staged_artifact():
    workflow = Path(".github/workflows/windows-desktop-preview.yml").read_text(encoding="utf-8")
    assert "Stage preview artifact" in workflow
    assert "scripts/build_desktop_preview_windows.ps1" in workflow
    assert "path: dist/scbkr-windows-desktop-preview" in workflow


def test_windows_packaging_scripts_use_powershell_51_compatible_windows_detection():
    script_paths = (
        Path("scripts/build_api_sidecar_windows.ps1"),
        Path("scripts/build_desktop_preview_windows.ps1"),
        Path("scripts/smoke_api_sidecar_windows.ps1"),
    )

    for script_path in script_paths:
        text = script_path.read_text(encoding="utf-8")
        assert "$IsWindows" not in text
        assert "function Test-IsWindows" in text
        assert 'if ($env:OS -eq "Windows_NT")' in text
        assert "if ($env:SYSTEMROOT)" in text
        assert "RuntimeInformation]::IsOSPlatform" in text
        assert "OSPlatform]::Windows" in text
        assert "if (-not (Test-IsWindows))" in text
        assert "throw" in text


def test_windows_preview_workflow_invokes_all_windows_packaging_scripts():
    workflow = Path(".github/workflows/windows-desktop-preview.yml").read_text(encoding="utf-8")
    api_script = Path("scripts/build_api_sidecar_windows.ps1").read_text(encoding="utf-8")

    assert "powershell -ExecutionPolicy Bypass -File scripts/build_api_sidecar_windows.ps1" in workflow
    assert "powershell -ExecutionPolicy Bypass -File scripts/build_desktop_preview_windows.ps1" in workflow
    assert "powershell -ExecutionPolicy Bypass -File scripts\\smoke_api_sidecar_windows.ps1" in api_script
