from flask import render_template, request

from wlanpi_webui.config import get_hostname
from wlanpi_webui.dashboard import bp
from wlanpi_webui.utils import get_core_json, is_htmx


def get_mode() -> str:
    try:
        with open("/etc/wlanpi-state") as state_file:
            return state_file.read().strip()
    except OSError:
        return "unknown"


def get_wlan_management() -> str:
    """Return wlanpi-core WLAN_MANAGEMENT (auto/manual), or unknown."""
    info = get_core_json("/api/v1/system/device/info") or {}
    return info.get("wlan_management") or "unknown"


@bp.route("/")
def dashboard():
    resp_data = {
        "hostname": get_hostname(),
        "mode": get_mode(),
        "wlan_management": get_wlan_management(),
    }
    if is_htmx(request):
        return render_template("/partials/dashboard.html", **resp_data)
    else:
        return render_template("/extends/dashboard.html", **resp_data)
