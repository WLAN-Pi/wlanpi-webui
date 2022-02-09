import glob
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from flask import (abort, current_app, render_template, request, safe_join,
                   send_file)

from wlanpi_webui.profiler import bp


class ProfileResultType(Enum):
    """File types for profiler files"""

    TEXT = "text"
    PCAP = "pcap"
    REPORT = "report"
    JSON = "json"
    UNKNOWN = "unknown"


@dataclass
class ProfileContent:
    """Class for storing custom html"""

    text: str
    pcap: str


@dataclass
class Profile:
    """Class for storing profiler data"""

    client: str
    friendly: str
    modifytime: str
    profiletype: ProfileResultType
    band: str
    content: ProfileContent


@dataclass
class ProfilerFileAttributes:
    """Class for storing profiler file attributes"""

    filepath: str
    modifytime: str
    band: str
    content: str
    profiletype: ProfileResultType


def get_profiler_file_listing_html() -> list:
    """Function to generate custom html file listing for profiler results"""
    files = get_files()
    reports = []
    results = []
    seen_hash = {}
    try:
        if len(files) == 0:
            return None
        for profile in files:
            client = profile.filepath.replace(current_app.config["FILES_ROOT_DIR"], "")
            friendly = client.replace("profiler/clients/", "")
            _key = friendly.rsplit(".", 1)[0]
            modifytime = profile.modifytime
            if len(friendly.split("/")) == 2:
                defolder, friendly = friendly.split("/")
                _key = friendly.rsplit(".", 1)[0]
                text = ""
                if profile.profiletype == ProfileResultType.TEXT:
                    div_id = friendly.split("/")[-1].replace(".txt", "")
                    clean_div_id = div_id.replace(".txt", "").replace(".", "")
                    text = "<a href='#_{4}' uk-toggle><button class='uk-button uk-button-default uk-button-small' uk-tooltip='{6}'>profile</button></a><div id='_{4}' class='uk-modal-container' uk-modal><div class='uk-modal-dialog uk-modal-body'><h2 class='uk-modal-title'>{3}</h2><button class='uk-modal-close-default' type='button' uk-close></button><pre>{5}</pre><div class='uk-modal-footer uk-text-right'><button class='uk-button uk-button-default uk-modal-close' type='button'>Cancel</button> <a href='{1}{2}'><button class='uk-button uk-button-primary' type='button'>Save</button></a></div></div></div>".format(
                        modifytime,
                        request.url_root,
                        client,
                        div_id,
                        clean_div_id,
                        profile.content,
                        f'View text report for {client.split("/")[-1]}',
                    )

                pcap = ""
                if profile.profiletype == ProfileResultType.PCAP:
                    pcap = "<a href='{1}{2}'><button class='uk-button uk-button-default uk-button-small' uk-tooltip='{4}'>pcap</button></a>".format(
                        modifytime,
                        request.url_root,
                        client,
                        friendly,
                        f'Download {client.split("/")[-1]} ',
                    )

                if _key not in seen_hash.keys():
                    _profile = Profile(
                        client,
                        friendly,
                        modifytime,
                        profile.profiletype,
                        profile.band,
                        ProfileContent(text, pcap),
                    )
                    seen_hash[_key] = _profile
                else:
                    if pcap:
                        seen_hash[_key].content.pcap = pcap
                    if text:
                        seen_hash[_key].content.text = text
            if profile.profiletype == ProfileResultType.REPORT:
                reports.append(profile)

        results.append(
            '<div uk-alert><a class="uk-alert-close" uk-close></a><h3>Note</h3><p>Output below is sorted by last modification timestamps. Most recent profiles will show on top.</p></div>'
        )
        results.append('<div><h3 class="uk-h3">Results</h3>')
        results.append("<h4>Profiles</h4></div>")
        results.append(
            '<div class="uk-overflow-auto"><table class="uk-table uk-table-small uk-table-responsive">'
        )
        results.append("<thead>")
        for _key, _attrs in seen_hash.items():
            results.append(
                '<tr><th class="uk-width-small uk-text-nowrap">Last Modification</th><th class="uk-width-small uk-text-no-wrap">Client MAC</th><th class="uk-width-small">Band</th><th class="uk-width-small">Text Report</th><th>Download</th></tr>'
            )
            break
        results.append("</thead>")
        results.append("<tbody>")
        for key, attrs in seen_hash.items():
            client_mac_value = key.split("_")[0]
            if "diff" in attrs.content.text:
                client_mac_value += " (diff)"
            results.append(
                f'<tr><td class="uk-width-small uk-text-nowrap">{attrs.modifytime}</td><td class="uk-width-small uk-text-nowrap">{client_mac_value}</td><td>{attrs.band}</td><td>{attrs.content.text}</td><td>{attrs.content.pcap}</td></tr>'
            )
        results.append("</tbody></table></div>")

        if reports:
            results.append('<div class="uk-flex uk-flex-column"><h4>Reports</h4></div>')
            results.append(
                '<div class="uk-overflow-auto"><table class="uk-table uk-table-small uk-table-responsive">'
            )
            results.append(
                '<thead><tr><th class="uk-width-small uk-text-nowrap">Last Modification</th><th class="uk-width-small">Report</th><th>Download</th></tr></thead><tbody>'
            )
            for attrs in reports:
                report = attrs.filepath.replace(
                    current_app.config["FILES_ROOT_DIR"], ""
                )
                friendly = report.replace("profiler/reports/", "")
                results.append(
                    "<tr><td class='uk-width-small uk-text-nowrap'>{0}</td><td class='uk-width-small uk-text-nowrap'>{3}</td><td><a href='{1}{2}'><button class='uk-button uk-button-default uk-button-small' uk-tooltip='Download report for {3}'>CSV</button></a></td></tr>".format(
                        attrs.modifytime,
                        request.url_root,
                        report,
                        friendly.replace(".csv", "").replace("profiler-", ""),
                    )
                )
            results.append("</tbody></table></div>")
    except Exception as error:
        return [
            "ERROR: problem building profiler link results {0}\n{1}".format(
                error, files
            )
        ]
    return results


