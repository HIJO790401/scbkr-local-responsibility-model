from apps.api import sidecar


def test_desktop_parent_pid_accepts_only_a_different_positive_pid(monkeypatch):
    monkeypatch.delenv("SCBKR_DESKTOP_PARENT_PID", raising=False)
    assert sidecar.desktop_parent_pid() is None

    monkeypatch.setenv("SCBKR_DESKTOP_PARENT_PID", "not-a-pid")
    assert sidecar.desktop_parent_pid() is None

    monkeypatch.setenv("SCBKR_DESKTOP_PARENT_PID", "0")
    assert sidecar.desktop_parent_pid() is None

    monkeypatch.setenv("SCBKR_DESKTOP_PARENT_PID", str(sidecar.os.getpid()))
    assert sidecar.desktop_parent_pid() is None

    monkeypatch.setenv("SCBKR_DESKTOP_PARENT_PID", str(sidecar.os.getpid() + 1000))
    assert sidecar.desktop_parent_pid() == sidecar.os.getpid() + 1000
