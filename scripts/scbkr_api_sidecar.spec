# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the SCBKR Windows preview FastAPI sidecar.

The explicit hidden imports keep PyInstaller from relying on uvicorn string app
loading to discover the FastAPI app and responsibility-chain modules.
"""
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hiddenimports = [
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
]

for package in (
    "apps.api",
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
    hiddenimports += collect_submodules(package)


a = Analysis(
    ["apps/api/sidecar.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="scbkr-api",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
