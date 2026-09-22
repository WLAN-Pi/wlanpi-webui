import warnings

import requests
from flask import jsonify, redirect, render_template, request

from wlanpi_webui.auth.auth import csrf_required, hx_post_anchor, service_toggle_anchor
from wlanpi_webui.grafana import bp
from wlanpi_webui.utils import (
    is_htmx,
    start_stop_service,
    system_service_active_state,
    system_service_exists,
    system_service_running_state,
)

GRAFANA_HEALTH_URL = "https://127.0.0.1:3000/api/health"


@bp.route("/grafana_url")
def grafana_url():
    return redirect("/app/grafana")


# Grafana data-stream services: (unit, name, stop route, start route)
GRAFANA_DATA_STREAMS = [
    (
        "wlanpi-grafana-internet",
        "Internet monitoring",
        "/stopgrafanainternet",
        "/startgrafanainternet",
    ),
    (
        "wlanpi-grafana-health",
        "WLAN Pi health",
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
        "Scanner wlan0",
        "/stopgrafanascanner0",
        "/startgrafanascanner0",
    ),
    (
        "wlanpi-grafana-scanner-wlan1",
        "Scanner wlan1",
        "/stopgrafanascanner1",
        "/startgrafanascanner1",
    ),
    (
        "wlanpi-grafana-scanner-wlan2",
        "Scanner wlan2",
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

# The toast reads "Grafana <name> data stream ...", so the label keeps the
# "Grafana" prefix and the name is stored in sentence case.
STREAM_LABELS = {unit: f"Grafana {name}" for unit, name, _, _ in GRAFANA_DATA_STREAMS}


def get_data_streams(target: str | None = "#content") -> list[dict]:
    """Return the installed Grafana data streams with a start/stop anchor."""
    streams = []
    for unit, name, stop_task, start_task in GRAFANA_DATA_STREAMS:
        if not system_service_exists(unit):
            continue
        running = system_service_running_state(unit)
        css = (
            "uk-button uk-button-default uk-button-small"
            if running
            else "uk-button uk-button-primary uk-button-small"
        )
        streams.append(
            {
                "name": name,
                "running": running,
                "anchor": hx_post_anchor(
                    stop_task if running else start_task,
                    "Stop" if running else "Start",
                    target=target,
                    css=css,
                ),
            }
        )
    return streams


def _toggle_data_stream(task, unit):
    """Start/stop one Grafana data stream, with a data-stream flavoured toast."""
    return start_stop_service(
        task, unit, label=STREAM_LABELS.get(unit), noun="data stream"
    )


def _grafana_responding(timeout: float = 2.0) -> bool:
    """True once Grafana's HTTP server answers, even with a 404.

    The service can be "active" while Grafana is still booting and not yet
    listening; this is the check that catches that window. Grafana serves a
    self-signed certificate, so verification is off (loopback only).
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            response = requests.get(GRAFANA_HEALTH_URL, verify=False, timeout=timeout)
        except requests.RequestException:
            return False
    return bool(response.status_code < 500)


# State -> (pill label, pill class, message) shown on the /grafana page.
GRAFANA_STATES = {
    "running": ("Running", "is-on", "Grafana is ready."),
    "waiting": (
        "Waiting for WebUI",
        "is-warn",
        "Waiting for the Grafana WebUI to respond…",
    ),
    "starting": ("Starting", "is-warn", "Starting the Grafana service…"),
    "stopping": ("Stopping", "is-warn", "Stopping the Grafana service…"),
    "stopped": ("Stopped", "is-off", "Grafana is not running."),
}


def grafana_state() -> dict:
    """Grafana service state, folding in whether its web UI answers yet."""
    active = system_service_active_state("grafana-server")
    if active == "active":
        responding = _grafana_responding()
        state = "running" if responding else "waiting"
    elif active == "activating":
        state, responding = "starting", False
    elif active == "deactivating":
        state, responding = "stopping", False
    else:
        state, responding = "stopped", False
    return {"state": state, "running": active == "active", "responding": responding}


def _grafana_toggle(state: str) -> str:
    """Start/Stop control for the current state, disabled mid-transition."""
    if state == "stopped":
        return service_toggle_anchor(False, "/startgrafana", "/stopgrafana")
    if state in ("running", "waiting"):
        return service_toggle_anchor(True, "/startgrafana", "/stopgrafana")
    label = "Starting…" if state == "starting" else "Stopping…"
    return (
        f'<button class="uk-button uk-button-default" type="button" '
        f"disabled>{label}</button>"
    )


@bp.route("/grafana/status")
def grafana_status():
    """Report whether Grafana is running and its web UI is answering."""
    return jsonify(grafana_state())


@bp.route("/grafana/service")
def grafana_service():
    """The polling service card fragment for the /grafana page."""
    state = grafana_state()["state"]
    label, css, message = GRAFANA_STATES[state]
    return render_template(
        "/partials/grafana_service.html",
        state=state,
        state_label=label,
        state_class=css,
        state_message=message,
        toggle=_grafana_toggle(state),
    )


@bp.route("/grafana")
def grafana():
    """The Grafana data-streams page (the Grafana UI itself lives at /app/grafana)."""
    resp_data = {"grafana_data_streams": get_data_streams()}
    if is_htmx(request):
        return render_template("/partials/grafana.html", **resp_data)
    return render_template("/extends/grafana.html", **resp_data)


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
        return _toggle_data_stream(task, "wlanpi-grafana-scanner-wlan0")
    return "", 204


@bp.route("/<task>grafanascanner1", methods=["POST"])
@csrf_required
def start_stop_grafana_scanner1(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-scanner-wlan1")
    return "", 204


@bp.route("/<task>grafanascanner2", methods=["POST"])
@csrf_required
def start_stop_grafana_scanner2(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-scanner-wlan2")
    return "", 204


@bp.route("/<task>grafanascat", methods=["POST"])
@csrf_required
def start_stop_grafana_scat(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-scat")
    return "", 204


@bp.route("/<task>grafanascatpcap", methods=["POST"])
@csrf_required
def start_stop_grafana_scat_pcap(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-scat-pcap")
    return "", 204


@bp.route("/<task>grafanagps", methods=["POST"])
@csrf_required
def start_stop_grafana_gps(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-gps")
    return "", 204


@bp.route("/<task>grafanaqscan", methods=["POST"])
@csrf_required
def start_stop_grafana_qscan(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-qscan")
    return "", 204


@bp.route("/<task>grafanainternet", methods=["POST"])
@csrf_required
def start_stop_grafana_internet(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-internet")
    return "", 204


@bp.route("/<task>grafanahealth", methods=["POST"])
@csrf_required
def start_stop_grafana_health(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-health")
    return "", 204


@bp.route("/<task>grafanawipry24", methods=["POST"])
@csrf_required
def start_stop_grafana_wipry24(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-wipry-lp-24")
    return "", 204


@bp.route("/<task>grafanawipry5", methods=["POST"])
@csrf_required
def start_stop_grafana_wipry5(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-wipry-lp-5")
    return "", 204


@bp.route("/<task>grafanawipry6", methods=["POST"])
@csrf_required
def start_stop_grafana_wipry6(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-wipry-lp-6")
    return "", 204


@bp.route("/<task>grafanawispy24", methods=["POST"])
@csrf_required
def start_stop_grafana_wispy24(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-wispy-24")
    return "", 204


@bp.route("/<task>grafanawispy5", methods=["POST"])
@csrf_required
def start_stop_grafana_wispy5(task):
    if is_htmx(request):
        return _toggle_data_stream(task, "wlanpi-grafana-wispy-5")
    return "", 204
