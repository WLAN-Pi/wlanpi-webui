"""Tests for the Phase 3 dashboard at ``/``."""

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


class TestDashboard:
    def test_requires_login(self, client):
        assert client.get("/").status_code == 302

    def test_renders_system_card(self, client, monkeypatch):
        from wlanpi_webui.dashboard import dashboard as d

        monkeypatch.setattr(
            d,
            "get_core_json",
            lambda *a, **k: {
                "model": "R4",
                "name": "wlanpi-573",
                "hostname": "wlanpi-573.local",
                "mode": "classic",
                "software_version": "3.2.0",
            },
        )
        _login(client, monkeypatch)
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Quick links" in resp.data
        assert b"R4" in resp.data
        assert b"/dashboard/network" in resp.data

    def test_htmx_returns_partial(self, client, monkeypatch):
        from wlanpi_webui.dashboard import dashboard as d

        monkeypatch.setattr(d, "get_core_json", lambda *a, **k: {})
        _login(client, monkeypatch)
        resp = client.get("/", headers={"hx-request": "true"})
        assert resp.status_code == 200
        assert b"<html" not in resp.data

    def test_network_fragment_renders_core_data(self, client, monkeypatch):
        from wlanpi_webui.dashboard import dashboard as d

        def fake(path, params=None):
            if "reachability" in path:
                return {
                    "Ping Google": "5ms",
                    "Browse Google": "OK",
                    "Arping Gateway": "1ms",
                    "custom": [],
                }
            return {
                "interfaces": {"eth0": {"status": "UP", "ip": "192.168.6.63"}},
                "public_ip": {"info": ["1.2.3.4"]},
            }

        monkeypatch.setattr(d, "get_core_json", fake)
        _login(client, monkeypatch)
        resp = client.get("/dashboard/network")
        assert resp.status_code == 200
        assert b"Ping Google: 5ms" in resp.data
        assert b"eth0: UP 192.168.6.63" in resp.data
        assert b"1.2.3.4" in resp.data

    def test_network_fragment_fallback(self, client, monkeypatch):
        from wlanpi_webui.dashboard import dashboard as d

        monkeypatch.setattr(d, "get_core_json", lambda *a, **k: None)
        _login(client, monkeypatch)
        resp = client.get("/dashboard/network")
        assert b"wlanpi-core is unavailable" in resp.data


class TestLibrespeedMoved:
    def test_speedtest_still_available(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.get("/speedtest/librespeed").status_code == 200
