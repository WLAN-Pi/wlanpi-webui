"""Tests for the /cli terminal."""

import base64
import os
import re
import time

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


@pytest.fixture(autouse=True)
def _clean_session():
    """The live PTY is a module global; do not leak it between tests."""
    from wlanpi_webui.cli import cli as cli_module

    cli_module._session = None
    yield
    if cli_module._session is not None:
        cli_module._session.close()
        cli_module._session = None


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


def _read_until(client, needle, count, tries=40):
    """Poll /cli/output until `needle` has shown up `count` times."""
    output = b""
    since = 0
    for _ in range(tries):
        body = client.get(f"/cli/output?since={since}").get_json()
        since = body["offset"]
        output += base64.b64decode(body["data"])
        if output.count(needle) >= count:
            break
        time.sleep(0.05)
    return output


class TestCli:
    def test_requires_login(self, client):
        assert client.get("/cli").status_code == 302

    def test_page_renders(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/cli")
        assert resp.status_code == 200
        assert b'id="cli-terminal"' in resp.data
        assert b"vendor/xterm/xterm.js" in resp.data

    def test_start_requires_csrf(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.post("/cli/start").status_code == 400

    def test_shell_round_trip(self, client, monkeypatch):
        _login(client, monkeypatch)
        csrf = _csrf(client)
        headers = {"X-CSRF-Token": csrf}

        assert client.post("/cli/start", headers=headers).status_code == 200
        payload = base64.b64encode(b"echo wlanpi-cli-check\n").decode()
        resp = client.post("/cli/input", json={"data": payload}, headers=headers)
        assert resp.status_code == 204

        # once for the echoed command, once for its output
        output = _read_until(client, b"wlanpi-cli-check", 2)
        assert output.count(b"wlanpi-cli-check") >= 2
        assert client.post("/cli/stop", headers=headers).status_code == 204

    def test_shell_starts_in_home(self, client, monkeypatch):
        _login(client, monkeypatch)
        csrf = _csrf(client)
        headers = {"X-CSRF-Token": csrf}

        assert client.post("/cli/start", headers=headers).status_code == 200
        client.post(
            "/cli/input",
            json={"data": base64.b64encode(b"pwd\n").decode()},
            headers=headers,
        )
        output = _read_until(client, os.environ["HOME"].encode(), 1)
        assert os.environ["HOME"].encode() in output
        assert b"site-packages" not in output

    def test_output_reports_whether_the_shell_is_alive(self, client, monkeypatch):
        _login(client, monkeypatch)
        csrf = _csrf(client)
        headers = {"X-CSRF-Token": csrf}

        assert client.get("/cli/output").get_json()["alive"] is False
        assert client.post("/cli/start", headers=headers).status_code == 200
        assert client.get("/cli/output").get_json()["alive"] is True
        assert client.post("/cli/stop", headers=headers).status_code == 204
        assert client.get("/cli/output").get_json()["alive"] is False

    def test_session_resumes_across_remount(self, client, monkeypatch):
        _login(client, monkeypatch)
        csrf = _csrf(client)
        headers = {"X-CSRF-Token": csrf}

        started = client.post("/cli/start", headers=headers).get_json()
        assert started == {"ok": True, "resumed": False}

        client.post(
            "/cli/input",
            json={"data": base64.b64encode(b"echo wlanpi-resume\n").decode()},
            headers=headers,
        )
        _read_until(client, b"wlanpi-resume", 2)

        # Re-mounting /cli attaches to the live shell instead of replacing it.
        resumed = client.post("/cli/start", headers=headers).get_json()
        assert resumed == {"ok": True, "resumed": True}

        body = client.get("/cli/output?since=0").get_json()
        assert body["alive"] is True
        assert b"wlanpi-resume" in base64.b64decode(body["data"])

    def test_no_idle_banner(self, client, monkeypatch):
        _login(client, monkeypatch)
        csrf = _csrf(client)
        assert (
            client.post("/cli/start", headers={"X-CSRF-Token": csrf}).status_code == 200
        )
        body = client.get("/cli/output?since=0").get_json()
        assert b"no sudo" not in base64.b64decode(body["data"])
