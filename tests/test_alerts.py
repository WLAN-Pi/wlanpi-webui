"""Tests for the /alerts page, the navbar icon, and the alert header."""

import re

import pytest

from wlanpi_webui.app import create_app


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _make_app(tmp_path, monkeypatch, core_running=True):
    monkeypatch.setattr(
        "wlanpi_webui.config.Config.SESSION_KEY_PATH", str(tmp_path / "session_key")
    )
    monkeypatch.setattr(
        "wlanpi_webui.app.system_service_running_state",
        lambda service, quiet=False: core_running,
    )
    monkeypatch.setattr(
        "wlanpi_webui.utils.system_service_running_state",
        lambda service, quiet=False: core_running,
    )
    return create_app()


@pytest.fixture()
def app(tmp_path, monkeypatch):
    from wlanpi_webui import utils

    utils.clear_core_alert()
    return _make_app(tmp_path, monkeypatch)


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, monkeypatch):
    from wlanpi_webui.auth import auth

    monkeypatch.setattr(
        auth, "make_api_request", lambda *a, **k: FakeResponse({"status": "success"})
    )
    page = client.get("/login")
    csrf = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
    resp = client.post(
        "/login",
        data={"username": "wlanpi", "password": "x", "csrf_token": csrf},
    )
    assert resp.status_code == 302


class TestAlerts:
    def test_no_alerts(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/alerts")
        assert resp.status_code == 200
        assert b"No active alerts." in resp.data
        assert b'data-alert-keys=""' in resp.data
        assert resp.headers["X-Wlanpi-Alerts"] == ""

    def test_auth_alert_shown(self, client, monkeypatch):
        from wlanpi_webui import utils

        utils.record_core_alert("NTP needs set; cannot proceed")
        _login(client, monkeypatch)
        resp = client.get("/alerts")
        assert b"wlanpi-core authentication failed" in resp.data
        assert b"NTP needs set" in resp.data
        assert b'data-alert-keys="core-auth"' in resp.data
        assert resp.headers["X-Wlanpi-Alerts"] == "core-auth"

    def test_core_down_alert(self, tmp_path, monkeypatch):
        from wlanpi_webui import utils

        utils.clear_core_alert()
        app = _make_app(tmp_path, monkeypatch, core_running=False)
        client = app.test_client()
        _login(client, monkeypatch)
        resp = client.get("/alerts")
        assert b"wlanpi-core is not running" in resp.data
        assert resp.headers["X-Wlanpi-Alerts"] == "core-down"
