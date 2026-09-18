"""Tests for the Apps control page."""

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


def _everything_installed(monkeypatch):
    monkeypatch.setattr("wlanpi_webui.app.package_installed", lambda pkg: True)

    from wlanpi_webui.apps import apps as apps_module

    monkeypatch.setattr(apps_module, "system_service_running_state", lambda unit: True)
    monkeypatch.setattr(
        apps_module, "systemd_service_message", lambda unit: f"{unit} is running"
    )

    from wlanpi_webui.grafana import grafana as grafana_module

    monkeypatch.setattr(grafana_module, "system_service_exists", lambda unit: True)
    monkeypatch.setattr(
        grafana_module, "system_service_running_state", lambda unit: False
    )


class TestApps:
    def test_requires_login(self, client):
        assert client.get("/apps").status_code == 302

    def test_renders_speed_test_without_extras(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/apps")
        assert resp.status_code == 200
        assert b"Speed Test" in resp.data
        assert b'href="/speedtest/librespeed"' in resp.data

    def test_renders_all_installed_apps(self, client, monkeypatch):
        _everything_installed(monkeypatch)
        _login(client, monkeypatch)
        resp = client.get("/apps")
        assert resp.status_code == 200
        for name in (b"Profiler", b"Kismet", b"Grafana", b"Cockpit"):
            assert name in resp.data
        assert b'hx-post="/stopprofiler"' in resp.data
        assert b'href="/kismet"' in resp.data
        assert b'href="/grafana_url"' in resp.data
        assert b'href="/app/cockpit"' in resp.data
        assert b"Internet Monitoring" in resp.data

    def test_toggle_redirects_back_to_referrer(self, client, monkeypatch):
        _login(client, monkeypatch)

        from wlanpi_webui import utils

        class CoreResponse:
            status_code = 200
            text = ""

        monkeypatch.setattr(utils, "make_api_request", lambda *a, **k: CoreResponse())
        monkeypatch.setattr(utils, "system_service_exists", lambda service: True)

        from wlanpi_webui.profiler import profiler as profiler_module

        monkeypatch.setattr(
            profiler_module, "system_service_running_state", lambda service: True
        )

        with client.session_transaction() as sess:
            csrf = sess["csrf_token"]
        resp = client.post(
            "/startprofiler",
            headers={"hx-request": "true", "Referer": "https://wlanpi.local/apps"},
            data={"csrf_token": csrf},
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/apps")
