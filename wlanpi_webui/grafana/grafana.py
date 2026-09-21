from flask import redirect, request

from wlanpi_webui.auth.auth import csrf_required, hx_post_anchor
from wlanpi_webui.grafana import bp
from wlanpi_webui.utils import (
    is_htmx,
    start_stop_service,
    system_service_exists,
    system_service_running_state,
)


@bp.route("/grafana_url")
def grafana_url():
    return redirect("/app/grafana")


# Grafana data-stream services: (unit, friendly name, stop route, start route)
GRAFANA_DATA_STREAMS = [
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
        "wlanpi-grafana-scanner-wlan0",
        "Scanner WLAN0",
        "/stopgrafanascanner0",
        "/startgrafanascanner0",
    ),
    (
        "wlanpi-grafana-scanner-wlan1",
        "Scanner WLAN1",
        "/stopgrafanascanner1",
        "/startgrafanascanner1",
    ),
    (
        "wlanpi-grafana-scanner-wlan2",
        "Scanner WLAN2",
        "/stopgrafanascanner2",
        "/startgrafanascanner2",
    ),
    (
        "wlanpi-grafana-qscan",
        "Scanner LTE/5G",
        "/stopgrafanaqscan",
        "/startgrafanaqscan",
    ),
]


def get_data_streams(target: str | None = "#content") -> list[dict]:
    """Return the installed Grafana data streams with a start/stop anchor."""
    streams = []
    for unit, name, stop_task, start_task in GRAFANA_DATA_STREAMS:
        if not system_service_exists(unit):
            continue
        running = system_service_running_state(unit)
        streams.append(
            {
                "name": name,
                "running": running,
                "anchor": hx_post_anchor(
                    stop_task if running else start_task,
                    "STOP" if running else "START",
                    target=target,
                ),
            }
        )
    return streams


@bp.route("/<task>grafana", methods=["POST"])
@csrf_required
def start_stop_grafana(task):
    if is_htmx(request):
        return start_stop_service(task, "grafana-server")
    return "", 204


@bp.route("/<task>grafanascanner0", methods=["POST"])
@csrf_required
def start_stop_grafana_scanner0(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-scanner-wlan0")
    return "", 204


@bp.route("/<task>grafanascanner1", methods=["POST"])
@csrf_required
def start_stop_grafana_scanner1(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-scanner-wlan1")
    return "", 204


@bp.route("/<task>grafanascanner2", methods=["POST"])
@csrf_required
def start_stop_grafana_scanner2(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-scanner-wlan2")
    return "", 204


@bp.route("/<task>grafanascat", methods=["POST"])
@csrf_required
def start_stop_grafana_scat(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-scat")
    return "", 204


@bp.route("/<task>grafanascatpcap", methods=["POST"])
@csrf_required
def start_stop_grafana_scat_pcap(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-scat-pcap")
    return "", 204


@bp.route("/<task>grafanagps", methods=["POST"])
@csrf_required
def start_stop_grafana_gps(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-gps")
    return "", 204


@bp.route("/<task>grafanaqscan", methods=["POST"])
@csrf_required
def start_stop_grafana_qscan(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-qscan")
    return "", 204


@bp.route("/<task>grafanainternet", methods=["POST"])
@csrf_required
def start_stop_grafana_internet(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-internet")
    return "", 204


@bp.route("/<task>grafanahealth", methods=["POST"])
@csrf_required
def start_stop_grafana_health(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-health")
    return "", 204


@bp.route("/<task>grafanawipry24", methods=["POST"])
@csrf_required
def start_stop_grafana_wipry24(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-wipry-lp-24")
    return "", 204


@bp.route("/<task>grafanawipry5", methods=["POST"])
@csrf_required
def start_stop_grafana_wipry5(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-wipry-lp-5")
    return "", 204


@bp.route("/<task>grafanawipry6", methods=["POST"])
@csrf_required
def start_stop_grafana_wipry6(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-wipry-lp-6")
    return "", 204


@bp.route("/<task>grafanawispy24", methods=["POST"])
@csrf_required
def start_stop_grafana_wispy24(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-wispy-24")
    return "", 204


@bp.route("/<task>grafanawispy5", methods=["POST"])
@csrf_required
def start_stop_grafana_wispy5(task):
    if is_htmx(request):
        return start_stop_service(task, "wlanpi-grafana-wispy-5")
    return "", 204
