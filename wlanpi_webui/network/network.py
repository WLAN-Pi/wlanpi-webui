import ipaddress
import re
from datetime import UTC, datetime

from flask import render_template, request

from wlanpi_webui.config import get_hostname
from wlanpi_webui.network import bp
from wlanpi_webui.utils import get_core_json, is_htmx


def _lines(section) -> list[str]:
    """Return the info lines from a core ``InfoLinesSection``."""
    if isinstance(section, dict):
        return section.get("info") or []
    return []


def _wlan_cards(wlan) -> list[dict]:
    """One card per WLAN interface from core's ``wlan_interfaces`` mapping."""
    if not isinstance(wlan, dict):
        return []
    cards = []
    for name in sorted(wlan):
        info = wlan[name] if isinstance(wlan[name], dict) else {}
        mac = info.get("addr") or ""
        mac = ":".join(mac[i : i + 2] for i in range(0, len(mac), 2)) or "n/a"
        channel = f"Channel {info['channel']}" if info.get("channel") else "Channel n/a"
        if info.get("freq"):
            channel += f" ({info['freq']} MHz)"
        cards.append(
            {
                "id": f"wlan-{name}",
                "title": f"{name} Interface",
                "lines": [
                    f"Mode: {info.get('mode') or 'n/a'}",
                    f"SSID: {info.get('ssid') or 'n/a'}",
                    channel,
                    f"Driver: {info.get('driver') or 'n/a'}",
                    f"MAC: {mac}",
                ],
            }
        )
    return cards


def _routing_lines(routing) -> list[str]:
    lines = []
    for route in routing.get("routes") or []:
        if not isinstance(route, dict):
            lines.append(str(route))
            continue
        parts = [route.get("dst") or "default"]
        if route.get("gateway"):
            parts.append(f"via {route['gateway']}")
        if route.get("dev"):
            parts.append(f"dev {route['dev']}")
        if route.get("protocol"):
            parts.append(f"proto {route['protocol']}")
        if route.get("metric") is not None:
            parts.append(f"metric {route['metric']}")
        lines.append(" ".join(parts))
    return lines


# (label, NetworkManager key, dhclient key). Core returns NetworkManager's
# DHCP4 options when NM runs, else parsed dhclient lease files.
_LEASE_FIELDS = (
    ("Gateway", "routers", "option_routers"),
    ("DNS servers", "domain_name_servers", "option_domain_name_servers"),
    ("Domain", "domain_name", "option_domain_name"),
    ("Search domains", "domain_search", "option_domain_search"),
    ("NTP servers", "ntp_servers", "option_ntp_servers"),
    ("DHCP server", "dhcp_server_identifier", "option_dhcp_server_identifier"),
    ("MTU", "interface_mtu", "option_interface_mtu"),
)
_LIST_FIELDS = {"Gateway", "DNS servers", "Search domains", "NTP servers"}
# RFC 2131 3.3: an all-ones lease time means the lease never expires.
_INFINITE_LEASE = 0xFFFFFFFF


def _lease_value(lease: dict, nm_key: str, dhclient_key: str) -> str:
    value = lease.get(nm_key) or lease.get(dhclient_key) or ""
    return str(value).strip().strip('"')


def _address_lines(lease: dict) -> list[str]:
    """Address with its prefix length; a bad or missing mask is shown apart."""
    addr = _lease_value(lease, "ip_address", "fixed_address")
    mask = _lease_value(lease, "subnet_mask", "option_subnet_mask")
    if addr and mask:
        try:
            net = ipaddress.IPv4Network(f"0.0.0.0/{mask}")
            # IPv4Network also takes a prefix length or a host mask; only a
            # dotted netmask that round-trips is a real subnet mask.
            if net.netmask == ipaddress.IPv4Address(mask):
                return [f"Address: {addr}/{net.prefixlen}"]
        except ValueError:
            pass
    lines = [f"Address: {addr}"] if addr else []
    if mask:
        lines.append(f"Subnet mask: {mask}")
    return lines


def _duration(seconds: int) -> str:
    parts = []
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
        count, seconds = divmod(seconds, size)
        if count:
            parts.append(f"{count}{unit}")
    return " ".join(parts) or "0s"


def _lease_time(value) -> str:
    try:
        seconds = int(str(value).strip())
    except ValueError:
        return str(value)
    if seconds == _INFINITE_LEASE:
        return f"Infinite ({seconds} s)"
    return f"{_duration(seconds)} ({seconds} s)"


def _lease_expiry(lease: dict) -> str | None:
    # NetworkManager: epoch seconds. dhclient: "<weekday> YYYY/MM/DD HH:MM:SS"
    # in UTC, or "never". Anything else is shown as given.
    nm = lease.get("expiry")
    if nm not in (None, ""):
        try:
            when = datetime.fromtimestamp(int(str(nm)), tz=UTC)
        except (ValueError, OverflowError, OSError):
            return str(nm)
        return when.strftime("%Y-%m-%d %H:%M:%S UTC")
    expire = str(lease.get("expire") or "").strip()
    if not expire:
        return None
    if expire.lower() == "never":
        return "Never"
    try:
        when = datetime.strptime(" ".join(expire.split()[-2:]), "%Y/%m/%d %H:%M:%S")
    except ValueError:
        return expire
    return when.strftime("%Y-%m-%d %H:%M:%S UTC")


