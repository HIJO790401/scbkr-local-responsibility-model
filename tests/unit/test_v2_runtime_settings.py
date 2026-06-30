import json

from core.runtime_settings import load_runtime_section, save_runtime_section


def test_runtime_settings_survive_reload_and_preserve_other_sections(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SCBKR_PERSIST_RUNTIME_SETTINGS", "1")

    save_runtime_section("model", {"provider": "lm_studio", "model_name": "scbkr-qwen-0.5b"})
    save_runtime_section("permissions", {"model_generate": True})

    assert load_runtime_section("model", {"enabled": False}) == {
        "enabled": False,
        "provider": "lm_studio",
        "model_name": "scbkr-qwen-0.5b",
    }
    assert load_runtime_section("permissions", {"external_api": False}) == {
        "external_api": False,
        "model_generate": True,
    }
    raw = json.loads((tmp_path / "runtime-settings.json").read_text(encoding="utf-8"))
    assert set(raw) == {"model", "permissions"}
