import os, subprocess, queue, threading
from flask import render_template, current_app
from wlanpi_webui.network import bp


@bp.route("/network")
def network():
    """  fpms screen """
    FPMS_QUEUE = queue.Queue()

    def storeInQueue(f):
        def wrapper(*args):
            FPMS_QUEUE.put(f(*args))

        return wrapper

    @storeInQueue
    def get_script_results(script):
        name = script.strip().split("/")[-1]
        return name, run(script)

    def read(path: str) -> str:
        result = ""
        if os.path.exists(path):
            content = Path(path).read_text()
        else:
            content = "Cannot find file"
        # result = '<br />'.join([i.replace('\n', '') for i in content.readlines()])
        result += f"{content}: R_OK {os.access(path, os.R_OK)}; W_OK {os.access(path, os.W_OK)}; X_OK {os.access(path, os.X_OK)}; F_OK {os.access(path, os.F_OK)}"
        return result

    def run(script: str) -> str:
        result = ""
        if os.path.exists(script):
            content = subprocess.run(script, capture_output=True)
            result = str(content.stdout, "utf-8")
            result = result.replace("\n", "<br />")
        else:
            result = f"{script.strip().split('/')[-1]} does not exist"
        return result

    def dumpQueue(queue):
        results = []
        while not queue.empty():
            results.append(queue.get())
        return results

    reachability = (
        "/usr/share/fpms/BakeBit/Software/Python/scripts/networkinfo/reachability.sh"
    )
    publicip = "/usr/share/fpms/BakeBit/Software/Python/scripts/networkinfo/publicip.sh"
    ipconfig = "/usr/share/fpms/BakeBit/Software/Python/scripts/networkinfo/ipconfig.sh"

    threads = []
    for script in [reachability, publicip, ipconfig]:
        thread = threading.Thread(target=get_script_results, args=(script,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    cdpneigh = "/tmp/cdpneigh.txt"
    lldpneigh = "/tmp/lldpneigh.txt"

    def readlines(_file):
        out = ""
        with open(_file, "r") as reader:
            for line in reader.readlines():
                line = line.replace("\n", "<br />")
                out += line
        return out

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
        "public/network.html",
        title="network",
        wlanpi_version=current_app.config["WLANPI_VERSION"],
        webui_version=current_app.config["WEBUI_VERSION"],
        reachability=reachability,
        publicip=publicip,
        ipconfig=ipconfig,
        lldp=lldp,
        cdp=cdp,
    )
