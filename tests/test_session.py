"""Tests for the Phase 2 session lifecycle: idle timeout, reboot logout and
persisted session key."""

import json
import re
from pathlib import Path

import pytest

import wlanpi_webui.app as app_module
from wlanpi_webui.app import create_app
from wlanpi_webui.utils import boot_clock


def _registry(app):
    return app.extensions["wlanpi_auth"]["sessions"]


def _assert_expiry_revokes(app, client):
    """The expiring request signs out AND drops the sid, so a copy is dead."""
    copied = client.get_cookie("session").value
    assert client.get("/").status_code == 302
    assert _registry(app) == {}
    client.set_cookie("session", copied)
    assert client.get("/auth/check").status_code == 401


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


class TestSessionLifecycle:
    def test_active_session_reaches_app(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.get("/").status_code == 200
        assert client.get("/auth/check").status_code == 200

    def test_idle_expiry_signs_out_and_revokes(self, app, client, monkeypatch):
        _login(client, monkeypatch)
        with client.session_transaction() as sess:
            sess["last_seen"] = boot_clock() - app.config["IDLE_TIMEOUT"] - 1
        _assert_expiry_revokes(app, client)

    def test_reboot_signs_out_and_revokes(self, app, client, monkeypatch):
        _login(client, monkeypatch)
        with client.session_transaction() as sess:
            sess["boot_id"] = "not-the-current-boot-id"
        _assert_expiry_revokes(app, client)

    def test_background_poll_does_not_refresh(self, client, monkeypatch):
        _login(client, monkeypatch)
        with client.session_transaction() as sess:
            before = sess["last_seen"]
        resp = client.get(
            "/stream/stats", headers={"hx-request": "true", "X-Wlanpi-Poll": "1"}
        )
        assert "Set-Cookie" not in resp.headers
        with client.session_transaction() as sess:
            assert sess["last_seen"] == before

    def test_system_refresh_now_counts_as_activity(self, client, monkeypatch):
        _login(client, monkeypatch)
        with client.session_transaction() as sess:
            sess["last_seen"] = before = sess["last_seen"] - 60
        client.get("/stream/stats", headers={"hx-request": "true"})
        with client.session_transaction() as sess:
            assert sess["last_seen"] > before

    @pytest.mark.parametrize(
        "path", ["/static/js/app.js?v=1", "/static/img/favicon-16x16.png"]
    )
    def test_static_files_leave_the_session_alone(self, client, monkeypatch, path):
        # A new cookie per asset plus Vary: Cookie defeats the browser cache.
        _login(client, monkeypatch)
        with client.session_transaction() as sess:
            sess["last_seen"] = before = sess["last_seen"] - 60
        resp = client.get(path)
        assert resp.status_code == 200
        assert "Set-Cookie" not in resp.headers
        assert "Cookie" not in resp.headers.get("Vary", "")
        with client.session_transaction() as sess:
            assert sess["last_seen"] == before

    def test_background_endpoints_exist(self, app):
        # A typo here would silently keep an open tab signed in forever.
        from wlanpi_webui.app import BACKGROUND_ENDPOINTS

        endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
        assert BACKGROUND_ENDPOINTS <= endpoints

    def _last_seen_after(self, client, monkeypatch, headers):
        from wlanpi_webui.network import network

        monkeypatch.setattr(network, "get_core_json", lambda *a, **k: None)
        _login(client, monkeypatch)
        with client.session_transaction() as sess:
            sess["last_seen"] = before = sess["last_seen"] - 60
        client.get("/network/cards", headers={"hx-request": "true", **headers})
        with client.session_transaction() as sess:
            return before, sess["last_seen"]

    def test_marked_poll_does_not_refresh(self, client, monkeypatch):
        before, after = self._last_seen_after(
            client, monkeypatch, {"X-Wlanpi-Poll": "1"}
        )
        assert after == before

    def test_refresh_now_counts_as_activity(self, client, monkeypatch):
        # Same endpoint as the poll, but user-initiated: no poll header.
        before, after = self._last_seen_after(client, monkeypatch, {})
        assert after > before


class TestSessionKey:
    def test_persists_across_app_instances(self, tmp_path, monkeypatch):
        key_path = tmp_path / "session_key"
        monkeypatch.setattr(
            "wlanpi_webui.config.Config.SESSION_KEY_PATH", str(key_path)
        )
        app1 = create_app()
        app2 = create_app()
        assert app1.secret_key == app2.secret_key
        assert Path(key_path).exists()


class TestSystemPage:
    def test_requires_login(self, client):
        assert client.get("/system").status_code == 302

    def test_renders(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/system")
        assert resp.status_code == 200
        # Cards load individually from /system/card/<name>, not in the shell.
        assert b"system-health" in resp.data
        assert b"/system/card/facts" in resp.data
        assert b"Hostname" not in resp.data

    def test_facts_render(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/system/card/facts")
        assert resp.status_code == 200
        assert b"Hostname" in resp.data
        assert b"Core" in resp.data

    def test_stats_fragment_has_stat_rows(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/stream/stats", headers={"hx-request": "true"})
        assert resp.status_code == 200
        assert b'class="stat-container"' in resp.data
        # The card title now loads lazily with the rows.
        assert b'uk-card-title">Resource usage<' in resp.data
        # icons are fingerprinted like every other static URL
        assert re.search(rb"/static/icon/cpu\.svg\?v=[0-9a-f]{12}", resp.data)

    def test_debug_is_gone(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.get("/debug").status_code == 404


class TestThemeCookie:
    def test_theme_cookie_renders_data_theme(self, client):
        client.set_cookie("wlanpi_theme", "dark")
        resp = client.get("/login")
        assert b'data-theme="dark"' in resp.data


def _logout(client):
    with client.session_transaction() as sess:
        csrf = sess["csrf_token"]
    assert client.post("/logout", data={"csrf_token": csrf}).status_code == 302


class TestServerSideSessions:
    """Audit #2, #3, #10: sessions are registered server-side and revocable."""

    def test_cookie_is_secure_and_samesite(self, client, monkeypatch):
        _login(client, monkeypatch)
        cookie = client.get_cookie("session")
        assert cookie.secure
        assert cookie.http_only
        assert cookie.same_site == "Lax"

    def test_logout_revokes_a_copied_cookie(self, client, monkeypatch):
        _login(client, monkeypatch)
        stolen = client.get_cookie("session").value
        _logout(client)
        client.set_cookie("session", stolen)
        assert client.get("/auth/check").status_code == 401
        assert client.get("/").status_code == 302

    def test_session_survives_service_restart(self, app, client, monkeypatch):
        _login(client, monkeypatch)
        cookie = client.get_cookie("session").value
        restarted = create_app().test_client()
        restarted.set_cookie("session", cookie)
        assert restarted.get("/auth/check").status_code == 200

    def test_absolute_lifetime_signs_out_active_session(self, app, client, monkeypatch):
        _login(client, monkeypatch)
        for record in _registry(app).values():
            record["created"] -= app.config["MAX_SESSION_AGE"] + 1
        # Idle-fresh (last_seen is now), yet past the absolute lifetime.
        copied = client.get_cookie("session").value
        assert client.get("/").status_code == 302
        client.set_cookie("session", copied)
        assert client.get("/auth/check").status_code == 401

    def test_registry_user_mismatch_is_rejected(self, app, client, monkeypatch):
        _login(client, monkeypatch)
        for record in _registry(app).values():
            record["user"] = "someone-else"
        _assert_expiry_revokes(app, client)

    def test_login_prunes_expired_records(
        self, app, client, session_store, monkeypatch
    ):
        from wlanpi_webui.utils import read_boot_id

        old = boot_clock() - app.config["MAX_SESSION_AGE"] - 1
        session_store.write_text(
            json.dumps(
                {
                    "boot_id": read_boot_id(),
                    "sessions": {
                        "old": {"user": "wlanpi", "created": old},
                        "live": {"user": "wlanpi", "created": boot_clock()},
                    },
                }
            )
        )
        _login(client, monkeypatch)
        on_disk = json.loads(session_store.read_text())["sessions"]
        assert "old" not in on_disk and "live" in on_disk
        assert len(on_disk) == 2

    def test_store_from_another_boot_is_ignored(
        self, app, client, session_store, monkeypatch
    ):
        _login(client, monkeypatch)
        data = json.loads(session_store.read_text())
        data["boot_id"] = "previous-boot"
        session_store.write_text(json.dumps(data))
        restarted = create_app().test_client()
        restarted.set_cookie("session", client.get_cookie("session").value)
        assert restarted.get("/auth/check").status_code == 401

    def test_revocation_is_seen_by_another_worker(self, app, client, monkeypatch):
        """Gate: a gunicorn HUP reload briefly runs two workers."""
        _login(client, monkeypatch)
        cookie = client.get_cookie("session").value
        other_worker = create_app().test_client()
        other_worker.set_cookie("session", cookie)
        assert other_worker.get("/auth/check").status_code == 200
        _logout(client)
        assert other_worker.get("/auth/check").status_code == 401
        # ...and the other worker's next write must not resurrect it.
        _login(other_worker, monkeypatch)
        client.set_cookie("session", cookie)
        assert client.get("/auth/check").status_code == 401

    def test_failed_revocation_write_fails_closed(
        self, app, client, session_store, monkeypatch
    ):
        from wlanpi_webui.auth import auth

        _login(client, monkeypatch)
        cookie = client.get_cookie("session").value

        def broken_replace(*a, **k):
            raise OSError("disk full")

        # Scoped, so the autouse temporary SESSION_STORE_PATH stays patched.
        with monkeypatch.context() as broken:
            broken.setattr(auth.os, "replace", broken_replace)
            _logout(client)
        assert not session_store.exists()  # stale copy removed, not kept
        assert not list(session_store.parent.glob(".sessions.*"))  # no temp left
        restarted = create_app().test_client()
        restarted.set_cookie("session", cookie)
        assert restarted.get("/auth/check").status_code == 401
        client.set_cookie("session", cookie)
        assert client.get("/auth/check").status_code == 401

    def test_successful_change_clears_pending_username(self, client, monkeypatch):
        from wlanpi_webui.auth import auth

        monkeypatch.setattr(
            auth,
            "make_api_request",
            lambda *a, **k: FakeResponse({"status": "password_change_required"}),
        )
        page = client.get("/login")
        csrf = re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
        client.post(
            "/login",
            data={"username": "wlanpi", "password": "x", "csrf_token": csrf[1]},
        )
        with client.session_transaction() as sess:
            assert sess["pending_password_change"] == "wlanpi"
            csrf = sess["csrf_token"]
        monkeypatch.setattr(
            auth,
            "make_api_request",
            lambda *a, **k: FakeResponse({"status": "success"}),
        )
        resp = client.post(
            "/change_password",
            data={
                "username": "wlanpi",
                "current_password": "x",
                "new_password": "Wx7-kettle",
                "new_password_confirm": "Wx7-kettle",
                "csrf_token": csrf,
            },
        )
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert "pending_password_change" not in sess
            assert sess["user"] == "wlanpi"

    def test_password_change_revokes_other_sessions(self, app, monkeypatch):
        other = app.test_client()
        _login(other, monkeypatch)
        changer = app.test_client()
        _login(changer, monkeypatch)  # patches core to return "success"
        with changer.session_transaction() as sess:
            csrf = sess["csrf_token"]
        resp = changer.post(
            "/change_password",
            data={
                "username": "wlanpi",
                "current_password": "old",
                "new_password": "new-Pass-9",
                "new_password_confirm": "new-Pass-9",
                "csrf_token": csrf,
            },
        )
        assert resp.status_code == 302
        assert other.get("/auth/check").status_code == 401
        assert changer.get("/auth/check").status_code == 200

    def test_unwritable_store_still_allows_login(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "wlanpi_webui.config.Config.SESSION_STORE_PATH",
            str(tmp_path / "missing" / "sessions.json"),
        )
        client = create_app().test_client()
        _login(client, monkeypatch)
        assert client.get("/auth/check").status_code == 200

    def test_corrupt_store_is_ignored(self, session_store, monkeypatch):
        session_store.write_text("not json")
        client = create_app().test_client()
        _login(client, monkeypatch)
        assert client.get("/auth/check").status_code == 200


POLL = {"hx-request": "true", "X-Wlanpi-Poll": "1"}


class TestUnchangedPoll:
    """Polls echo the last X-Wlanpi-Etag; identical markup comes back as 204."""

    def test_same_markup_is_204(self, client, monkeypatch):
        _login(client, monkeypatch)
        first = client.get("/alerts", headers=POLL)
        etag = first.headers["X-Wlanpi-Etag"]
        assert first.status_code == 200 and first.data
        again = client.get("/alerts", headers={**POLL, "X-Wlanpi-Etag": etag})
        assert again.status_code == 204
        assert again.data == b""
        assert again.headers["X-Wlanpi-Etag"] == etag

    def test_stale_etag_gets_markup(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/alerts", headers={**POLL, "X-Wlanpi-Etag": "stale"})
        assert resp.status_code == 200 and resp.data

    def test_user_request_is_never_skipped(self, client, monkeypatch):
        _login(client, monkeypatch)
        etag = client.get("/alerts", headers=POLL).headers["X-Wlanpi-Etag"]
        resp = client.get(
            "/alerts", headers={"hx-request": "true", "X-Wlanpi-Etag": etag}
        )
        assert resp.status_code == 200
        assert "X-Wlanpi-Etag" not in resp.headers

    def test_post_is_never_skipped(self, client, monkeypatch):
        # A client header must not be able to swallow a mutation's response.
        client.application.add_url_rule(
            "/test-post", "test_post", lambda: "<p>done</p>", methods=["POST"]
        )
        _login(client, monkeypatch)
        resp = client.post("/test-post", headers=POLL)
        etag = resp.headers.get("X-Wlanpi-Etag", "")
        resp = client.post("/test-post", headers={**POLL, "X-Wlanpi-Etag": etag})
        assert resp.status_code == 200
        assert "X-Wlanpi-Etag" not in resp.headers

    def test_alert_change_alone_is_not_skipped(self, client, monkeypatch):
        # The bell reads X-Wlanpi-Alerts after a swap; a 204 would hide it.
        client.application.add_url_rule(
            "/test-poll", "test_poll", lambda: "<p>same</p>"
        )
        _login(client, monkeypatch)
        monkeypatch.setattr(app_module, "active_alerts", lambda core_running: [])
        etag = client.get("/test-poll", headers=POLL).headers["X-Wlanpi-Etag"]
        monkeypatch.setattr(
            app_module, "active_alerts", lambda core_running: [{"key": "core"}]
        )
        resp = client.get("/test-poll", headers={**POLL, "X-Wlanpi-Etag": etag})
        assert resp.status_code == 200
        assert resp.headers["X-Wlanpi-Alerts"] == "core"
        assert resp.headers["X-Wlanpi-Etag"] != etag

    def test_toast_is_delivered_even_if_markup_matches(self, client, monkeypatch):
        _login(client, monkeypatch)
        etag = client.get("/alerts", headers=POLL).headers["X-Wlanpi-Etag"]
        with client.session_transaction() as sess:
            sess["wlanpi_toast"] = {"message": "hi", "status": "primary"}
        resp = client.get("/alerts", headers={**POLL, "X-Wlanpi-Etag": etag})
        assert resp.status_code == 200
        assert "X-Wlanpi-Toast" in resp.headers
