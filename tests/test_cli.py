"""Tests for the /cli terminal."""

import base64
import os
import re
import threading
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

    def _fake_session(self, monkeypatch, block=None):
        """Replace Session; the first instance optionally blocks in __init__."""
        from wlanpi_webui.cli import cli as cli_module

        created = []

        class FakeSession:
            def __init__(self):
                self.last = time.time()
                self.closed = False
                created.append(self)
                if block and len(created) == 1:
                    block["entered"].set()
                    assert block["release"].wait(5), "test never released"

            def drain(self):
                pass

            def close(self):
                self.closed = True

        monkeypatch.setattr(cli_module, "Session", FakeSession)
        return created

    def _clients(self, app, monkeypatch, n=2):
        clients = [app.test_client() for _ in range(n)]
        for c in clients:
            _login(c, monkeypatch)
        return clients

    def _post(self, c, path, results):
        results.append(c.post(path, headers={"X-CSRF-Token": _csrf(c)}))

    def test_concurrent_starts_share_one_shell(self, app, monkeypatch):
        # gunicorn runs with threads; two tabs mounting /cli at once must not
        # each spawn a shell (the second would orphan the first PTY).
        from conftest import ContendedLock, join_all

        from wlanpi_webui.cli import cli as cli_module

        lock = ContendedLock()
        monkeypatch.setattr(cli_module, "_lock", lock)
        block = {"entered": threading.Event(), "release": threading.Event()}
        created = self._fake_session(monkeypatch, block)
        c1, c2 = self._clients(app, monkeypatch)
        results = []

        first = threading.Thread(target=self._post, args=(c1, "/cli/start", results))
        first.start()
        assert block["entered"].wait(5)
        second = threading.Thread(target=self._post, args=(c2, "/cli/start", results))
        second.start()
        assert lock.contended.wait(5), "second start never reached the lock"
        block["release"].set()
        join_all(first, second)

        assert len(created) == 1
        assert sorted(r.get_json()["resumed"] for r in results) == [False, True]

    def test_start_during_stop_gets_a_new_shell(self, app, monkeypatch):
        # A tab mounting /cli while another tab's stop is closing the shell
        # must not "resume" the shell that is about to disappear.
        from conftest import ContendedLock, join_all

        from wlanpi_webui.cli import cli as cli_module

        lock = ContendedLock()
        monkeypatch.setattr(cli_module, "_lock", lock)
        created = self._fake_session(monkeypatch)
        closing = threading.Event()
        release = threading.Event()

        class ClosingSession:
            last = time.time()

            def drain(self):
                pass

            def close(self):
                closing.set()
                assert release.wait(5), "test never released"

        cli_module._session = ClosingSession()
        c1, c2 = self._clients(app, monkeypatch)
        stops, starts = [], []

        stop = threading.Thread(target=self._post, args=(c1, "/cli/stop", stops))
        stop.start()
        assert closing.wait(5)
        start = threading.Thread(target=self._post, args=(c2, "/cli/start", starts))
        start.start()
        assert lock.contended.wait(5), "start never reached the lock"
        release.set()
        join_all(stop, start)

        assert stops[0].status_code == 204
        assert starts[0].get_json() == {"ok": True, "resumed": False}
        assert cli_module._session is created[0]

    def test_shell_owns_its_terminal(self, client, monkeypatch):
        # setsid --ctty: the shell leads its own session with the PTY as its
        # controlling terminal, so job control (Ctrl-Z, fg) works.
        _login(client, monkeypatch)
        headers = {"X-CSRF-Token": _csrf(client)}
        client.post("/cli/start", headers=headers)
        client.post(
            "/cli/input",
            json={
                "data": base64.b64encode(
                    # "JC""X" prints as JCX, so the typed line never matches
                    b'echo "JC""X $$ $(ps -o sid= -p $$) $(ps -o tty= -p $$)"\n'
                ).decode()
            },
            headers=headers,
        )
        output = _read_until(client, b"JCX ", 1, tries=200).decode(errors="replace")
        match = re.search(r"JCX (\d+) +(\d+) +(\S+)", output)
        assert match, output
        pid, sid, tty = match.groups()
        assert pid == sid
        assert tty != "?"

    def test_no_idle_banner(self, client, monkeypatch):
        _login(client, monkeypatch)
        csrf = _csrf(client)
        assert (
            client.post("/cli/start", headers={"X-CSRF-Token": csrf}).status_code == 200
        )
        body = client.get("/cli/output?since=0").get_json()
        assert b"no sudo" not in base64.b64decode(body["data"])
