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


def test_pyinstaller_sidecar_spec_resolves_real_entrypoint_from_repo_root():
    spec_path = Path("scripts/scbkr_api_sidecar.spec")
    spec_text = spec_path.read_text(encoding="utf-8")

    assert '["apps/api/sidecar.py"]' not in spec_text
    assert "['apps/api/sidecar.py']" not in spec_text
    assert 'scripts/apps/api/sidecar.py' not in spec_text
    assert 'scripts\\apps\\api\\sidecar.py' not in spec_text
    assert "REPO_ROOT = SPEC_DIR.parent" in spec_text
    assert "SIDECAR_ENTRY = REPO_ROOT" in spec_text
    assert '"apps" / "api" / "sidecar.py"' in spec_text
    assert "SCBKR sidecar entrypoint not found" in spec_text
    assert "[str(SIDECAR_ENTRY)]" in spec_text
    assert "pathex=[str(REPO_ROOT)]" in spec_text
    assert not Path("scripts/apps/api/sidecar.py").exists()


def test_build_api_sidecar_windows_invokes_pyinstaller_spec():
    api_script = Path("scripts/build_api_sidecar_windows.ps1").read_text(encoding="utf-8")

    assert "-m PyInstaller" in api_script
    assert "scripts\\scbkr_api_sidecar.spec" in api_script


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


def test_p14c_build_time_preview_icon_generator_contract(tmp_path):
    import subprocess
    import sys

    generator = Path("scripts/generate_tauri_preview_icon.py")
    icon = Path("apps/desktop/src-tauri/icons/icon.ico")

    assert generator.exists()
    generator.read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(generator)], check=True)

    assert icon.exists()
    assert icon.stat().st_size > 0
    assert icon.read_bytes()[:4] == b"\x00\x00\x01\x00"


def test_p14c_windows_desktop_script_generates_and_validates_tauri_icon_before_build():
    text = Path("scripts/build_desktop_preview_windows.ps1").read_text(encoding="utf-8")
    generator_call = "python scripts/generate_tauri_preview_icon.py"
    tauri_build = "npm run tauri:build:preview"
    assert generator_call in text
    assert text.index(generator_call) < text.index(tauri_build)
    assert "apps\\desktop\\src-tauri\\icons\\icon.ico" in text
    assert "P14-C Tauri Windows icon missing or invalid: apps\\desktop\\src-tauri\\icons\\icon.ico" in text
    assert "Test-Path $TauriIcon" in text
    assert "$TauriIconItem.Length -le 0" in text
    assert "[System.IO.File]::ReadAllBytes($TauriIcon)[0..3]" in text
    assert "$ExpectedTauriIconHeader = @(0, 0, 1, 0)" in text


def test_p14c_tauri_bundle_icon_and_packaging_contract():
    import json

    config = json.loads(Path("apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    bundle = config["bundle"]
    assert bundle["icon"] == ["icons/icon.ico"]
    assert bundle["externalBin"] == ["sidecar/scbkr-api"]
    assert "nsis" in bundle["targets"]
    assert bundle["createUpdaterArtifacts"] is False


def test_p14c_preview_icon_binary_is_not_tracked_and_is_gitignored():
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "--", "apps/desktop/src-tauri/icons/icon.ico"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    assert tracked == ""
    ignore_text = Path("apps/desktop/src-tauri/.gitignore").read_text(encoding="utf-8")
    assert "/icons/icon.ico" in ignore_text


def test_p14c_docs_describe_build_time_generated_preview_icon():
    readme = Path("apps/desktop/README.md").read_text(encoding="utf-8")
    runtime = Path("docs/desktop_runtime.md").read_text(encoding="utf-8")
    for text in (readme, runtime):
        assert "generated" in text
        assert "build time" in text or "build-time" in text
        assert "placeholder" in text
        assert "not a production brand asset" in text
        assert "code signing" in text
        assert "auto-update" in text
        assert "bundled model" in text
        assert "bundled API key" in text
