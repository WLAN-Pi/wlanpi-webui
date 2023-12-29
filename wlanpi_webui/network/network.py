import os
import queue
import subprocess
import threading
import json

from flask import render_template, request

from wlanpi_webui.network import bp
from wlanpi_webui.utils import is_htmx, get_wifi_scan, get_interfaces, set_network

# from json2html import *

@bp.route("/network/setup", methods=('GET', 'POST'))
def netSetup():
    messages = []
    if request.method == "POST":
        form_data = request.form
        
        try:
            body = {
                "interface": form_data["interface"],
                "netConfig": {
                    "ssid": form_data["ssid"],
                    "psk": form_data["psk"],
                    "key_mgmt": form_data["key_mgmt"],
                    "ieee80211w": int(form_data["ieee80211w"])
                },
                "removeAllFirst": (True if form_data["removeAllFirst"] == "true" else False)
            }
        except:
            return "Fail"
            
        result = set_network(body)
        
        try:
            result = json.loads(result)
        except:
            pass
        
        messages.append(result)

    result = get_interfaces()
    
    try:
        result = json.loads(result)
    except:
        return "Error"
    
    interfaces = []
    
    for interface in result["interfaces"]:
        interfaces.append(interface["interface"])
    
    if is_htmx(request):
        return render_template("/partials/network_setup.html", interfaces=interfaces, messages=messages)
    else:
        return render_template("/extends/network_setup.html", interfaces=interfaces, messages=messages)

@bp.route("/network/getscan")
def getscan():
    netScan = get_wifi_scan('wlan0')
    
    try:
        netScan = json.loads(netScan)
    except:
        return "Error"
    
    grouped_scan = []
    unique_ssids = []
    
    for network in netScan["nets"]:
        if ("\0" in network["ssid"]) or (network["ssid"] in [" ", ""]):
            network["ssid"] = "<hidden>"
        if not network["ssid"] in unique_ssids:
            unique_ssids.append(network["ssid"])
    
    idx = 0
    for ssid in unique_ssids:
        grouped_scan.append({"ssid": ssid, "scan": []})
        for network in netScan["nets"]:
            if network["ssid"] == ssid:
                scan = {"bssid": network["bssid"], "wpa": network["wpa"], "wpa2": network["wpa2"], "signal": network["signal"], "freq": network["freq"]}
                grouped_scan[idx]["scan"].append(scan)
        idx += 1
    
    return render_template("netscan_iframe.html", netScan=netScan, groupedScan=grouped_scan)

    
@bp.route("/network")
def network():
    """fpms screen"""
    FPMS_QUEUE = queue.Queue()

    def storeInQueue(f):
        def wrapper(*args):
            FPMS_QUEUE.put(f(*args))

        return wrapper

    @storeInQueue
    def get_script_results(script):
        name = script.strip().split("/")[-1]
        return name, run(script)

    def run(script: str) -> str:
        result = ""
        if os.path.exists(script):
            content = subprocess.run(script, capture_output=True)
            result = str(content.stdout, "utf-8")
            result = result.replace("\n", "<br />")
        else:
            result = f"Error: required {script.strip().split('/')[-1]} not found."
        return result

    def dumpQueue(queue):
        results = []
        while not queue.empty():
            results.append(queue.get())
        return results

    reachability = "/opt/wlanpi-common/networkinfo/reachability.sh"
    publicip = "/opt/wlanpi-common/networkinfo/publicip.sh"
    ipconfig = "/opt/wlanpi-common/networkinfo/ipconfig.sh"

    threads = []
    for script in [reachability, publicip, ipconfig]:
        thread = threading.Thread(target=get_script_results, args=(script,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    def readlines(_file):
        out = ""
        if os.path.exists(_file):
            with open(_file, "r") as reader:
                for line in reader.readlines():
                    line = line.replace("\n", "<br />")
                    out += line
        else:
            out += f"Error: required {_file} not found."
        return out

    cdpneigh = "/tmp/cdpneigh.txt"
    lldpneigh = "/tmp/lldpneigh.txt"

    cdp = readlines(cdpneigh)
    lldp = readlines(lldpneigh)

    # netScan = get_wifi_scan('wlan0')
    # netScan_html = json2html.convert(json=netScan)

    script_results = dumpQueue(FPMS_QUEUE)
    for result in script_results:
        if "reachability" in str(result):
            reachability = result[1]

        if "publicip" in str(result):
            publicip = result[1]

        if "ipconfig" in str(result):
            ipconfig = result[1]

    resp_data = {
        "reachability": reachability,
        "publicip": publicip,
        "ipconfig": ipconfig,
        "lldp": lldp,
        "cdp": cdp,
        # "scan": netScan_html,
    }

    if is_htmx(request):
        return render_template("/partials/network.html", **resp_data)
    else:
        return render_template("/extends/network.html", **resp_data)
