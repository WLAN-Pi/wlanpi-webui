from flask import render_template, request

from wlanpi_webui.about import bp
from wlanpi_webui.config import Config, get_apt_package_version, get_hostname
from wlanpi_webui.utils import systemd_service_status_running


@bp.route("/about")
def about():
    htmx_request = request.headers.get("HX-Request") is not None

    resp_data = {
        "hostname": get_hostname(),
        "wlanpi_core_version": get_apt_package_version("wlanpi-core"),
        "wlanpi_core_status": (
            "active" if systemd_service_status_running("wlanpi-core") else "inactive"
        ),
        "wlanpi_version": Config.WLANPI_VERSION,
        "webui_version": Config.WEBUI_VERSION,
    }
    if htmx_request:
        return render_template("/public/about_partial.html", **resp_data)
    else:
        return render_template("/public/about.html", **resp_data)
