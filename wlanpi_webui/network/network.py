from flask import render_template, request

from wlanpi_webui.network import bp
from wlanpi_webui.utils import get_core_json, is_htmx


def _lines(section) -> list[str]:
    """Return the info lines from a core ``InfoLinesSection``."""
    if isinstance(section, dict):
        return section.get("info") or []
    return []


@bp.route("/network")
def network():
    """Network cards, sourced from the wlanpi-core API."""
    reachability = get_core_json("/api/v1/utils/reachability") or {}
    net = get_core_json("/api/v1/network/info/") or {}

    resp_data = {
        "reachability": [
            f"{label}: {value}"
            for label, value in reachability.items()
            if label != "custom"
        ],
        "publicip": _lines(net.get("public_ip")),
        "ipconfig": _lines(net.get("eth0_ipconfig_info")),
        "lldp": _lines(net.get("lldp_neighbour_info")),
        "cdp": _lines(net.get("cdp_neighbour_info")),
    }

    if is_htmx(request):
        return render_template("/partials/network.html", **resp_data)
    else:
        return render_template("/extends/network.html", **resp_data)
