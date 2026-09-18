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
