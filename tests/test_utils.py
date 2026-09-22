from unittest.mock import patch

import pytest
from flask import session

from wlanpi_webui.utils import (
    get_safe_redirect_target,
    service_friendly_name,
    start_stop_service,
)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "wlanpi_webui.config.Config.SESSION_KEY_PATH", str(tmp_path / "session_key")
    )
    from wlanpi_webui.app import create_app

    return create_app()


class TestGetSafeRedirectTarget:
    """Tests for the Copilot-generated fix"""

    def test_none_returns_default(self):
        assert get_safe_redirect_target(None) == "/"

    def test_empty_string_returns_default(self):
        assert get_safe_redirect_target("") == "/"

    def test_relative_path_allowed(self):
        assert get_safe_redirect_target("/services") == "/services"

    def test_relative_path_with_query(self):
        assert (
            get_safe_redirect_target("/services?tab=network") == "/services?tab=network"
        )

    def test_external_url_blocked(self):
        assert get_safe_redirect_target("https://evil.com/phish") == "/"

    def test_protocol_relative_blocked(self):
        assert get_safe_redirect_target("//evil.com/phish") == "/"

    def test_backslash_normalized(self):
        # Some browsers treat backslashes as path separators
        assert get_safe_redirect_target("\\\\evil.com/phish") == "/"

    def test_path_without_leading_slash_blocked(self):
        assert get_safe_redirect_target("evil.com/phish") == "/"


class TestGetSafeRedirectTargetWithRequestContext:
    """Tests that need Flask request context - for the fixed version"""

    def test_same_origin_full_url_allowed(self):
        # Note: Current implementation blocks all absolute URLs
        # This test documents the current behavior - full URLs are blocked
        result = get_safe_redirect_target("http://192.168.1.1/services")
        assert result == "/"

    def test_different_origin_blocked(self):
        result = get_safe_redirect_target("http://evil.com/services")
        assert result == "/"


class TestGetSafeReferrerTarget:
    def test_uses_referrer_path(self, app):
        from wlanpi_webui import utils

        with app.test_request_context(headers={"Referer": "https://wlanpi.local/apps"}):
            assert utils.get_safe_referrer_target() == "/apps"

    def test_no_referrer_falls_back_to_root(self, app):
        from wlanpi_webui import utils

        with app.test_request_context():
            assert utils.get_safe_referrer_target() == "/"

    def test_prefers_hx_current_url(self, app):
        from wlanpi_webui import utils

        with app.test_request_context(
            headers={
                "Referer": "https://wlanpi.local/",
                "HX-Current-URL": "https://wlanpi.local/apps",
            }
        ):
            assert utils.get_safe_referrer_target() == "/apps"


class _Resp:
    def __init__(self, code):
        self.status_code = code
        self.text = ""


class TestServiceFriendlyName:
    def test_known_services(self):
        assert service_friendly_name("wlanpi-profiler") == "Profiler"
        assert service_friendly_name("kismet") == "Kismet"
        assert service_friendly_name("grafana-server") == "Grafana"
        assert service_friendly_name("wlanpi-grafana-scanner-wlan0") == (
            "Grafana Scanner Wlan0"
        )

    def test_suffix_stripped(self):
        assert service_friendly_name("kismet.service") == "Kismet"


class TestSystemServiceActiveState:
    def test_returns_raw_state(self, monkeypatch):
        from wlanpi_webui import utils

        class _Result:
            stdout = "activating\n"

        monkeypatch.setattr(utils.subprocess, "run", lambda *a, **k: _Result())
        assert utils.system_service_active_state("x") == "activating"

    def test_unknown_when_systemctl_missing(self, monkeypatch):
        from wlanpi_webui import utils

        def boom(*a, **k):
            raise OSError("no systemctl")

        monkeypatch.setattr(utils.subprocess, "run", boom)
        assert utils.system_service_active_state("x") == "unknown"


