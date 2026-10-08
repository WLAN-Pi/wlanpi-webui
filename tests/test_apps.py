"""Tests for the Apps control page."""

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


def _everything_installed(monkeypatch):
    monkeypatch.setattr("wlanpi_webui.app.package_installed", lambda pkg: True)

    from wlanpi_webui.apps import apps as apps_module

    monkeypatch.setattr(apps_module, "system_service_running_state", lambda unit: True)
    monkeypatch.setattr(
        apps_module, "systemd_service_message", lambda unit: f"{unit} is running"
    )

    from wlanpi_webui.grafana import grafana as grafana_module

    monkeypatch.setattr(grafana_module, "system_service_exists", lambda unit: True)
    monkeypatch.setattr(
        grafana_module, "system_service_running_state", lambda unit: False
    )
    _grafana(monkeypatch, "active", True)


def _grafana(monkeypatch, active, responding):
    from wlanpi_webui.grafana import grafana as g

    monkeypatch.setattr(g, "system_service_active_state", lambda *a, **kw: active)
    monkeypatch.setattr(g, "_grafana_responding", lambda *a, **kw: responding)


class TestApps:
    def test_requires_login(self, client):
        assert client.get("/apps").status_code == 302

    def test_renders_speed_test_without_extras(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/apps/cards")
        assert resp.status_code == 200
        assert b"Speedtest" in resp.data
        assert b'href="/speedtest/librespeed"' in resp.data

    def test_renders_all_installed_apps(self, client, monkeypatch):
        _everything_installed(monkeypatch)
        _login(client, monkeypatch)
        resp = client.get("/apps/cards")
        assert resp.status_code == 200
        for name in (b"Profiler", b"Kismet", b"Grafana", b"Cockpit"):
            assert name in resp.data
        assert b'<button type="button" hx-post="/stopprofiler"' in resp.data
        assert b'href="/kismet"' in resp.data
        assert b'href="/grafana_url"' in resp.data
        assert b'href="/app/cockpit"' in resp.data
        assert b'href="/grafana"' in resp.data
        # Grafana is the last card, after Cockpit
        assert resp.data.index(b"Grafana") > resp.data.index(b"Cockpit")
        # data streams moved to their own page
        assert b"Internet monitoring" not in resp.data

    def test_shell_loads_without_services(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/apps")
        assert resp.status_code == 200
        assert b"apps/cards" in resp.data
        assert b"Speedtest" not in resp.data

    def test_toggle_redirects_back_to_referrer(self, client, monkeypatch):
        _login(client, monkeypatch)

        from wlanpi_webui import utils

        class CoreResponse:
            status_code = 200
            text = ""

        monkeypatch.setattr(utils, "make_api_request", lambda *a, **k: CoreResponse())
        monkeypatch.setattr(utils, "system_service_exists", lambda service: True)

        from wlanpi_webui.profiler import profiler as profiler_module

        monkeypatch.setattr(
            profiler_module, "system_service_running_state", lambda service: True
        )

        with client.session_transaction() as sess:
            csrf = sess["csrf_token"]
        resp = client.post(
            "/startprofiler",
            headers={"hx-request": "true", "Referer": "https://wlanpi.local/apps"},
            data={"csrf_token": csrf},
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/apps")


class TestAppsGrafanaCard:
    """The Apps card follows Grafana's web UI, not just systemd's active state."""

    POLL = b'hx-trigger="load delay:3s"'

    def _cards(self, client, monkeypatch, active, responding):
        _everything_installed(monkeypatch)
        _grafana(monkeypatch, active, responding)
        _login(client, monkeypatch)
        resp = client.get("/apps/cards")
        assert resp.status_code == 200
        return resp.data[resp.data.index(b'id="apps-grafana-card"') :]

    def test_running_offers_launch_and_stops_polling(self, client, monkeypatch):
        card = self._cards(client, monkeypatch, "active", True)
        assert b">Running<" in card
        assert b'data-action="launch-grafana"' in card
        assert b'hx-post="/stopgrafana"' in card
        assert self.POLL not in card

    def test_active_but_not_answering_is_starting(self, client, monkeypatch):
        card = self._cards(client, monkeypatch, "active", False)
        assert b">Starting<" in card
        assert b">Running<" not in card
        assert b'data-action="launch-grafana"' not in card
        assert b'hx-post="/stopgrafana"' in card
        assert self.POLL in card
        assert b'hx-select="#apps-grafana-card"' in card

    def test_activating_polls_without_toggle(self, client, monkeypatch):
        card = self._cards(client, monkeypatch, "activating", False)
        assert b">Starting<" in card
        assert b'hx-post="/startgrafana"' not in card
        assert b'data-action="launch-grafana"' not in card
        assert self.POLL in card

    def test_deactivating_polls(self, client, monkeypatch):
        card = self._cards(client, monkeypatch, "deactivating", False)
        assert b">Stopping<" in card
        assert self.POLL in card

    def test_stopped_offers_start_without_polling(self, client, monkeypatch):
        card = self._cards(client, monkeypatch, "inactive", False)
        assert b">Stopped<" in card
        assert b'hx-post="/startgrafana"' in card
        assert b'data-action="launch-grafana"' not in card
        assert self.POLL not in card

    @pytest.mark.parametrize(
        "package, shown", [("grafana", False), ("wlanpi-grafana", True)]
    )
    def test_card_keyed_on_wlanpi_grafana(self, client, monkeypatch, package, shown):
        _everything_installed(monkeypatch)
        monkeypatch.setattr(
            "wlanpi_webui.app.package_installed", lambda pkg: pkg == package
        )
        _login(client, monkeypatch)
        assert (b'hx-get="/grafana"' in client.get("/apps/cards").data) is shown


class TestGrafanaPage:
    def test_requires_login(self, client):
        assert client.get("/grafana").status_code == 302

    def test_lists_data_streams(self, client, monkeypatch):
        _everything_installed(monkeypatch)
        _login(client, monkeypatch)
        resp = client.get("/grafana")
        assert resp.status_code == 200
        assert b'hx-get="/grafana/service"' in resp.data
        assert b"Internet monitoring" in resp.data
        assert b"WLAN Pi health" in resp.data
        assert b'hx-post="/startgrafanainternet"' in resp.data

    def test_htmx_returns_partial(self, client, monkeypatch):
        _everything_installed(monkeypatch)
        _login(client, monkeypatch)
        resp = client.get("/grafana", headers={"hx-request": "true"})
        assert resp.status_code == 200
        assert b"<html" not in resp.data
        assert b"Data streams" in resp.data


class TestGrafanaServiceFragment:
    def _patch(self, monkeypatch, active, responding):
        from wlanpi_webui.grafana import grafana as g

        monkeypatch.setattr(g, "system_service_active_state", lambda *a, **kw: active)
        monkeypatch.setattr(g, "_grafana_responding", lambda *a, **kw: responding)

    def test_running_enables_launch(self, client, monkeypatch):
        self._patch(monkeypatch, "active", True)
        _login(client, monkeypatch)
        resp = client.get("/grafana/service")
        assert resp.status_code == 200
        assert b"Running" in resp.data
        assert b'href="/grafana_url"' in resp.data
        assert b'hx-post="/stopgrafana"' in resp.data

    def test_waiting_disables_launch(self, client, monkeypatch):
        self._patch(monkeypatch, "active", False)
        _login(client, monkeypatch)
        resp = client.get("/grafana/service")
        assert b">Starting<" in resp.data
        assert b"Waiting for Grafana to answer" in resp.data
        assert b"disabled" in resp.data
        assert b'href="/grafana_url"' not in resp.data

    def test_starting_hides_toggle(self, client, monkeypatch):
        self._patch(monkeypatch, "activating", False)
        _login(client, monkeypatch)
        resp = client.get("/grafana/service")
        assert b"Starting" in resp.data
        assert b'hx-post="/startgrafana"' not in resp.data
        assert b'hx-post="/stopgrafana"' not in resp.data

    def test_stopped_offers_start(self, client, monkeypatch):
        self._patch(monkeypatch, "inactive", False)
        _login(client, monkeypatch)
        resp = client.get("/grafana/service")
        assert b"Stopped" in resp.data
        assert b'hx-post="/startgrafana"' in resp.data
