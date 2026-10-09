"""Tests for the Phase 1 UI work: branded auth pages and the PWA manifest."""

import hashlib
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

    @pytest.mark.parametrize("path", ["/login", "/change_password"])
    def test_fields_have_visible_labels(self, client, path):
        html = client.get(path).data.decode()
        assert "<main" in html and "<h1" in html
        assert "placeholder=" not in html
        inputs = re.findall(r'<input id="([^"]+)" class="uk-input"', html)
        assert inputs
        for field_id in inputs:
            assert f'<label class="uk-form-label" for="{field_id}">' in html


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
        # Desktop navbar and phone offcanvas both mark the current page.
        assert resp.data.count(b'aria-current="page"') == 2

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


class TestKeyboardReachable:
    ROOT = Path(__file__).parent.parent / "wlanpi_webui" / "templates"

    def _offenders(self, pattern):
        return [
            f"{path.name}: {' '.join(m.group(0).split())[:80]}"
            for path in self.ROOT.rglob("*.html")
            for m in re.finditer(pattern, path.read_text())
        ]

    def test_htmx_links_have_href(self):
        # Without href an <a> is not focusable and Enter does nothing; a
        # different href would send new-tab clicks somewhere else.
        bad = []
        for path in self.ROOT.rglob("*.html"):
            for m in re.finditer(
                r"<a\b[^>]*\bhx-get=\"([^\"]*)\"[^>]*>", path.read_text()
            ):
                if f'href="{m.group(1)}"' not in m.group(0):
                    bad.append(f"{path.name}: {m.group(1)}")
        assert bad == []

    def test_no_button_inside_link(self):
        assert self._offenders(r"<a\b[^>]*>\s*<button\b") == []

    def test_no_fake_buttons(self):
        assert self._offenders(r"<(?!button\b)\w+\b[^>]*\brole=\"button\"") == []

    def test_htmx_forms_post_natively(self):
        # Without method, a click before deferred htmx runs would GET the
        # form, putting the CSRF token in the URL and access log.
        assert self._offenders(r"<form\b(?![^>]*\bmethod=)[^>]*\bhx-post=[^>]*>") == []


class TestHeadings:
    ROOT = Path(__file__).parent.parent / "wlanpi_webui" / "templates"

    def test_page_titles_are_h1(self):
        titles = [
            (path.name, m.group(1))
            for path in self.ROOT.rglob("*.html")
            for m in re.finditer(r'<(h\d) class="page-title', path.read_text())
        ]
        assert titles
        assert [t for t in titles if t[1] != "h1"] == []

    def test_no_unclassed_low_headings(self):
        # Section and sub-section headings carry a class; a bare <h4>/<h5>
        # was how levels got skipped.
        bare = [
            path.name
            for path in self.ROOT.rglob("*.html")
            if re.search(r"<h[4-6]>", path.read_text())
        ]
        assert bare == []


class TestAssets:
    def test_shell_loads_minified_uikit_and_no_xterm(self, client):
        resp = client.get("/login")
        assert b"css/uikit.min.css" in resp.data
        assert b"css/uikit.css" not in resp.data
        assert b"xterm.css" not in resp.data


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

    def _fingerprint(self, app, filename):
        data = (Path(app.static_folder) / filename).read_bytes()
        return hashlib.sha256(data).hexdigest()[:12]

    def test_static_urls_carry_fingerprint(self, app, client):
        page = client.get("/login").data.decode()
        assert f"/static/js/app.js?v={self._fingerprint(app, 'js/app.js')}" in page
        fp = self._fingerprint(app, "img/favicon-16x16.png")
        img = client.get(f"/static/img/favicon-16x16.png?v={fp}")
        assert img.status_code == 200
        assert img.mimetype == "image/png"
        assert "immutable" in img.headers["Cache-Control"]

    def test_only_matching_fingerprint_is_cached_long(self, app, client):
        fp = self._fingerprint(app, "js/app.js")
        current = client.get(f"/static/js/app.js?v={fp}")
        assert "max-age=31536000" in current.headers["Cache-Control"]
        # a hand-copied or newer file no longer matches an old URL
        for url in ("/static/js/app.js", "/static/js/app.js?v=000000000000"):
            assert "immutable" not in client.get(url).headers.get("Cache-Control", "")

    def test_request_path_never_reads_files(self, app, client, monkeypatch):
        # Fingerprints come from a table built at startup; a client-chosen
        # path (traversal, random names, OPTIONS) must not reach the disk
        # or grow anything.
        def boom(self):
            raise AssertionError(f"read {self}")

        monkeypatch.setattr(Path, "read_bytes", boom)
        for method, url in (
            ("OPTIONS", "/static/x/../../../../etc/passwd?v=1"),
            ("OPTIONS", "/static/nope-1.js?v=1"),
            ("GET", "/static/js/zz/../app.js?v=1"),
        ):
            resp = client.open(url, method=method)
            assert "immutable" not in resp.headers.get("Cache-Control", "")

    def test_replaced_file_loses_long_cache(self, app, client, monkeypatch):
        import os

        fp = self._fingerprint(app, "js/app.js")
        target = Path(app.static_folder) / "js/app.js"
        stat = target.stat()
        real_stat = Path.stat

        def changed(self, **kwargs):
            if self == target:
                return os.stat_result(
                    (stat.st_mode, 0, 0, 0, 0, 0, stat.st_size + 1, 0, 0, 0)
                )
            return real_stat(self, **kwargs)

        monkeypatch.setattr(Path, "stat", changed)
        resp = client.get(f"/static/js/app.js?v={fp}")
        assert "immutable" not in resp.headers.get("Cache-Control", "")
        assert f"app.js?v={fp}" not in client.get("/login").data.decode()

    def test_revalidation_keeps_long_cache_and_no_cookie(self, app, client):
        url = f"/static/js/app.js?v={self._fingerprint(app, 'js/app.js')}"
        first = client.get(url)
        again = client.get(url, headers={"If-None-Match": first.headers["ETag"]})
        assert again.status_code == 304
        assert "immutable" in again.headers["Cache-Control"]
        assert "Set-Cookie" not in again.headers
        assert "Cookie" not in again.headers.get("Vary", "")
