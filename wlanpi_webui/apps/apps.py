from flask import render_template, request

from wlanpi_webui.apps import bp
from wlanpi_webui.auth.auth import service_toggle_anchor
from wlanpi_webui.grafana.grafana import get_data_streams
from wlanpi_webui.utils import (
    is_htmx,
    system_service_running_state,
    systemd_service_message,
)


@bp.route("/apps")
def apps():
    """Render the apps shell; cards lazy-load from ``/apps/cards``."""
    if is_htmx(request):
        return render_template("/partials/apps.html")
    return render_template("/extends/apps.html")


@bp.route("/apps/cards")
def apps_cards():
    """Render the app cards (service checks, may be slow)."""
    profiler_running = system_service_running_state("wlanpi-profiler")
    kismet_running = system_service_running_state("kismet")
    grafana_running = system_service_running_state("grafana-server")

    resp_data = {
        "profiler_running": profiler_running,
        "profiler_status": systemd_service_message("wlanpi-profiler").replace(
            "wlanpi-", ""
        ),
        "profiler_toggle": service_toggle_anchor(
            profiler_running, "/startprofiler", "/stopprofiler"
        ),
        "kismet_running": kismet_running,
        "kismet_status": systemd_service_message("kismet"),
        "kismet_toggle": service_toggle_anchor(
            kismet_running, "/startkismet", "/stopkismet"
        ),
        "grafana_running": grafana_running,
        "grafana_status": systemd_service_message("grafana-server").replace(
            "-server", ""
        ),
        "grafana_toggle": service_toggle_anchor(
            grafana_running, "/startgrafana", "/stopgrafana"
        ),
        "grafana_data_streams": get_data_streams(),
    }

    return render_template("/partials/apps_cards.html", **resp_data)
