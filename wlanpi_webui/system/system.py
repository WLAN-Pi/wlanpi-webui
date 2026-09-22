"""System page: live stats plus device facts and diagnostics."""

import subprocess

from flask import abort, render_template, request

from wlanpi_webui.config import Config, get_apt_package_version, get_hostname
from wlanpi_webui.stream.stream import get_local_ip
from wlanpi_webui.system import bp
from wlanpi_webui.utils import (
    get_core_json,
    is_htmx,
    run_pipeline,
    system_service_running_state,
)


def _kernel_version() -> str:
    try:
        return subprocess.check_output(["uname", "-r"]).decode().strip()
    except Exception:
        return "unknown"


def _hardware_model() -> str:
    try:
        return (
            run_pipeline(
                ["grep", "Model", "/proc/cpuinfo"],
                ["cut", "-d", ":", "-f", "2"],
            ).strip()
            or "unknown"
        )
    except Exception:
        return "unknown"


def _mode() -> str:
    try:
        with open("/etc/wlanpi-state") as state_file:
            return state_file.read().strip()
    except Exception:
        return "unknown"


def _battery_text(battery: dict) -> str:
    """Human-readable battery line; always says so when there is no battery."""
    if not battery.get("present"):
        return "Not detected"
    capacity = battery.get("capacity_percent")
    status = battery.get("status")
    if capacity is None:
        return status or "Present"
    return f"{capacity}%" + (f" ({status})" if status else "")


def _fmt_item(item) -> str:
    if isinstance(item, dict):
        return ", ".join(f"{key}: {value}" for key, value in item.items())
    return str(item)


def _pci_line(device) -> str:
    if isinstance(device, dict):
        return f"{device.get('pci_id', '')} {device.get('description', '')}".strip()
    return str(device)


def _throttle_text(throttled: dict) -> str:
    """Current throttling state in plain English."""
    if not throttled:
        return "Unavailable"
    flags = []
    if throttled.get("undervoltage"):
        flags.append("Under-voltage")
    if throttled.get("frequency_capped"):
        flags.append("Frequency capped")
    if throttled.get("throttled"):
        flags.append("Throttled")
    if throttled.get("soft_temperature_limit"):
        flags.append("Soft temperature limit")
    return ", ".join(flags) if flags else "No throttling"


def _throttle_occurred_text(throttled: dict) -> str:
    """Past throttling events in plain English."""
    if not throttled:
        return "Unavailable"
    flags = []
    if throttled.get("undervoltage_occurred"):
        flags.append("Under-voltage")
    if throttled.get("frequency_capped_occurred"):
        flags.append("Frequency capped")
    if throttled.get("throttled_occurred"):
        flags.append("Throttled")
    if throttled.get("soft_temperature_limit_occurred"):
        flags.append("Soft temperature limit")
    return ", ".join(flags) if flags else "None"


def get_system_info() -> dict:
    """Device identity from wlanpi-core, with local reads as a fallback."""
    info = get_core_json("/api/v1/system/device/info") or {}
    stats = get_core_json("/api/v1/system/device/stats") or {}
    battery = get_core_json("/api/v1/system/battery") or {}

    return {
        "mode": info.get("mode") or _mode(),
        "hostname": info.get("name") or get_hostname(),
        "ip": stats.get("ip") or get_local_ip(),
        "hardware_model": info.get("model") or _hardware_model(),
        "kernel_version": _kernel_version(),
        "wlanpi_version": info.get("software_version") or Config.WLANPI_VERSION,
        "webui_version": Config.WEBUI_VERSION,
        "wlanpi_core_version": get_apt_package_version("wlanpi-core"),
        "wlanpi_core_status": (
            "active" if system_service_running_state("wlanpi-core") else "inactive"
        ),
        "battery": _battery_text(battery),
    }


def get_system_usb() -> dict:
    """USB interfaces from wlanpi-core."""
    usb = get_core_json("/api/v1/utils/usb") or {}
    return {
        "usb_interfaces": [_fmt_item(item) for item in usb.get("interfaces") or []],
    }


def get_system_pci() -> dict:
    """PCI devices from wlanpi-core."""
    pci = get_core_json("/api/v1/utils/pci") or {}
    return {
        "pci_devices": [_pci_line(device) for device in pci.get("devices") or []],
    }


def get_system_health() -> dict:
    """Device health from wlanpi-core: throttle, thermals, time, load, radios."""
    health = get_core_json("/api/v1/system/health") or {}
    throttled = health.get("throttled") or {}
    ntp = health.get("ntp") or {}
    return {
        "health_available": bool(health),
        "throttle_state": _throttle_text(throttled),
        "throttle_occurred": _throttle_occurred_text(throttled),
        "temperatures": health.get("temperatures") or [],
        "ntp_enabled": ntp.get("enabled"),
        "ntp_synced": ntp.get("synchronized"),
        "load": health.get("load") or {},
        "swap": health.get("swap") or {},
        "rfkill": health.get("rfkill") or [],
    }


@bp.route("/system")
def system():
    """Render the system shell; the cards load individually."""
    if is_htmx(request):
        return render_template("/partials/system.html")
    return render_template("/extends/system.html")


# One System card per request so they load in parallel and pack in one masonry.
SYSTEM_CARDS = {
    "status": ("/partials/system_status.html", get_system_health),
    "temperatures": ("/partials/system_temperatures.html", get_system_health),
    "radios": ("/partials/system_radios.html", get_system_health),
    "facts": ("/partials/system_facts.html", get_system_info),
    "usb": ("/partials/system_usb.html", get_system_usb),
    "pci": ("/partials/system_pci.html", get_system_pci),
}


@bp.route("/system/card/<card>")
def system_card(card):
    """Render the inner content of one System card."""
    entry = SYSTEM_CARDS.get(card)
    if entry is None:
        abort(404)
    template, build = entry
    return render_template(template, **build())
