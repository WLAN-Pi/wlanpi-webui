"""Tests for the System page facts and diagnostics, sourced from wlanpi-core."""

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


def _device_info(**overrides):
    info = {
        "model": "R4",
        "name": "wlanpi-x",
        "hostname": "wlanpi-x.local",
        "software_version": "3.2.0",
        "mode": "classic",
    }
    info.update(overrides)
    return info


class TestSystemFacts:
    def _patch(self, monkeypatch, info, stats, battery):
        from wlanpi_webui.system import system as s

        payloads = {
            "/api/v1/system/device/info": info,
            "/api/v1/system/device/stats": stats,
            "/api/v1/system/battery": battery,
        }
        monkeypatch.setattr(
            s, "get_core_json", lambda path, params=None: payloads.get(path, {})
        )
        monkeypatch.setattr(s, "system_service_running_state", lambda *a, **k: True)
        monkeypatch.setattr(s, "get_apt_package_version", lambda p: "2.2.0-1")

    def test_facts_come_from_core(self, client, monkeypatch):
        self._patch(
            monkeypatch,
            _device_info(),
            {"ip": "10.0.0.5", "cpu": "23%", "cpu_temp": "52.0C"},
            {"present": False},
        )
        _login(client, monkeypatch)
        resp = client.get("/system/card/facts")
        assert resp.status_code == 200
        assert b"R4" in resp.data
        assert b"wlanpi-x" in resp.data
        assert b"10.0.0.5" in resp.data
        assert b"3.2.0" in resp.data

    def test_battery_not_detected(self, client, monkeypatch):
        self._patch(monkeypatch, _device_info(), {"ip": "10.0.0.5"}, {"present": False})
        _login(client, monkeypatch)
        resp = client.get("/system/card/facts")
        assert b"Not detected" in resp.data

    def test_battery_present(self, client, monkeypatch):
        self._patch(
            monkeypatch,
            _device_info(),
            {"ip": "10.0.0.5"},
            {"present": True, "capacity_percent": 85, "status": "Discharging"},
        )
        _login(client, monkeypatch)
        resp = client.get("/system/card/facts")
        assert b"85% (Discharging)" in resp.data

    def test_battery_unknown_when_core_silent(self, client, monkeypatch):
        self._patch(monkeypatch, _device_info(), {"ip": "10.0.0.5"}, None)
        _login(client, monkeypatch)
        resp = client.get("/system/card/facts")
        assert b"Unknown" in resp.data
        assert b"Not detected" not in resp.data

    def test_wlan_management_shown(self, client, monkeypatch):
        self._patch(
            monkeypatch,
            _device_info(wlan_management="manual"),
            {"ip": "10.0.0.5"},
            {"present": False},
        )
        _login(client, monkeypatch)
        resp = client.get("/system/card/facts")
        assert b"Wi-Fi mgmt" in resp.data
        assert b"manual" in resp.data