def get_files() -> list:
    """Retrieve all profiler files (.pcap, .txt, .csv) on local system"""
    _glob = glob.glob(f"{current_app.config['PROFILER_DIR']}**", recursive=True)
    try:
        _glob.sort(key=os.path.getmtime, reverse=True)
    except Exception:
        pass
    files = []
    for _file in _glob:
        if not os.path.isdir(_file):
            if os.path.isfile(_file):
                profiletype = ProfileResultType.UNKNOWN
                modifytime = datetime.fromtimestamp(os.path.getmtime(_file)).strftime(
                    "%Y-%m-%d %H:%M:%S%z"  # "%Y-%m-%d %H:%M"
                )
                band = ""
                if any(x in _file for x in [".pcap"]):
                    try:
                        band = _file.split("_")[1].split(".pcap")[0]
                    except IndexError:
                        pass
                    profiletype = ProfileResultType.PCAP
                content = ""
                if any(x in _file for x in [".txt"]):
                    try:
                        band = _file.split("_")[1].split(".txt")[0]
                    except IndexError:
                        pass
                    profiletype = ProfileResultType.TEXT
                    content = Path(_file).read_text()
                if ".csv" in _file:
                    profiletype = ProfileResultType.REPORT
                if profiletype is not ProfileResultType.UNKNOWN:
                    pfa = ProfilerFileAttributes(
                        _file, modifytime, band, content, profiletype
                    )
                    files.append(pfa)
    return files


def purge_all_profiler_files() -> list:
    """Provide a purge list for all profiler files"""
    files = []
    _glob = glob.glob(f"{current_app.config['PROFILER_DIR']}**", recursive=True)
    for _file in _glob:
        if not os.path.isdir(_file):
            if os.path.isfile(_file):
                if any(x in _file for x in [".pcap", ".pcapng"]):
                    files.append(_file)
                if any(x in _file for x in [".txt"]):
                    files.append(_file)
                if ".csv" in _file:
                    files.append(_file)
                if ".json" in _file:
                    files.append(_file)
    return files


@bp.route("/profiler/purge")
def purge():
    """Purges profiler files"""
    files = purge_all_profiler_files()
    content = "\r\n".join([f"rm {file}" for file in files])
    listing = f"<div><p>The <tt>wlanpi-webui</tt> process does not have permission to remove files.</p><p>To purge profiler files, open a root shell and paste in the following:<br /><pre>{content}</pre></p></div>"
    if not files:
        listing = '<div class="uk-alert-danger" uk-alert><p>No profiler files found on host to generate purge script.</p></div>'
    return render_template(
        "public/profiler.html",
        hostname=current_app.config["HOSTNAME"],
        title=current_app.config["TITLE"],
        wlanpi_version=current_app.config["WLANPI_VERSION"],
        webui_version=current_app.config["WEBUI_VERSION"],
        content=listing,
    )


@bp.route("/profiler")
def profiler():
    """Route setup for /profiler"""
    custom_output = get_profiler_file_listing_html()
    if not custom_output:
        _content = '<div class="uk-alert-danger" uk-alert><p>No client profiles found on host. See the getting started instructions above to get started.</p></div>'
    else:
        _content = "".join(custom_output)
        _content += '<br/><div class="uk-flex uk-flex-center"><a href="" uk-icon="icon: refresh; ratio: 2" uk-tooltip="Refresh page" class="uk-icon-button"></a></div>'
    return render_template(
        "public/profiler.html",
        hostname=current_app.config["HOSTNAME"],
        title=current_app.config["TITLE"],
        wlanpi_version=current_app.config["WLANPI_VERSION"],
        webui_version=current_app.config["WEBUI_VERSION"],
        content=_content,
    )


@bp.route("/profiler/<path:filename>")
def get_profiler_results(filename):
    """Handle when user downloading profiler results"""
    safe_path = safe_join(current_app.config["PROFILER_DIR"], filename)
    try:
        return send_file(safe_path, as_attachment=True)
    except FileNotFoundError:
        abort(404)
    except IsADirectoryError:
        abort(405)
