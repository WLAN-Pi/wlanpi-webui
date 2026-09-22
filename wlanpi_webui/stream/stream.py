# stats for homepage
import socket

from flask import request

from wlanpi_webui.stream import bp
from wlanpi_webui.utils import get_core_json, is_htmx


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

    Falls back to "unavailable" per field rather than shelling out here, so the
    numbers match what core reports elsewhere.
    """
    stats = get_core_json("/api/v1/system/device/stats") or {}

    def value(key):
        return str(stats.get(key) or "unavailable")

    return {
        "CPU": value("cpu"),
        "RAM": value("ram"),
        "DISK": value("disk"),
        "CPU_TEMP": value("cpu_temp"),
        "UPTIME": value("uptime"),
    }


@bp.route("/stream/stats")
def stream_stats():
    stats = get_stats()
    if is_htmx(request):
        html = """
<div class="stat-container">
<div class="stat-icon"><img src="/static/icon/cpu.svg" alt=""></div>
<div class="stat-label">CPU</div>
<div class="stat-text">
<span class="stat-text">{CPU} {CPU_TEMP}</span>
</div>
</div>
<div class="stat-container">
<div class="stat-icon"><img src="/static/icon/ram.svg" alt=""></div>
<div class="stat-label">RAM</div>
<div class="stat-text">{RAM}</div>
</div>
<div class="stat-container">
<div class="stat-icon"><img src="/static/icon/storage.svg" alt=""></div>
<div class="stat-label">Disk</div>
<div class="stat-text">{DISK}</div>
</div>
<div class="stat-container">
<div class="stat-icon"><img src="/static/icon/uptime.svg" alt=""></div>
<div class="stat-label">Uptime</div>
<div class="stat-text">{UPTIME}</div>
</div>
""".format(**stats)
        return html
