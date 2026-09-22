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


def _lease_lines(leases) -> list[str]:
    lines = []
    for lease in leases.get("leases") or []:
        if isinstance(lease, dict):
            lines.append(", ".join(f"{key}: {value}" for key, value in lease.items()))
        else:
            lines.append(str(lease))
    return lines


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
        "leases": _lease_lines(leases),
        "link_stats": link_stats,
    }

    return render_template("/partials/network_cards.html", **resp_data)
