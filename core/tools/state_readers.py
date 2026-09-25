"""Bounded production readers for confirmation-time tool preconditions."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any


def read_tool_evidence_state(request: dict[str, Any]) -> dict[str, Any]:
    scope = str(request.get("state_scope") or request.get("tool", {}).get("state_scope") or "")
    if scope != "file_modification":
        raise ValueError("no trusted production reader for this state scope")
    configured_root = os.environ.get("SCBKR_TOOL_WORKSPACE_ROOT")
    if not configured_root:
        raise ValueError("SCBKR_TOOL_WORKSPACE_ROOT is not configured")
    root = Path(configured_root).resolve(strict=True)
    path_text = request.get("file_path")
    if not isinstance(path_text, str) or not path_text.strip():
        raise ValueError("file_path is required")
    path = Path(path_text).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("file_path is outside the configured workspace")
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("file exceeds trusted reader limit")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            if size > 50 * 1024 * 1024:
                raise ValueError("file exceeds trusted reader limit")
            digest.update(chunk)
    return {"resource_id": f"file:{path}", "content_hash": digest.hexdigest(), "size_bytes": size}
