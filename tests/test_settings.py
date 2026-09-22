"""Tests for the Settings page."""

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


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "wlanpi_webui.config.Config.SESSION_KEY_PATH", str(tmp_path / "session_key")
    )
    return create_app()


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


class TestSettings:
    def test_requires_login(self, client):
        assert client.get("/settings").status_code == 302

    def test_renders(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/settings")
        assert resp.status_code == 200
        assert b"Signed in as" in resp.data
        assert b"Toggle dark mode" in resp.data
        assert b"Diagnostics" in resp.data
        assert b"/alerts" in resp.data
        assert b"Log out" in resp.data
        assert b"/debug" not in resp.data
        assert b"/notifications" not in resp.data


class TestAlertsHistory:
    """Alerts and the toast history share one page."""

    def test_notifications_route_is_gone(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.get("/notifications").status_code == 404

    def test_alerts_page_carries_the_message_history(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/alerts")
        assert resp.status_code == 200
        assert b"notifications-list" in resp.data

    def test_alerts_partial_has_the_history(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/alerts", headers={"hx-request": "true"})
        assert resp.status_code == 200
        assert b"<html" not in resp.data
        assert b"notifications-list" in resp.data


def _csrf(client):
    with client.session_transaction() as sess:
        return sess["csrf_token"]


class TestSettingsCore:
    def test_renders_clock_and_domain(self, client, monkeypatch):
        from wlanpi_webui.settings import settings as s

        def fake(path, params=None):
            if "timezone/list" in path:
                return {"timezones": ["UTC", "Europe/London"]}
            if "reg-domain/list" in path:
                return {"countries": [{"code": "GB", "name": "United Kingdom"}]}
            if "reg-domain" in path:
                return {"country": "GB"}
            return {"display": "Sun 2026-09-21 20:00 UTC", "timezone": "UTC"}

        monkeypatch.setattr(s, "get_core_json", fake)
        _login(client, monkeypatch)
        resp = client.get("/settings")
        assert resp.status_code == 200
        assert b"Europe/London" in resp.data
        assert b"United Kingdom (GB)" in resp.data
        assert b"Sun 2026-09-21 20:00 UTC" in resp.data

    def test_set_timezone_queues_toast(self, client, monkeypatch):
        from wlanpi_webui.settings import settings as s

        monkeypatch.setattr(s, "post_core_json", lambda *a, **k: {"timezone": "UTC"})
        _login(client, monkeypatch)
        resp = client.post(
            "/settings/timezone",
            data={"timezone": "UTC", "csrf_token": _csrf(client)},
            headers={"Referer": "https://wlanpi.local/settings"},
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/settings")
        with client.session_transaction() as sess:
            assert sess["wlanpi_toast"]["message"] == "Timezone set to UTC."

    def test_set_reg_domain_queues_toast(self, client, monkeypatch):
        from wlanpi_webui.settings import settings as s

        monkeypatch.setattr(s, "post_core_json", lambda *a, **k: {"country": "GB"})
        _login(client, monkeypatch)
        resp = client.post(
            "/settings/reg-domain",
            data={"country": "gb", "csrf_token": _csrf(client)},
            headers={"Referer": "https://wlanpi.local/settings"},
        )
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert sess["wlanpi_toast"]["message"] == "Regulatory domain set to GB."

    def test_reboot_failure_queues_warning(self, client, monkeypatch):
        from wlanpi_webui.settings import settings as s

        monkeypatch.setattr(s, "post_core_json", lambda *a, **k: None)
        _login(client, monkeypatch)
        resp = client.post(
            "/settings/reboot",
            data={"csrf_token": _csrf(client)},
            headers={"Referer": "https://wlanpi.local/settings"},
        )
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert sess["wlanpi_toast"]["message"] == "Could not reboot the device."

    def test_writes_require_csrf(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.post("/settings/ntp").status_code == 400
        assert client.post("/settings/shutdown").status_code == 400
