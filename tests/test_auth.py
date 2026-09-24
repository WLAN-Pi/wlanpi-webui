"""Tests for PAM-backed session login, CSRF, and POST-only mutating routes."""

import json
import re

import pytest
import requests as requests_module

from wlanpi_webui.app import create_app


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self._status = status

    def raise_for_status(self):
        if self._status >= 400:
            raise AssertionError(f"unexpected status {self._status}")

    def json(self):
        return self._payload


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
def client(app):
    return app.test_client()


def _get_csrf(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    match = re.search(rb'name="csrf_token" value="([^"]+)"', resp.data)
    assert match, "csrf token not found in login page"
    return match.group(1).decode()


def _login(client, monkeypatch, status="success"):
    from wlanpi_webui.auth import auth

    monkeypatch.setattr(
        auth, "make_api_request", lambda *a, **k: FakeResponse({"status": status})
    )
    csrf = _get_csrf(client)
    resp = client.post(
        "/login",
        data={"username": "wlanpi", "password": "wlanpi", "csrf_token": csrf},
    )
    return resp


class TestLoginGate:
    def test_anonymous_redirected_to_login(self, client):
        resp = client.get("/")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_anonymous_static_allowed(self, client):
        resp = client.get("/static/css/app.css")
        assert resp.status_code in (200, 404)

    def test_login_page_accessible(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert b"Log in" in resp.data

    def test_authenticated_reaches_app(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/")
        assert resp.status_code == 200


class TestLogin:
    def test_success_sets_session(self, client, monkeypatch):
        from wlanpi_webui.auth import auth

        calls = []

        def fake(*args, **kwargs):
            calls.append((args, kwargs))
            return FakeResponse({"status": "success"})

        monkeypatch.setattr(auth, "make_api_request", fake)
        csrf = _get_csrf(client)
        resp = client.post(
            "/login",
            data={"username": "wlanpi", "password": "secretpw", "csrf_token": csrf},
        )
        assert resp.status_code == 302
        assert calls[0][0] == ("POST", auth.CORE_PAM_URL)
        assert calls[0][1]["json_body"] == {
            "username": "wlanpi",
            "password": "secretpw",
        }
        with client.session_transaction() as sess:
            assert sess["user"] == "wlanpi"
            assert sess["csrf_token"]

    def test_wrong_password_rejected(self, client, monkeypatch):
        resp = _login(client, monkeypatch, status="failure")
        assert resp.status_code == 401
        assert b"Incorrect username or password" in resp.data
        with client.session_transaction() as sess:
            assert "user" not in sess

    def test_expired_password_redirects_to_change(self, client, monkeypatch):
        resp = _login(client, monkeypatch, status="password_change_required")
        assert resp.status_code == 302
        # The username rides the signed session, not the URL (audit #11).
        assert resp.headers["Location"] == "/change_password"

    def test_change_page_prefills_username(self, client, monkeypatch):
        _login(client, monkeypatch, status="password_change_required")
        resp = client.get("/change_password")
        assert resp.status_code == 200
        assert b'value="wlanpi"' in resp.data
        assert b"new_password_confirm" in resp.data

    def test_change_page_ignores_username_query(self, client):
        resp = client.get("/change_password?username=wlanpi")
        assert b'value="wlanpi"' not in resp.data

    def test_change_rejects_mismatched_confirm(self, client):
        csrf = _get_csrf(client)
        resp = client.post(
            "/change_password",
            data={
                "username": "wlanpi",
                "current_password": "old",
                "new_password": "new1",
                "new_password_confirm": "new2",
                "csrf_token": csrf,
            },
        )
        assert resp.status_code == 400
        assert b"do not match" in resp.data

    def test_change_rejects_same_password(self, client):
        csrf = _get_csrf(client)
        resp = client.post(
            "/change_password",
            data={
                "username": "wlanpi",
                "current_password": "same",
                "new_password": "same",
                "new_password_confirm": "same",
                "csrf_token": csrf,
            },
        )
        assert resp.status_code == 400
        assert b"different" in resp.data

    def test_core_unreachable_shows_error(self, client, monkeypatch):
        import requests

        from wlanpi_webui.auth import auth

        monkeypatch.setattr(
            auth,
            "make_api_request",
            lambda *a, **k: (_ for _ in ()).throw(requests.exceptions.ConnectionError),
        )
        csrf = _get_csrf(client)
        resp = client.post(
            "/login",
            data={"username": "wlanpi", "password": "x", "csrf_token": csrf},
        )
        assert resp.status_code == 401
        assert b"wlanpi-core" in resp.data

    def test_missing_csrf_rejected(self, client):
        resp = client.post("/login", data={"username": "wlanpi", "password": "x"})
        assert resp.status_code == 400


class TestAuthCheck:
    def test_anonymous_401(self, client):
        assert client.get("/auth/check").status_code == 401

    def test_authenticated_200(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.get("/auth/check").status_code == 200


class TestLogout:
    def test_logout_clears_session(self, client, monkeypatch):
        _login(client, monkeypatch)
        with client.session_transaction() as sess:
            csrf = sess["csrf_token"]
        resp = client.post("/logout", data={"csrf_token": csrf})
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert "user" not in sess

    def test_logout_requires_csrf(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.post("/logout", data={"csrf_token": "x"}).status_code == 400
        assert client.get("/auth/check").status_code == 200


class TestMutatingRoutes:
    def test_get_rejected(self, client):
        assert client.get("/startprofiler").status_code == 405
        assert client.get("/startgrafana").status_code == 405
        assert client.get("/startkismet").status_code == 405

    def test_post_without_csrf_rejected(self, client, monkeypatch):
        from wlanpi_webui.auth import auth

        monkeypatch.setattr(
            auth,
            "make_api_request",
            lambda *a, **k: FakeResponse({"status": "success"}),
        )
        _login(client, monkeypatch)
        assert client.post("/startprofiler").status_code == 400
        assert client.post("/stopgrafana").status_code == 400

    def test_post_with_csrf_executes(self, client, monkeypatch):
        from wlanpi_webui.auth import auth

        monkeypatch.setattr(
            auth,
            "make_api_request",
            lambda *a, **k: FakeResponse({"status": "success"}),
        )
        _login(client, monkeypatch)
        profiler = __import__("wlanpi_webui.profiler.profiler", fromlist=["x"])
        monkeypatch.setattr(profiler, "system_service_running_state", lambda s: True)
        monkeypatch.setattr(
            profiler, "start_stop_service", lambda task, service: ("", 204)
        )
        with client.session_transaction() as sess:
            csrf = sess["csrf_token"]
        resp = client.post(
            "/startprofiler", headers={"hx-request": "true", "X-CSRF-Token": csrf}
        )
        assert resp.status_code == 204


class _Resp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests_module.HTTPError(response=self)

    def json(self):
        return self._payload


class TestCoreToken:
    def _patch_token(self, monkeypatch, token="abc"):
        def fake_run(*a, **k):
            return type(
                "R", (), {"stdout": json.dumps({"access_token": token}), "stderr": ""}
            )()

        monkeypatch.setattr("wlanpi_webui.utils.subprocess.run", fake_run)

    def test_make_api_request_sends_bearer(self, app, monkeypatch):
        from wlanpi_webui import utils

        utils.reset_core_token()
        self._patch_token(monkeypatch)
        captured = {}

        def fake_request(method, url, headers=None, **kwargs):
            captured["headers"] = headers
            return _Resp(200)

        monkeypatch.setattr(requests_module, "request", fake_request)
        with app.test_request_context():
            utils.make_api_request(
                "POST",
                "https://127.0.0.1:31415/api/v1/auth/pam",
                json_body={"username": "u"},
            )
        assert captured["headers"]["Authorization"] == "Bearer abc"
        assert "X-Request-Signature" not in captured["headers"]

    def test_401_remints_and_retries(self, app, monkeypatch):
        from wlanpi_webui import utils

        utils.reset_core_token()
        self._patch_token(monkeypatch, token="fresh")
        seen = []

        def fake_request(method, url, headers=None, **kwargs):
            seen.append(headers["Authorization"])
            return _Resp(401 if len(seen) == 1 else 200)

        monkeypatch.setattr(requests_module, "request", fake_request)
        with app.test_request_context():
            utils.make_api_request("GET", "https://127.0.0.1:31415/api/v1/x")
        assert seen == ["Bearer fresh", "Bearer fresh"]
        assert len(seen) == 2

    def test_clock_error_raises_core_auth_error(self, app, monkeypatch):
        from wlanpi_webui import utils

        utils.reset_core_token()
        self._patch_token(monkeypatch)
        monkeypatch.setattr(
            requests_module,
            "request",
            lambda *a, **k: _Resp(503, {"error": "AUTH_CLOCK_NOT_SET"}),
        )
        with app.test_request_context():
            with pytest.raises(utils.CoreAuthError):
                utils.make_api_request("GET", "https://127.0.0.1:31415/api/v1/x")


def _post_login(client, username="wlanpi", ip="192.0.2.10"):
    csrf = _get_csrf(client)
    return client.post(
        "/login",
        data={"username": username, "password": "guess", "csrf_token": csrf},
        headers={"X-Forwarded-For": ip},
    )


class TestLoginThrottle:
    """Audit #4: failed logins back off per client IP and per username."""

    def _core(self, monkeypatch, status="failure"):
        from wlanpi_webui.auth import auth

        calls = []

        def fake(*args, **kwargs):
            calls.append(kwargs["json_body"]["username"])
            return FakeResponse({"status": status})

        monkeypatch.setattr(auth, "make_api_request", fake)
        return calls

    def test_backs_off_after_free_attempts(self, client, monkeypatch):
        from wlanpi_webui.auth import auth

        calls = self._core(monkeypatch)
        for _ in range(auth.FREE_ATTEMPTS):
            assert _post_login(client).status_code == 401
        resp = _post_login(client)
        assert resp.status_code == 429
        assert b"Too many failed attempts" in resp.data
        assert len(calls) == auth.FREE_ATTEMPTS  # core never asked

    def test_per_ip_across_usernames(self, client, monkeypatch):
        from wlanpi_webui.auth import auth

        self._core(monkeypatch)
        for i in range(auth.FREE_ATTEMPTS):
            _post_login(client, username=f"user{i}")
        assert _post_login(client, username="fresh").status_code == 429
        assert _post_login(client, username="fresh", ip="192.0.2.99").status_code == 401

    def test_per_username_across_ips(self, client, monkeypatch):
        """Spread guessing is throttled after each new IP's first miss."""
        from wlanpi_webui.auth import auth

        self._core(monkeypatch)
        for i in range(auth.FREE_ATTEMPTS):
            _post_login(client, ip=f"192.0.2.{i + 20}")
        assert _post_login(client, ip="192.0.2.99").status_code == 401
        assert _post_login(client, ip="192.0.2.99").status_code == 429

    def test_username_backoff_does_not_lock_out_a_clean_client(
        self, client, monkeypatch
    ):
        """Audit gate: hammering one username must not lock the admin out."""
        from wlanpi_webui.auth import auth

        self._core(monkeypatch)
        for _ in range(auth.FREE_ATTEMPTS + 3):
            _post_login(client, ip="192.0.2.66")
        calls = self._core(monkeypatch, status="success")
        assert _post_login(client, ip="192.0.2.5").status_code == 302
        assert calls == ["wlanpi"]

    def test_backoff_expires(self, client, monkeypatch):
        from wlanpi_webui.auth import auth

        self._core(monkeypatch)
        for _ in range(auth.FREE_ATTEMPTS):
            _post_login(client)
        now = auth.boot_clock()
        monkeypatch.setattr(auth, "boot_clock", lambda: now + 2)  # past the 1s delay
        assert _post_login(client).status_code == 401

    def test_success_clears_failures(self, client, monkeypatch):
        from wlanpi_webui.auth import auth

        self._core(monkeypatch)
        for _ in range(auth.FREE_ATTEMPTS - 1):
            _post_login(client)
        self._core(monkeypatch, status="success")
        assert _post_login(client).status_code == 302
        assert not client.application.extensions["wlanpi_auth"]["failures"]

    def test_core_errors_do_not_count(self, client, monkeypatch):
        from wlanpi_webui.auth import auth

        monkeypatch.setattr(
            auth,
            "make_api_request",
            lambda *a, **k: (_ for _ in ()).throw(requests_module.ConnectionError),
        )
        for _ in range(auth.FREE_ATTEMPTS + 1):
            assert _post_login(client).status_code == 401

    def test_failure_is_logged_with_client_ip(self, client, monkeypatch, caplog):
        self._core(monkeypatch)
        _post_login(client, username="bad\nname", ip="192.0.2.77")
        assert "failed login for 'bad\\nname' from 192.0.2.77" in caplog.text

    def test_tracked_keys_are_bounded(self, client, monkeypatch):
        from wlanpi_webui.auth import auth

        self._core(monkeypatch)
        monkeypatch.setattr(auth, "MAX_TRACKED", 4)
        for i in range(5):
            _post_login(client, username=f"u{i}", ip=f"192.0.2.{i + 1}")
        assert len(client.application.extensions["wlanpi_auth"]["failures"]) <= 4

    def test_change_password_is_throttled(self, client, monkeypatch):
        from wlanpi_webui.auth import auth

        calls = self._core(monkeypatch)
        csrf = _get_csrf(client)
        data = {
            "username": "wlanpi",
            "current_password": "guess",
            "new_password": "n3w-Pass",
            "new_password_confirm": "n3w-Pass",
            "csrf_token": csrf,
        }
        for _ in range(auth.FREE_ATTEMPTS):
            assert client.post("/change_password", data=data).status_code == 400
        resp = client.post("/change_password", data=data)
        assert resp.status_code == 429
        assert b"Too many failed attempts" in resp.data
        assert len(calls) == auth.FREE_ATTEMPTS  # core never asked


class TestCoreErrorMessages:
    """Audit #9: core errors get a message that matches the cause."""

    def _http_error(self, monkeypatch, code):
        from wlanpi_webui.auth import auth

        def fake(*a, **k):
            raise requests_module.HTTPError(response=_Resp(code))

        monkeypatch.setattr(auth, "make_api_request", fake)

    @pytest.mark.parametrize(
        ("code", "text", "counted"),
        [
            (422, b"up to 128 characters", True),  # a flood of bad input
            (429, b"wlanpi-core is busy", False),
            (503, b"could not check the password", False),
            (500, b"Unable to reach wlanpi-core", False),
        ],
    )
    def test_login_maps_core_http_errors(
        self, client, monkeypatch, code, text, counted
    ):
        self._http_error(monkeypatch, code)
        resp = _post_login(client)
        assert resp.status_code == 401
        assert text in resp.data
        failures = client.application.extensions["wlanpi_auth"]["failures"]
        assert bool(failures) is counted

    def test_rejected_new_password_explained(self, client, monkeypatch):
        from wlanpi_webui.auth import auth

        monkeypatch.setattr(
            auth,
            "make_api_request",
            lambda *a, **k: FakeResponse({"status": "password_rejected"}),
        )
        csrf = _get_csrf(client)
        resp = client.post(
            "/change_password",
            data={
                "username": "wlanpi",
                "current_password": "wlanpi",
                "new_password": "a",
                "new_password_confirm": "a",
                "csrf_token": csrf,
            },
        )
        assert resp.status_code == 400
        assert b"too short, too simple" in resp.data
        assert not client.application.extensions["wlanpi_auth"]["failures"]


class TestRequestHardening:
    def test_control_characters_in_username_never_reach_core(self, client, monkeypatch):
        """PAM would cut at a NUL and check a different account (audit gate)."""
        from wlanpi_webui.auth import auth

        calls = []
        monkeypatch.setattr(auth, "make_api_request", lambda *a, **k: calls.append(1))
        resp = _post_login(client, username="wlanpi\x00junk")
        assert resp.status_code == 401
        assert b"Incorrect username or password" in resp.data
        assert calls == []
        assert client.application.extensions["wlanpi_auth"]["failures"]

    def test_forwarded_for_and_proto_are_trusted(self, app, monkeypatch):
        """The throttle keys on the client IP nginx appends (ProxyFix x_for)."""
        seen = {}

        @app.route("/_probe")
        def _probe():
            from flask import request

            seen["addr"], seen["scheme"] = request.remote_addr, request.scheme
            return ""

        client = app.test_client()
        _login(client, monkeypatch)
        client.get(
            "/_probe",
            headers={"X-Forwarded-For": "192.0.2.8", "X-Forwarded-Proto": "https"},
        )
        assert seen == {"addr": "192.0.2.8", "scheme": "https"}

    def test_nginx_sets_frame_options_everywhere(self):
        from pathlib import Path

        conf = (
            Path(__file__).parent.parent / "install/etc/nginx/wlanpi_webui.conf"
        ).read_text()
        directives = [
            line.strip()
            for line in conf.splitlines()
            if "X-Frame-Options" in line and not line.strip().startswith("#")
        ]
        # server level, plus the grafana and cockpit locations that override it
        assert directives == ['add_header X-Frame-Options "SAMEORIGIN" always;'] * 3

    def test_non_ascii_csrf_is_rejected_not_500(self, client):
        _get_csrf(client)
        resp = client.post(
            "/login", data={"username": "wlanpi", "password": "x", "csrf_token": "é"}
        )
        assert resp.status_code == 400

    def test_forwarded_prefix_and_host_are_ignored(self, client):
        resp = client.get(
            "/login",
            headers={
                "X-Forwarded-Prefix": "//evil.example",
                "X-Forwarded-Host": "evil.example",
            },
        )
        assert b"evil.example" not in resp.data
