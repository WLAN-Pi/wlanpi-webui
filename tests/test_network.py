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

    def test_core_down_shows_one_message(self, client, monkeypatch):
        from wlanpi_webui.network import network as n

        monkeypatch.setattr(n, "get_core_json", lambda *a, **k: None)
        monkeypatch.setattr(
            "wlanpi_webui.app.system_service_running_state", lambda *a, **k: False
        )
        _login(client, monkeypatch)
        resp = client.get("/network/cards")
        assert resp.status_code == 200
        assert resp.data.count(b"wlanpi-core isn't running") == 1
        assert b"Unavailable." not in resp.data
        assert b"Reachability" not in resp.data

    def test_api_down_shows_unavailable(self, client, monkeypatch):
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
        # the latency graph script (it lazy-loads Chart.js)
        assert b"/static/js/network.js" in resp.data
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
                return {"leases": [{"interface": "eth0", "ip_address": "192.168.6.63"}]}
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
        assert b"eth0 DHCP Lease" in resp.data
        assert b"eth0 Link" in resp.data
        assert b"wlan0 Link" in resp.data
        assert b"SSID: HomeNet" in resp.data
        assert b"Signal: -48.0 dBm" in resp.data
        assert b"Address: 192.168.6.63" in resp.data
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


class TestDhcpLeases:
    def test_networkmanager_options(self):
        from wlanpi_webui.network.network import _lease_cards

        cards = _lease_cards(
            {
                "leases": [
                    {
                        "interface": "eth0",
                        "ip_address": "192.168.6.60",
                        "subnet_mask": "255.255.255.0",
                        "routers": "192.168.6.1",
                        "domain_name_servers": "9.9.9.9 1.0.0.1",
                        "domain_name": "home.arpa",
                        "dhcp_server_identifier": "192.168.6.1",
                        "dhcp_lease_time": "4294967295",
                        "requested_routers": "1",
                        "dhcp_client_identifier": "01:dc:a6:32:e7:25:e1",
                        "host_name": "wlanpi-5e1",
                    },
                    {
                        "interface": "wlan0",
                        "ip_address": "10.0.0.5",
                        "dhcp_lease_time": "86400",
                        "expiry": "1791547200",
                    },
                ],
                "source": "NetworkManager",
            }
        )
        assert cards == [
            {
                "interface": "eth0",
                "lines": [
                    "Address: 192.168.6.60/24",
                    "Hostname: wlanpi-5e1",
                    "Client ID: 01:dc:a6:32:e7:25:e1",
                    "Gateway: 192.168.6.1",
                    "DNS servers: 9.9.9.9, 1.0.0.1",
                    "Domain: home.arpa",
                    "DHCP server: 192.168.6.1",
                    "Lease time: Infinite (4294967295 s)",
                ],
            },
            {
                "interface": "wlan0",
                "lines": [
                    "Address: 10.0.0.5",
                    "Lease time: 1d (86400 s)",
                    "Expires: 2026-10-09 12:00:00 UTC",
                ],
            },
        ]

    def test_dhclient_keeps_latest_lease_per_interface(self):
        from wlanpi_webui.network.network import _lease_cards

        old = {"interface": "eth0", "fixed_address": "192.168.1.9"}
        new = {
            "interface": "eth0",
            "fixed_address": "192.168.1.10",
            "option_subnet_mask": "255.255.252.0",
            "option_host_name": '"wlanpi-lab"',
            "option_dhcp_client_identifier": "1:dc:a6:32:e7:25:e1",
            "option_routers": "192.168.1.1",
            "option_domain_name_servers": "192.168.1.1,8.8.8.8",
            "option_domain_search": 'lab.example", "example.com',
            "option_dhcp_lease_time": "5400",
            "expire": "4 2026/10/08 12:30:00",
            "source_file": "dhclient.eth0.leases",
        }
        cards = _lease_cards({"leases": [old, new]})
        assert cards == [
            {
                "interface": "eth0",
                "lines": [
                    "Address: 192.168.1.10/22",
                    "Hostname: wlanpi-lab",
                    "Client ID: 1:dc:a6:32:e7:25:e1",
                    "Gateway: 192.168.1.1",
                    "DNS servers: 192.168.1.1, 8.8.8.8",
                    "Search domains: lab.example, example.com",
                    "Lease time: 1h 30m (5400 s)",
                    "Expires: 2026-10-08 12:30:00 UTC",
                ],
            }
        ]

    def test_unknown_shape_and_bad_values_fall_back(self):
        from wlanpi_webui.network.network import _lease_cards

        cards = _lease_cards(
            {
                "leases": [
                    {"ip": "10.0.0.9", "requested_x": "1"},
                    {
                        "ip_address": "10.0.0.8",
                        "dhcp_lease_time": "soon",
                        "expire": " ",
                    },
                    "raw lease text",
                ]
            }
        )
        assert [c["lines"] for c in cards] == [
            ["ip: 10.0.0.9"],
            ["Address: 10.0.0.8", "Lease time: soon"],
            ["raw lease text"],
        ]
        assert all(c["interface"] == "" for c in cards)

    @pytest.mark.parametrize(
        ("lease", "expected"),
        [
            ({"expire": "never"}, "Never"),
            ({"expire": "x unavailable now"}, "x unavailable now"),
            ({"expire": "4 2026/13/40 12:30:00"}, "4 2026/13/40 12:30:00"),
            ({"expiry": "soon"}, "soon"),
            ({"expiry": ["1"]}, "['1']"),
        ],
    )
    def test_expiry_fallbacks(self, lease, expected):
        from wlanpi_webui.network.network import _lease_expiry

        assert _lease_expiry(lease) == expected

    @pytest.mark.parametrize(
        ("lease", "expected"),
        [
            # Mask without address, and masks that are not dotted netmasks
            ({"subnet_mask": "255.255.255.0"}, ["Subnet mask: 255.255.255.0"]),
            (
                {"ip_address": "10.0.0.2", "subnet_mask": "255.0.255.0"},
                ["Address: 10.0.0.2", "Subnet mask: 255.0.255.0"],
            ),
            (
                {"ip_address": "10.0.0.2", "subnet_mask": "0.0.0.255"},
                ["Address: 10.0.0.2", "Subnet mask: 0.0.0.255"],
            ),
            (
                {"ip_address": "10.0.0.2", "subnet_mask": "24"},
                ["Address: 10.0.0.2", "Subnet mask: 24"],
            ),
        ],
    )
    def test_address_without_valid_mask(self, lease, expected):
        from wlanpi_webui.network.network import _address_lines

        assert _address_lines(lease) == expected
