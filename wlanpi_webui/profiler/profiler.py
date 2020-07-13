import os, glob
from datetime import datetime
from pathlib import Path

from flask import render_template, current_app, request, safe_join, send_file
from wlanpi_webui.profiler import bp


root_dir = "/var/www/html/"
profiler_dir = "/var/www/html/profiler/"


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
                modifytime = datetime.fromtimestamp(os.path.getmtime(_file)).strftime(
                    "%Y-%m-%d %H:%M:%S%z" #"%Y-%m-%d %H:%M"
                )
                if any(x in _file for x in [".pcap", ".pcapng"]):
                    files.append((_file, modifytime, ""))
                if any(x in _file for x in [".txt"]):
                    files.append((_file, modifytime, Path(_file).read_text()))
                if ".csv" in _file:
                    reports.append((_file, modifytime, ""))
    result = []
    seen = {}
    try:
        for client, date, contents in files:
            client = client.replace(root_dir, "")
            friendly = client.replace("profiler/clients/", "")
            if len(friendly.split("/")) == 2:
                defolder, friendly = friendly.split("/")
                if defolder not in seen:
                    seen[defolder] = []
                if contents:
                    seen[defolder].append(
                        "&nbsp;&nbsp;{0} -- <a href='#_{4}' uk-toggle>{3}</a><div id='_{4}' class='uk-modal-container' uk-modal><div class='uk-modal-dialog uk-modal-body'><h2 class='uk-modal-title'>{3}</h2><button class='uk-modal-close-default' type='button' uk-close></button><pre>{5}</pre><div class='uk-modal-footer uk-text-right'><button class='uk-button uk-button-default uk-modal-close' type='button'>Cancel</button> <a href='{1}{2}'><button class='uk-button uk-button-primary' type='button'>Save</button></a></div></div></div>".format(
                            date,
                            request.url_root,
                            client,
                            friendly,
                            friendly.replace(".txt", "").replace(".", ""),
                            contents,
                        )
                    )
                else:
                    seen[defolder].append(
                        "&nbsp;&nbsp;{0} -- <a href='{1}{2}'>{3}</a>".format(
                            date, request.url_root, client, friendly
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
            friendly = report.replace("profiler/reports/", "")
            result.append(
                "&nbsp;&nbsp;{0} -- <a href='{1}{2}'>{3}</a>".format(
                    date, request.url_root, report, friendly
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


@bp.route("/profiler")
def profiler():
    """ route setup for /profiler """
    links = profiler_file_listing()
    listing = "<br />".join(links)
    return render_template(
        "public/profiler.html",
        wlanpi_version=current_app.config['WLANPI_VERSION'],
        webui_version=current_app.config['WEBUI_VERSION'],  
        title="profiler",
        content=listing,
    )


@bp.route("/profiler/<path:filename>")
def get_profiler_results(filename):
    """ handle when user downloading profiler results """
    safe_path = safe_join(profiler_dir, filename)
    print(safe_path)
    try:
        return send_file(safe_path, as_attachment=True)
    except FileNotFoundError:
        abort(404)
