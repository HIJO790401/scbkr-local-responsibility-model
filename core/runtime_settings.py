"""Atomic local persistence for model and permission settings."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
from typing import Any

from core.storage.runtime_paths import current_data_dir


def persistence_enabled() -> bool:
    return os.environ.get("SCBKR_PERSIST_RUNTIME_SETTINGS", "1") == "1"


def settings_path() -> Path:
    return current_data_dir() / "runtime-settings.json"


def _read_all() -> dict[str, Any]:
    path = settings_path()
    if not persistence_enabled() or not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        return {}


def load_runtime_section(section: str, defaults: dict[str, Any]) -> dict[str, Any]:
    loaded = _read_all().get(section)
    if not isinstance(loaded, dict):
        return deepcopy(defaults)
    return {**deepcopy(defaults), **loaded}


def save_runtime_section(section: str, values: dict[str, Any]) -> Path | None:
    if not persistence_enabled():
        return None
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _read_all()
    payload[section] = deepcopy(values)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path
