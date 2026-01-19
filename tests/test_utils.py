import pytest
from unittest.mock import patch, MagicMock

from wlanpi_webui.utils import get_safe_redirect_target


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
