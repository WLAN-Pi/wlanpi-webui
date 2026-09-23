import pytest


@pytest.fixture(autouse=True)
def core_up(monkeypatch):
    """Treat wlanpi-core as running unless a test says otherwise; keeps the
    core-down gate off the real systemctl."""
    monkeypatch.setattr(
        "wlanpi_webui.app.system_service_running_state", lambda *a, **k: True
    )
