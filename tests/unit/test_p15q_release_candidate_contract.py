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
    assert '"version": "0.15.0-rc.1"' in Path("package.json").read_text(encoding="utf-8")
    desktop_package = Path("apps/desktop/package.json").read_text(encoding="utf-8")
    assert '"name": "scbkr-desktop"' in desktop_package
    assert '"check:release"' in desktop_package
    assert Path("scripts/build_desktop_release_windows.ps1").exists()
    assert Path("scripts/smoke_desktop_release_windows.ps1").exists()
    tauri_conf = Path("apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    assert "P14-C preview" not in tauri_conf
    assert "not a production installer" not in tauri_conf
    assert "SCBKR_DESKTOP_PREVIEW" not in Path("apps/desktop/src-tauri/src/main.rs").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "P15-Q Release Candidate" in readme
    assert "準備進入 P15-H" not in readme
