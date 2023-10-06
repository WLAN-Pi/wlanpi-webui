import ssl
import urllib

from flask import current_app, redirect, render_template, request
from flask_minify import decorators as minify_decorators

from wlanpi_webui.grafana import bp
from wlanpi_webui.utils import (get_apt_package_version,
                                get_service_down_message, is_htmx,
                                start_stop_service, system_service_exists,
                                system_service_running_state,
                                systemd_service_message, wlanpi_core_warning)


def try_url(url):
    try:
        context = ssl._create_unverified_context()
        urllib.request.urlopen(url, context=context, timeout=1)
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

    current_app.logger.debug("systemctl is-active for grafana-server is %s", is_running)
    service_down_message = get_service_down_message("grafana-server").replace(
        "-server", ""
    )
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
                service="Grafana is running but we received a 502 Bad Gateway server error.<br />Try again in a few moments.",
            )
        if return_code == 502:
            return render_template(
                "/partials/service.html",
                service="Grafana is not running and we received a 502 Bad Gateway server error.<br />Start the service, wait a few moments and try again.",
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
            return render_template(
                "/extends/service.html", service=service_down_message
            )
        if is_running and return_code == 502:
            return render_template(
                "/extends/service.html",
                service="Grafana is running but we received a 502 Bad Gateway server error.<br />Try again in a few moments.",
            )
        if return_code == 502:
            return render_template(
                "/extends/service.html",
                service="Grafana is not running and we received a 502 Bad Gateway server error.<br />Start the service, wait a few moments and try again.",
            )
        return render_template("/extends/iframe.html", **resp_data)


@bp.route("/grafana/side_menu")
@minify_decorators.minify(html=True)
def grafana_side_menu():
    if is_htmx(request):
        return grafana_menu("side")


@bp.route("/grafana/main_menu")
@minify_decorators.minify(html=True)
def grafana_main_menu():
    if is_htmx(request):
        return grafana_menu("main")


def get_datastream_info(
    datastream: str, friendly_name: str, stop_task: str, start_task: str
):
    ds_service_unit_exists = system_service_exists(datastream)
    enabled_ds = ""
    disabled_ds = ""
    ds_service_running = False
    if ds_service_unit_exists:
        ds_service_running = system_service_running_state(datastream)
        if ds_service_running:
            enabled_ds = """
            <li><span>{friendly_name} <a hx-get="{stop_task}" hx-indicator=".progress"><span uk-icon="close"></span></a></span></li>
            """.format(
                friendly_name=friendly_name, stop_task=stop_task
            )
        else:
            disabled_ds += """
            <li><span>{friendly_name} <a hx-get="{start_task}" hx-indicator=".progress"><span uk-icon="play-circle"></span></a></span></li>
            """.format(
                friendly_name=friendly_name, start_task=start_task
            )
    return enabled_ds, disabled_ds


def grafana_menu(type):
    enabled_data_streams = ""
    disabled_data_streams = ""

    streams = [
        (
            "wlanpi-grafana-internet",
            "Internet Monitoring",
            "/stopgrafanainternet",
            "/startgrafanainternet",
        ),
        (
            "wlanpi-grafana-health",
            "WLAN Pi Health",
            "/stopgrafanahealth",
            "/startgrafanahealth",
        ),
        (
            "wlanpi-grafana-wipry-lp-24",
            "Oscium WiPry Clarity 2.4 GHz",
            "/stopgrafanawipry24",
            "/startgrafanawipry24",
        ),
        (
            "wlanpi-grafana-wipry-lp-5",
            "Oscium WiPry Clarity 5 GHz",
            "/stopgrafanawipry5",
            "/startgrafanawipry5",
        ),
        (
            "wlanpi-grafana-wipry-lp-6",
            "Oscium WiPry Clarity 6 GHz",
            "/stopgrafanawipry6",
            "/startgrafanawipry6",
        ),
        (
            "wlanpi-grafana-wispy-24",
            "MetaGeek Wi-Spy DBx 2.4 GHz",
            "/stopgrafanawispy24",
            "/startgrafanawispy24",
        ),
        (
            "wlanpi-grafana-wispy-5",
            "MetaGeek Wi-Spy DBx 5 GHz",
            "/stopgrafanawispy5",
            "/startgrafanawispy5",
        ),
        (
            "wlanpi-grafana-scanner",
            "Scanner WLAN0",
            "/stopgrafanascanner",
            "/startgrafanascanner",
        ),
    ]

    for stream in streams:
        enabled, disabled = get_datastream_info(
            stream[0], stream[1], stream[2], stream[3]
        )
        enabled_data_streams += enabled
        disabled_data_streams += disabled

    data_streams_html = ""
    if enabled_data_streams == "" and disabled_data_streams == "":
        pass
    else:
        data_streams_html = """
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
            enabled_data_streams=enabled_data_streams,
            disabled_data_streams=disabled_data_streams,
        )
    grafana_message = systemd_service_message("grafana-server").replace("-server", "")
    grafana_status = system_service_running_state("grafana-server")
    if grafana_status:
        # active
        grafana_task_url = "/stopgrafana"
        grafana_task_anchor_text = "STOP"
    else:
        # not active
        grafana_task_url = "/startgrafana"
        grafana_task_anchor_text = "START"
    args = {
        "grafana_message": grafana_message,
        "grafana_task_url": grafana_task_url,
        "grafana_task_anchor_text": grafana_task_anchor_text,
        "data_streams_html": data_streams_html,
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
        <li class='uk-nav-divider'></li>
        {data_streams_html}
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
        core_status = system_service_running_state("wlanpi-core")
        if core_status:
            start_stop_service(task, "grafana-server")
        else:
            return wlanpi_core_warning
    return "", 204


@bp.route("/<task>grafanascanner")
def start_stop_grafana_scanner(task):
    if is_htmx(request):
        core_status = system_service_running_state("wlanpi-core")
        if core_status:
            start_stop_service(task, "wlanpi-grafana-scanner")
        else:
            return wlanpi_core_warning
    return "", 204


@bp.route("/<task>grafanainternet")
def start_stop_grafana_internet(task):
    if is_htmx(request):
        core_status = system_service_running_state("wlanpi-core")
        if core_status:
            start_stop_service(task, "wlanpi-grafana-internet")
        else:
            return wlanpi_core_warning
    return "", 204


@bp.route("/<task>grafanahealth")
def start_stop_grafana_health(task):
    if is_htmx(request):
        core_status = system_service_running_state("wlanpi-core")
        if core_status:
            start_stop_service(task, "wlanpi-grafana-health")
        else:
            return wlanpi_core_warning
    return "", 204


@bp.route("/<task>grafanawipry24")
def start_stop_grafana_wipry24(task):
    if is_htmx(request):
        core_status = system_service_running_state("wlanpi-core")
        if core_status:
            start_stop_service(task, "wlanpi-grafana-wipry-lp-24")
        else:
            return wlanpi_core_warning
    return "", 204
    
@bp.route("/<task>grafanawipry5")
def start_stop_grafana_wipry5(task):
    if is_htmx(request):
        core_status = system_service_running_state("wlanpi-core")
        if core_status:
            start_stop_service(task, "wlanpi-grafana-wipry-lp-5")
        else:
            return wlanpi_core_warning
    return "", 204

@bp.route("/<task>grafanawipry6")
def start_stop_grafana_wipry6(task):
    if is_htmx(request):
        core_status = system_service_running_state("wlanpi-core")
        if core_status:
            start_stop_service(task, "wlanpi-grafana-wipry-lp-6")
        else:
            return wlanpi_core_warning
    return "", 204

@bp.route("/<task>grafanawispy24")
def start_stop_grafana_wispy24(task):
    if is_htmx(request):
        core_status = system_service_running_state("wlanpi-core")
        if core_status:
            start_stop_service(task, "wlanpi-grafana-wispy-24")
        else:
            return wlanpi_core_warning
    return "", 204

@bp.route("/<task>grafanawispy5")
def start_stop_grafana_wispy5(task):
    if is_htmx(request):
        core_status = system_service_running_state("wlanpi-core")
        if core_status:
            start_stop_service(task, "wlanpi-grafana-wispy-5")
        else:
            return wlanpi_core_warning
    return "", 204