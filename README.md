# SCBKR 本地責任鏈模型｜Release Candidate

目前版本：**P15-Q Release Candidate 收束**（`0.15.0-rc.1`）。

SCBKR 是本地責任鏈模型產品候選版，核心流程為：

**Chat → Workbench → SCBKR Draft Grammar → Owner Signature → Generation → Review → Storage → Data Center → Evidence Reuse**

## 核心規則

- 模型只能描述與編譯 S/C/B/K/R 草案，不能簽名。
- 使用者簽名後，SCBKR 責任鏈才成立。
- 生成前必須先完成使用者責任鏈確認。
- 驗收通過後才可入庫。
- 入庫必須同時滿足 `storage_confirmed=true`、`second_confirm=true`、`confirmed_by=user`，且 `signature` 不可空。
- 實體入庫必須完成 physical write gate，不得以假閉環取代。
- 四庫引用只採用 `owner_signed`、`review_passed`，且未 `revoked` / `archived` / `superseded` 的資料。

## Release Candidate 桌面包

- Desktop package：`scbkr-desktop`
- Version：`0.15.0-rc.1`
- Tauri runtime：release candidate
- Windows RC build output：`dist/scbkr-windows-desktop-rc`
- Code signing may be configured by distributor.

## 常用驗收命令

```bash
python -m pytest -q
npm --prefix apps/web run build
npm --prefix apps/desktop run check:skeleton
npm --prefix apps/desktop run check:release
```

Windows release candidate packaging / smoke：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_desktop_release_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts/smoke_desktop_release_windows.ps1
```

## History

Preview-era desktop scripts remain for compatibility with older workflow names, but the product metadata and release scripts now target the P15-Q Release Candidate flow.
