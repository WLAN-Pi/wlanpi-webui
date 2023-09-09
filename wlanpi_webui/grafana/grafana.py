import ssl
import urllib

from flask import current_app, redirect, render_template, request

from wlanpi_webui.grafana import bp
from wlanpi_webui.utils import (get_apt_package_version,
                                get_service_down_message, is_htmx,
                                start_stop_service,
                                system_service_running_state,
                                systemd_service_message)


def try_url(url):
    try:
        context = ssl._create_unverified_context()
        res = urllib.request.urlopen(url, context=context, timeout=1)
    except urllib.error.HTTPError as e:
        if e.code == 502:
            return 502
    return 0


@bp.route("/grafana_url")
def grafana_url():
    base = request.host.split(":")[0]
    return redirect(f"http://{base}/app/grafana", code=302)


@bp.route("/grafana")
def grafana():
    base = request.host.split(":")[0]

    resp_data = {"iframe_url": f"https://{base}/app/grafana"}
    is_running = system_service_running_state("grafana-server")

    current_app.logger.debug(
        "systemctl is-active for grafana-server is %s" % is_running
    )
    service_down_message = get_service_down_message("grafana-server")
    return_code = try_url(resp_data["iframe_url"])
    version = get_apt_package_version("grafana")

    if is_htmx(request):
        # is a htmx request
        if version == "":
            return render_template(
                "/partials/service.html",
                service="Grafana is not installed.",
            )
        if not is_running:
            return render_template(
                "/partials/service.html", service=service_down_message
            )
        if is_running and return_code == 502:
            return render_template(
                "/partials/service.html",
                service="Grafana is running and responded with 502 Bad Gateway. Try again in a few moments.",
            )
        if return_code == 502:
            return render_template(
                "/partials/service.html",
                service="Grafana is not running and responded with 502 Bad Gateway. Start the service, wait a few moments and try again.",
            )
        return render_template("/partials/iframe.html", **resp_data)
    else:
        # not a htmx request
        if version == "":
            return render_template(
                "/extends/service.html",
                service="Grafana is not installed.",
            )
        if not is_running:
            return render_template("/public/service.html", service=service_down_message)
        if is_running and return_code == 502:
            return render_template(
                "/extends/service.html",
                service="Grafana URL responded with HTTP code 502. Try again in a few moments.",
            )
        if return_code == 502:
            return render_template(
                "/extends/service.html",
                service="Grafana URL responded with HTTP code 502. Start the service, wait a few moments, and try again.",
            )
        return render_template("/extends/iframe.html", **resp_data)


@bp.route("/grafana/side_menu")
def grafana_side_menu():
    if is_htmx(request):
        grafana_message = systemd_service_message("grafana-server").replace(
            "-server", ""
        )
        grafana_status = system_service_running_state("grafana-server")
        grafana_scanner_status = system_service_running_state("wlanpi-grafana-scanner")
        if grafana_status:
            # active
            grafana_task_url = "/stopgrafana"
            grafana_task_anchor_text = "STOP"
        else:
            # not active
            grafana_task_url = "/startgrafana"
            grafana_task_anchor_text = "START"

        enabled_data_streams = ""
        disabled_data_streams = ""
        if grafana_scanner_status:
            # active
            enabled_data_streams += """
            <li><span>SCANNER WLAN0 <a hx-get="/stopgrafanascanner"
                                       hx-indicator=".progress"><span uk-icon="close"></span></a></span></li>
            """
        else:
            disabled_data_streams += """
            <li><span>SCANNER WLAN0 <a hx-get="/startgrafanascanner"
                                       hx-indicator=".progress"><span uk-icon="play-circle"></span></a></span></li>
            """
        args = {
            "grafana_message": grafana_message,
            "grafana_task_url": grafana_task_url,
            "grafana_task_anchor_text": grafana_task_anchor_text,
            "grafana_scanner_status": grafana_scanner_status,
            "enabled_data_streams": enabled_data_streams,
            "disabled_data_streams": disabled_data_streams,
        }
        if grafana_status:
            # active
            html = """
            <li class="uk-nav-header">{grafana_message}</li>
            <li><a hx-get="{grafana_task_url}"
                   hx-indicator=".progress">{grafana_task_anchor_text}</a></li>
            <li><a class="uk-link"
                   hx-get="/grafana"
                   hx-target="#content"
                   hx-trigger="click"
                   hx-indicator=".progress"
                   hx-push-url="true"
                   hx-swap="innerHTML">OPEN GRAFANA IFRAME</a></li>
            <li><a class="uk-link" href="/grafana_url" target="_blank">LAUNCH GRAFANA NEW TAB</a></li>
            <li class="uk-parent">
                <li>DATA STREAMS <span data-uk-icon="chevron-down"></span></li>
                <ul class="uk-nav-sub">
                    <li>ENABLED:</li>
                    {enabled_data_streams}
                    <li class="uk-nav-divider"></li>
                    <li>AVAILABLE:</li>
                    {disabled_data_streams}
                </ul>
            </li>
            """.format(
                **args
            )
        else:
            # not active
            html = """
            <li class="uk-nav-header">{grafana_message}</li>
            <li><a hx-get="{grafana_task_url}"
                   hx-indicator=".progress">{grafana_task_anchor_text}</a></li>
            """.format(
                **args
            )
        return html


