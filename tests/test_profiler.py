"""Tests for the profiler client capabilities page."""

import json
import os
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
def profiler_root(tmp_path, monkeypatch):
    root = tmp_path / "profiler"
    (root / "clients").mkdir(parents=True)
    monkeypatch.setattr(
        "wlanpi_webui.config.Config.SESSION_KEY_PATH", str(tmp_path / "session_key")
    )
    monkeypatch.setattr("wlanpi_webui.config.Config.PROFILER_DIR", f"{root}/")
    monkeypatch.setattr("wlanpi_webui.config.Config.FILES_ROOT_DIR", f"{tmp_path}/")
    monkeypatch.setattr(
        "wlanpi_webui.config.Config.PROFILER_STATUS_PATH", str(tmp_path / "status.json")
    )
    monkeypatch.setattr(
        "wlanpi_webui.config.Config.PROFILER_INFO_PATH", str(tmp_path / "info.json")
    )
    monkeypatch.setattr(
        "wlanpi_webui.config.Config.PROFILER_LAST_SESSION_PATH",
        str(tmp_path / "last-session.json"),
    )
    return root


@pytest.fixture()
def app(profiler_root, monkeypatch):
    # The shell route checks the service; keep tests off systemctl.
    monkeypatch.setattr(
        "wlanpi_webui.profiler.profiler.system_service_running_state",
        lambda service, quiet=False: False,
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


def _write_profile(root, mac, band, chipset, features, mtime):
    dashed = mac.replace(":", "-")
    client_dir = root / "clients" / dashed
    client_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "mac": mac,
        "is_laa": False,
        "manuf": "Test Vendor",
        "chipset": chipset,
        "capture_ssid": "Wi-Co",
        "capture_bssid": "98:8f:00:ee:2d:30",
        "capture_band": band,
        "capture_channel": 36,
        "features": features,
        "pcapng": "AAAA",
        "schema_version": 2,
        "profiler_version": "2.0.1",
        "capture_source": "profiler",
    }
    json_path = client_dir / f"{dashed}_{band}GHz.json"
    json_path.write_text(json.dumps(data))
    (client_dir / f"{dashed}_{band}GHz.txt").write_text("Client MAC: " + mac)
    (client_dir / f"{dashed}_{band}GHz.pcap").write_bytes(b"\x00")
    os.utime(json_path, (mtime, mtime))
    return json_path


