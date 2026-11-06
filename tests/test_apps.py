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

    monkeypatch.setattr(apps_module, "system_service_state", lambda unit: "running")

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
        assert b'href="/cockpit"' in resp.data
        assert b'href="/grafana"' in resp.data
        # Grafana is the last card, after Cockpit
        assert resp.data.index(b"Grafana") > resp.data.index(b"Cockpit")
        # data streams moved to their own page
        assert b"Internet monitoring" not in resp.data

    def test_profiler_cli_run_disables_start(self, client, monkeypatch):
        _everything_installed(monkeypatch)
        from wlanpi_webui.apps import apps as apps_module

        monkeypatch.setattr(
            apps_module,
            "system_service_state",
            lambda unit: "stopped" if unit == "wlanpi-profiler" else "running",
        )
        monkeypatch.setattr(
            apps_module,
            "get_profiler_session",
            lambda running: {"up": True, "state": "running"},
        )
        _login(client, monkeypatch)
        resp = client.get("/apps/cards")
        assert resp.status_code == 200
        assert b"Profiler is running from the command line" in resp.data
        assert b'hx-post="/startprofiler"' not in resp.data
        card = resp.data.split(b'id="apps-profiler-card"')[1].split(b"</a>")[0]
        assert b'app-status is-on">Running' in card
        assert b'type="button" disabled' in card
        assert b"uk-button-primary" in card

    def test_profiler_cli_run_starting_keeps_polling(self, client, monkeypatch):
        _everything_installed(monkeypatch)
        from wlanpi_webui.apps import apps as apps_module

        monkeypatch.setattr(
            apps_module,
            "system_service_state",
            lambda unit: "stopped" if unit == "wlanpi-profiler" else "running",
        )
        monkeypatch.setattr(
            apps_module,
            "get_profiler_session",
            lambda running: {"up": True, "state": "starting"},
        )
        _login(client, monkeypatch)
        resp = client.get("/apps/cards")
        assert resp.status_code == 200
        card = resp.data.split(b'id="apps-profiler-card"')[1].split(
            b"</div>\n    </div>"
        )[0]
        assert b'app-status is-warn">Starting' in card
        assert b'hx-select="#apps-profiler-card"' in card
        assert b'type="button" disabled' in card

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
        monkeypatch.setattr(utils, "system_service_state", lambda service: "running")

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


class TestAppsServiceCards:
    POLL = b'hx-select="#apps-kismet-card"'

    def _kismet_card(self, client, monkeypatch, state):
        _everything_installed(monkeypatch)
        from wlanpi_webui.apps import apps as apps_module

        monkeypatch.setattr(apps_module, "system_service_state", lambda unit: state)
        _login(client, monkeypatch)
        resp = client.get("/apps/cards")
        assert resp.status_code == 200
        start = resp.data.index(b'id="apps-kismet-card"')
        return resp.data[start : resp.data.index(b"Cockpit", start)]

    @pytest.mark.parametrize(
        "state, label", [("starting", b"Starting"), ("stopping", b"Stopping")]
    )
    def test_transition_disables_toggle_and_polls(
        self, client, monkeypatch, state, label
    ):
        card = self._kismet_card(client, monkeypatch, state)
        assert b">" + label + b"<" in card
        assert b"disabled>" + label + "…".encode() + b"</button>" in card
        assert b"hx-post=" not in card
        assert self.POLL in card

    def test_failed_shows_failed_and_offers_start(self, client, monkeypatch):
        card = self._kismet_card(client, monkeypatch, "failed")
        assert b'class="app-status is-bad">Failed<' in card
        assert b'hx-post="/startkismet"' in card
        assert self.POLL not in card

    def test_toggle_disables_itself_while_in_flight(self, client, monkeypatch):
        card = self._kismet_card(client, monkeypatch, "running")
        assert b'hx-post="/stopkismet"' in card
        assert b'hx-disable="this"' in card


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
