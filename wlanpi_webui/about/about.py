from flask import render_template

from wlanpi_webui.about import bp
from wlanpi_webui.config import Config, get_apt_package_version, get_hostname
from wlanpi_webui.utils import systemd_service_status


@bp.route("/about")
def about():
    return render_template(
        "public/about.html",
        hostname=get_hostname(),
        wlanpi_core_version=get_apt_package_version("wlanpi-core"),
        wlanpi_core_status=(
            "active" if systemd_service_status("wlanpi-core") else "inactive"
        ),
        wlanpi_version=Config.WLANPI_VERSION,
        webui_version=Config.WEBUI_VERSION,
    )
