"""Tests for the Phase 1 UI work: branded auth pages and the PWA manifest."""

import json
from pathlib import Path

import pytest

from wlanpi_webui.app import create_app


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
def client(app):
    return app.test_client()


class TestAuthPages:
    def test_login_uses_auth_shell(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert b"auth-shell" in resp.data
        assert b"WLAN Pi" in resp.data

    def test_login_shows_expired_notice(self, client):
        resp = client.get("/login?reason=expired")
        assert resp.status_code == 200
        assert b"session expired" in resp.data.lower()

    def test_login_hides_expired_notice_by_default(self, client):
        resp = client.get("/login")
        assert b"session expired" not in resp.data.lower()

    def test_change_password_uses_auth_shell(self, client):
        resp = client.get("/change_password")
        assert resp.status_code == 200
        assert b"auth-shell" in resp.data
        assert b"Change password" in resp.data


class TestManifest:
    def test_manifest_is_valid_and_icons_exist(self, app):
        static = Path(app.root_path) / "static"
        manifest = json.loads((static / "img" / "site.webmanifest").read_text())
        assert manifest["name"] == "WLAN Pi"
        assert manifest["icons"]
        for icon in manifest["icons"]:
            assert icon["src"].startswith("/static/")
            assert (static / icon["src"].removeprefix("/static/")).exists()


class TestModernization:
    def test_login_has_fixed_icon_path(self, client):
        resp = client.get("/login")
        assert b"apple-icon-touch" not in resp.data
        assert b"apple-touch-icon.png" in resp.data

    def test_dashboard_has_heading(self, client, monkeypatch):
        import re

        from wlanpi_webui.auth import auth

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"status": "success"}

        monkeypatch.setattr(auth, "make_api_request", lambda *a, **k: _FakeResp())
        page = client.get("/login")
        csrf = (
            re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
            .group(1)
            .decode()
        )
        assert (
            client.post(
                "/login",
                data={"username": "wlanpi", "password": "x", "csrf_token": csrf},
            ).status_code
            == 302
        )
        resp = client.get("/")
        assert b"<h1" in resp.data
        assert b"skip-link" in resp.data
        assert b"Portable testing, troubleshooting" in resp.data
        assert b"uk-active" in resp.data
        assert b'aria-current="page"' in resp.data

    def test_full_pages_have_header_and_footer(self, client, monkeypatch):
        import re

        from wlanpi_webui.auth import auth

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"status": "success"}

        monkeypatch.setattr(auth, "make_api_request", lambda *a, **k: _FakeResp())
        page = client.get("/login")
        csrf = (
            re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
            .group(1)
            .decode()
        )
        client.post(
            "/login",
            data={"username": "wlanpi", "password": "x", "csrf_token": csrf},
        )
        resp = client.get("/apps")
        assert b"page-head" in resp.data
        assert b"Applications" in resp.data
        assert b"app-footer" in resp.data
