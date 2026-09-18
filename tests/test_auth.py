"""Tests for PAM-backed session login, CSRF, and POST-only mutating routes."""

import hashlib
import hmac
import re

import pytest

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
        assert "/change_password" in resp.headers["Location"]

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
        resp = client.post("/logout", data={"csrf_token": "x"})
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert "user" not in sess


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


class TestHmacSignature:
    def test_json_body_signed_exactly(self, monkeypatch):
        import requests as requests_module

        from wlanpi_webui import utils

        captured = {}

        def fake_request(
            method, url, headers=None, params=None, data=None, verify=None, timeout=None
        ):
            captured.update(method=method, url=url, headers=headers, data=data)

            class R:
                def raise_for_status(self):
                    pass

            return R()

        monkeypatch.setattr(requests_module, "request", fake_request)
        monkeypatch.setattr(utils, "get_shared_secret", lambda *a, **k: b"test-secret")
        utils.make_api_request(
            "POST",
            "https://127.0.0.1:31415/api/v1/auth/pam",
            json_body={"username": "u", "password": "p"},
        )
        assert captured["method"] == "POST"
        assert captured["data"] == '{"username": "u", "password": "p"}'
        expected = hmac.new(
            b"test-secret",
            b"POST\n/api/v1/auth/pam\n\n" + captured["data"].encode(),
            hashlib.sha256,
        ).hexdigest()
        assert captured["headers"]["X-Request-Signature"] == expected
        assert captured["headers"]["Content-Type"] == "application/json"

    def test_no_body_in_debug_logging(self, app, monkeypatch):
        from wlanpi_webui import utils

        calls = []
        with app.test_request_context():
            logger = app.logger
            monkeypatch.setattr(logger, "debug", lambda *a: calls.append(a))
            utils.generate_hmac_signature("POST", "/api/v1/auth/pam", body="s3cretpw")
        assert not any("s3cretpw" in str(c) for c in calls)