class TestProfilerService:
    def test_shows_start_when_stopped(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/profiler/profiles")
        assert resp.status_code == 200
        assert b"Stopped" in resp.data
        assert b"Start the profiler to begin capturing." in resp.data
        assert b'hx-post="/startprofiler"' in resp.data
        assert b"X-CSRF-Token" in resp.data
        assert b"dropdown" not in resp.data

    def test_shows_starting_when_not_confirmed_up(self, client, monkeypatch):
        monkeypatch.setattr(
            "wlanpi_webui.profiler.profiler.system_service_running_state",
            lambda service, quiet=False: True,
        )
        _login(client, monkeypatch)
        resp = client.get("/profiler/profiles")
        assert resp.status_code == 200
        assert b"Profiler is starting..." in resp.data
        assert b"up and ready" not in resp.data

    def test_shows_up_when_running(self, client, monkeypatch, profiler_root):
        _write_session(
            profiler_root,
            {"state": "running"},
            {"ssid": "Profiler 573", "passphrase": "profiler"},
        )
        monkeypatch.setattr(
            "wlanpi_webui.profiler.profiler.system_service_running_state",
            lambda service, quiet=False: True,
        )
        _login(client, monkeypatch)
        resp = client.get("/profiler/profiles")
        assert resp.status_code == 200
        assert b"Profiler is up and ready to capture association requests." in resp.data
        assert b'hx-post="/stopprofiler"' in resp.data


def _write_session(root, status, info, last=None):
    tmp = root.parent
    (tmp / "status.json").write_text(json.dumps(status))
    (tmp / "info.json").write_text(json.dumps(info))
    if last is not None:
        (tmp / "last-session.json").write_text(json.dumps(last))


class TestProfilerSession:
    def test_live_session(self, client, monkeypatch, profiler_root):
        _write_session(
            profiler_root,
            {"state": "running", "reason": "startup_complete", "pid": 1},
            {
                "schema_version": "1.0",
                "profiler_version": "2.0.1",
                "phy": "phy0",
                "interfaces": {"ap": "wlan0", "monitor": "wlan0profiler"},
                "channel": 36,
                "frequency": 5180,
                "country_code": "US",
                "ssid": "Profiler 573",
                "bssid": "e8:bf:b8:73:9a:47",
                "mode": "hostapd",
                "passphrase": "profiler",
                "started_at": "2026-09-21T15:50:35.523900+00:00",
                "uptime_seconds": 70,
                "profile_count": 2,
                "failed_profile_count": 1,
                "total_clients_seen": 18,
                "invalid_frame_count": 0,
                "bad_fcs_count": 0,
                "last_profile": None,
                "last_profile_timestamp": None,
            },
        )
        _login(client, monkeypatch)
        resp = client.get("/profiler/session")
        assert resp.status_code == 200
        assert b"Running" in resp.data
        assert b"Profiler 573" in resp.data
        assert b"1m 10s" in resp.data
        assert b"phy0" in resp.data

    def test_last_session_when_stopped(self, client, monkeypatch, profiler_root):
        _write_session(
            profiler_root,
            {"state": "stopped"},
            {},
            last={
                "schema_version": "1.0",
                "session": {
                    "started_at": "2026-09-19T08:30:00+00:00",
                    "ended_at": "2026-09-19T08:35:00+00:00",
                    "duration_seconds": 300,
                },
                "exit": {
                    "status": "failed",
                    "code": 1,
                    "reason": "hostapd_crashed",
                    "message": "hostapd process exited with code 1",
                },
                "configuration": {
                    "mode": "hostapd",
                    "channel": 36,
                    "frequency": 5180,
                    "ssid": "Profiler 573",
                },
                "metrics": {
                    "profile_count": 3,
                    "failed_profile_count": 0,
                    "total_clients_seen": 5,
                    "last_profile": "aa:bb:cc:dd:ee:ff",
                },
            },
        )
        _login(client, monkeypatch)
        resp = client.get("/profiler/session")
        assert resp.status_code == 200
        assert b"Failed" in resp.data
        assert b"hostapd_crashed" in resp.data
        assert b"5m 0s" in resp.data

    def test_no_session(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/profiler/session")
        assert resp.status_code == 200
        assert b"No profiler session recorded yet" in resp.data

    def test_poll_updates_service_bar(self, client, monkeypatch, profiler_root):
        _write_session(
            profiler_root,
            {"state": "running"},
            {"ssid": "Profiler 573", "passphrase": "profiler"},
        )
        monkeypatch.setattr(
            "wlanpi_webui.profiler.profiler.system_service_running_state",
            lambda service, quiet=False: True,
        )
        _login(client, monkeypatch)
        resp = client.get("/profiler/session")
        assert resp.status_code == 200
        assert b'hx-swap-oob="true"' in resp.data
        assert b"Profiler is up and ready to capture association requests." in resp.data

    def test_poll_shows_starting_before_up(self, client, monkeypatch, profiler_root):
        monkeypatch.setattr(
            "wlanpi_webui.profiler.profiler.system_service_running_state",
            lambda service, quiet=False: True,
        )
        _login(client, monkeypatch)
        resp = client.get("/profiler/session")
        assert resp.status_code == 200
        assert b"Profiler is starting..." in resp.data
        assert b"up and ready" not in resp.data

    def test_poll_carries_new_profile_marker(self, client, monkeypatch, profiler_root):
        _write_session(
            profiler_root,
            {"state": "running"},
            {
                "ssid": "Profiler 573",
                "passphrase": "profiler",
                "profile_count": 2,
                "last_profile": "aa:bb:cc:dd:ee:ff",
            },
        )
        _login(client, monkeypatch)
        resp = client.get("/profiler/session")
        assert resp.status_code == 200
        assert b'id="profiler-session-events"' in resp.data
        assert b'data-profile-count="2"' in resp.data
        assert b'data-last-profile="aa:bb:cc:dd:ee:ff"' in resp.data

    def test_shell_renders_qr_when_running(self, client, monkeypatch, profiler_root):
        _write_session(
            profiler_root,
            {"state": "running"},
            {"ssid": "Profiler 573", "passphrase": "profiler"},
        )
        monkeypatch.setattr(
            "wlanpi_webui.profiler.profiler.system_service_running_state",
            lambda service, quiet=False: True,
        )
        _login(client, monkeypatch)
        resp = client.get("/profiler/profiles")
        assert resp.status_code == 200
        assert b"WIFI:S:Profiler 573;T:WPA;P:profiler;;" in resp.data
        assert b"profiler-qr" in resp.data


class TestProfilerCapabilities:
    def test_requires_login(self, client):
        assert client.get("/profiler/profiles").status_code == 302

    def test_shell_lazy_loads_capabilities(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/profiler/profiles")
        assert resp.status_code == 200
        assert b'hx-get="/profiler/capabilities"' in resp.data

    def test_empty_state(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/profiler/capabilities")
        assert resp.status_code == 200
        assert b"No client profiles found" in resp.data

    def test_shell_renders_session_reports(self, client, monkeypatch, profiler_root):
        reports_dir = profiler_root / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "profiler-2026-09-21.csv").write_text("mac,band\n")
        _login(client, monkeypatch)
        resp = client.get("/profiler/profiles")
        assert resp.status_code == 200
        assert b"Session reports" in resp.data
        assert b"2026-09-21" in resp.data

    def test_renders_capabilities(self, client, monkeypatch, profiler_root):
        _write_profile(
            profiler_root,
            "2e:3d:0c:6f:cb:49",
            "5",
            "Broadcom",
            {
                "dot11be": 1,
                "dot11be_mle": 1,
                "dot11be_mle_emlsr_support": 0,
                "dot11be_320mhz": -1,
                "dot11r": 1,
            },
            1_700_000_000,
        )
        _login(client, monkeypatch)
        resp = client.get("/profiler/capabilities")
        assert resp.status_code == 200
        assert b"2e:3d:0c:6f:cb:49" in resp.data
        assert b"Broadcom" in resp.data
        assert b"Wi-Fi 7 (11be)" in resp.data
        assert b"11be MLE" in resp.data
        assert b"cap-yes" in resp.data
        assert b"cap-no" in resp.data
        assert b"cap-na" in resp.data

    def test_rows_carry_mac_for_highlight(self, client, monkeypatch, profiler_root):
        _write_profile(
            profiler_root,
            "2e:3d:0c:6f:cb:49",
            "5",
            "Broadcom",
            {"dot11be": 1},
            1_700_000_000,
        )
        _login(client, monkeypatch)
        resp = client.get("/profiler/capabilities")
        assert b'data-mac="2e:3d:0c:6f:cb:49"' in resp.data

    def test_sort_orders_rows(self, client, monkeypatch, profiler_root):
        _write_profile(
            profiler_root,
            "2e:3d:0c:6f:cb:49",
            "5",
            "Broadcom",
            {"dot11be": 1},
            1_700_000_000,
        )
        _write_profile(
            profiler_root,
            "24:eb:16:35:d4:f5",
            "6",
            "Intel",
            {"dot11be": 0},
            1_700_000_001,
        )
        _login(client, monkeypatch)
        ascending = client.get("/profiler/capabilities?sort=dot11be&dir=asc").data
        descending = client.get("/profiler/capabilities?sort=dot11be&dir=desc").data
        first = b"2e:3d:0c:6f:cb:49"
        second = b"24:eb:16:35:d4:f5"
        assert ascending.index(second) < ascending.index(first)
        assert descending.index(first) < descending.index(second)

    def test_filter(self, client, monkeypatch, profiler_root):
        _write_profile(
            profiler_root,
            "2e:3d:0c:6f:cb:49",
            "5",
            "Broadcom",
            {"dot11be": 1},
            1_700_000_000,
        )
        _write_profile(
            profiler_root,
            "24:eb:16:35:d4:f5",
            "6",
            "Intel",
            {"dot11be": 0},
            1_700_000_001,
        )
        _login(client, monkeypatch)
        resp = client.get("/profiler/capabilities?filter=intel")
        assert b"Intel" in resp.data
        assert b"Broadcom" not in resp.data

    def test_report_modal(self, client, monkeypatch, profiler_root):
        _write_profile(
            profiler_root,
            "2e:3d:0c:6f:cb:49",
            "5",
            "Broadcom",
            {"dot11be": 1},
            1_700_000_000,
        )
        _login(client, monkeypatch)
        resp = client.get(
            "/profiler/profile?profile=2e-3d-0c-6f-cb-49_5GHz",
            headers={"hx-request": "true"},
        )
        assert resp.status_code == 200
        assert b"Client MAC: 2e:3d:0c:6f:cb:49" in resp.data


class HTTPErrorResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def _csrf(client):
    with client.session_transaction() as sess:
        return sess["csrf_token"]


class TestProfilerPurge:
    PROFILES = "https://wlanpi.local/profiler/profiles"

    def _core(self, monkeypatch, result):
        """Stand in for wlanpi-core: a payload, an HTTP status, or an exception."""
        import requests

        calls = []

        def fake(method, url, **kwargs):
            calls.append((method, url))
            if isinstance(result, Exception):
                raise result
            if isinstance(result, int):
                raise requests.HTTPError(response=HTTPErrorResponse(result))
            return FakeResponse(result)

        monkeypatch.setattr("wlanpi_webui.profiler.profiler.make_api_request", fake)
        return calls

    def _purge(self, client, csrf=True):
        data = {"csrf_token": _csrf(client)} if csrf else {}
        return client.post(
            "/profiler/purge",
            data=data,
            headers={"hx-request": "true", "Referer": self.PROFILES},
        )

    def _toast(self, client):
        with client.session_transaction() as sess:
            return sess["wlanpi_toast"]

    def test_button_posts_with_csrf_and_confirm(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/profiler/profiles")
        assert b'hx-post="/profiler/purge"' in resp.data
        assert b'hx-get="/profiler/purge"' not in resp.data
        assert (
            b'hx-confirm="Delete all profiler reports and captures? '
            b'This cannot be undone."' in resp.data
        )
        token = _csrf(client).encode()
        assert b'name="csrf_token" value="' + token + b'"' in resp.data

    def test_rejects_missing_csrf(self, client, monkeypatch):
        _login(client, monkeypatch)
        calls = self._core(monkeypatch, {"files": 1, "bytes": 1})
        assert self._purge(client, csrf=False).status_code == 400
        assert calls == []

    def test_get_does_not_purge(self, client, monkeypatch, profiler_root):
        (profiler_root / "reports").mkdir()
        (profiler_root / "reports" / "r.csv").write_text("x")
        _login(client, monkeypatch)
        calls = self._core(monkeypatch, {"files": 1, "bytes": 1})
        assert client.get("/profiler/purge").status_code == 404
        assert calls == []
        assert (profiler_root / "reports" / "r.csv").exists()

    def test_success_shows_counts_and_refreshes(self, client, monkeypatch):
        _login(client, monkeypatch)
        calls = self._core(monkeypatch, {"files": 12, "bytes": 3_500_000})
        resp = self._purge(client)
        assert calls == [("POST", "https://127.0.0.1:31415/api/v1/profiler/purge")]
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profiler/profiles")
        assert self._toast(client) == {
            "message": "Removed 12 files (3.50 MB).",
            "status": "success",
        }

    def test_running_profiler_says_stop_first(self, client, monkeypatch):
        _login(client, monkeypatch)
        self._core(monkeypatch, 409)
        resp = self._purge(client)
        assert resp.status_code == 302
        assert self._toast(client)["message"] == "Stop the profiler before purging."

    @pytest.mark.parametrize("status", [404, 405])
    def test_old_core_falls_back_to_rm_listing(
        self, client, monkeypatch, profiler_root, status
    ):
        (profiler_root / "clients" / "x.pcap").write_bytes(b"\x00")
        _login(client, monkeypatch)
        self._core(monkeypatch, status)
        resp = self._purge(client)
        assert resp.status_code == 200
        assert b"open a root shell" in resp.data
        assert f"rm {profiler_root}/clients/x.pcap".encode() in resp.data

    def test_core_down(self, client, monkeypatch):
        import requests

        _login(client, monkeypatch)
        self._core(monkeypatch, requests.ConnectionError("refused"))
        resp = self._purge(client)
        assert resp.status_code == 302
        assert self._toast(client) == {
            "message": "wlanpi-core is not running.",
            "status": "danger",
        }

    def test_core_error_status(self, client, monkeypatch):
        _login(client, monkeypatch)
        self._core(monkeypatch, 500)
        self._purge(client)
        assert self._toast(client)["message"] == "Could not purge profiler data."
