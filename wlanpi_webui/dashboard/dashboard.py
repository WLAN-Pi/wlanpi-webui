from flask import render_template, request

from wlanpi_webui.config import Config, get_apt_package_version, get_hostname
from wlanpi_webui.dashboard import bp
from wlanpi_webui.utils import get_core_json, is_htmx


def get_system_info() -> dict:
    device = get_core_json("/api/v1/system/device/info") or {}
    return {
        "model": device.get("model"),
        "name": device.get("name"),
        "hostname": device.get("hostname") or get_hostname(),
        "mode": device.get("mode"),
        "wlanpi_version": device.get("software_version") or Config.WLANPI_VERSION,
        "webui_version": Config.WEBUI_VERSION,
        "wlanpi_core_version": get_apt_package_version("wlanpi-core"),
    }


@bp.route("/")
def dashboard():
    resp_data = get_system_info()
    if is_htmx(request):
        return render_template("/partials/dashboard.html", **resp_data)
    else:
        return render_template("/extends/dashboard.html", **resp_data)


@bp.route("/dashboard/network")
def dashboard_network():
    # ponytail: lazy fragment; reachability (~2s) and the public-IP probe
    # (~5s) must not block the home page. Upgrade: cache in wlanpi-core.
    return render_template(
        "/partials/dashboard_network.html",
        reachability=get_core_json("/api/v1/utils/reachability"),
        network=get_core_json("/api/v1/network/info/"),
    )
