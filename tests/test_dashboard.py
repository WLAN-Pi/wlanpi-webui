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
        from wlanpi_webui.dashboard import dashboard as d

        monkeypatch.setattr(d, "get_hostname", lambda: "testpi")
        monkeypatch.setattr(d, "get_mode", lambda: "classic")
        _login(client, monkeypatch)
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"flipper-screen" in resp.data
        assert resp.data.count(b'class="flipper-tile"') >= 2
        assert b"Speedtest" in resp.data
        assert b"flipper-foot" in resp.data
        assert b"testpi" in resp.data
        assert b"classic" in resp.data

    def test_htmx_returns_partial(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/", headers={"hx-request": "true"})
        assert resp.status_code == 200
        assert b"<html" not in resp.data


class TestRedirects:
    def test_speedtest_redirects_to_app(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/speedtest/librespeed")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith(
            "/app/librespeed/librespeed_detailed.html"
        )

    def test_speedtest_details_redirects_to_app(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/speedtest/librespeed/details")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/speedtest/librespeed")

    def test_cockpit_redirects_to_app(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/cockpit")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/app/cockpit")

    def test_grafana_url_redirects_to_app(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/grafana_url")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/app/grafana")

    def test_kismet_redirects_to_its_port(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/kismet")
        assert resp.status_code == 302
        assert ":2501" in resp.headers["Location"]


class TestNoIframes:
    @pytest.mark.parametrize(
        "path", ["/", "/apps", "/settings", "/about", "/network", "/system"]
    )
    def test_pages_have_no_iframe(self, client, monkeypatch, path):
        _login(client, monkeypatch)
        assert b"<iframe" not in client.get(path).data


class TestAboutPage:
    def test_description_and_resources(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/about")
        assert resp.status_code == 200
        assert b"open-source Wi-Fi analysis tool" in resp.data
        assert b"Resources" not in resp.data
        assert b"ko-fi.com/wlanpi" in resp.data
        assert b">System</h3>" not in resp.data


class TestPacketStorm:
    def test_requires_login(self, client):
        resp = client.get("/packetstorm")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_htmx_requires_login(self, client):
        resp = client.get("/packetstorm", headers={"hx-request": "true"})
        assert resp.status_code == 401

    def test_full_page(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/packetstorm")
        assert resp.status_code == 200
        assert b"packetstorm-stage" in resp.data
        assert b"<html" in resp.data

    def test_htmx_returns_partial(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/packetstorm", headers={"hx-request": "true"})
        assert resp.status_code == 200
        assert b"packetstorm-stage" in resp.data
        assert b"packetstorm.js" in resp.data
        assert b"<html" not in resp.data

    def test_dashboard_tile_uses_custom_svg(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"/packetstorm" in resp.data
        assert b"<svg" in resp.data
