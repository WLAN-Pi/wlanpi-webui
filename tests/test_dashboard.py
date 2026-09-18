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

    def test_renders_tile_launcher(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"flipper-screen" in resp.data
        assert resp.data.count(b'class="flipper-tile"') >= 2
        assert b"Speed Test" in resp.data
        assert b"Hostname:" in resp.data
        assert b"Mode:" in resp.data

    def test_htmx_returns_partial(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/", headers={"hx-request": "true"})
        assert resp.status_code == 200
        assert b"<html" not in resp.data


class TestLibrespeedMoved:
    def test_speedtest_still_available(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.get("/speedtest/librespeed").status_code == 200


class TestAboutPage:
    def test_description_and_resources(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/about")
        assert resp.status_code == 200
        assert b"open-source Wi-Fi analysis tool" in resp.data
        assert b"Resources" in resp.data
        assert b">System</h3>" not in resp.data