@bp.route("/grafana/main_menu")
def grafana_main_menu():
    if is_htmx(request):
        grafana_message = systemd_service_message("grafana-server").replace(
            "-server", ""
        )
        grafana_status = system_service_running_state("grafana-server")
        grafana_scanner_status = system_service_running_state("wlanpi-grafana-scanner")
        if grafana_status:
            # active
            grafana_task_url = "/stopgrafana"
            grafana_task_anchor_text = "STOP"
        else:
            # not active
            grafana_task_url = "/startgrafana"
            grafana_task_anchor_text = "START"

        enabled_data_streams = ""
        disabled_data_streams = ""
        if grafana_scanner_status:
            # active
            enabled_data_streams += """
            <li><span>SCANNER WLAN0 <a hx-get="/stopgrafanascanner"
                                       hx-indicator=".progress"><span uk-icon="close"></span></a></span></li>
            """
        else:
            disabled_data_streams += """
            <li><span>SCANNER WLAN0 <a hx-get="/startgrafanascanner"
                                       hx-indicator=".progress"><span uk-icon="play-circle"></span></a></span></li>
            """
        args = {
            "grafana_message": grafana_message,
            "grafana_task_url": grafana_task_url,
            "grafana_task_anchor_text": grafana_task_anchor_text,
            "grafana_scanner_status": grafana_scanner_status,
            "enabled_data_streams": enabled_data_streams,
            "disabled_data_streams": disabled_data_streams,
        }
        if grafana_status:
            # active
            html = """
            <li class="uk-nav-header">{grafana_message}</li>
            <li><a hx-get="{grafana_task_url}"
                   hx-indicator=".progress">{grafana_task_anchor_text}</a></li>
            <li class="uk-nav-divider"></li>
            <li><a class="uk-link"
                   hx-get="/grafana"
                   hx-target="#content"
                   hx-trigger="click"
                   hx-indicator=".progress"
                   hx-push-url="true"
                   hx-swap="innerHTML">OPEN GRAFANA IFRAME</a></li>
            <li><a class="uk-link" href="/grafana_url" target="_blank">LAUNCH GRAFANA NEW TAB</a></li>
            <li class="uk-parent">
                <li>DATA STREAMS <span data-uk-icon="chevron-down"></span></li>
                <ul class="uk-nav-sub">
                    <li>ENABLED:</li>
                    {enabled_data_streams}
                    <li class="uk-nav-divider"></li>
                    <li>AVAILABLE:</li>
                    {disabled_data_streams}
                </ul>
            </li>
            """.format(
                **args
            )
        else:
            # not active
            html = """
            <li class="uk-nav-header">{grafana_message}</li>
            <li><a hx-get="{grafana_task_url}"
                   hx-indicator=".progress">{grafana_task_anchor_text}</a></li>
            """.format(
                **args
            )
        return html


@bp.route("/<task>grafana")
def start_stop_grafana(task):
    if is_htmx(request):
        start_stop_service(task, "grafana-server")
    return "", 204


@bp.route("/<task>grafanascanner")
def start_stop_grafana_scanner(task):
    if is_htmx(request):
        start_stop_service(task, "wlanpi-grafana-scanner")
    return "", 204
