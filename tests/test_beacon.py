"""Tests for the hidden easter egg: /beacon, /beacon/data, arm, tile."""

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
    monkeypatch.setattr(
        "wlanpi_webui.config.Config.BEACON_FLAG_PATH", str(tmp_path / "beacon")
    )
    monkeypatch.setattr(
        "wlanpi_webui.config.Config.BEACON_DATA_PATH", str(tmp_path / "data.wad")
    )
    return create_app()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def flag_path(app):
    return Path(app.config["BEACON_FLAG_PATH"])


@pytest.fixture()
def wad_path(app):
    return Path(app.config["BEACON_DATA_PATH"])


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


def _csrf(client):
    with client.session_transaction() as sess:
        return sess["csrf_token"]


class TestLocked:
    def test_requires_login(self, client):
        resp = client.get("/beacon")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_locked_returns_404_when_signed_in(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.get("/beacon").status_code == 404

    def test_locked_htmx_is_bare_404(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/beacon", headers={"hx-request": "true"})
        assert resp.status_code == 404
        assert b"<html" not in resp.data

    def test_dashboard_has_no_tile(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert b'href="/beacon"' not in client.get("/").data


class TestUnlocked:
    def _arm(self, flag_path):
        flag_path.write_text("unlocked\n")

    def test_page_renders_game(self, client, monkeypatch, flag_path, wad_path):
        self._arm(flag_path)
        wad_path.write_bytes(b"IWAD" * 16)
        _login(client, monkeypatch)
        resp = client.get("/beacon")
        assert resp.status_code == 200
        assert b"beacon-stage" in resp.data
        assert b"beacon.js" in resp.data

    def test_page_htmx_returns_partial(self, client, monkeypatch, flag_path, wad_path):
        self._arm(flag_path)
        wad_path.write_bytes(b"IWAD")
        _login(client, monkeypatch)
        resp = client.get("/beacon", headers={"hx-request": "true"})
        assert resp.status_code == 200
        assert b"beacon-stage" in resp.data
        assert b"<html" not in resp.data

    def test_missing_wad_shows_install_message(self, client, monkeypatch, flag_path):
        self._arm(flag_path)
        _login(client, monkeypatch)
        resp = client.get("/beacon")
        assert resp.status_code == 200
        assert b"beacon-stage" not in resp.data
        assert b"Install the game data" in resp.data

    def test_dashboard_has_tile(self, client, monkeypatch, flag_path):
        self._arm(flag_path)
        _login(client, monkeypatch)
        assert b'href="/beacon"' in client.get("/").data

    def test_wad_route_streams(self, client, monkeypatch, flag_path, wad_path):
        self._arm(flag_path)
        wad_path.write_bytes(b"DATA")
        _login(client, monkeypatch)
        resp = client.get("/beacon/data")
        assert resp.status_code == 200
        assert resp.data == b"DATA"

    def test_wad_route_locked_is_404(self, client, monkeypatch, flag_path):
        _login(client, monkeypatch)
        assert client.get("/beacon/data").status_code == 404


class TestArmEndpoint:
    def test_requires_login(self, client):
        assert client.post("/beacon/arm").status_code == 302

    def test_rejects_get(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.get("/beacon/arm").status_code == 405

    def test_requires_csrf(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.post("/beacon/arm").status_code == 400

    def test_writes_flag_and_is_idempotent(self, client, monkeypatch, flag_path):
        _login(client, monkeypatch)
        headers = {"X-CSRF-Token": _csrf(client)}
        assert client.post("/beacon/arm", headers=headers).status_code == 204
        assert flag_path.is_file()
        assert client.post("/beacon/arm", headers=headers).status_code == 204


class TestUnwritableFlag:
    def test_app_stays_up_and_disarmed(self, monkeypatch, tmp_path):
        # Point the flag at a path whose parent is a regular file, so neither
        # reading nor creating it can succeed. Config is copied into the app at
        # create_app time, so patch before building the app.
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("x")
        monkeypatch.setattr(
            "wlanpi_webui.config.Config.SESSION_KEY_PATH", str(tmp_path / "session_key")
        )
        monkeypatch.setattr(
            "wlanpi_webui.config.Config.BEACON_FLAG_PATH",
            str(blocker / "beacon"),
        )
        monkeypatch.setattr(
            "wlanpi_webui.config.Config.BEACON_DATA_PATH", str(tmp_path / "data.wad")
        )
        client = create_app().test_client()
        _login(client, monkeypatch)
        assert client.get("/").status_code == 200
        assert client.get("/beacon").status_code == 404
