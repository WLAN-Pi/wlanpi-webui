"""Tests for the Phase 1 UI work: branded auth pages and the PWA manifest."""

import json
import re
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


class TestThemes:
    def test_launcher_and_interactive_states_use_theme_tokens(self, app):
        css = (Path(app.root_path) / "static" / "css" / "app.css").read_text()
        launcher = css[css.index(".launcher-screen {") : css.index(".game-stage {")]

        assert "background: var(--bg-surface);" in launcher
        assert "background: var(--bg-page);" in launcher
        assert "color: var(--text) !important;" in launcher
        assert ".uk-input:focus" in css
        assert ".uk-button-primary:active" in css
        assert ".uk-alert-primary" in css

    def test_canvas_redraws_on_theme_change(self, app):
        js = (
            Path(app.root_path) / "static" / "js" / "speedtest_results.js"
        ).read_text()
        assert 'document.addEventListener("wlanpi:theme", renderAll);' in js


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
        assert b"Wi-Fi Analysis. Anywhere. Anytime." in resp.data
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


class TestContentSecurityPolicy:
    @pytest.mark.parametrize("path", ["/login", "/no-such-page", "/auth/check"])
    def test_policy_on_every_response(self, client, path):
        # after_request covers pages, error pages and JSON alike
        resp = client.get(path)
        csp = resp.headers["Content-Security-Policy"]
        assert "script-src 'self' 'wasm-unsafe-eval'" in csp
        assert "object-src 'none'" in csp
        assert "'unsafe-inline'" not in csp
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    # script-src 'self' blocks inline <script>, on* attributes, javascript:
    # URLs and eval (hyperscript's js() block).
    INLINE = re.compile(
        r"<script\b(?![^>]*\bsrc\s*=)[^>]*>|\son[a-z]+\s*=|javascript:"
        r"""|(?<![\w-])_\s*=\s*["'][^"']*\bjs\s*\(""",
        re.IGNORECASE,
    )

    @pytest.mark.parametrize(
        "snippet",
        [
            "<SCRIPT>alert(1)</SCRIPT>",
            "<script type=module>alert(1)</script>",
            '<button ONCLICK="x()">',
            '<button onclick = "x()">',
            '<a href="javascript:x()">',
            '_="on load JS (window.x())"',
        ],
    )
    def test_inline_detector_catches(self, snippet):
        assert self.INLINE.search(snippet)

    def test_inline_detector_allows_external_script(self):
        assert not self.INLINE.search('<script src="/static/js/app.js" defer></script>')

    def test_templates_have_no_inline_script(self):
        root = Path(__file__).parent.parent / "wlanpi_webui" / "templates"
        offenders = [
            f"{path.name}: {m.group(0)}"
            for path in root.rglob("*.html")
            for m in self.INLINE.finditer(path.read_text())
        ]
        assert offenders == []

    def test_toast_from_query_string_is_gone(self):
        # ?toast= was rendered as HTML, pre-auth on /login.
        app_js = Path(__file__).parent.parent / "wlanpi_webui/static/js/app.js"
        text = app_js.read_text()
        assert 'params.get("toast")' not in text
        assert "message: escapeHtml(message)" in text
        assert "escapeHtml(n.message)" in text

    def test_static_urls_carry_version(self, client):
        from wlanpi_webui.__version__ import __version__

        page = client.get("/login").data.decode()
        assert f"/static/js/app.js?v={__version__}" in page
        img = client.get(f"/static/img/favicon-16x16.png?v={__version__}")
        assert img.status_code == 200
        assert img.mimetype == "image/png"
