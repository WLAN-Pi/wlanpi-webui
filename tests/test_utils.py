from unittest.mock import patch

from wlanpi_webui.utils import (
    get_safe_redirect_target,
    service_not_installed_warning,
    start_stop_service,
)


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


class TestServiceNotInstalled:
    @patch("wlanpi_webui.utils.system_service_exists")
    def test_start_uninstalled_service_returns_warning(self, mock_exists):
        mock_exists.return_value = False
        res = start_stop_service("start", "kismet")
        assert "Kismet is not installed" in res
        assert "wlanpiToast" in res

    @patch("wlanpi_webui.utils.system_service_exists")
    def test_start_uninstalled_grafana_returns_warning(self, mock_exists):
        mock_exists.return_value = False
        res = start_stop_service("start", "grafana-server")
        assert "Grafana is not installed" in res

    def test_service_not_installed_warning_formatting(self):
        res = service_not_installed_warning("wlanpi-profiler")
        assert "Profiler is not installed" in res


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
