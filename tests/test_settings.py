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
        assert b"wlanpiToast" in resp.data
        assert b"Log out" in resp.data
        assert b"/debug" not in resp.data
