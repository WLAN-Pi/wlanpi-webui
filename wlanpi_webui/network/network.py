import os
import queue
import subprocess
import threading

from flask import render_template

from wlanpi_webui.network import bp


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

    script_results = dumpQueue(FPMS_QUEUE)
    for result in script_results:
        if "reachability" in str(result):
            reachability = result[1]

        if "publicip" in str(result):
            publicip = result[1]

        if "ipconfig" in str(result):
            ipconfig = result[1]

    return render_template(
        "public/partial_network.html",
        reachability=reachability,
        publicip=publicip,
        ipconfig=ipconfig,
        lldp=lldp,
        cdp=cdp,
    )
