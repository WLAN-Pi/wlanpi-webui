#!/usr/bin/python3
# -*- coding: utf-8 -*-
#

"""
wlanpi_webui
~~~~~~~~

a custom local WebUI made for the WLAN Pi
"""

import glob, logging, os, queue, subprocess, threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    safe_join,
    send_file,
    send_from_directory,
)

from .__version__ import __version__


def create_app(test_config=None):
    """ Create Flask application """
    app = Flask(__name__, instance_relative_config=True)

    if test_config is None:
        app.config.from_pyfile("config.py", silent=True)
    else:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    print(f"ENV is set to: {app.config['ENV']}")

    app.url_map.strict_slashes = False

    root_dir = "/var/www/html"
    profiler_dir = "/var/www/html/profiler/"

    webui_version = f"{__version__}"
    wlanpi_release_file = "/etc/wlanpi-release"
    wlanpi_version = ""
    try:
        with open(wlanpi_release_file) as _file:
            lines = _file.read().splitlines()
            for line in lines:
                if "VERSION" in line:
                    wlanpi_version = "{0}".format(
                        line.split("=")[1].replace('"', "").strip()
                    )
    except OSError:
        pass

    @app.route("/fpms")
    def fpms():
        """  fpms screen """
        FPMS_QUEUE = queue.Queue()

        def storeInQueue(f):
            def wrapper(*args):
                FPMS_QUEUE.put(f(*args))
            return wrapper

        @storeInQueue
        def get_script_results(script):
            name = script.strip().split('/')[-1]
            return name, run(script)

        def read(path: str) -> str:
            result = ""
            if os.path.exists(path):
                content = Path(path).read_text()
            else:
                content = "Cannot find file"
            #result = '<br />'.join([i.replace('\n', '') for i in content.readlines()])
            result += f"{content}: R_OK {os.access(path, os.R_OK)}; W_OK {os.access(path, os.W_OK)}; X_OK {os.access(path, os.X_OK)}; F_OK {os.access(path, os.F_OK)}"
            return result

        def run(script: str) -> str:
            result = ""
            if os.path.exists(script):
                content = subprocess.run(script, capture_output=True)
                result = str(content.stdout, 'utf-8')
                result = result.replace('\n', '<br />')
            else:
                result = f"{script.strip().split('/')[-1]} does not exist"
            return result

        def dumpQueue(queue):
            results = []
            while not queue.empty():
                results.append(queue.get())
            return results

        reachability = "/usr/share/fpms/BakeBit/Software/Python/scripts/networkinfo/reachability.sh"
        publicip = "/usr/share/fpms/BakeBit/Software/Python/scripts/networkinfo/publicip.sh"
        ipconfig = "/usr/share/fpms/BakeBit/Software/Python/scripts/networkinfo/ipconfig.sh"

        threads = []
        for script in [reachability, publicip, ipconfig]:
            thread = threading.Thread(target=get_script_results, args=(script, ))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        #lldp = read("/tmp/fpms/lldpneigh.txt")
        #cdp = read("/tmp/cdpneigh.txt")

        script_results = dumpQueue(FPMS_QUEUE)
        for result in script_results:
            if "reachability" in str(result):
                reachability = result[1]

            if "publicip" in str(result):
                publicip = result[1]

            if "ipconfig" in str(result):
                ipconfig = result[1]

        return render_template(
            "fpms.html",
            wlanpi_version=wlanpi_version,
            webui_version=webui_version,
            title="fpms",
            reachability=reachability,
            publicip=publicip,
            ipconfig=ipconfig,
            #lldp=lldp,
            #cdp=cdp,
        )

    @app.errorhandler(404)
    def page_not_found(error):
        """ 404 errors """
        return (
            render_template(
                "error.html",
                title="error",
                wlanpi_version=wlanpi_version,
                webui_version=webui_version,
            ),
            404,
        )

    @app.route("/static/img/<path:filename>")
    def img(filename):
        try:
            return send_from_directory(f"{app.root_path}/static/img/", filename)
        except FileNotFoundError:
            abort(404)

    def profiler_file_listing():
        """ custom file listing for profiler results """
        _glob = glob.glob(f"{profiler_dir}**", recursive=True)
        try:
            _glob.sort(key=os.path.getmtime, reverse=True)
        except Exception:
            pass
        reports = []
        files = []
        for _file in _glob:
            if not os.path.isdir(_file):
                if os.path.isfile(_file):
                    modifytime = datetime.fromtimestamp(
                        os.path.getmtime(_file)
                    ).strftime("%Y-%m-%d %H:%M")
                    if any(x in _file for x in [".pcap", ".pcapng"]):
                        files.append((_file, modifytime, ""))
                    if any(x in _file for x in [".txt"]):
                        files.append((_file, modifytime, Path(_file).read_text()))
                    if ".csv" in _file:
                        reports.append((_file, modifytime, ""))
        base = request.host.split(":")[0]
        result = []
        seen = {}
        try:
            for client, date, contents in files:
                client = client.replace(root_dir, "")
                friendly = client.replace("/profiler/clients/", "")
                print(friendly)
                if len(friendly.split("/")) == 2:
                    defolder, friendly = friendly.split("/")
                    if defolder not in seen:
                        seen[defolder] = []
                    if contents:
                        seen[defolder].append(
                            "&nbsp;&nbsp;{0}...<a href='#_{4}' uk-toggle>{3}</a><div id='_{4}' class='uk-modal-container' uk-modal><div class='uk-modal-dialog uk-modal-body'><h2 class='uk-modal-title'>{3}</h2><button class='uk-modal-close-default' type='button' uk-close></button><pre>{5}</pre><div class='uk-modal-footer uk-text-right'><button class='uk-button uk-button-default uk-modal-close' type='button'>Cancel</button> <a href='http://{1}{2}'><button class='uk-button uk-button-primary' type='button'>Save</button></a></div></div></div>".format(
                                date,
                                base,
                                client,
                                friendly,
                                friendly.replace(".txt", "").replace(".", ""),
                                contents,
                            )
                        )
                    else:
                        seen[defolder].append(
                            "&nbsp;&nbsp;{0}...<a href='http://{1}{2}'>{3}</a>".format(
                                date, base, client, friendly
                            )
                        )
            for key, value in seen.items():
                result.append(f"{key}:")
                for e in value:
                    result.append(e)
            if reports:
                result.append("reports:")
            for report, date, contents in reports:
                report = report.replace(root_dir, "")
                friendly = report.replace("/profiler/reports/", "")
                result.append(
                    "&nbsp;&nbsp;{0}...<a href='http://{1}{2}'>{3}</a>".format(
                        date, base, report, friendly
                    )
                )
        except Exception as error:
            print(error)
            return [
                "ERROR: problem building profiler link results {0}\n{1}".format(
                    error, files
                )
            ]
        return result

    @app.route("/profiler")
    def profiler():
        """ route setup for /profiler """
        links = profiler_file_listing()
        print(links)
        listing = "<br />".join(links)
        return render_template(
            "profiler.html",
            wlanpi_version=wlanpi_version,
            webui_version=webui_version,
            title="profiler",
            content=listing,
        )

    @app.route("/profiler/<path:filename>")
    def get_profiler_results(filename):
        """ handle when user downloading profiler results """
        safe_path = safe_join(profiler_dir, filename)
        print(safe_path)
        try:
            return send_file(safe_path, as_attachment=True)
        except FileNotFoundError:
            abort(404)

    @app.route("/docs")
    def docs():
        """ handle docs.wlanpi.com redirect """
        return redirect("https://docs.wlanpi.com")

    @app.route("/")
    @app.route("/speedtest")
    def speedtest():
        """ handle speedtest redirect """
        speed_test = "8080"
        base = request.host.split(":")[0]
        iframe = f"http://{base}:{speed_test}/speedtest.html"
        print(iframe)
        return render_template(
            "speedtest.html",
            wlanpi_version=wlanpi_version,
            webui_version=webui_version,
            title="speedtest",
            iframe=iframe,
        )

    @app.route("/speedtest2")
    def speedtest2():
        """ handle speedtest redirect """
        speed_test = "8080"
        base = request.host.split(":")[0]
        iframe = f"http://{base}:{speed_test}/wip/speedtest.html"
        print(iframe)
        return render_template(
            "speedtest.html",
            wlanpi_version=wlanpi_version,
            webui_version=webui_version,
            title="speedtest",
            iframe=iframe,
        )


    @app.route("/cockpit")
    def cockpit():
        """ handle cockpit redirect """
        cockpit_port = "9090"
        base = request.host.split(":")[0]
        return redirect(f"http://{base}:{cockpit_port}")

    return app
