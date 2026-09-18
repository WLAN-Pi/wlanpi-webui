from flask import render_template, request

from wlanpi_webui.config import Config, get_apt_package_version, get_hostname
from wlanpi_webui.dashboard import bp
from wlanpi_webui.utils import is_htmx


def get_mode() -> str:
    try:
        with open("/etc/wlanpi-state") as state_file:
            return state_file.read().strip()
    except OSError:
        return "unknown"


@bp.route("/")
def dashboard():
    resp_data = {
        "hostname": get_hostname(),
        "mode": get_mode(),
        "webui_version": Config.WEBUI_VERSION,
        "wlanpi_version": Config.WLANPI_VERSION,
        "wlanpi_core_version": get_apt_package_version("wlanpi-core"),
    }
    if is_htmx(request):
        return render_template("/partials/dashboard.html", **resp_data)
    else:
        return render_template("/extends/dashboard.html", **resp_data)
