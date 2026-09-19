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
                "title": name,
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


@bp.route("/network")
def network():
    """Network shell; cards lazy-load from ``/network/cards``."""
    if is_htmx(request):
        return render_template("/partials/network.html")
    else:
        return render_template("/extends/network.html")


@bp.route("/network/cards")
def network_cards():
    """Network cards, sourced from the wlanpi-core API."""
    reach = get_core_json("/api/v1/utils/reachability")
    net = get_core_json("/api/v1/network/info/") or {}

    if reach is None:
        reachability: list[str] = []
        reachability_empty = "wlanpi-core API is not responding."
    else:
        reachability = [
            f"{label}: {value}" for label, value in reach.items() if label != "custom"
        ]
        reachability_empty = "No reachability data returned."

    resp_data = {
        "hostname": get_hostname(),
        "reachability": reachability,
        "reachability_empty": reachability_empty,
        "publicip": _lines(net.get("public_ip")),
        "ipconfig": _lines(net.get("eth0_ipconfig_info")),
        "lldp": _lines(net.get("lldp_neighbour_info")),
        "cdp": _lines(net.get("cdp_neighbour_info")),
        "wlan_cards": _wlan_cards(net.get("wlan_interfaces")),
    }

    return render_template("/partials/network_cards.html", **resp_data)
