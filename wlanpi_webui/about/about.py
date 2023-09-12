import subprocess

from flask import render_template, request

from wlanpi_webui.about import bp
from wlanpi_webui.config import Config, get_apt_package_version, get_hostname
from wlanpi_webui.utils import is_htmx, system_service_running_state


@bp.route("/about")
def about():
    try:
        kernel_version = subprocess.check_output("uname -r", shell=True).decode()
    except Exception:
        kernel_version = "unknown"
    try:
        hardware_model = subprocess.check_output(
            "cat /proc/cpuinfo | grep Model | cut -d ':' -f 2", shell=True
        ).decode()
    except Exception:
        hardware_model = "unknown"
    try:
        mode = subprocess.check_output("cat /etc/wlanpi-state", shell=True).decode()
    except Exception:
        mode = "unknown"
    resp_data = {
        "mode": mode,
        "hostname": get_hostname(),
        "wlanpi_core_version": get_apt_package_version("wlanpi-core"),
        "wlanpi_core_status": (
            "active" if system_service_running_state("wlanpi-core") else "inactive"
        ),
        "kernel_version": kernel_version,
        "hardware_model": hardware_model,
        "wlanpi_version": Config.WLANPI_VERSION,
        "webui_version": Config.WEBUI_VERSION,
    }
    if is_htmx(request):
        return render_template("/partials/about.html", **resp_data)
    else:
        return render_template("/extends/about.html", **resp_data)
