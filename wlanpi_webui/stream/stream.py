# stats for homepage
import socket

from flask import request

from wlanpi_webui.stream import bp
from wlanpi_webui.utils import is_htmx, run_pipeline


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
    # determine CPU load
    try:
        CPU_USAGE = run_pipeline(
            ["top", "-bn1"], ["awk", r"/Cpu\(s\):/ {print $2 + $4}"]
        )
        CPU = f"{float(CPU_USAGE):.0f}%"
        if float(CPU_USAGE) == 0:
            CPU = "0%"
        elif float(CPU_USAGE) >= 99.99:
            CPU = "100%"
    except Exception:
        CPU = "unknown"

    # determine mem useage
    try:
        MemUsage = run_pipeline(
            ["free", "-m"],
            ["awk", 'NR==2{printf "%s/%sMB %.0f%%", $3,$2,$3*100/$2 }'],
        )
    except Exception:
        MemUsage = "unknown"

    # determine disk util
    try:
        Disk = run_pipeline(
            ["df", "-h"], ["awk", '$NF=="/"{printf "%d/%dGB %s", $3,$2,$5}']
        )
    except Exception:
        Disk = "unknown"

    # determine temp
    try:
        tempI = int(open("/sys/class/thermal/thermal_zone0/temp").read())
    except Exception:
        tempI = "unknown"

    if tempI > 1000:
        tempI = tempI / 1000
    tempStr = f"{round(tempI, 1)}C"

    # determine uptime
    try:
        uptime = run_pipeline(
            ["uptime", "-p"],
            ["sed", "-r", "s/up|,//g"],
            ["sed", "-r", r"s/\s*week[s]?/w/g"],
            ["sed", "-r", r"s/\s*day[s]?/d/g"],
            ["sed", "-r", r"s/\s*hour[s]?/h/g"],
            ["sed", "-r", r"s/\s*minute[s]?/m/g"],
        ).strip()
    except Exception:
        uptime = "unknown"

    uptimeStr = f"{uptime}"

    results = {
        "CPU": str(CPU),
        "RAM": str(MemUsage),
        "DISK": str(Disk),
        "CPU_TEMP": tempStr,
        "UPTIME": uptimeStr,
    }

    return results


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
