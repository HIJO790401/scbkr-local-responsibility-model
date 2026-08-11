"""SCBKR Windows desktop FastAPI sidecar entrypoint.

This module is intended as the PyInstaller target for `scbkr-api.exe`. It sets
safe local defaults before importing the FastAPI app so runtime path constants
honor SCBKR_DATA_DIR.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path


def _default_windows_app_data() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "SCBKR" / "data"


def _ensure_writable_data_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".scbkr-write-check"
    try:
        probe.write_text("ok", encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"SCBKR cannot write to its data directory: {path}. "
            "Choose a writable local folder and restart the app."
        ) from exc
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
    return path


def configure_sidecar_environment() -> dict[str, str]:
    os.environ.setdefault("SCBKR_DESKTOP_RUNTIME", "store-candidate")
    os.environ.setdefault("SCBKR_DATA_DIR", str(_default_windows_app_data()))
    os.environ.setdefault("SCBKR_API_HOST", "127.0.0.1")
    os.environ.setdefault("SCBKR_API_PORT", "8787")
    os.environ.setdefault("SCBKR_LAN_COMPANION_ENABLED", "0")
    os.environ["SCBKR_DATA_DIR"] = str(
        _ensure_writable_data_dir(Path(os.environ["SCBKR_DATA_DIR"]).expanduser())
    )
    return {
        "SCBKR_DESKTOP_RUNTIME": os.environ["SCBKR_DESKTOP_RUNTIME"],
        "SCBKR_DATA_DIR": os.environ["SCBKR_DATA_DIR"],
        "SCBKR_API_HOST": os.environ["SCBKR_API_HOST"],
        "SCBKR_API_PORT": os.environ["SCBKR_API_PORT"],
        "SCBKR_LAN_COMPANION_ENABLED": os.environ["SCBKR_LAN_COMPANION_ENABLED"],
        "SCBKR_COMPANION_TOKEN": os.environ.get("SCBKR_COMPANION_TOKEN", ""),
    }


def assert_port_available(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        if sock.connect_ex((host, port)) == 0:
            raise RuntimeError(f"SCBKR API sidecar port already in use: {host}:{port}")


def record_startup_failure(exc: Exception) -> None:
    message = f"SCBKR API sidecar failed: {exc}\n"
    try:
        data_dir = Path(os.environ.get("SCBKR_DATA_DIR") or _default_windows_app_data())
        data_dir.mkdir(parents=True, exist_ok=True)
        with (data_dir / "sidecar-error.log").open("a", encoding="utf-8") as handle:
            handle.write(message)
    except OSError:
        pass
    if sys.stderr is not None:
        print(message.rstrip(), file=sys.stderr)


def desktop_parent_pid() -> int | None:
    raw = str(os.environ.get("SCBKR_DESKTOP_PARENT_PID") or "").strip()
    try:
        pid = int(raw)
    except ValueError:
        return None
    return pid if pid > 0 and pid != os.getpid() else None


def _wait_for_parent_exit(parent_pid: int) -> None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        synchronize = 0x00100000
        infinite = 0xFFFFFFFF
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(synchronize, False, parent_pid)
        if handle:
            try:
                kernel32.WaitForSingleObject(handle, infinite)
            finally:
                kernel32.CloseHandle(handle)
    else:
        while True:
            try:
                os.kill(parent_pid, 0)
            except OSError:
                break
            time.sleep(1)
    os._exit(0)


def start_desktop_parent_watchdog() -> threading.Thread | None:
    parent_pid = desktop_parent_pid()
    if parent_pid is None:
        return None
    watcher = threading.Thread(
        target=_wait_for_parent_exit,
        args=(parent_pid,),
        name="scbkr-desktop-parent-watchdog",
        daemon=True,
    )
    watcher.start()
    return watcher


def main() -> int:
    env = configure_sidecar_environment()
    start_desktop_parent_watchdog()
    host = env["SCBKR_API_HOST"]
    port = int(env["SCBKR_API_PORT"])
    lan_enabled = env.get("SCBKR_LAN_COMPANION_ENABLED") == "1"
    token = env.get("SCBKR_COMPANION_TOKEN", "")
    if lan_enabled:
        if host != "0.0.0.0":
            raise RuntimeError("SCBKR LAN Companion Mode must bind to 0.0.0.0")
        if not token.strip():
            raise RuntimeError("SCBKR LAN Companion Mode requires SCBKR_COMPANION_TOKEN")
    elif host != "127.0.0.1":
        raise RuntimeError("SCBKR API sidecar must bind only to 127.0.0.1 unless LAN Companion Mode is enabled")
    assert_port_available(host, port)

    import uvicorn
    from apps.api.main import app

    # Store builds use a windowed PyInstaller bootloader, where stdout and
    # stderr do not exist. Uvicorn's default console handlers can therefore
    # prevent startup. Runtime failures are persisted by record_startup_failure.
    uvicorn.run(app, host=host, port=port, log_config=None, access_log=False)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        record_startup_failure(exc)
        raise
