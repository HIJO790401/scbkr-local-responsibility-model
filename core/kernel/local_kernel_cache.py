"""Local cache helpers for SCBKR Kernel Pack."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .scbkr_kernel_compiler import DEFAULT_KERNEL_PACK_PATH, compile_kernel_pack, load_kernel_pack


def ensure_local_kernel_cache(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_KERNEL_PACK_PATH
    if target.exists():
        return load_kernel_pack(target)
    return compile_kernel_pack(target)

