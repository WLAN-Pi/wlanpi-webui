from flask import render_template, request

from wlanpi_webui.apps import bp
from wlanpi_webui.auth.auth import service_toggle_anchor
from wlanpi_webui.grafana.grafana import GRAFANA_STATES, grafana_state, grafana_toggle
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
    # systemd reports Grafana active long before it listens (about a minute
    # of migrations on first start), so use the state that probes the port.
    grafana = grafana_state()["state"]
    grafana_label, grafana_class, _ = GRAFANA_STATES[grafana]

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
        "grafana_state": grafana,
        "grafana_state_label": grafana_label,
        "grafana_state_class": grafana_class,
        "grafana_settling": grafana not in ("running", "stopped"),
        "grafana_toggle": grafana_toggle(grafana),
    }

    return render_template("/partials/apps_cards.html", **resp_data)
