import re
from pathlib import Path

APP = Path("apps/web/src/App.tsx").read_text(encoding="utf-8")
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
    assert 'setMessage("請先輸入使用者簽名，才能建立入庫請求或二次確認寫入。")' in APP
    assert 'signature: ownerSignature.trim()' in APP
    assert 'const storageConfirm = async () => { if (!task) return; if (!ownerSignature.trim())' in APP


def test_frontend_clears_owner_signature_after_draft_changes():
    assert 'const clearOwnerSignatureForDraftChange = () => { setOwnerSignature("")' in APP
    assert 'const updateField = (d: ScbkrDimensionKey, f: string, v: string) => { if (!task?.scbkr || locked) return; const old = task.scbkr[d]?.[f]; clearOwnerSignatureForDraftChange();' in APP
    assert 'const applyPatch = () => task && pendingPatch && !locked' in APP and 'clearOwnerSignatureForDraftChange(); setPendingPatch(null);' in APP
    assert 'const regenerateDraft = () => task && !task.confirmed && !locked' in APP and 'clearOwnerSignatureForDraftChange(); });' in APP
    assert 'const localRevision = invalidateDownstreamForRevision(task)' in APP and 'setOwnerSignature("");' in APP
    assert 'create_scbkr_draft: true, prefill }) })).then((r: any) => r?.task_id && (setOwnerSignature(""), setPage("workbench")))' in APP


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


def test_data_center_confirm_uses_dedicated_signature_and_blocks_empty_signature():
    assert 'const [dataCenterOwnerSignature, setDataCenterOwnerSignature] = useState("")' in APP
    assert '資料中心使用者簽名' in APP
    assert '請先輸入資料中心使用者簽名，才能確認更改或封存資料。' in APP
    assert 'signature: dataCenterOwnerSignature.trim()' in APP
    assert 'signature: ownerSignature.trim(), change_reason' not in APP
    assert 'signature: ownerSignature.trim(), delete_reason' not in APP
    assert 'if (!signature) { setMessage(dataCenterSignatureRequiredMessage); return; }' in APP
    assert 'disabled={!updateDraft || !dataCenterOwnerSignature.trim()}' in APP
    assert 'disabled={!dataCenterOwnerSignature.trim()}' in APP
    assert 'setDataCenterOwnerSignature("")' in APP


def test_storage_confirm_has_no_legacy_exports_physical_target_path():
    main_py = Path("apps/api/main.py").read_text(encoding="utf-8")
    assert "legacy_exports_requested" not in main_py
    assert 'physical_targets.append("exports")' not in main_py
    assert 'if t != "exports"' not in main_py
