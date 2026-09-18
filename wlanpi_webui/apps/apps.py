from flask import render_template, request

from wlanpi_webui.apps import bp
from wlanpi_webui.auth.auth import hx_post_anchor
from wlanpi_webui.grafana.grafana import get_data_streams
from wlanpi_webui.utils import (
    is_htmx,
    system_service_running_state,
    systemd_service_message,
)


def _toggle(running: bool, start: str, stop: str) -> str:
    """Start/Stop anchor that re-renders the apps page in place."""
    return hx_post_anchor(
        stop if running else start,
        "Stop" if running else "Start",
        target="#content",
    )


@bp.route("/apps")
def apps():
    profiler_running = system_service_running_state("wlanpi-profiler")
    kismet_running = system_service_running_state("kismet")
    grafana_running = system_service_running_state("grafana-server")

    resp_data = {
        "profiler_running": profiler_running,
        "profiler_status": systemd_service_message("wlanpi-profiler").replace(
            "wlanpi-", ""
        ),
        "profiler_toggle": _toggle(profiler_running, "/startprofiler", "/stopprofiler"),
        "kismet_running": kismet_running,
        "kismet_status": systemd_service_message("kismet"),
        "kismet_toggle": _toggle(kismet_running, "/startkismet", "/stopkismet"),
        "grafana_running": grafana_running,
        "grafana_status": systemd_service_message("grafana-server").replace(
            "-server", ""
        ),
        "grafana_toggle": _toggle(grafana_running, "/startgrafana", "/stopgrafana"),
        "grafana_data_streams": get_data_streams(),
    }

    if is_htmx(request):
        return render_template("/partials/apps.html", **resp_data)
    return render_template("/extends/apps.html", **resp_data)
