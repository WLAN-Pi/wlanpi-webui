import glob
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from flask import abort, current_app, render_template, request, send_file
from flask_minify import decorators as minify_decorators
from werkzeug.utils import safe_join

from wlanpi_webui.profiler import bp
from wlanpi_webui.utils import (is_htmx, run_command, start_stop_service,
                                system_service_running_state,
                                systemd_service_message, wlanpi_core_warning)

getting_started = """
<ul uk-accordion="">
<li>
<a class="uk-accordion-title" href="#">Getting started</a>
<div class="uk-accordion-content">
<p>Starting the profiler system process:</p>
<ul class="uk-list uk-list-hyphen">
<li>Install a supported WLAN NIC into the WLAN Pi.</li>
<li>There are a few different ways to start profiler: WebUI, FPMS, or CLI.</li>
<li>WebUI: Start the profiler process by tapping <kbd>START</kbd> on the profiler dropdown nav.</li>
<li>FPMS: Start the profiler process by navigating the Front Panel Menu System: <kbd>Menu &gt; Apps &gt; Profiler &gt; Start</kbd></li>
<li>CLI: Run profiler manually as a power user: <kbd>$ profiler -h</kbd>to print usage.</li>
</ul>
<p>Profiling a client:</p>
<ul class="uk-list uk-list-hyphen">
<li>On start a fake soft AP will broadcast (default SSID is <kbd>Profiler xxx</kbd> where <kbd>xxx</kbd> is the last 3 characters of the eth0 MAC address).</li>
<li>Connect your client by QR code on FPMS or enter any random 8 characters for the PSK.</li>
<li>The client will expectedly fail authentication but we should receive the association request.</li>
</ul>
<p>After associating a client to the profiler SSID, refresh this page to view the result.</p>
</div>
</li>
</ul>
"""


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


def get_profiler_file_listing_html(target) -> list:
    """Function to generate custom html file listing for a specific result"""
    files = get_files()
    html = ""
    try:
        if len(files) == 0:
            return None
        for profile in files:
            client = profile.filepath.replace(current_app.config["FILES_ROOT_DIR"], "")
            friendly = client.replace("profiler/clients/", "")
            friendly.rsplit(".", 1)[0]
            profile.modifytime
            if len(friendly.split("/")) == 2:
                defolder, friendly = friendly.split("/")
                friendly.rsplit(".", 1)[0]
                if profile.profiletype == ProfileResultType.TEXT:
                    profile_stub = f"{friendly.split('/')[-1].replace('.txt', '').replace('.', '')}"
                    div_id = f"profile_{profile_stub}"

                    if target == profile_stub:
                        html = """<div id="{profile_div_id}" class="uk-modal uk-modal-container" style="display:block;">
<div class="uk-modal-dialog uk-modal-body">
<h2 class="uk-modal-title">{modal_title}</h2>
<pre>{profile_content}</pre>
<div class='uk-modal-footer uk-text-right'>
<form _="on submit take .uk-open from #{profile_div_id}">
<button 
id="cancelButton"
type="button" 
class="uk-button uk-button-default" 
_="on click take .uk-open from #{profile_div_id} wait 200ms then remove #{profile_div_id}">Close</button>
<a href='{content_url}'><button class='uk-button uk-button-secondary' type='button'>Save</button></a>
</form>
</div>
</div>
</div>""".format(
                            profile_div_id=div_id,
                            modal_title=friendly,
                            profile_content=profile.content,
                            content_url=f"{request.url_root}{client}",
                        )
                        break
    except Exception as error:
        raise Exception(
            "ERROR: problem building profile html results for {profile}\n{error}".format(
                profile=profile, error=error
            )
        )
    return html


