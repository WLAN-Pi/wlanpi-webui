"""Tests for the /network page backed by the wlanpi-core API (#108)."""

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


class TestNetwork:
    def test_requires_login(self, client):
        assert client.get("/network").status_code == 302

    def test_renders_core_sections(self, client, monkeypatch):
        from wlanpi_webui.network import network as n

        def fake(path, params=None):
            if "reachability" in path:
                return {
                    "Ping Google": "5ms",
                    "Arping Gateway": "1ms",
                    "custom": [],
                }
            return {
                "eth0_ipconfig_info": {"info": ["IP: 192.168.6.63", "GW: 192.168.6.1"]},
                "public_ip": {"info": ["1.2.3.4"]},
                "lldp_neighbour_info": {"info": ["Name: sw1"]},
                "cdp_neighbour_info": {"error": "No neighbour", "info": []},
            }

        monkeypatch.setattr(n, "get_core_json", fake)
        _login(client, monkeypatch)
        resp = client.get("/network/cards")
        assert resp.status_code == 200
        assert b"Ping Google: 5ms" in resp.data
        assert b"192.168.6.63" in resp.data
        assert b"sw1" in resp.data
        assert b"1.2.3.4" in resp.data

    def test_core_down_shows_unavailable(self, client, monkeypatch):
        from wlanpi_webui.network import network as n

        monkeypatch.setattr(n, "get_core_json", lambda *a, **k: None)
        _login(client, monkeypatch)
        resp = client.get("/network/cards")
        assert resp.status_code == 200
        # Six generic cards plus Routing and DHCP Leases; the reachability card
        # carries its own message.
        assert resp.data.count(b"Unavailable.") == 8
        assert b"wlanpi-core API is not responding." in resp.data

    def test_renders_wlan_cards(self, client, monkeypatch):
        from wlanpi_webui.network import network as n

        def fake(path, params=None):
            if "reachability" in path:
                return {"Ping Google": "5ms", "custom": []}
            if "publicip6" in path:
                return {"info": ["2001:db8::1", "Testland"]}
            return {
                "public_ip": {"info": []},
                "eth0_ipconfig_info": {"info": []},
                "lldp_neighbour_info": {"info": []},
                "cdp_neighbour_info": {"info": []},
                "wlan_interfaces": {
                    "wlan0": {
                        "driver": "brcmfmac",
                        "addr": "AABBCCDDEEFF",
                        "mode": "managed",
                        "ssid": "HomeNet",
                        "freq": 2437,
                        "channel": 6,
                    }
                },
            }

        monkeypatch.setattr(n, "get_core_json", fake)
        _login(client, monkeypatch)
        resp = client.get("/network/cards")
        assert resp.status_code == 200
        assert b"wlan0 Interface" in resp.data
        assert b"Mode: managed" in resp.data
        assert b"SSID: HomeNet" in resp.data
        assert b"Channel 6 (2437 MHz)" in resp.data
        assert b"MAC: AA:BB:CC:DD:EE:FF" in resp.data
        assert b"Public IPv6" in resp.data
        assert b"2001:db8::1" in resp.data

    def test_shell_loads_without_core(self, client, monkeypatch):
        _login(client, monkeypatch)
        resp = client.get("/network")
        assert resp.status_code == 200
        assert b"network/cards" in resp.data
        assert b"refresh-network" in resp.data
        assert b"Pause refresh" in resp.data
        assert b"Refresh now" in resp.data
        assert b"Unavailable." not in resp.data
        assert b"latency-chart" in resp.data
        assert b"Chart.bundle.min.js" in resp.data
        assert b'hx-get="/network/cards"' in resp.data
        assert b"/network/detail" not in resp.data


class TestNetworkDetail:
    def test_detail_route_is_gone(self, client, monkeypatch):
        _login(client, monkeypatch)
        assert client.get("/network/detail").status_code == 404

    def test_renders_sections(self, client, monkeypatch):
        from wlanpi_webui.network import network as n

        def fake(path, params=None):
            if "link-stats" in path:
                return {
                    "interface": "eth0",
                    "link_detected": "yes",
                    "speed_mbps": 1000,
                    "duplex": "full",
                    "driver": "bcmgenet",
                }
            if "wlan-link" in path:
                return {
                    "interface": "wlan0",
                    "connected": True,
                    "ssid": "HomeNet",
                    "bssid": "aa:bb:cc:dd:ee:ff",
                    "freq_mhz": 5200.0,
                    "signal_dbm": -48.0,
                    "rx_bitrate": "286.7 MBit/s",
                    "tx_bitrate": "286.7 MBit/s",
                    "rx_bytes": 1,
                    "tx_bytes": 2,
                }
            if "routing" in path:
                return {
                    "routes": [
                        {
                            "dst": "default",
                            "gateway": "192.168.6.1",
                            "dev": "eth0",
                            "protocol": "dhcp",
                            "metric": 100,
                        }
                    ]
                }
            if "dhcp/leases" in path:
                return {"leases": [{"ip": "192.168.6.63", "mac": "aa:bb"}]}
            if "interfaces" in path:
                return {
                    "root": [{"ifname": "eth0"}, {"ifname": "wlan0"}, {"ifname": "lo"}]
                }
            return {}

        monkeypatch.setattr(n, "get_core_json", fake)
        _login(client, monkeypatch)
        resp = client.get("/network/cards")
        assert resp.status_code == 200
        assert b"default via 192.168.6.1 dev eth0" in resp.data
        assert b"Speed mbps: 1000" in resp.data
        assert b"DHCP Leases" in resp.data
        assert b"eth0 Link" in resp.data
        assert b"wlan0 Link" in resp.data
        assert b"SSID: HomeNet" in resp.data
        assert b"Signal: -48.0 dBm" in resp.data
        assert b"ip: 192.168.6.63" in resp.data
        # The latency card ships in the same masonry so cards pack beside it.
        assert b'id="latency-card"' in resp.data
        assert b"card-wide" in resp.data

    def test_wlan_link_not_connected(self, client, monkeypatch):
        from wlanpi_webui.network import network as n

        def fake(path, params=None):
            if "wlan-link" in path:
                return {"interface": "wlan0", "connected": False}
            if "interfaces" in path:
                return {"root": [{"ifname": "wlan0"}]}
            return {}

        monkeypatch.setattr(n, "get_core_json", fake)
        _login(client, monkeypatch)
        resp = client.get("/network/cards")
        assert b"wlan0 Link" in resp.data
        assert b"Not connected" in resp.data
