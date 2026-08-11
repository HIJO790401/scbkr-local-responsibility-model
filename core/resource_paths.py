"""Resolve read-only product resources in source and frozen desktop builds."""

from __future__ import annotations

from pathlib import Path
import sys


def product_resource_path(*parts: str) -> Path:
    """Return a bundled resource path without assuming the process cwd."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    root = Path(frozen_root) if frozen_root else Path(__file__).resolve().parents[1]
    return root.joinpath(*parts)
