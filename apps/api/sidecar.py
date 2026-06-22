"""P14-C Windows preview FastAPI sidecar entrypoint.

This module is intended as the PyInstaller target for `scbkr-api.exe`. It sets
safe local defaults before importing the FastAPI app so runtime path constants
honor SCBKR_DATA_DIR.
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path


def _default_windows_app_data() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "SCBKR" / "data"


def configure_sidecar_environment() -> dict[str, str]:
    os.environ.setdefault("SCBKR_DESKTOP_PREVIEW", "1")
    os.environ.setdefault("SCBKR_DATA_DIR", str(_default_windows_app_data()))
    os.environ.setdefault("SCBKR_API_HOST", "127.0.0.1")
    os.environ.setdefault("SCBKR_API_PORT", "8787")
    return {
        "SCBKR_DESKTOP_PREVIEW": os.environ["SCBKR_DESKTOP_PREVIEW"],
        "SCBKR_DATA_DIR": os.environ["SCBKR_DATA_DIR"],
        "SCBKR_API_HOST": os.environ["SCBKR_API_HOST"],
        "SCBKR_API_PORT": os.environ["SCBKR_API_PORT"],
    }


def assert_port_available(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        if sock.connect_ex((host, port)) == 0:
            raise RuntimeError(f"SCBKR API sidecar port already in use: {host}:{port}")


def main() -> int:
    env = configure_sidecar_environment()
    host = env["SCBKR_API_HOST"]
    port = int(env["SCBKR_API_PORT"])
    if host != "127.0.0.1":
        raise RuntimeError("SCBKR API sidecar must bind only to 127.0.0.1")
    assert_port_available(host, port)

    import uvicorn
    from apps.api.main import app

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SCBKR API sidecar failed: {exc}", file=sys.stderr)
        raise
