import importlib
import json
from pathlib import Path


def _reload_main(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    main = importlib.reload(main)
    main.TASKS.clear()
    return main


def test_desktop_status_contract_and_no_external_call(tmp_path, monkeypatch):
    main = _reload_main(tmp_path, monkeypatch)
    called = {"external": False}
    def fail_if_called(*args, **kwargs):
        called["external"] = True
        raise AssertionError("desktop status must not call model backends")
    monkeypatch.setattr(main, "_post_openai_compatible", fail_if_called)

    before_tasks = dict(main.TASKS)
    status = main.desktop_status()

    assert status["desktop_stage"].startswith("P14-C")
    assert status["desktop_shell"] is True
    assert status["installer_built"] is False
    assert status["tauri_skeleton"] is True
    assert status["sandbox_available"] is True
    assert status["api_status"] == "running"
    assert status["production_packaging"] is False
    assert called["external"] is False
    assert main.TASKS == before_tasks


def test_desktop_status_does_not_generate_store_or_change_retrieval(tmp_path, monkeypatch):
    main = _reload_main(tmp_path, monkeypatch)
    task = main.create_task({"raw_input": "desktop status no side effect", "task_type": "workflow"})

    status = main.desktop_status()
    reloaded = main.get_task(task["task_id"])

    assert status["desktop_stage"].startswith("P14-C")
    assert "generation_result" not in reloaded
    assert reloaded["physical_write_performed"] is False
    assert "retrieval_result" not in reloaded


def test_desktop_skeleton_files_and_tauri_config_exist():
    root = Path("apps/desktop")
    required = [
        root / "README.md",
        root / "package.json",
        root / "src" / "App.tsx",
        root / "src-tauri" / "tauri.conf.json",
        root / "src-tauri" / "Cargo.toml",
        root / "src-tauri" / "src" / "main.rs",
    ]
    for path in required:
        assert path.exists(), f"missing {path}"

    config = json.loads((root / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    assert config["productName"] == "SCBKR Local Responsibility Model"
    assert config["identifier"] == "com.shenyao.scbkr.local"
    assert config["build"]["devUrl"] == "http://localhost:5500"
    assert config["bundle"]["createUpdaterArtifacts"] is False
    assert "nsis" in config["bundle"].get("targets", [])


def test_desktop_runtime_doc_contract_exists():
    text = Path("docs/desktop_runtime.md").read_text(encoding="utf-8")
    required_phrases = [
        "P14-B is not installer",
        "P14-C pending",
        "Sandbox path",
        "LM Studio local path",
        "SCBKR does not download models",
        "No cloud requirement",
    ]
    for phrase in required_phrases:
        assert phrase in text
