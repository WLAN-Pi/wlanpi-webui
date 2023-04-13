from flask import current_app, render_template, request, Response

from wlanpi_webui.stream import bp



#stats for homepage    
import socket, subprocess

def get_stats():
    # figure out our IP
    IP = ''
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()

    ipStr = f"{IP}"

    # determine CPU load
    cmd = "top -bn1 | grep load | awk '{printf \"%.2f%%\", $(NF-2)}'"
    try:
        CPU = subprocess.check_output(cmd, shell=True).decode()
    except:
        CPU = "unknown"

    # determine mem useage
    cmd = "free -m | awk 'NR==2{printf \"%s/%sMB %.2f%%\", $3,$2,$3*100/$2 }'"
    try:
        MemUsage = subprocess.check_output(cmd, shell=True).decode()
    except:
        MemUsage = "unknown"

    # determine disk util
    cmd = "df -h | awk '$NF==\"/\"{printf \"%d/%dGB %s\", $3,$2,$5}'"
    try:
        Disk = subprocess.check_output(cmd, shell=True).decode()
    except:
        Disk = "unknown"

    # determine temp
    try:
        tempI = int(open('/sys/class/thermal/thermal_zone0/temp').read())
    except:
        tempI = "unknown"

    if tempI > 1000:
        tempI = tempI/1000
    tempStr = "%sC" % str(round(tempI, 1))

    # determine uptime
    cmd = "uptime -p | sed -r 's/up|,//g' | sed -r 's/\s*week[s]?/w/g' | sed -r 's/\s*day[s]?/d/g' | sed -r 's/\s*hour[s]?/h/g' | sed -r 's/\s*minute[s]?/m/g'"
    try:
        uptime = subprocess.check_output(cmd, shell=True).decode().strip()
    except:
        uptime = "unknown"

    uptimeStr = f"{uptime}"

    results = {
        "IP":ipStr,
        "CPU":str(CPU),
        "RAM":str(MemUsage),
        "DISK":str(Disk),
        "CPU_TEMP":tempStr,
        "UPTIME":uptimeStr
    }

    return results

@bp.route('/stream')
def stream():
    return get_stats()