# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the SCBKR Windows FastAPI sidecar.

The explicit hidden imports keep PyInstaller from relying on uvicorn string app
loading to discover the FastAPI app and responsibility-chain modules.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

SPEC_DIR = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_DIR.parent
SIDECAR_ENTRY = REPO_ROOT / "apps" / "api" / "sidecar.py"
WEB_DIST = REPO_ROOT / "apps" / "web" / "dist"
PRODUCT_MANIFEST = REPO_ROOT / "config" / "product_manifest.json"
KERNEL_PACK = REPO_ROOT / "kernel_pack" / "scbkr_kernel_pack.json"

if not SIDECAR_ENTRY.exists():
    raise FileNotFoundError(f"SCBKR sidecar entrypoint not found: {SIDECAR_ENTRY}")
if not (WEB_DIST / "index.html").exists():
    raise FileNotFoundError(f"SCBKR web dist missing; run npm --prefix apps/web run build first: {WEB_DIST}")
if not PRODUCT_MANIFEST.is_file():
    raise FileNotFoundError(f"SCBKR product manifest missing: {PRODUCT_MANIFEST}")
if not KERNEL_PACK.is_file():
    raise FileNotFoundError(f"SCBKR Kernel Pack missing: {KERNEL_PACK}")

datas = [
    (str(WEB_DIST), "web-dist"),
    (str(PRODUCT_MANIFEST), "config"),
    (str(KERNEL_PACK), "kernel_pack"),
]

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
    [str(SIDECAR_ENTRY)],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "py",
        "transformers",
        "numpy",
        "torch",
        "scipy",
        "pandas",
    ],
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