def _lease_lines(lease: dict) -> list[str]:
    lines = _address_lines(lease)
    hostname = _lease_value(lease, "host_name", "option_host_name")
    if hostname:
        lines.append(f"Hostname: {hostname}")
    client_id = _lease_value(
        lease, "dhcp_client_identifier", "option_dhcp_client_identifier"
    )
    if client_id:
        lines.append(f"Client ID: {client_id}")
    for label, nm_key, dhclient_key in _LEASE_FIELDS:
        value = _lease_value(lease, nm_key, dhclient_key)
        if not value:
            continue
        if label in _LIST_FIELDS:
            value = ", ".join(v.strip('"') for v in re.split(r"[,\s]+", value) if v)
        lines.append(f"{label}: {value}")
    lease_time = lease.get("dhcp_lease_time") or lease.get("option_dhcp_lease_time")
    if lease_time:
        lines.append(f"Lease time: {_lease_time(lease_time)}")
    expiry = _lease_expiry(lease)
    if expiry:
        lines.append(f"Expires: {expiry}")
    if lines:
        return lines
    # Unknown payload shape: show it raw rather than nothing.
    return [
        f"{key}: {value}"
        for key, value in lease.items()
        if key != "interface" and not key.startswith("requested_")
    ]


def _lease_cards(leases) -> list[dict]:
    """One card per interface; dhclient files append, so the last lease wins."""
    cards: dict[str, dict] = {}
    for i, lease in enumerate(leases.get("leases") or []):
        if not isinstance(lease, dict):
            cards[f"#{i}"] = {"interface": "", "lines": [str(lease)]}
            continue
        iface = str(lease.get("interface") or "").strip('"')
        cards[iface or f"#{i}"] = {"interface": iface, "lines": _lease_lines(lease)}
    return list(cards.values())


def _link_stats_lines(stats) -> list[str]:
    lines = []
    for key in ("link_detected", "speed_mbps", "duplex", "port", "driver"):
        value = stats.get(key)
        if value not in (None, ""):
            lines.append(f"{key.replace('_', ' ').capitalize()}: {value}")
    return lines


def _wlan_link_lines(link) -> list[str]:
    """Render a core ``wlan-link`` payload as card lines."""
    if not link.get("connected"):
        return ["Not connected"]
    lines = []
    if link.get("ssid"):
        lines.append(f"SSID: {link['ssid']}")
    if link.get("bssid"):
        lines.append(f"BSSID: {link['bssid']}")
    if link.get("freq_mhz") is not None:
        lines.append(f"Frequency: {link['freq_mhz']} MHz")
    if link.get("signal_dbm") is not None:
        lines.append(f"Signal: {link['signal_dbm']} dBm")
    if link.get("rx_bitrate"):
        lines.append(f"Rx bitrate: {link['rx_bitrate']}")
    if link.get("tx_bitrate"):
        lines.append(f"Tx bitrate: {link['tx_bitrate']}")
    if link.get("rx_bytes") is not None:
        lines.append(f"Rx bytes: {link['rx_bytes']}")
    if link.get("tx_bytes") is not None:
        lines.append(f"Tx bytes: {link['tx_bytes']}")
    return lines or ["Connected"]


def _interface_names(interfaces) -> list[str]:
    names = []
    if isinstance(interfaces, dict):
        for group in interfaces.values():
            for iface in group or []:
                name = iface.get("ifname") if isinstance(iface, dict) else None
                if name and name != "lo" and name[:3] in ("eth", "wla"):
                    names.append(name)
    return names


@bp.route("/network")
def network():
    """Network shell; cards lazy-load from ``/network/cards``."""
    if is_htmx(request):
        return render_template("/partials/network.html")
    else:
        return render_template("/extends/network.html")


@bp.route("/network/cards")
def network_cards():
    """Network cards and detail, sourced from the wlanpi-core API."""
    reach = get_core_json("/api/v1/utils/reachability")
    net = get_core_json("/api/v1/network/info/") or {}
    public_ip6 = get_core_json("/api/v1/network/info/publicip6")
    routing = get_core_json("/api/v1/network/routing") or {}
    leases = get_core_json("/api/v1/network/dhcp/leases") or {}
    interfaces = get_core_json("/api/v1/network/interfaces") or {}

    if reach is None:
        reachability: list[str] = []
        reachability_empty = "wlanpi-core API is not responding."
    else:
        reachability = [
            f"{label}: {value}" for label, value in reach.items() if label != "custom"
        ]
        reachability_empty = "No reachability data returned."

    link_stats = []
    for name in _interface_names(interfaces)[:4]:
        if name.startswith("wlan"):
            link = get_core_json(f"/api/v1/network/interfaces/{name}/wlan-link")
            if link:
                link_stats.append({"interface": name, "lines": _wlan_link_lines(link)})
        else:
            stats = get_core_json(f"/api/v1/network/interfaces/{name}/link-stats")
            if stats:
                link_stats.append(
                    {"interface": name, "lines": _link_stats_lines(stats)}
                )

    resp_data = {
        "hostname": get_hostname(),
        "reachability": reachability,
        "reachability_empty": reachability_empty,
        "publicip": _lines(net.get("public_ip")),
        "publicip6": _lines(public_ip6),
        "ipconfig": _lines(net.get("eth0_ipconfig_info")),
        "lldp": _lines(net.get("lldp_neighbour_info")),
        "cdp": _lines(net.get("cdp_neighbour_info")),
        "wlan_cards": _wlan_cards(net.get("wlan_interfaces")),
        "routing": _routing_lines(routing),
        "leases": _lease_cards(leases),
        "link_stats": link_stats,
    }

    return render_template("/partials/network_cards.html", **resp_data)
