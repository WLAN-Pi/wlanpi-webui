# stats for homepage
import socket
import subprocess

from flask import request
from flask_minify import decorators as minify_decorators

from wlanpi_webui.stream import bp
from wlanpi_webui.utils import is_htmx


def get_stats():
    # figure out our IP
    IP = ""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(("10.255.255.255", 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = "127.0.0.1"
    finally:
        s.close()

    ipStr = f"{IP}"

    # determine CPU load
    cmd = r"top -bn1 | awk '/Cpu\(s\):/ {print $2 + $4}'"
    try:
        CPU_USAGE = subprocess.check_output(cmd, shell=True).decode()
        CPU = f"{float(CPU_USAGE):.0f}%"
        if float(CPU_USAGE) == 0:
            CPU = "0%"
        elif float(CPU_USAGE) >= 99.99:
            CPU = "100%"
    except Exception:
        CPU = "unknown"

    # determine mem useage
    cmd = "free -m | awk 'NR==2{printf \"%s/%sMB %.0f%%\", $3,$2,$3*100/$2 }'"
    try:
        MemUsage = subprocess.check_output(cmd, shell=True).decode()
    except Exception:
        MemUsage = "unknown"

    # determine disk util
    cmd = 'df -h | awk \'$NF=="/"{printf "%d/%dGB %s", $3,$2,$5}\''
    try:
        Disk = subprocess.check_output(cmd, shell=True).decode()
    except Exception:
        Disk = "unknown"

    # determine temp
    try:
        tempI = int(open("/sys/class/thermal/thermal_zone0/temp").read())
    except Exception:
        tempI = "unknown"

    if tempI > 1000:
        tempI = tempI / 1000
    tempStr = "%sC" % str(round(tempI, 1))

    # determine uptime
    cmd = r"uptime -p | sed -r 's/up|,//g' | sed -r 's/\s*week[s]?/w/g' | sed -r 's/\s*day[s]?/d/g' | sed -r 's/\s*hour[s]?/h/g' | sed -r 's/\s*minute[s]?/m/g'"
    try:
        uptime = subprocess.check_output(cmd, shell=True).decode().strip()
    except Exception:
        uptime = "unknown"

    uptimeStr = f"{uptime}"

    results = {
        "IP": ipStr,
        "CPU": str(CPU),
        "RAM": str(MemUsage),
        "DISK": str(Disk),
        "CPU_TEMP": tempStr,
        "UPTIME": uptimeStr,
    }

    return results


@bp.route("/stream/stats")
@minify_decorators.minify(html=True)
def stream_stats():
    stats = get_stats()
    if is_htmx(request):
        html = """
<div class="stat-container">
<div class="stat-icon"><img src="/static/icon/globe.svg"></div>
<div class="stat-text">{IP}</div>
</div>
<div class="stat-container" style="align-items: center;">
<div class="stat-icon"><img src="/static/icon/cpu.svg"></div>
<div class="stat-text">
<span class="stat-text">{CPU} {CPU_TEMP}</span>
</div>
</div>
<div class="stat-container">
<div class="stat-icon"><img src="/static/icon/ram.svg"></div>
<div class="stat-text">{RAM}</div>
</div>
<div class="stat-container">
<div class="stat-icon"><img src="/static/icon/storage.svg"></div>
<div class="stat-text">{DISK}</div>
</div>
<div class="stat-container">
<div class="stat-icon"><img src="/static/icon/uptime.svg"></div>
<div class="stat-text">{UPTIME}</div>
</div>
""".format(**stats)
        return html