class TestSystemDiag:
    def _patch(self, monkeypatch):
        from wlanpi_webui.system import system as s

        payloads = {
            "/api/v1/utils/usb": {"interfaces": ["Bus 001 Device 002: id 1234:5678"]},
            "/api/v1/utils/pci": {
                "devices": [
                    {"pci_id": "01:00.0", "description": "Network controller: test"}
                ]
            },
        }
        monkeypatch.setattr(
            s, "get_core_json", lambda path, params=None: payloads.get(path, {})
        )

    def test_usb_card(self, client, monkeypatch):
        self._patch(monkeypatch)
        _login(client, monkeypatch)
        resp = client.get("/system/card/usb")
        assert resp.status_code == 200
        assert b"Bus 001 Device 002" in resp.data

    def test_pci_card(self, client, monkeypatch):
        self._patch(monkeypatch)
        _login(client, monkeypatch)
        resp = client.get("/system/card/pci")
        assert resp.status_code == 200
        assert b"01:00.0 Network controller: test" in resp.data

    def test_unknown_card_is_404(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.get("/system/card/nope").status_code == 404

    def test_shell_has_card_hooks(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/system")
        # Resource usage loads lazily (header included) from /stream/stats.
        assert b"system-health" in resp.data
        assert b'hx-get="/stream/stats"' in resp.data
        for card in (
            b"status",
            b"temperatures",
            b"radios",
            b"facts",
            b"usb",
            b"pci",
            b"bluetooth",
        ):
            assert b"/system/card/" + card in resp.data
        assert b"Device Health" not in resp.data
        # System facts is the first card.
        assert resp.data.index(b"/system/card/facts") < resp.data.index(
            b"/system/card/status"
        )


class TestSystemHealth:
    def _patch(self, monkeypatch):
        from wlanpi_webui.system import system as s

        payloads = {
            "/api/v1/system/health": {
                "throttled": {
                    "raw": "throttled=0x0",
                    "undervoltage": False,
                    "frequency_capped": False,
                    "throttled": False,
                    "soft_temperature_limit": False,
                    "undervoltage_occurred": False,
                    "frequency_capped_occurred": False,
                    "throttled_occurred": False,
                    "soft_temperature_limit_occurred": False,
                },
                "temperatures": [
                    {"name": "cpu_thermal", "label": None, "celsius": 63.3}
                ],
                "ntp": {"enabled": True, "synchronized": False},
                "load": {"one": 1.48, "five": 0.6, "fifteen": 0.44},
                "swap": {"used_mb": 103, "total_mb": 2047},
                "rfkill": [
                    {
                        "name": "phy0",
                        "type": "wlan",
                        "soft_blocked": False,
                        "hard_blocked": False,
                    }
                ],
            },
        }
        monkeypatch.setattr(
            s, "get_core_json", lambda path, params=None: payloads.get(path, {})
        )

    def test_status_card(self, client, monkeypatch):
        self._patch(monkeypatch)
        _login(client, monkeypatch)
        resp = client.get("/system/card/status")
        assert resp.status_code == 200
        assert b"Device status" in resp.data
        assert b"No throttling" in resp.data
        assert b"Enabled, not synchronised" in resp.data
        assert b"bt-agent.service" not in resp.data

    def test_temperatures_card(self, client, monkeypatch):
        self._patch(monkeypatch)
        _login(client, monkeypatch)
        resp = client.get("/system/card/temperatures")
        assert resp.status_code == 200
        assert b"cpu_thermal: 63.3" in resp.data

    def test_radios_card(self, client, monkeypatch):
        self._patch(monkeypatch)
        _login(client, monkeypatch)
        resp = client.get("/system/card/radios")
        assert resp.status_code == 200
        assert b"phy0 (wlan)" in resp.data

    def test_health_unavailable(self, client, monkeypatch):
        from wlanpi_webui.system import system as s

        monkeypatch.setattr(s, "get_core_json", lambda *a, **k: None)
        _login(client, monkeypatch)
        resp = client.get("/system/card/status")
        assert b"Requires wlanpi-core 2.3.0" in resp.data

    def test_core_down_usb(self, client, monkeypatch):
        from wlanpi_webui.system import system as s

        monkeypatch.setattr(s, "get_core_json", lambda *a, **k: None)
        monkeypatch.setattr(
            "wlanpi_webui.app.system_service_running_state", lambda *a, **k: False
        )
        _login(client, monkeypatch)
        resp = client.get("/system/card/usb")
        assert b"wlanpi-core isn't running" in resp.data
        assert b"No USB interfaces detected" not in resp.data


class TestStreamStats:
    def test_stats_from_core(self, client, monkeypatch):
        from wlanpi_webui.stream import stream as st

        monkeypatch.setattr(
            st,
            "get_core_json",
            lambda path, params=None: {
                "cpu": "5%",
                "ram": "1024/2048MB 50%",
                "disk": "6/59GB 11%",
                "cpu_temp": "50.0C",
                "uptime": "1h",
            },
        )
        _login(client, monkeypatch)
        resp = client.get("/stream/stats", headers={"hx-request": "true"})
        assert resp.status_code == 200
        assert b"5% 50.0C" in resp.data
        assert b"1h" in resp.data

    def test_stats_unavailable_when_core_down(self, client, monkeypatch):
        from wlanpi_webui.stream import stream as st

        monkeypatch.setattr(st, "get_core_json", lambda *a, **k: None)
        monkeypatch.setattr(
            "wlanpi_webui.app.system_service_running_state", lambda *a, **k: False
        )
        _login(client, monkeypatch)
        resp = client.get("/stream/stats", headers={"hx-request": "true"})
        assert resp.status_code == 200
        assert b"wlanpi-core isn't running" in resp.data
        assert b"Unavailable" not in resp.data

    def test_stats_unavailable_when_api_empty(self, client, monkeypatch):
        from wlanpi_webui.stream import stream as st

        monkeypatch.setattr(st, "get_core_json", lambda *a, **k: None)
        _login(client, monkeypatch)
        resp = client.get("/stream/stats", headers={"hx-request": "true"})
        assert b"Unavailable" in resp.data


class TestSystemNtp:
    def _patch(self, monkeypatch, ntp):
        from wlanpi_webui.system import system as s

        monkeypatch.setattr(
            s,
            "get_core_json",
            lambda path, params=None: ntp if path.endswith("/ntp") else {},
        )

    def test_ntp_card_synced(self, client, monkeypatch):
        self._patch(
            monkeypatch,
            {
                "synchronized": True,
                "ntp_service": True,
                "server_name": "192.168.2.123",
                "server_address": "192.168.2.123",
                "fallback_servers": ["0.debian.pool.ntp.org"],
                "poll_interval": "32s",
                "source": "dhcp",
            },
        )
        _login(client, monkeypatch)
        resp = client.get("/system/card/ntp")
        assert resp.status_code == 200
        assert b"Synchronised" in resp.data
        assert b"192.168.2.123" in resp.data
        assert b"dhcp" in resp.data
        assert b"32s" in resp.data

    def test_ntp_card_unavailable(self, client, monkeypatch):
        self._patch(monkeypatch, {})
        _login(client, monkeypatch)
        resp = client.get("/system/card/ntp")
        assert resp.status_code == 200
        assert b"NTP data unavailable" in resp.data


_BLUETOOTH_STATUS = {
    "name": "wlanpi",
    "alias": "wlanpi-bt",
    "addr": "00:11:22:33:44:55",
    "power": "Off",
    "blocked": True,
    "paired_devices": [],
}


class TestSystemBluetooth:
    def _patch(self, monkeypatch, bt, post=None):
        from wlanpi_webui.system import system as s

        monkeypatch.setattr(
            s,
            "get_core_json",
            lambda path, params=None: bt if path.endswith("/bluetooth/status") else {},
        )
        monkeypatch.setattr(s, "post_core_json", lambda *a, **k: post)

    def _csrf(self, client):
        with client.session_transaction() as sess:
            return sess["csrf_token"]

    def test_bluetooth_card_blocked(self, client, monkeypatch):
        self._patch(monkeypatch, _BLUETOOTH_STATUS)
        _login(client, monkeypatch)
        resp = client.get("/system/card/bluetooth")
        assert resp.status_code == 200
        assert b"00:11:22:33:44:55" in resp.data
        assert b"RF kill: Blocked" in resp.data
        assert b"Power on" in resp.data

    def test_bluetooth_card_unavailable(self, client, monkeypatch):
        self._patch(monkeypatch, {})
        _login(client, monkeypatch)
        resp = client.get("/system/card/bluetooth")
        assert resp.status_code == 200
        assert b"Bluetooth unavailable" in resp.data

    def test_bluetooth_power_route(self, client, monkeypatch):
        self._patch(
            monkeypatch, _BLUETOOTH_STATUS, post={"status": "success", "action": "on"}
        )
        _login(client, monkeypatch)
        resp = client.post(
            "/system/bluetooth/power/on", data={"csrf_token": self._csrf(client)}
        )
        assert resp.status_code == 200
        assert b"00:11:22:33:44:55" in resp.data

    def test_bluetooth_power_route_rejects_bad_action(self, client, monkeypatch):
        self._patch(
            monkeypatch, _BLUETOOTH_STATUS, post={"status": "success", "action": "on"}
        )
        _login(client, monkeypatch)
        resp = client.post(
            "/system/bluetooth/power/sideways", data={"csrf_token": self._csrf(client)}
        )
        assert resp.status_code == 400

    def test_bluetooth_pair_route(self, client, monkeypatch):
        self._patch(
            monkeypatch,
            _BLUETOOTH_STATUS,
            post={
                "status": "discoverable",
                "alias": "wlanpi-bt",
                "message": 'Bluetooth is on. Discoverable as "wlanpi-bt"',
            },
        )
        _login(client, monkeypatch)
        resp = client.post(
            "/system/bluetooth/pair", data={"csrf_token": self._csrf(client)}
        )
        assert resp.status_code == 200
        assert b"Discoverable" in resp.data
