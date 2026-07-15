import subprocess

from flask import render_template, request

from wlanpi_webui.about import bp
from wlanpi_webui.config import Config, get_apt_package_version, get_hostname
from wlanpi_webui.utils import is_htmx, run_pipeline, system_service_running_state


@bp.route("/about")
def about():
    try:
        kernel_version = subprocess.check_output(["uname", "-r"]).decode()
    except Exception:
        kernel_version = "unknown"
    try:
        hardware_model = run_pipeline(
            ["grep", "Model", "/proc/cpuinfo"],
            ["cut", "-d", ":", "-f", "2"],
        )
    except Exception:
        hardware_model = "unknown"
    try:
        with open("/etc/wlanpi-state") as state_file:
            mode = state_file.read()
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
