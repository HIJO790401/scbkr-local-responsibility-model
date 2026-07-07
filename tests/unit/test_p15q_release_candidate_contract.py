import re
from pathlib import Path

APP = Path("apps/web/src/V2App.tsx").read_text(encoding="utf-8")
PREVIEW_SMOKE = Path("scripts/smoke_p14c_preview_windows.ps1").read_text(encoding="utf-8")
RELEASE_SMOKE = Path("scripts/smoke_desktop_release_windows.ps1").read_text(encoding="utf-8")


def test_windows_smoke_uses_owner_signature_and_second_confirm_gate():
    assert '$OwnerSignature = "smoke-owner-signature"' in PREVIEW_SMOKE
    assert 'signature = $OwnerSignature' in PREVIEW_SMOKE
    assert 'second_confirm = $true' in PREVIEW_SMOKE
    assert 'storage_confirmed = $true' in PREVIEW_SMOKE
    assert 'confirmed_by = "user"' in PREVIEW_SMOKE


def test_release_smoke_proves_second_confirm_is_required_before_success():
    assert "storage-confirm without second_confirm unexpectedly succeeded" in RELEASE_SMOKE
    assert 'second_confirm = $true' in RELEASE_SMOKE
    assert 'physical_write_performed' in RELEASE_SMOKE
    assert '/api/data-center/storage' in RELEASE_SMOKE


def test_frontend_storage_has_no_fallback_signatures_and_requires_owner_signature():
    assert "owner-signature-required" not in APP
    assert "storage-owner-signature" not in APP
    assert 'signature: ownerSignature.trim()' in APP
    assert "if (!task || !ownerSignature.trim()) return;" in APP
    assert "disabled={!ownerSignature.trim()}" in APP


def test_frontend_clears_owner_signature_when_creating_or_patching_drafts():
    assert "setOwnerSignature(\"\")" in APP
    assert "setPendingPatch(null)" in APP
    assert "/scbkr/patch-draft" in APP
    assert "/scbkr/apply-patch" in APP
    assert "create_scbkr_draft: true" in APP


def test_release_candidate_metadata_and_readme_contracts():
    assert '"version": "2.3.0"' in Path("package.json").read_text(encoding="utf-8")
    assert '"version": "2.3.0"' in Path("apps/web/package.json").read_text(encoding="utf-8")
    desktop_package = Path("apps/desktop/package.json").read_text(encoding="utf-8")
    assert '"name": "scbkr-desktop"' in desktop_package
    assert '"version": "2.1.0"' in desktop_package
    assert '"check:release"' in desktop_package
    assert Path("scripts/build_desktop_release_windows.ps1").exists()
    assert Path("scripts/smoke_desktop_release_windows.ps1").exists()
    tauri_conf = Path("apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    assert "P14-C preview" not in tauri_conf
    assert "not a production installer" not in tauri_conf
    assert "SCBKR_DESKTOP_PREVIEW" not in Path("apps/desktop/src-tauri/src/main.rs").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "2.1.0" in readme
    assert "準備進入 P15-H" not in readme


def _selected_target_sets(script: str):
    return re.findall(r'selected_targets = @\(([^)]*)\)', script)


def test_windows_smoke_targets_are_formal_four_store_targets_only():
    for script in (PREVIEW_SMOKE, RELEASE_SMOKE):
        assert 'selected_targets = @("corpus", "logic", "exports")' not in script
        assert 'selected_targets = @("vector", "corpus", "logic", "memory")' in script
        for targets in _selected_target_sets(script):
            assert '"exports"' not in targets
            for target in ('"vector"', '"corpus"', '"logic"', '"memory"'):
                assert target in targets


def test_storage_ui_targets_remain_formal_four_store_targets():
    storage_suggestion = Path("core/storage/storage_suggestion.py").read_text(encoding="utf-8")
    assert 'UI_TARGETS = ("vector", "corpus", "logic", "memory")' in storage_suggestion
    assert 'UI_TARGETS = ("vector", "corpus", "logic", "memory", "exports")' not in storage_suggestion


def test_data_center_is_readable_four_store_evidence_not_raw_duplicate_panels():
    assert "四庫資料中心" in APP
    assert "用人話查詢已簽名資料" in APP
    assert "模型只能引用已簽名、已驗收的資料" in APP
    assert "/api/data-center/ask" in APP
    assert "/api/data-center/" in APP


def test_storage_confirm_has_no_legacy_exports_physical_target_path():
    main_py = Path("apps/api/main.py").read_text(encoding="utf-8")
    assert "legacy_exports_requested" not in main_py
    assert 'physical_targets.append("exports")' not in main_py
    assert 'if t != "exports"' not in main_py
