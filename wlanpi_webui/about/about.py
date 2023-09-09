from flask import render_template, request

from wlanpi_webui.about import bp
from wlanpi_webui.config import Config, get_apt_package_version, get_hostname
from wlanpi_webui.utils import is_htmx, system_service_running_state


@bp.route("/about")
def about():
    resp_data = {
        "hostname": get_hostname(),
        "wlanpi_core_version": get_apt_package_version("wlanpi-core"),
        "wlanpi_core_status": (
            "active" if system_service_running_state("wlanpi-core") else "inactive"
        ),
        "wlanpi_version": Config.WLANPI_VERSION,
        "webui_version": Config.WEBUI_VERSION,
    }
    if is_htmx(request):
        return render_template("/partials/about.html", **resp_data)
    else:
        return render_template("/extends/about.html", **resp_data)
