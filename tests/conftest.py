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
