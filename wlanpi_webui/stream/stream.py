# stats for homepage
import socket

from flask import render_template

from wlanpi_webui.stream import bp
from wlanpi_webui.utils import get_core_json


def get_local_ip() -> str:
    # figure out our IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(("10.255.255.255", 1))
        return str(s.getsockname()[0])
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def get_stats():
    """Device health from wlanpi-core, which owns the platform quirks.

    Falls back to "Unavailable" per field rather than shelling out here, so the
    numbers match what core reports elsewhere.
    """
    stats = get_core_json("/api/v1/system/device/stats") or {}

    def value(key):
        return str(stats.get(key) or "Unavailable")

    return {
        "CPU": value("cpu"),
        "RAM": value("ram"),
        "DISK": value("disk"),
        "CPU_TEMP": value("cpu_temp"),
        "UPTIME": value("uptime"),
    }


@bp.route("/stream/stats")
def stream_stats():
    return render_template("partials/stream_stats.html", **get_stats())
