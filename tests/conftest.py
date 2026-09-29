import threading

import pytest


@pytest.fixture(autouse=True)
def core_up(monkeypatch):
    """Treat wlanpi-core as running unless a test says otherwise; keeps the
    core-down gate off the real systemctl."""
    monkeypatch.setattr(
        "wlanpi_webui.app.system_service_running_state", lambda *a, **k: True
    )


@pytest.fixture(autouse=True)
def session_store(tmp_path, monkeypatch):
    """Keep the server-side session registry out of /var/lib."""
    path = tmp_path / "sessions.json"
    monkeypatch.setattr("wlanpi_webui.config.Config.SESSION_STORE_PATH", str(path))
    return path


class ContendedLock:
    """A drop-in Lock that reports when a second thread starts waiting on it.

    Concurrency tests park one request inside the lock, wait for `contended`,
    then release it, so the interleaving is forced rather than hoped for.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.contended = threading.Event()

    def __enter__(self):
        if not self._lock.acquire(blocking=False):
            self.contended.set()
            self._lock.acquire()
        return self

    def __exit__(self, *exc):
        self._lock.release()


def join_all(*threads):
    for t in threads:
        t.join(5)
        assert not t.is_alive(), "request thread hung"