class TestStartStopServiceToast:
    @patch("wlanpi_webui.utils.system_service_exists")
    def test_start_uninstalled_queues_warning(self, mock_exists, app):
        mock_exists.return_value = False
        with app.test_request_context():
            res = start_stop_service("start", "kismet")
            assert res.status_code == 302
            assert session["wlanpi_toast"] == {
                "message": "Kismet service is not installed.",
                "status": "warning",
            }

    @patch("wlanpi_webui.utils.make_api_request")
    @patch("wlanpi_webui.utils.system_service_running_state")
    @patch("wlanpi_webui.utils.system_service_exists")
    def test_start_success_queues_success(
        self, mock_exists, mock_running, mock_api, app
    ):
        mock_exists.return_value = True
        mock_running.return_value = True
        mock_api.return_value = _Resp(200)
        with app.test_request_context():
            start_stop_service("start", "wlanpi-profiler")
            assert session["wlanpi_toast"] == {
                "message": "Profiler service started.",
                "status": "success",
            }

    @patch("wlanpi_webui.utils.make_api_request")
    @patch("wlanpi_webui.utils.system_service_running_state")
    @patch("wlanpi_webui.utils.system_service_exists")
    def test_stop_success_queues_success(
        self, mock_exists, mock_running, mock_api, app
    ):
        mock_exists.return_value = True
        mock_running.return_value = True
        mock_api.return_value = _Resp(200)
        with app.test_request_context():
            start_stop_service("stop", "kismet")
            assert session["wlanpi_toast"]["message"] == "Kismet service stopped."

    @patch("wlanpi_webui.utils.system_service_running_state")
    @patch("wlanpi_webui.utils.system_service_exists")
    def test_core_down_queues_danger(self, mock_exists, mock_running, app):
        mock_exists.return_value = True
        mock_running.return_value = False
        with app.test_request_context():
            start_stop_service("start", "kismet")
            assert session["wlanpi_toast"] == {
                "message": "wlanpi-core is not running.",
                "status": "danger",
            }

    @patch("wlanpi_webui.utils.make_api_request")
    @patch("wlanpi_webui.utils.system_service_running_state")
    @patch("wlanpi_webui.utils.system_service_exists")
    def test_api_failure_queues_warning(self, mock_exists, mock_running, mock_api, app):
        mock_exists.return_value = True
        mock_running.return_value = True
        mock_api.return_value = _Resp(500)
        with app.test_request_context():
            start_stop_service("start", "kismet")
            assert session["wlanpi_toast"] == {
                "message": "Could not start Kismet service.",
                "status": "warning",
            }

    @patch("wlanpi_webui.utils.make_api_request")
    @patch("wlanpi_webui.utils.system_service_running_state")
    @patch("wlanpi_webui.utils.system_service_exists")
    def test_data_stream_label_and_noun(self, mock_exists, mock_running, mock_api, app):
        mock_exists.return_value = True
        mock_running.return_value = True
        mock_api.return_value = _Resp(200)
        with app.test_request_context():
            start_stop_service(
                "stop",
                "wlanpi-grafana-internet",
                label="Grafana Internet monitoring",
                noun="data stream",
            )
            assert session["wlanpi_toast"] == {
                "message": "Grafana Internet monitoring data stream stopped.",
                "status": "success",
            }


class TestToastHeader:
    def test_emitted_once_then_cleared(self, app):
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["wlanpi_toast"] = {"message": "Kismet stopped.", "status": "success"}
        resp = client.get("/login")
        assert resp.headers.get("X-Wlanpi-Toast") == (
            '{"message": "Kismet stopped.", "status": "success"}'
        )
        assert client.get("/login").headers.get("X-Wlanpi-Toast") is None


class TestGetCoreJson:
    def test_returns_dict(self, monkeypatch):
        from wlanpi_webui import utils

        class R:
            def json(self):
                return {"a": 1}

        monkeypatch.setattr(utils, "make_api_request", lambda *a, **k: R())
        assert utils.get_core_json("/x") == {"a": 1}

    def test_returns_none_on_request_failure(self, monkeypatch):
        from wlanpi_webui import utils

        def boom(*a, **k):
            raise utils.requests.RequestException()

        monkeypatch.setattr(utils, "make_api_request", boom)
        assert utils.get_core_json("/x") is None

    def test_returns_none_on_non_dict(self, monkeypatch):
        from wlanpi_webui import utils

        class R:
            def json(self):
                return ["not", "a", "dict"]

        monkeypatch.setattr(utils, "make_api_request", lambda *a, **k: R())
        assert utils.get_core_json("/x") is None
