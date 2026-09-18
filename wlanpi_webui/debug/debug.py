"""Debug page: toast tests, theme toggle, session and system details."""

import subprocess
from time import time

from flask import render_template, request, session

from wlanpi_webui.config import Config, get_apt_package_version, get_hostname
from wlanpi_webui.debug import bp
from wlanpi_webui.utils import is_htmx, run_pipeline, system_service_running_state

TOAST_STATUSES = ["primary", "success", "warning", "danger"]


def get_system_info() -> dict:
    try:
        kernel_version = subprocess.check_output(["uname", "-r"]).decode().strip()
    except Exception:
        kernel_version = "unknown"
    try:
        hardware_model = run_pipeline(
            ["grep", "Model", "/proc/cpuinfo"],
            ["cut", "-d", ":", "-f", "2"],
        ).strip()
    except Exception:
        hardware_model = "unknown"
    try:
        with open("/etc/wlanpi-state") as state_file:
            mode = state_file.read().strip()
    except Exception:
        mode = "unknown"
    return {
        "mode": mode,
        "hostname": get_hostname(),
        "kernel_version": kernel_version,
        "hardware_model": hardware_model,
        "wlanpi_version": Config.WLANPI_VERSION,
        "webui_version": Config.WEBUI_VERSION,
        "wlanpi_core_version": get_apt_package_version("wlanpi-core"),
        "wlanpi_core_status": (
            "active" if system_service_running_state("wlanpi-core") else "inactive"
        ),
    }


@bp.route("/debug")
def debug():
    """Render the debug page (toast tests, theme toggle, session and system)."""
    last_seen = session.get("last_seen")
    resp_data = {
        "toast_statuses": TOAST_STATUSES,
        "idle_timeout": Config.IDLE_TIMEOUT,
        "boot_id": session.get("boot_id"),
        "last_seen_age": (int(time() - last_seen) if last_seen else None),
        **get_system_info(),
    }
    if is_htmx(request):
        return render_template("/partials/debug.html", **resp_data)
    return render_template("/extends/debug.html", **resp_data)
