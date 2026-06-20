import importlib


def test_desktop_status_api_contract_no_side_effects(tmp_path, monkeypatch):
    monkeypatch.setenv("SCBKR_DATA_DIR", str(tmp_path))
    import apps.api.main as main
    main = importlib.reload(main)

    called = {"external": False}
    def fail_if_called(*args, **kwargs):
        called["external"] = True
        raise AssertionError("desktop status must not call external model")
    monkeypatch.setattr(main, "_post_openai_compatible", fail_if_called)

    status = main.desktop_status()
    assert status["desktop_stage"] == "P14-B"
    assert status["installer_built"] is False
    assert status["tauri_skeleton"] is True
    assert status["sandbox_available"] is True
    assert status["production_packaging"] is False
    assert called["external"] is False