def get_profiler_files_listing_html() -> list:
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
                    profile_stub = f"{friendly.split('/')[-1].replace('.txt', '').replace('.', '')}"
                    div_id = f"profile_{profile_stub}"
                    tooltip = f'View text report for {client.split("/")[-1]}'
                    text = """<button 
class="uk-button uk-button-default uk-button-small" 
hx-get="/profiler/profile?profile={stub}" 
hx-trigger="click" 
hx-target="#profiler-modals"
uk-tooltip="{tip}"
hx-indicator=".progress"
_="on htmx:afterOnLoad wait 10ms then add .uk-open to #{id}">profile</button>""".format(
                        stub=profile_stub, id=div_id, tip=tooltip
                    )

                pcap = ""
                if profile.profiletype == ProfileResultType.PCAP:
                    pcap = """<a href='{0}{1}'>
<button class='uk-button uk-button-default uk-button-small' uk-tooltip='{2}'>pcap</button>
</a>""".format(
                        request.url_root,
                        client,
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

        results.append(getting_started)
        results.append(
            """<div><h3 class="uk-h3">Profiles</h3></div>
<p>Output below is sorted by last modification timestamps. Most recent profiles will show at the top.</p>
<div class="uk-overflow-auto"><table class="uk-table uk-table-small uk-table-responsive">
<thead></thead><tbody>"""
        )
        heading_appended = False
        for key, attrs in seen_hash.items():
            if not heading_appended:
                results.append(
                    """<tr><th class="uk-width-small uk-text-nowrap">Last Modification</th>
<th class="uk-width-small uk-text-no-wrap">Client MAC</th>
<th class="uk-width-small">Band</th>
<th class="uk-width-small">Text Report</th>
<th>Download</th></tr>"""
                )
                heading_appended = True
            client_mac_value = key.split("_")[0]
            if "diff" in attrs.content.text:
                client_mac_value += " (diff)"
            results.append(
                f'<tr><td class="uk-width-small uk-text-nowrap">{attrs.modifytime}</td><td class="uk-width-small uk-text-nowrap">{client_mac_value}</td><td>{attrs.band}</td><td>{attrs.content.text}</td><td>{attrs.content.pcap}</td></tr>'
            )
        results.append("</tbody></table></div>")

        if reports:
            results.append(
                """<div class="uk-flex uk-flex-column"><h4>Reports</h4></div>
<div class="uk-overflow-auto"><table class="uk-table uk-table-small uk-table-responsive">
<thead><tr><th class="uk-width-small uk-text-nowrap">Last Modification</th><th class="uk-width-small">Report</th><th>Download</th></tr></thead><tbody>"""
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
            "ERROR: problem in get_profiler_files_listing_html() building link results {0}\n{1}".format(
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


def get_profiler_files_to_purge() -> list:
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
    files = get_profiler_files_to_purge()
    inner = "\r\n".join([f"rm {file}" for file in files])
    content = """<div>
<p>The <tt>webui</tt> process does not have permission to remove files.</p>
<p>To purge profiler files, open a root shell and paste in the following:<br /><pre>{0}</pre></p>
</div>""".format(
        inner
    )
    if not files:
        content = '<div class="uk-alert-danger" uk-alert><p>No profiler files found on host to generate purge script.</p></div>'
    resp_data = {"content": content}
    if is_htmx(request):
        return render_template("/partials/profiler.html", **resp_data)
    else:
        return render_template("/extends/profiler.html", **resp_data)


@bp.route("/profiler/profile")
def profile():
    """Profile"""
    # if key doesn't exist, returns None
    profile = request.args.get("profile")
    html = get_profiler_file_listing_html(profile)
    if is_htmx(request):
        return html


@bp.route("/profiler/profiles")
def profiler():
    """Profiles"""
    custom_output = get_profiler_files_listing_html()
    if not custom_output:
        content = """
        {0}
        <div class="uk-alert-danger" uk-alert><p>No client profiles found on host. See the getting started instructions above to get started.</p></div>
        """.format(
            getting_started
        )
    else:
        content = "".join(custom_output)
        content += """
<div class="uk-flex uk-flex-center">
<a hx-get="/profiler/profiles" hx-target="#content" hx-trigger="click" hx-indicator=".progress" hx-push-url="true"
hx-swap="innerHTML" uk-icon="icon: refresh; ratio: 2" uk-tooltip="Refresh page" class="uk-icon-button"></a>
</div>
  """
    resp_data = {"content": content}
    if is_htmx(request):
        return render_template("/partials/profiler.html", **resp_data)
    else:
        return render_template("/extends/profiler.html", **resp_data)


@bp.route("/profiler/<path:filename>")
def get_profiler_results(filename):
    """Handle when user downloads profiler results"""
    safe_path = safe_join(current_app.config["PROFILER_DIR"], filename)
    try:
        return send_file(safe_path, as_attachment=True)
    except FileNotFoundError:
        abort(404)
    except IsADirectoryError:
        abort(405)


@bp.route("/<task>profiler")
def start_stop_profiler(task):
    if is_htmx(request):
        core_status = system_service_running_state("wlanpi-core")
        if core_status:
            start_stop_service(task, "wlanpi-profiler")
        else:
            return wlanpi_core_warning
    return "", 204


@bp.route("/profiler/side_menu")
@minify_decorators.minify(html=True)
def profiler_side_menu():
    if is_htmx(request):
        profiler_message = systemd_service_message("wlanpi-profiler")
        profiler_status = system_service_running_state("wlanpi-profiler")
        if profiler_status:
            # active
            profiler_task_url = "/stopprofiler"
            profiler_task_anchor_text = "STOP"
        else:
            # not active
            profiler_task_url = "/startprofiler"
            profiler_task_anchor_text = "START"
        args = {
            "profiler_message": profiler_message.replace("wlanpi-", ""),
            "profiler_task_url": profiler_task_url,
            "profiler_task_anchor_text": profiler_task_anchor_text,
        }
        html = """<li class="uk-nav-header">{profiler_message}</li>
<li><a hx-get="{profiler_task_url}"
        hx-indicator=".progress">{profiler_task_anchor_text}</a></li>
<li><a hx-get="/profiler/profiles"
    hx-target="#content"
    hx-swap="innerHTML"
    hx-push-url="true"
    hx-indicator=".progress">PROFILES</a></li>
<li><a hx-get="/profiler/purge"
    hx-target="#content"
    hx-swap="innerHTML"
    hx-push-url="true"
    hx-indicator=".progress">PURGE DATA</a></li>""".format(
            **args
        )
        return html


@bp.route("/profiler/main_menu")
@minify_decorators.minify(html=True)
def profiler_main_menu():
    if is_htmx(request):
        profiler_message = systemd_service_message("wlanpi-profiler")
        profiler_status = system_service_running_state("wlanpi-profiler")
        profiler_ssid = run_command(["cat", "/run/wlanpi-profiler.ssid"])
        if "No such file" not in profiler_ssid:
            qrcode_spec = "WIFI:S:{0};T:WPA;P:{1};;".format(profiler_ssid, "0123456789")
            profiler_ssid = """<li>SSID: {profiler_ssid}</li>
<div id="qrcode" style="width:200px; height:200px;"></div>
<script type="text/javascript">
    new QRCode(document.getElementById("qrcode"), "{qrcode_spec}");
</script>""".format(
                profiler_ssid=profiler_ssid, qrcode_spec=qrcode_spec
            )
        else:
            profiler_ssid = ""
        if profiler_status:
            # active
            profiler_task_url = "/stopprofiler"
            profiler_task_anchor_text = "STOP"
        else:
            # not active
            profiler_task_url = "/startprofiler"
            profiler_task_anchor_text = "START"
        args = {
            "profiler_message": profiler_message.replace("wlanpi-", ""),
            "profiler_task_url": profiler_task_url,
            "profiler_task_anchor_text": profiler_task_anchor_text,
            "profiler_ssid": profiler_ssid,
        }
        html = """<li class="uk-nav-header">{profiler_message}</li>
{profiler_ssid}
<li><a hx-get="{profiler_task_url}"
        hx-indicator=".progress">{profiler_task_anchor_text}</a></li>
<li class="uk-nav-divider"></li>
<li><a hx-get="/profiler/profiles"
    hx-target="#content"
    hx-swap="innerHTML"
    hx-push-url="true"
    hx-indicator=".progress">PROFILES</a></li>
<li><a hx-get="/profiler/purge"
    hx-target="#content"
    hx-swap="innerHTML"
    hx-push-url="true"
    hx-indicator=".progress">PURGE DATA</a></li>""".format(
            **args
        )
        return html
