"""Tests for the Phase 2 session lifecycle: idle timeout, reboot logout and
persisted session key."""

import re
from pathlib import Path

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


class TestSessionLifecycle:
    def test_active_session_reaches_app(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.get("/").status_code == 200
        assert client.get("/auth/check").status_code == 200

    def test_idle_expiry_signs_out(self, client, monkeypatch):
        _login(client, monkeypatch)
        with client.session_transaction() as sess:
            sess["last_seen"] = 0  # ancient
        assert client.get("/").status_code == 302
        assert client.get("/auth/check").status_code == 401

    def test_reboot_signs_out(self, client, monkeypatch):
        _login(client, monkeypatch)
        with client.session_transaction() as sess:
            sess["boot_id"] = "not-the-current-boot-id"
        assert client.get("/").status_code == 302

    def test_background_poll_does_not_refresh(self, client, monkeypatch):
        _login(client, monkeypatch)
        with client.session_transaction() as sess:
            before = sess["last_seen"]
        resp = client.get("/stream/stats", headers={"hx-request": "true"})
        assert "Set-Cookie" not in resp.headers
        with client.session_transaction() as sess:
            assert sess["last_seen"] == before


class TestSessionKey:
    def test_persists_across_app_instances(self, tmp_path, monkeypatch):
        key_path = tmp_path / "session_key"
        monkeypatch.setattr(
            "wlanpi_webui.config.Config.SESSION_KEY_PATH", str(key_path)
        )
        app1 = create_app()
        app2 = create_app()
        assert app1.secret_key == app2.secret_key
        assert Path(key_path).exists()


class TestSystemPage:
    def test_requires_login(self, client):
        assert client.get("/system").status_code == 302

    def test_renders(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/system")
        assert resp.status_code == 200
        # The Health title loads with the stats fragment, not in the shell.
        assert b"system-health" in resp.data
        assert b"system/facts" in resp.data
        assert b"Hostname" not in resp.data

    def test_facts_render(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/system/facts")
        assert resp.status_code == 200
        assert b"Hostname" in resp.data
        assert b"Core" in resp.data

    def test_stats_fragment_has_health_title(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/stream/stats", headers={"hx-request": "true"})
        assert resp.status_code == 200
        assert b'uk-card-title">Health<' in resp.data

    def test_debug_is_gone(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.get("/debug").status_code == 404


class TestThemeCookie:
    def test_theme_cookie_renders_data_theme(self, client):
        client.set_cookie("wlanpi_theme", "dark")
        resp = client.get("/login")
        assert b'data-theme="dark"' in resp.data
