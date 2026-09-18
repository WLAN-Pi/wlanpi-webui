"""System page: live stats plus device facts (moved out of the old debug page)."""

import subprocess

from flask import render_template, request

from wlanpi_webui.config import Config, get_apt_package_version, get_hostname
from wlanpi_webui.stream.stream import get_local_ip
from wlanpi_webui.system import bp
from wlanpi_webui.utils import is_htmx, run_pipeline, system_service_running_state


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
        "ip": get_local_ip(),
        "kernel_version": kernel_version,
        "hardware_model": hardware_model,
        "wlanpi_version": Config.WLANPI_VERSION,
        "webui_version": Config.WEBUI_VERSION,
        "wlanpi_core_version": get_apt_package_version("wlanpi-core"),
        "wlanpi_core_status": (
            "active" if system_service_running_state("wlanpi-core") else "inactive"
        ),
    }


@bp.route("/system")
def system():
    """Render the system shell; facts lazy-load from ``/system/facts``."""
    if is_htmx(request):
        return render_template("/partials/system.html")
    return render_template("/extends/system.html")


@bp.route("/system/facts")
def system_facts():
    """Render the system facts card (device facts, may be slow)."""
    return render_template("/partials/system_facts.html", **get_system_info())
